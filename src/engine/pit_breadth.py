"""Breadth counted over the stocks in an index on each date (S150).

Counting today's members back in time leaves out the stocks that later left
the index, mostly the ones that fell: measured 20 Nov 2026 on the Nifty 500,
weekly since Jun 2016, today's members read on average 4.5 points more stocks
above their 200D EMA, 5.0 more ahead of the index over a year and a median
stock 4.9 points better than the members of the day did. Today's readings then
looked worse against their history than they were (the share ahead of the
index over a year: 29th percentile on today's members, 50th on the members of
the day).

`member_mask` turns a membership timeline (src/engine/membership.py) into a
sessions x symbols table of booleans that the breadth measures in
src/engine/market_questions.py accept as `members`.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from src.engine import membership


def member_mask(history: dict[str, Any], index: pd.DatetimeIndex, columns) -> pd.DataFrame:
    """True where the stock was in the index on that session. Sessions before the
    timeline starts are all False: unknown is not today's list."""
    index = pd.DatetimeIndex(index)
    cols = list(columns)
    out = pd.DataFrame(False, index=index, columns=cols)
    base = history.get("baseline") or {}
    if not base:
        return out
    starts = [pd.Timestamp(base["date"])] + [pd.Timestamp(c["date"]) for c in history.get("changes") or []]
    starts = sorted(set(starts))
    colset = set(cols)
    for i, start in enumerate(starts):
        end = starts[i + 1] if i + 1 < len(starts) else None
        rows = (index >= start) & ((index < end) if end is not None else True)
        if not rows.any():
            continue
        on = membership.members_on(history, start, canonical=True) or set()
        keep = [c for c in on if c in colset]
        out.loc[rows, keep] = True
    return out


FILE = __import__("pathlib").Path(__file__).resolve().parents[2] / "data" / "breadth_history.csv"


def load(universe: str, path=FILE) -> pd.DataFrame | None:
    """One universe's readings by date (scripts/build_breadth_history.py), or None."""
    try:
        f = pd.read_csv(path, parse_dates=["date"])
    except (OSError, ValueError):
        return None
    f = f[f["universe"] == universe].drop(columns="universe").set_index("date").sort_index()
    return f if len(f) else None


def splice(live: pd.Series, history: pd.DataFrame | None, column: str) -> pd.Series:
    """The members-of-the-day reading up to its last date, the live one after.
    The live reading counts today's members, which is right for today and
    wrong for the past; the file is written weekly-to-daily, so the two meet
    within days of the present."""
    if history is None or column not in history:
        return live
    past = pd.to_numeric(history[column], errors="coerce").dropna()
    if past.empty:
        return live
    if live is None or live.empty or not isinstance(live.index, pd.DatetimeIndex):
        return past
    return pd.concat([past, live[live.index > past.index[-1]]]).sort_index()
