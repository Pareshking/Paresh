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

from typing import Any
from collections.abc import Iterable

# The close that signals November 2026 (1 Nov is a Sunday): the record starts with the
# November book, as the ₹2,000 Cr list is dated the session that signals its month.
START = "2026-10-30"
FIRST_PUBLISHED = "2026-11-16"
NOTE = ("Reconstructed from 2026-10-30 (the close that signals November) until the first list recorded here (2026-11-22): NSE "
        "launched the Nifty 1000 on 2026-11-12 (ind_prs12112026.pdf; base date 24 Sep 2007, reviewed each March and September) "
        "and first lists it in the daily index archive on 2026-11-16. Members on each earlier day are NSE's Nifty "
        "Total Market of that day plus the 250 NSE's first recorded list adds to it; that the 250 were "
        "the same then is an assumption no published list confirms. The Nov 2026 book, signalled at "
        "the 30 Oct close, uses a list not public until 16 Nov: label that month reconstructed, not "
        "recorded. Names the Total Market took in meanwhile that NSE's own notices place outside the Nifty 1000 are "
        "not carried (not_carried, with the notice). Owner, 21 Nov 2026 (S175); S196.")


# The first list the daily step recorded (fb7eb1e, 21 Nov 2026 22:52 UTC: 22 Nov in India, the step's date).
FIRST_RECORDED = "2026-11-22"

# Names the Nifty Total Market took in between START and the first recorded list that were NOT in the
# Nifty 1000: NSE's own exclusion notices, issued after the index's launch (ind_prs12112026.pdf,
# 12 Nov 2026), list every index each name leaves, and the Nifty 1000 is not among them (S196).
# Without this the reconstruction held 1,002 names from 4 to 14 Nov and 1,001 to 17 Nov.
NOT_IN_1000: dict[str, str] = {
    "IGLSPIRITS": ("ind_prs12112026_1.pdf (12 Nov 2026): excluded w.e.f. 16 Nov from Nifty Total Market, "
                   "Microcap 250, Smallcap 500 and Sugar & Ethanol; the Nifty 1000 is not listed"),
    "ENNATURE": ("ind_prs13112026.pdf (13 Nov 2026): excluded w.e.f. 17 Nov from Nifty Total Market, "
                 "Microcap 250, Smallcap 500 and Sugar & Ethanol; the Nifty 1000 is not listed"),
}


def members_at(entry: dict[str, Any], day: str) -> set[str]:
    """An entry's members on `day`: its baseline with every change dated on or before it applied."""
    out = set(entry.get("baseline", {}).get("symbols", []))
    for c in entry.get("changes", []):
        if c["date"] <= day:
            out |= set(c.get("added", []))
            out -= set(c.get("removed", []))
    return out


def reconstruct(total_market: dict[str, Any], current: Iterable[str], observed: str,
                start: str = START, not_in: dict[str, str] | None = None) -> dict[str, Any]:
    """The Nifty 1000 entry from `start`, ending at the list observed on `observed`.

    `total_market` is the 750's entry (baseline + changes) already updated for
    `observed`; `current` is the Nifty 1000 list observed that day. A change is
    recorded on every date the 750 changed in between, and on `observed` if the
    list itself differs from the reconstruction.
    """
    not_in = NOT_IN_1000 if not_in is None else not_in
    current = set(current)
    extra = current - members_at(total_market, observed)
    dates = sorted({c["date"] for c in total_market.get("changes", []) if start < c["date"] < observed})
    base = sorted((members_at(total_market, start) | extra) - set(not_in))
    entry: dict[str, Any] = {"baseline": {"date": start, "symbols": base}, "changes": [], "note": NOTE}
    if not_in:
        entry["not_carried"] = dict(sorted(not_in.items()))
    prev = set(base)
    for d in dates + [observed]:
        now = current if d == observed else (members_at(total_market, d) | extra) - set(not_in)
        added, removed = sorted(now - prev), sorted(prev - now)
        if added or removed:
            entry["changes"].append({"date": d, "added": added, "removed": removed})
        prev = now
    return entry


def rebuild(entry: dict[str, Any], total_market: dict[str, Any], first_recorded: str = FIRST_RECORDED,
            not_in: dict[str, str] | None = None) -> dict[str, Any]:
    """The entry reconstructed again up to the first list recorded, every recorded change after it kept.

    The first recorded list is the entry's own members on `first_recorded` (what the step saw that day), so
    only the reconstructed stretch before it can change; the record from then on is NSE's list as observed.
    """
    recorded = members_at(entry, first_recorded)
    out = reconstruct(total_market, recorded, first_recorded, not_in=not_in)
    out["changes"] += [c for c in entry.get("changes", []) if c["date"] > first_recorded]
    for k, v in entry.items():
        if k not in out:
            out[k] = v
    return out
