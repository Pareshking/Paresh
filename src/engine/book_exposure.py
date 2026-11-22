"""The book's industry and size at every rebalance, kept (owner, 20 Nov 2026).

"Industry exposure and book by size we should record and save, it gives trend
to understand how portfolio moved over the period."

One row per (rebalance fill date, kind, name): kind "industry" (the record's
own industry, `model_record.record_sector_map`) or "size" (Large, Mid, Small,
Micro, by NSE's index lists ON THAT DATE from data/membership_history.json;
"Other" for a name in none of them). Weight is the book's weight at the fill,
in percent.

`data/book_exposure.csv` keeps every rebalance once written: `merge` adds the
dates the file lacks and never rewrites one it has, so a later change to an
index list or to an industry label does not rewrite the past. The monthly
Track Record run appends (scripts/update_track_record.py); the page reads the
file and works out only the rebalances it does not have yet (the live month).
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

PATH = Path(__file__).resolve().parents[2] / "data" / "book_exposure.csv"
FIELDS = ["date", "kind", "name", "weight"]
SIZES = ("Large", "Mid", "Small", "Micro", "Other")
# Nifty 100 = Nifty 50 + Next 50 is "Large", as the Dashboard's size lists.
SIZE_INDICES = (("Large", "nifty_50"), ("Large", "nifty_next_50"), ("Mid", "nifty_midcap_150"),
                ("Small", "nifty_smallcap_250"), ("Micro", "nifty_microcap_250"))


def books(tradebook: pd.DataFrame) -> dict[pd.Timestamp, pd.Series]:
    """Each rebalance's book: fill date -> weight by symbol (bought and kept lines)."""
    if tradebook is None or tradebook.empty or not {"Period", "Action", "Symbol", "Weight %"} <= set(tradebook.columns):
        return {}
    held = tradebook[tradebook["Action"].astype(str).str.contains("BUY|HOLD", regex=True)]
    out = {}
    for period, g in held.groupby("Period", sort=False):
        start = pd.to_datetime(str(period).split("→")[0].strip(), errors="coerce")
        if pd.isna(start):
            continue
        w = pd.to_numeric(g.set_index("Symbol")["Weight %"], errors="coerce").dropna()
        if len(w):
            out[pd.Timestamp(start)] = w.groupby(level=0).sum()
    return dict(sorted(out.items()))


def size_of(symbols, on: pd.Timestamp, membership: dict) -> dict[str, str]:
    from src.engine.membership import members_on
    out: dict[str, str] = {}
    for label, key in SIZE_INDICES:
        hist = (membership.get("indices") or {}).get(key)
        mem = members_on(hist, on, canonical=True) if hist else None
        for s in symbols:
            if s not in out and mem and s in mem:
                out[s] = label
    return {s: out.get(s, "Other") for s in symbols}


def exposure(tradebook: pd.DataFrame, industry: dict[str, str], membership: dict) -> pd.DataFrame:
    rows = []
    for d, w in books(tradebook).items():
        ind = w.groupby(w.index.map(lambda s: industry.get(s, "–"))).sum()
        size = w.groupby(w.index.map(size_of(list(w.index), d, membership))).sum()
        rows += [(d, "industry", k, round(float(v), 2)) for k, v in ind.items()]
        rows += [(d, "size", k, round(float(size.get(k, 0.0)), 2)) for k in SIZES]
    return pd.DataFrame(rows, columns=FIELDS)


def load(path: Path = PATH) -> pd.DataFrame:
    if not Path(path).exists():
        return pd.DataFrame(columns=FIELDS)
    f = pd.read_csv(path, parse_dates=["date"])
    return f[FIELDS]


def merge(kept: pd.DataFrame, new: pd.DataFrame) -> pd.DataFrame:
    """The kept rebalances as they are, plus the new dates only."""
    kept = kept if kept is not None else pd.DataFrame(columns=FIELDS)
    have = set(pd.to_datetime(kept["date"])) if len(kept) else set()
    add = new[~pd.to_datetime(new["date"]).isin(have)] if len(new) else new
    out = pd.concat([kept, add], ignore_index=True) if len(add) else kept.copy()
    return out.sort_values(["date", "kind", "weight"], ascending=[True, True, False]).reset_index(drop=True)


def save(frame: pd.DataFrame, path: Path = PATH) -> None:
    f = frame.copy()
    f["date"] = pd.to_datetime(f["date"]).dt.strftime("%Y-%m-%d")
    f.to_csv(path, index=False)
