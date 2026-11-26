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
`-` means no value; decimals may lack a leading zero (".82"); one date per file,
usually DD-MM-YYYY but sometimes DD/MM/YYYY or month-first (see _session_dates). Each index enters the archive at its launch, so this store holds
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
from src.loaders.app_pack import resolve as _pack

URL = "https://nsearchives.nseindia.com/content/indices/ind_close_all_{d:%d%m%Y}.csv"
FIRST_SESSION = pd.Timestamp("2012-02-21")
DATASET = "indices/nse_close_all"
ALIASES = Path(__file__).resolve().parents[2] / "data" / "reference" / "nse_index_aliases.csv"
# Rows NSE mislabelled, relabelled with their evidence (a name, never a price).
CORRECTIONS = Path(__file__).resolve().parents[2] / "data" / "reference" / "nse_index_corrections.csv"
# Trading days NSE's archive has no file for, with their evidence.
MISSING = Path(__file__).resolve().parents[2] / "data" / "reference" / "nse_index_missing_sessions.csv"
GROUPS = Path(__file__).resolve().parents[2] / "data" / "reference" / "nse_index_groups.csv"
# The app's copy (the store is in R2): stock indices only, the columns pages read.
# History is frozen in one parquet; the nightly job appends later sessions to a
# small CSV, so the repository grows by a few KB a night, not megabytes.
COMPACT_HISTORY = Path(__file__).resolve().parents[2] / "data" / "nse_indices_history.parquet"
COMPACT_RECENT = Path(__file__).resolve().parents[2] / "data" / "nse_indices_recent.csv"
COMPACT_COLUMNS = ["date", "key", "close", "pe", "pb", "div_yield", "derived"]
# A derived close more than this far from the session before is refused.
DERIVED_MAX_MOVE = 0.20

COLUMNS = {
    "Index Name": "name", "Index Date": "date", "Open Index Value": "open",
    "High Index Value": "high", "Low Index Value": "low", "Closing Index Value": "close",
    "Points Change": "points_change", "Change(%)": "change_pct", "Volume": "volume",
    "Turnover (Rs. Cr.)": "turnover_cr", "P/E": "pe", "P/B": "pb", "Div Yield": "div_yield",
}
NUMERIC = ["open", "high", "low", "close", "points_change", "change_pct", "volume",
           "turnover_cr", "pe", "pb", "div_yield"]
# `derived` marks a close NSE published no file for, worked out from the next
# session's close and points change (owner, 21 Nov 2026: decision B).
STORE_COLUMNS = ["date", "key", "name"] + NUMERIC + ["derived"]
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


def _session_dates(col: pd.Series, session: pd.Timestamp | None) -> pd.Series:
    """The file's Index Date column as timestamps, checked against the session the
    file was asked for. NSE has printed it three ways: 20-11-2026 (usual),
    09/06/2014 (59 files, Jun 2014 - Jun 2015) and month-first 04-10-2023 (the
    files for 6, 10 and 11 Apr 2023). A month-first date that is the session is
    the session; any other date that is not the session refuses the file, so a
    stale file served under a new name never enters as a new day."""
    text = col.astype(str).str.strip().str.replace("/", "-", regex=False)
    day_first = pd.to_datetime(text, format="%d-%m-%Y", errors="coerce")
    if session is None:
        if day_first.isna().any():
            raise NotAnIndexFile(f"unreadable Index Date: {text[day_first.isna()].iloc[0]!r}")
        return day_first
    session = pd.Timestamp(session).normalize()
    if (day_first == session).all():
        return day_first
    month_first = pd.to_datetime(text, format="%m-%d-%Y", errors="coerce")
    if (month_first == session).all():
        return month_first
    raise NotAnIndexFile(f"dated {text.iloc[0]!r}, asked for {session:%d %b %Y}")


def session_from_name(name: str) -> pd.Timestamp | None:
    """The session a saved file is for, from NSE's name (ind_close_all_DDMMYYYY)
    or a YYYYMMDD name; None when the name says neither."""
    m = re.search(r"ind_close_all_(\d{2})(\d{2})(\d{4})", name)
    if m:
        return pd.Timestamp(f"{m[3]}-{m[2]}-{m[1]}")
    m = re.fullmatch(r"(\d{4})(\d{2})(\d{2})(?:\.csv)?", name)
    return pd.Timestamp(f"{m[1]}-{m[2]}-{m[3]}") if m else None


