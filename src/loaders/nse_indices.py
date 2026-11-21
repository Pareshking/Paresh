"""Every NSE index, every session: NSE's daily all-indices file, kept whole (S168).

Owner, 21 Nov 2026: "Shouldn't our GitHub get all NSE indices (including missing
broad indices, sector, industries, new themes, quantitative like momentum, quality
etc from NSE getting updated daily? Download full history once for all and let
daily run update daily data quickly."

NSE publishes one file per session,
https://nsearchives.nseindia.com/content/indices/ind_close_all_DDMMYYYY.csv, with
every index it calculates: open, high, low, close, points change, volume, turnover,
P/E, P/B and dividend yield. The archive starts on 21 Feb 2012 (30 indices) and had
169 indices on 20 Nov 2026. Earlier dates return an HTML page, not a CSV.

Facts the parser relies on (docs/INDICES_RESEARCH_DATA_2026-11-21.md, section 0):
`-` means no value; decimals may lack a leading zero (".82"); dates are DD-MM-YYYY;
one date per file. Each index enters the archive at its launch, so this store holds
live history only, never NSE's back-calculated years (a known bias in strategy
indices). Prices are price-index levels, not total return.

Renamed indices are joined by `data/reference/nse_index_aliases.csv` (raw name ->
key, with its evidence). A name not in that table is its own series under its own
key. The store is long: one row per (date, key).
"""
from __future__ import annotations

import io
import re
from pathlib import Path

import numpy as np
import pandas as pd

URL = "https://nsearchives.nseindia.com/content/indices/ind_close_all_{d:%d%m%Y}.csv"
FIRST_SESSION = pd.Timestamp("2012-02-21")
DATASET = "indices/nse_close_all"
ALIASES = Path(__file__).resolve().parents[2] / "data" / "reference" / "nse_index_aliases.csv"
# Rows NSE mislabelled, relabelled with their evidence (a name, never a price).
CORRECTIONS = Path(__file__).resolve().parents[2] / "data" / "reference" / "nse_index_corrections.csv"

COLUMNS = {
    "Index Name": "name", "Index Date": "date", "Open Index Value": "open",
    "High Index Value": "high", "Low Index Value": "low", "Closing Index Value": "close",
    "Points Change": "points_change", "Change(%)": "change_pct", "Volume": "volume",
    "Turnover (Rs. Cr.)": "turnover_cr", "P/E": "pe", "P/B": "pb", "Div Yield": "div_yield",
}
NUMERIC = ["open", "high", "low", "close", "points_change", "change_pct", "volume",
           "turnover_cr", "pe", "pb", "div_yield"]
STORE_COLUMNS = ["date", "key", "name"] + NUMERIC
# A stored close may move by rounding only (a paisa); anything more is a restatement
# or a mislabelled row, and the writer refuses it.
CLOSE_TOLERANCE = 0.011


class NotAnIndexFile(ValueError):
    """NSE answered with something that is not the all-indices CSV (an HTML page)."""


def slug(name: str) -> str:
    """A stable key from a name: lower case, words joined by underscores."""
    s = re.sub(r"[^a-z0-9]+", "_", str(name).strip().lower())
    return s.strip("_")


def load_aliases(path: Path | None = None) -> dict[str, str]:
    """{slug of a raw name: key} from the committed alias table."""
    p = ALIASES if path is None else path
    if not p.exists():
        return {}
    t = pd.read_csv(p, dtype=str).fillna("")
    return {slug(r): k.strip() for r, k in zip(t["name_raw"], t["key"]) if r.strip() and k.strip()}


def key_for(name: str, aliases: dict[str, str]) -> str:
    s = slug(name)
    return aliases.get(s, s)


def apply_corrections(rows: pd.DataFrame, path: Path | None = None) -> pd.DataFrame:
    """Relabel rows listed in the corrections file, matched on date, raw name and close."""
    p = CORRECTIONS if path is None else path
    if not p.exists() or rows.empty:
        return rows
    c = pd.read_csv(p, dtype={"name_raw": str, "name_correct": str})
    out = rows.copy()
    for r in c.itertuples():
        hit = ((out["date"] == pd.Timestamp(r.date)) & (out["name"] == str(r.name_raw).strip())
               & ((out["close"] - float(r.close)).abs() < 0.005))
        out.loc[hit, "name"] = str(r.name_correct).strip()
    return out


