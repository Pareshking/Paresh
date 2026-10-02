"""The indices a long backtest can be run on, each point in time from 2010.

Owner, 2026-10-03: a backtest from 2010 on a chosen index -- Nifty 50, 100,
500, Midcap 150, Smallcap 250, Microcap 250 or Total Market -- with size set
by the index tier (NSE builds them by free-float market cap) and an optional
traded-value floor; no market-cap cutoff.

data/membership_history.json keeps each index's own timeline under
``indices`` (nse_index_rebuild/merge_into_history.py); the top level is the
Total Market copy the live systems read. Nifty 100 is not stored: it is
Nifty 50 plus Nifty Next 50 on every date, which is how NSE defines it.

An index cannot be chosen for a month before its timeline begins (Midcap and
Smallcap from Apr 2016, Microcap from Sep 2021, Total Market from Oct 2021).
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from src.engine.membership import load_history_or_none, members_on
from src.engine.systems import combined_history

# key -> display name, in the order the picker lists them.
INDICES: dict[str, str] = {
    "nifty_50": "Nifty 50",
    "nifty_100": "Nifty 100",
    "nifty_500": "Nifty 500",
    "nifty_midcap_150": "Nifty Midcap 150",
    "nifty_smallcap_250": "Nifty Smallcap 250",
    "nifty_microcap_250": "Nifty Microcap 250",
    "nifty_total_market": "Nifty Total Market",
}
DEFAULT_INDEX = "nifty_500"
NIFTY_100_PARTS = ("nifty_50", "nifty_next_50")


def _stored(full: dict[str, Any], key: str) -> dict[str, Any] | None:
    sub = (full.get("indices") or {}).get(key)
    if not sub or not sub.get("baseline"):
        return None
    return {"schema_version": full.get("schema_version", 2), "index": key,
            "baseline": sub["baseline"], "changes": list(sub.get("changes") or []),
            "aliases": full.get("aliases") or {}}


def index_history(key: str, full: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """One index's membership timeline, in the form members_on() reads; None if not held."""
    full = full if full is not None else load_history_or_none()
    if not full:
        return None
    if key == "nifty_100":
        a, b = (_stored(full, k) for k in NIFTY_100_PARTS)
        out = combined_history(a, b)
        if out is None:
            return None
        return {**out, "index": key, "aliases": full.get("aliases") or {}}
    return _stored(full, key)


def first_month(history: dict[str, Any] | None) -> pd.Period | None:
    """The first whole month the timeline answers for."""
    if not history or not history.get("baseline"):
        return None
    start = pd.Timestamp(history["baseline"]["date"])
    month = start.to_period("M")
    return month if start.day == 1 else month + 1


def ever_members(history: dict[str, Any] | None) -> set[str]:
    """Every symbol the timeline ever lists, under its current ticker too."""
    if not history or not history.get("baseline"):
        return set()
    out = set(history["baseline"]["symbols"])
    for change in history.get("changes") or []:
        out |= set(change.get("added") or [])
    aliases = history.get("aliases") or {}
    return out | {aliases[s]["new_symbol"] for s in out if s in aliases}


def all_ever_members(full: dict[str, Any] | None = None) -> set[str]:
    """Every symbol any index (and the top-level Total Market copy) ever listed."""
    full = full if full is not None else load_history_or_none()
    if not full:
        return set()
    out = ever_members(full)
    for key in (full.get("indices") or {}):
        out |= ever_members(_stored(full, key))
    return out


def size_on(history: dict[str, Any] | None, on) -> int | None:
    members = members_on(history, on) if history else None
    return len(members) if members is not None else None