def parse_file(raw: bytes, aliases: dict[str, str] | None = None,
               session: pd.Timestamp | None = None) -> pd.DataFrame:
    """One session's file as store rows. `session` is the day the file was asked
    for; when given, the file must be that day's. Raises NotAnIndexFile on an HTML
    answer, a file without the expected columns, or a date that is not the session."""
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
    f = f[f["name"].ne("") & f["name"].ne("nan")]
    f["date"] = _session_dates(f["date"], session)
    for c in NUMERIC:
        if c not in f.columns:
            f[c] = np.nan
            continue
        v = f[c].astype(str).str.strip().str.replace(",", "", regex=False)
        f[c] = pd.to_numeric(v.where(~v.isin({"-", "", "nan", "NaN"})), errors="coerce")
    f = f[f["close"].notna()]
    # The same row printed twice, identical in every field (15 Sep 2014, GSEC10):
    # one copy is the row.
    f = f.drop_duplicates()
    f = apply_corrections(f)
    al = load_aliases() if aliases is None else aliases
    f["key"] = f["name"].map(lambda n: key_for(n, al))
    f["derived"] = False
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
    if stored is not None and "derived" not in stored.columns:
        stored = stored.assign(derived=False)
    if stored is None or stored.empty:
        out = new
    else:
        out = pd.concat([stored, new[~new.set_index(["date", "key"]).index.isin(
            stored.set_index(["date", "key"]).index)]], ignore_index=True)
    return out.sort_values(["date", "key"]).reset_index(drop=True)[STORE_COLUMNS]


def missing_sessions(path: Path | None = None) -> list[pd.Timestamp]:
    """Trading days with no NSE file whose close can be derived (`derivable` yes)."""
    p = MISSING if path is None else path
    if not p.exists():
        return []
    t = pd.read_csv(p, dtype=str)
    return [pd.Timestamp(d) for d, ok in zip(t["date"], t["derivable"]) if ok.strip() == "yes"]


def derive_missing(store: pd.DataFrame, days: list[pd.Timestamp] | None = None) -> pd.DataFrame:
    """The store with a derived row for each listed missing day: close = the next
    session's close minus its points change, for every index listed on both the
    session before and the session after. Checked 21 Nov 2026: exact for the
    Nifty 50 and Nifty 500 on all 11 days against Kaggle and SS. Idempotent."""
    days = missing_sessions() if days is None else days
    if store.empty or not days:
        return store
    store = store if "derived" in store.columns else store.assign(derived=False)
    sess = pd.DatetimeIndex(sorted(store["date"].unique()))
    rows = []
    for day in days:
        day = pd.Timestamp(day)
        if day in sess or day <= sess[0] or day >= sess[-1]:
            continue
        before, after = sess[sess < day][-1], sess[sess > day][0]
        a = store[store["date"] == after].set_index("key")
        b = store[store["date"] == before].set_index("key")
        both = a.index.intersection(b.index)
        a, b = a.loc[both], b.loc[both]
        close = a["close"] - a["points_change"]
        ok = close.notna() & ((close / b["close"] - 1).abs() <= DERIVED_MAX_MOVE)
        for key in close.index[ok]:
            r = {c: np.nan for c in NUMERIC}
            r.update(date=day, key=key, name=a.at[key, "name"], close=round(float(close[key]), 2), derived=True)
            rows.append(r)
    if not rows:
        return store
    add = pd.DataFrame(rows)[STORE_COLUMNS]
    return pd.concat([store, add], ignore_index=True).sort_values(["date", "key"]).reset_index(drop=True)


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


# An index is live from the first row that the next session's file also lists and
# that starts LIVE_RUN rows with no gap of more than LIVE_GAP sessions. NSE regenerated two archive files (7 Jul 2016, 12 Apr 2023)
# with back-calculated values for indices launched years later (Nifty Total Market
# in the 2016 file; Nifty100 Low Volatility 30 two sessions before its launch on
# 11 Jul 2016); those rows stay in the store, as NSE published them, and
# readers start each series at its launch.
LIVE_RUN, LIVE_GAP = 20, 10