def parse_file(raw: bytes, aliases: dict[str, str] | None = None) -> pd.DataFrame:
    """One session's file as store rows. Raises NotAnIndexFile on an HTML answer
    or a file without the expected columns."""
    head = raw[:200].lstrip().lower()
    if head.startswith(b"<") or b"<html" in head:
        raise NotAnIndexFile("an HTML page, not the all-indices CSV")
    try:
        f = pd.read_csv(io.BytesIO(raw), dtype=str)
    except Exception as exc:  # noqa: BLE001
        raise NotAnIndexFile(f"unreadable CSV: {type(exc).__name__}") from exc
    f.columns = [str(c).strip() for c in f.columns]
    missing = [c for c in ("Index Name", "Index Date", "Closing Index Value") if c not in f.columns]
    if missing:
        raise NotAnIndexFile(f"missing columns: {', '.join(missing)}")
    f = f.rename(columns=COLUMNS)
    f = f[[c for c in COLUMNS.values() if c in f.columns]].copy()
    f["name"] = f["name"].astype(str).str.strip()
    f["date"] = pd.to_datetime(f["date"].astype(str).str.strip(), format="%d-%m-%Y", errors="coerce")
    for c in NUMERIC:
        if c not in f.columns:
            f[c] = np.nan
            continue
        v = f[c].astype(str).str.strip().str.replace(",", "", regex=False)
        f[c] = pd.to_numeric(v.where(~v.isin({"-", "", "nan", "NaN"})), errors="coerce")
    f = f[f["date"].notna() & f["close"].notna() & (f["name"] != "")]
    # The same row printed twice, identical in every field (15 Sep 2014, GSEC10):
    # one copy is the row.
    f = f.drop_duplicates()
    f = apply_corrections(f)
    al = load_aliases() if aliases is None else aliases
    f["key"] = f["name"].map(lambda n: key_for(n, al))
    return f[STORE_COLUMNS].reset_index(drop=True)


def duplicates(rows: pd.DataFrame) -> pd.DataFrame:
    """Rows sharing a (date, key): NSE printed one index twice (8 Feb 2013's two
    "CNX Alpha Index" rows, the second really High Beta)."""
    return rows[rows.duplicated(["date", "key"], keep=False)]


def disagreements(stored: pd.DataFrame, new: pd.DataFrame, tolerance: float = CLOSE_TOLERANCE) -> pd.DataFrame:
    """(date, key) pairs both hold whose closes differ by more than `tolerance`."""
    if stored is None or stored.empty or new.empty:
        return new.iloc[0:0]
    j = new.merge(stored[["date", "key", "close"]], on=["date", "key"], suffixes=("", "_stored"))
    return j[(j["close"] - j["close_stored"]).abs() > tolerance]


def merge(stored: pd.DataFrame | None, new: pd.DataFrame) -> pd.DataFrame:
    """The store with `new`'s sessions added. Raises ValueError, writing nothing,
    when a new row would change a stored close or a session holds a key twice."""
    dup = duplicates(new)
    if len(dup):
        raise ValueError("an index printed twice in one session: "
                         + "; ".join(f"{d:%Y-%m-%d} {k}" for d, k in dup[["date", "key"]].drop_duplicates().itertuples(index=False)))
    bad = disagreements(stored, new)
    if len(bad):
        raise ValueError("a stored close would change: "
                         + "; ".join(f"{r.date:%Y-%m-%d} {r.key} {r.close_stored} -> {r.close}" for r in bad.head(10).itertuples()))
    if stored is None or stored.empty:
        out = new
    else:
        out = pd.concat([stored, new[~new.set_index(["date", "key"]).index.isin(
            stored.set_index(["date", "key"]).index)]], ignore_index=True)
    return out.sort_values(["date", "key"]).reset_index(drop=True)[STORE_COLUMNS]


def seams(store: pd.DataFrame) -> pd.DataFrame:
    """Where an aliased series changes name: the first row under the new name, its
    points change, and the close it implies against the old name's last close.
    A seam is continuous when `points_change` equals `close - prev_close` to 0.01."""
    out = []
    for key, g in store.sort_values("date").groupby("key"):
        g = g.reset_index(drop=True)
        change = g["name"].ne(g["name"].shift()) & g.index.to_series().gt(0)
        for i in g.index[change]:
            prev, row = g.loc[i - 1], g.loc[i]
            implied = row["close"] - prev["close"]
            out.append({"key": key, "date": row["date"], "old": prev["name"], "new": row["name"],
                        "prev_close": prev["close"], "close": row["close"],
                        "points_change": row["points_change"],
                        "continuous": bool(pd.notna(row["points_change"])
                                           and abs(row["points_change"] - implied) <= 0.011)})
    return pd.DataFrame(out, columns=["key", "date", "old", "new", "prev_close", "close",
                                      "points_change", "continuous"])


def series(store: pd.DataFrame, key: str, field: str = "close") -> pd.Series:
    """One index's daily values by date."""
    g = store[store["key"] == key]
    return pd.Series(g[field].to_numpy(dtype="float64"), index=pd.DatetimeIndex(g["date"]), name=key).sort_index()
