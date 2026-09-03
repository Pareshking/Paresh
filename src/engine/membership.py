"""Point-in-time index membership: who was actually in the index, and when.

A backtest that scores January against today's constituent list has a known bias
in a known direction. Index additions skew toward stocks that have recently done
well, and a momentum screen preferentially buys exactly those, so applying
today's membership to a past month lets the strategy hold names it could not
have known to hold. The result flatters, by an amount nobody can state.

The fix is to know who was in the index at the time. That data was never
purchased -- it is accumulating for free, because the daily sync commits
data/indices/*.csv to git on every run. This module turns those snapshots into a
queryable timeline.

Storage is a baseline plus append-only diffs. Index membership changes rarely --
NSE reconstitutes semi-annually -- so a full list per day would be almost
entirely repetition. A baseline of ~750 symbols and a handful of small diffs
stays small enough to commit daily for years.

What it CANNOT do is reconstruct membership before the first snapshot. Ask for a
date before coverage and you get None, not a guess. A silent fallback to today's
list is precisely the bias this module exists to remove.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable

from src.core.tickers import is_tradeable_symbol

HISTORY_PATH = Path("data/membership_history.json")
SCHEMA_VERSION = 1
DEFAULT_INDEX = "NIFTY TOTAL MARKET"


def _as_date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()


def _clean(symbols: Iterable[str]) -> list[str]:
    """Real constituents only, deduplicated and sorted.

    Placeholders are filtered with the same predicate the index loader uses. If
    the two disagreed, every DUMMY row appearing or vanishing would register as
    a membership change and the diffs would fill with phantom churn.
    """
    return sorted({
        str(s).strip().upper() for s in symbols if is_tradeable_symbol(s)
    })


def empty_history(index: str = DEFAULT_INDEX) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "index": index,
        "baseline": None,
        "changes": [],
    }


def load_history(path: Path | str = HISTORY_PATH) -> dict[str, Any]:
    """Read the timeline, or an empty one. A corrupt file raises, never resets."""
    p = Path(path)
    if not p.exists():
        return empty_history()
    with p.open("r", encoding="utf-8") as fh:
        history = json.load(fh)
    if not isinstance(history, dict) or "changes" not in history:
        raise ValueError(f"{p} is not a membership history")
    return history


def save_history(history: dict[str, Any], path: Path | str = HISTORY_PATH) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as fh:
        json.dump(history, fh, indent=2)
        fh.write("\n")


def coverage(history: dict[str, Any]) -> tuple[date | None, date | None]:
    """First and last dates the timeline can answer for."""
    baseline = history.get("baseline")
    if not baseline:
        return None, None
    first = _as_date(baseline["date"])
    changes = history.get("changes") or []
    last = _as_date(changes[-1]["date"]) if changes else first
    return first, last


def record_snapshot(
    history: dict[str, Any], on: Any, symbols: Iterable[str]
) -> tuple[dict[str, Any], bool]:
    """Append one day's membership. Returns (history, changed).

    Append-only and chronological: a snapshot dated on or before the last
    recorded date is rejected rather than reordered or merged. A day whose
    membership matches the previous state writes nothing -- that is the normal
    case, and it is why the file stays small.
    """
    snap_date = _as_date(on)
    members = _clean(symbols)
    if not members:
        raise ValueError("refusing to record an empty membership snapshot")

    out = dict(history)
    out.setdefault("schema_version", SCHEMA_VERSION)
    out.setdefault("index", DEFAULT_INDEX)
    out["changes"] = list(out.get("changes") or [])

    if not out.get("baseline"):
        out["baseline"] = {"date": snap_date.isoformat(), "symbols": members}
        return out, True

    first, last = coverage(out)
    if snap_date <= last:
        raise ValueError(
            f"snapshot {snap_date} is not after the last recorded date {last}; "
            "membership history is append-only"
        )

    previous = members_on(out, last)
    assert previous is not None
    added = sorted(set(members) - previous)
    removed = sorted(previous - set(members))
    if not added and not removed:
        return out, False

    out["changes"].append(
        {"date": snap_date.isoformat(), "added": added, "removed": removed}
    )
    return out, True


def members_on(history: dict[str, Any], on: Any) -> set[str] | None:
    """Constituents as of `on`, or None when the date predates coverage.

    None is the honest answer, and callers must treat it as "unknown" rather
    than falling back to the current list. Returning today's membership for a
    date we have no record of would reintroduce exactly the bias this module
    removes, while looking like it had been removed.
    """
    baseline = history.get("baseline")
    if not baseline:
        return None
    target = _as_date(on)
    first = _as_date(baseline["date"])
    if target < first:
        return None

    members = set(baseline["symbols"])
    for change in history.get("changes") or []:
        if _as_date(change["date"]) > target:
            break
        members |= set(change.get("added") or [])
        members -= set(change.get("removed") or [])
    return members


def describe(history: dict[str, Any]) -> dict[str, Any]:
    first, last = coverage(history)
    changes = history.get("changes") or []
    churn = sum(
        len(c.get("added") or []) + len(c.get("removed") or []) for c in changes
    )
    return {
        "index": history.get("index", DEFAULT_INDEX),
        "first": first.isoformat() if first else None,
        "last": last.isoformat() if last else None,
        "snapshots_with_changes": len(changes),
        "total_churn": churn,
        "current_size": len(members_on(history, last)) if last else 0,
    }
