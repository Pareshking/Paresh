"""Which size of company is leading: Nifty 50, Midcap 150, Smallcap 250 and
Microcap 250 against the Nifty 500 over one, three and six months.

The dashboard's market context (owner, 7 Nov 2026; the idea from tipsheet's
"what is leading", the data from NSE's own index closes). Price returns, as
NSE publishes the index levels; no dividends.

Every window starts on the same session for every index: the series are
joined on the dates they share, and each window opens on the first shared
session on or after the same date one, three or six months back (the rule the
ranking's own windows use, `calendar_start_positions`). The index-level file
falls back to Screener's index chart when niftyindices.com refuses the nightly
job (it refused every night checked, 5-7 Nov 2026). That chart is weekly over
ten years and daily over the last 400 days; until 7 Nov the job kept only the
weekly series, so 1M opened on 9 Oct while every other page used 6 Oct. The
job now merges the daily closes in (scripts/build_nse_index_prices.py). The
start dates are returned so the page says which session each window counts
from.

`cross_check` compares the file's Nifty 50 with NSE's own daily closes in
`data/benchmarks.csv`. The dashboard shows the table only when they agree.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.engine.calendar_momentum import calendar_start_positions

INDICES = (
    ("nifty50", "Nifty 50"),
    ("nifty_midcap150", "Midcap 150"),
    ("nifty_smallcap250", "Smallcap 250"),
    ("nifty_microcap250", "Microcap 250"),
)
WINDOWS = (1, 3, 6)
# Nifty 50 in the index file against NSE's own close, same session.
CHECK_TOLERANCE = 0.001


@dataclass(frozen=True)
class SizeLeadership:
    table: pd.DataFrame          # one row per index: "<w>M" return and "<w>M vs 500"
    starts: dict[int, pd.Timestamp]
    end: pd.Timestamp
    sources: tuple[str, ...]


def closes(levels: pd.DataFrame) -> pd.DataFrame:
    """The long index-level file (date, index, close) as one column per index."""
    frame = levels.assign(date=pd.to_datetime(levels["date"]).dt.normalize())
    wide = frame.pivot_table(index="date", columns="index", values="close", aggfunc="last")
    return wide.sort_index()


def cross_check(levels: pd.DataFrame, nse_nifty50: pd.Series) -> tuple[bool, str]:
    """Does the file's Nifty 50 equal NSE's daily close on the sessions both have?"""
    wide = closes(levels)
    if "nifty50" not in wide:
        return False, "no Nifty 50 in the index file"
    ours = wide["nifty50"].dropna()
    nse = pd.to_numeric(nse_nifty50, errors="coerce").dropna()
    nse.index = pd.to_datetime(nse.index).normalize()
    both = ours.to_frame("file").join(nse.rename("nse"), how="inner").tail(60)
    if both.empty:
        return False, "no session shared with NSE's Nifty 50 file"
    worst = float((both["file"] / both["nse"] - 1).abs().max())
    if worst > CHECK_TOLERANCE:
        return False, f"Nifty 50 differs from NSE's close by up to {worst:.2%}"
    return True, f"Nifty 50 equals NSE's close on {len(both)} shared sessions"


def size_leadership(levels: pd.DataFrame, nifty500: pd.Series) -> SizeLeadership | None:
    wide = closes(levels)
    keys = [k for k, _ in INDICES if k in wide]
    if len(keys) != len(INDICES):
        return None
    n500 = pd.to_numeric(nifty500, errors="coerce").dropna()
    n500.index = pd.to_datetime(n500.index).normalize()
    joined = wide[keys].join(n500.rename("nifty500"), how="inner").dropna()
    if len(joined) < 2:
        return None
    idx = pd.DatetimeIndex(joined.index)
    end = idx[-1]
    rows: dict[str, dict[str, float]] = {name: {} for _, name in INDICES}
    rows["Nifty 500"] = {}
    starts: dict[int, pd.Timestamp] = {}
    for w in WINDOWS:
        pos = int(calendar_start_positions(idx, w)[-1])
        if pos >= len(idx) - 1:
            continue
        start = idx[pos]
        starts[w] = start
        r500 = joined.at[end, "nifty500"] / joined.at[start, "nifty500"] - 1
        rows["Nifty 500"][f"{w}M"] = r500
        for key, name in INDICES:
            r = joined.at[end, key] / joined.at[start, key] - 1
            rows[name][f"{w}M"] = r
            rows[name][f"{w}M vs 500"] = (1 + r) / (1 + r500) - 1
    sources = tuple(sorted(set(levels.get("source", pd.Series(dtype=str)).dropna().astype(str))))
    return SizeLeadership(pd.DataFrame(rows).T, starts, end, sources)


def headline(result: SizeLeadership) -> str:
    """One plain sentence: who leads over the shortest and the longest window."""
    t = result.table.drop(index="Nifty 500", errors="ignore")
    parts = []
    for w in (min(result.starts), max(result.starts)) if result.starts else ():
        col = f"{w}M vs 500"
        if col in t:
            parts.append(f"{t[col].idxmax()} leads over {w} month{'s' if w > 1 else ''}")
    return "; ".join(dict.fromkeys(parts)) + "." if parts else ""