def live_from(store: pd.DataFrame, keys: list[str] | None = None) -> dict[str, pd.Timestamp]:
    """{key: first live session}, gaps counted in the whole store's sessions."""
    sess = pd.Index(sorted(store["date"].unique()))
    pos = pd.Series(np.arange(len(sess)), index=sess)
    rows = store if keys is None else store[store["key"].isin(keys)]
    out = {}
    for key, g in rows.sort_values("date").groupby("key"):
        si, d = pos[g["date"]].to_numpy(), g["date"].to_numpy()
        n = len(si)
        out[key] = pd.Timestamp(d[0])
        for i in range(n):
            j = min(i + LIVE_RUN, n)
            next_too = n == 1 or (i + 1 < n and si[i + 1] == si[i] + 1)
            if next_too and j - i >= min(LIVE_RUN, n) and (np.diff(si[i:j]) <= LIVE_GAP).all():
                out[key] = pd.Timestamp(d[i])
                break
    return out


def series(store: pd.DataFrame, key: str, field: str = "close", *, live_only: bool = True) -> pd.Series:
    """One index's daily values by date, from its launch unless `live_only` is False.
    Returns are computed from closes: NSE's points change is not always against the
    previous session (13 Mar 2023's file measures from 9 Mar)."""
    g = store[store["key"] == key]
    s = pd.Series(g[field].to_numpy(dtype="float64"), index=pd.DatetimeIndex(g["date"]), name=key).sort_index()
    if live_only and len(s):
        s = s[s.index >= live_from(store, [key])[key]]
    return s


def groups(path: Path | None = None) -> pd.DataFrame:
    """key, group (Broad market, Sector, Theme, Strategy, not a stock index), name."""
    return pd.read_csv(GROUPS if path is None else path, dtype=str)


def stock_index_keys(path: Path | None = None) -> set[str]:
    g = groups(path)
    return set(g.loc[g["group"] != "not a stock index", "key"])


def compact(store: pd.DataFrame, keys: set[str] | None = None) -> pd.DataFrame:
    """The columns pages read, for stock indices only, live rows only."""
    keys = stock_index_keys() if keys is None else keys
    s = store[store["key"].isin(keys)]
    if "derived" not in s.columns:
        s = s.assign(derived=False)
    lf = live_from(s)
    s = s[s["date"] >= s["key"].map(lf)]
    return s[COMPACT_COLUMNS].sort_values(["date", "key"]).reset_index(drop=True)


def write_compact(store: pd.DataFrame, *, freeze: bool = False, history: Path | None = None,
                  recent: Path | None = None) -> tuple[int, int]:
    """Write the app's copy. With `freeze`, everything goes into the history file
    and the recent file is emptied; otherwise the recent file holds every row after
    the history file's last session. Returns (history rows, recent rows)."""
    h_path, r_path = history or COMPACT_HISTORY, recent or COMPACT_RECENT
    c = compact(store)
    if freeze or not h_path.exists():
        c.to_parquet(h_path, index=False, compression="zstd")
        c.iloc[0:0].to_csv(r_path, index=False)
        return len(c), 0
    last = pd.read_parquet(h_path, columns=["date"])["date"].max()
    r = c[c["date"] > last]
    r.to_csv(r_path, index=False, date_format="%Y-%m-%d", float_format="%.4f")
    return len(pd.read_parquet(h_path, columns=["date"])), len(r)


def read_compact(history: Path | None = None, recent: Path | None = None) -> pd.DataFrame:
    """The app's copy, history and recent sessions together; empty if absent."""
    h_path, r_path = history or COMPACT_HISTORY, recent or COMPACT_RECENT
    parts = []
    if h_path.exists():
        parts.append(pd.read_parquet(h_path))
    if r_path.exists() and r_path.stat().st_size > 0:
        r = pd.read_csv(_pack(r_path), parse_dates=["date"])
        if len(r):
            r["derived"] = r["derived"].astype(str).str.lower().eq("true")
            parts.append(r)
    if not parts:
        return pd.DataFrame(columns=COMPACT_COLUMNS)
    out = pd.concat(parts, ignore_index=True).drop_duplicates(["date", "key"], keep="last")
    return out.sort_values(["date", "key"]).reset_index(drop=True)
