"""Which days NSE can have traded: weekends, fixed holidays, NSE's own holiday list.

Owner, 2026-10-03: NSE never publishes a bhavcopy on a holiday, so a session
held for one is a mistake (a holiday filed as a copy of the day before, as the
GitHub mirror did for every holiday from 2021) or a day still to collect. A
weekend session must be one NSE announced (Muhurat trading, a Budget day, a
special Saturday): data/reference/nse/special_sessions.csv. Fixed-date
holidays (26 Jan, 1 May, 15 Aug, 2 Oct, 25 Dec) never trade.
data/reference/nse/holidays.csv is NSE's published list (its holiday-master
API); a day marked "muhurat" there is a holiday with an evening session.
"""

from __future__ import annotations

from datetime import date
from functools import lru_cache
from pathlib import Path

import pandas as pd

REF = Path(__file__).resolve().parents[2] / "data" / "reference" / "nse"
HOLIDAYS = REF / "holidays.csv"
SPECIAL = REF / "special_sessions.csv"
FIXED = {(1, 26): "Republic Day", (5, 1): "Maharashtra Day", (8, 15): "Independence Day",
         (10, 2): "Mahatma Gandhi Jayanti", (12, 25): "Christmas"}


@lru_cache(maxsize=1)
def _lists() -> tuple[dict[date, str], set[date], set[date]]:
    """(published holidays, their Muhurat days, announced special sessions)."""
    hol, muhurat, special = {}, set(), set()
    try:
        h = pd.read_csv(HOLIDAYS, dtype=str).fillna("")
        for r in h.itertuples():
            d = date.fromisoformat(r.date)
            hol[d] = r.description
            if r.special_session:
                muhurat.add(d)
    except (OSError, ValueError):
        pass
    try:
        special = {date.fromisoformat(d) for d in pd.read_csv(SPECIAL, dtype=str)["date"]}
    except (OSError, ValueError, KeyError):
        pass
    return hol, muhurat, special


def not_a_session(day) -> str:
    """Why NSE cannot have traded on `day` ("" when it could)."""
    d = pd.Timestamp(day).date()
    hol, muhurat, special = _lists()
    if d in special or d in muhurat:
        return ""
    if d.weekday() >= 5:
        return "weekend"
    if (d.month, d.day) in FIXED:
        return FIXED[(d.month, d.day)]
    return hol.get(d, "")


def impossible_sessions(days) -> dict[date, str]:
    """{day: reason} for each held day NSE cannot have traded."""
    out = {}
    for day in days:
        why = not_a_session(day)
        if why:
            out[pd.Timestamp(day).date()] = why
    return out
