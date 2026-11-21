"""Nifty 1000 membership from 1 Nov 2026, before NSE published the index (S175).

Owner, 21 Nov 2026: "start date is 01-Nov for us, we will backfill price history."
NSE first lists the Nifty 1000 in its daily index archive on 16 Nov 2026
(ind_close_all_16112026.csv; absent from every file to 13 Nov), so NSE never
published a 1 Nov list. The membership before the first list we hold is
therefore OUR reconstruction, by the index's own construction (the 750 plus 250
more):

    member on day d  =  Nifty Total Market on d (NSE's own, recorded history)
                        ∪  the 250 that NSE's first list we hold adds to the 750

The second term assumes NSE's 250 were the same on 1 Nov as on that list. No
published list can confirm it, so the entry carries a note saying so, and the
backtest must treat Nov 2026 as reconstructed, not recorded.

Pure: scripts/update_membership_history.py does the I/O, once, when it first
meets the index.
"""
from __future__ import annotations

from typing import Any, Iterable

# The close that signals November 2026 (1 Nov is a Sunday): the record starts with the
# November book, as the ₹2,000 Cr list is dated the session that signals its month.
START = "2026-10-30"
FIRST_PUBLISHED = "2026-11-16"
NOTE = ("Reconstructed from 2026-10-30 (the close that signals November) until the first list recorded here: NSE first published the "
        "Nifty 1000 on 2026-11-16 (daily index archive). Members on each earlier day are NSE's Nifty "
        "Total Market of that day plus the 250 NSE's first recorded list adds to it; that the 250 were "
        "the same then is an assumption no published list confirms. The Nov 2026 book, signalled at "
        "the 30 Oct close, uses a list not public until 16 Nov: label that month reconstructed, not "
        "recorded. Owner, 21 Nov 2026 (S175).")


def members_at(entry: dict[str, Any], day: str) -> set[str]:
    """An entry's members on `day`: its baseline with every change dated on or before it applied."""
    out = set(entry.get("baseline", {}).get("symbols", []))
    for c in entry.get("changes", []):
        if c["date"] <= day:
            out |= set(c.get("added", []))
            out -= set(c.get("removed", []))
    return out


def reconstruct(total_market: dict[str, Any], current: Iterable[str], observed: str,
                start: str = START) -> dict[str, Any]:
    """The Nifty 1000 entry from `start`, ending at the list observed on `observed`.

    `total_market` is the 750's entry (baseline + changes) already updated for
    `observed`; `current` is the Nifty 1000 list observed that day. A change is
    recorded on every date the 750 changed in between, and on `observed` if the
    list itself differs from the reconstruction.
    """
    current = set(current)
    extra = current - members_at(total_market, observed)
    dates = sorted({c["date"] for c in total_market.get("changes", []) if start < c["date"] < observed})
    base = sorted(members_at(total_market, start) | extra)
    entry: dict[str, Any] = {"baseline": {"date": start, "symbols": base}, "changes": [], "note": NOTE}
    prev = set(base)
    for d in dates + [observed]:
        now = current if d == observed else members_at(total_market, d) | extra
        added, removed = sorted(now - prev), sorted(prev - now)
        if added or removed:
            entry["changes"].append({"date": d, "added": added, "removed": removed})
        prev = now
    return entry
