"""Per-system facts the strategy runs on: ledger, inception and membership.

Owner, 2026-09-27: three systems in one app -- Nifty 750, Nano Cap and
Combined -- each ranked, booked and recorded on its own. The strategy
(src/engine/backtester, the record's pinned configuration) is the same for
all three; what differs is who may be held, since when, and where the frozen
months are kept. Those three answers live here and nowhere else.

Membership is point in time for every system:
  Nifty 750  NSE's constituents, from data/membership_history.json
  Nano Cap   each month-end list (data/nanocap_membership.json), in force from
             the session it was built on -- the close that signals the next
             month's book -- until the next list
  Combined   the union of the two on every date both answer for
  Nifty 1000 NSE's constituents, data/membership_history.json indices.nifty_1000,
             reconstructed from 30 Oct 2026 until NSE's first list (S175)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from src.engine.extra_universe import (
    SYSTEM_750,
    SYSTEM_1000,
    SYSTEM_COMBINED,
    SYSTEM_INCEPTION,
    SYSTEM_NANO,
)
from src.engine.membership import (
    load_history_or_none,
    members_on,
    record_snapshot,
)
from src.engine.track_record import INCEPTION, LEDGER_PATH
from src.loaders.app_pack import resolve as _pack

DATA = Path(__file__).resolve().parents[2] / "data"
NANO_HISTORY_PATH = DATA / "nanocap_membership.json"

LEDGERS = {
    SYSTEM_750: LEDGER_PATH,
    SYSTEM_1000: DATA / "track_record_1000.json",
    SYSTEM_NANO: DATA / "track_record_nano.json",
    SYSTEM_COMBINED: DATA / "track_record_combined.json",
}


def ledger_path(system: str) -> Path:
    return LEDGERS[system]


def inception(system: str) -> pd.Period:
    """The first month a system's live record may hold."""
    return (INCEPTION if system == SYSTEM_750
            else pd.Period(SYSTEM_INCEPTION[system], freq="M"))


def nano_history(path: Path | str = NANO_HISTORY_PATH) -> dict[str, Any] | None:
    """Nano Cap's month-end lists as a membership timeline, or None without any."""
    try:
        months = json.loads(Path(_pack(path)).read_text(encoding="utf-8")).get("months", {})
    except (OSError, ValueError):
        return None
    history: dict[str, Any] = {"schema_version": 1, "index": "NANO CAP",
                               "baseline": None, "changes": []}
    for as_of in sorted(months):
        symbols = months[as_of].get("symbols") or []
        if symbols:
            history, _ = record_snapshot(history, as_of, symbols)
    return history if history.get("baseline") else None


def _dates(history: dict[str, Any]) -> list[str]:
    return [history["baseline"]["date"]] + [c["date"] for c in history.get("changes") or []]


def combined_history(h750: dict[str, Any] | None,
                     hnano: dict[str, Any] | None) -> dict[str, Any] | None:
    """The union of the two timelines, from the first date both answer for."""
    if not h750 or not hnano:
        return None
    start = max(h750["baseline"]["date"], hnano["baseline"]["date"])
    dates = sorted({d for d in _dates(h750) + _dates(hnano) if d >= start} | {start})
    history: dict[str, Any] = {"schema_version": 1, "index": "COMBINED",
                               "baseline": None, "changes": []}
    for d in dates:
        a, b = members_on(h750, d, canonical=True), members_on(hnano, d, canonical=True)
        if a is None or b is None:
            continue
        history, _ = record_snapshot(history, d, a | b)
    return history if history.get("baseline") else None


def membership_for(system: str) -> dict[str, Any] | None:
    """The point-in-time membership timeline the backtest scores a system on."""
    h750 = load_history_or_none()
    if system == SYSTEM_750:
        return h750
    if system == SYSTEM_1000:
        # NSE's Nifty 1000, recorded from 30 Oct 2026 (S175). Imported here:
        # index_universe imports this module.
        from src.engine.index_universe import index_history
        return index_history("nifty_1000", h750)
    hnano = nano_history()
    if system == SYSTEM_NANO:
        return hnano
    return combined_history(h750, hnano)


def unpriced_members(adj_close: pd.DataFrame, membership: dict[str, Any] | None, start: pd.Period,
                     months: int, skip=()) -> dict[str, list[str]]:
    """{signal session: members with no close that session} for each month from `start`.

    A month's book is formed at the last session before it; a member with no
    close there would be silently left out of the ranking it is scored on
    (S175). `skip` holds months ("YYYY-MM") not to check: those already frozen.
    The monthly freeze refuses the Nifty 1000 on any gap; the live record names
    them on the page.
    """
    if membership is None or adj_close is None or adj_close.empty:
        return {}
    idx = pd.DatetimeIndex(adj_close.index)
    skip = {str(k) for k in skip}
    out: dict[str, list[str]] = {}
    for k in range(months):
        month = start + k
        if str(month) in skip:
            continue
        before = idx[idx < month.start_time]
        if not len(before):
            continue
        day = before[-1]
        members = members_on(membership, day, canonical=True) or set()
        row = adj_close.loc[day]
        if isinstance(row, pd.DataFrame):          # a duplicated session: its last row
            row = row.iloc[-1]
        missing = sorted(s for s in members if s not in row.index or pd.isna(row[s]))
        if missing:
            out[f"{day:%Y-%m-%d}"] = missing
    return out
