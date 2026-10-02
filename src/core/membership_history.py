"""Point-in-time membership history for the canonical NSE index snapshots.

The history is derived from the actual constituent CSVs written by the index
sync. It intentionally excludes NSE's DUMMY* placeholders, so membership
history and the tradable universe share one symbol-eligibility rule.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

from src.core.tickers import is_tradeable_symbol

HISTORY_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "data",
    "membership_history.json",
)
SCHEMA_VERSION = 2
INDIA = ZoneInfo("Asia/Kolkata")


def india_today() -> str:
    return datetime.now(INDIA).date().isoformat()


def _clean(symbols) -> list[str]:
    return sorted({
        str(symbol).strip().upper()
        for symbol in symbols
        if is_tradeable_symbol(symbol)
    })


def load_history() -> dict:
    if not os.path.exists(HISTORY_FILE):
        return {"schema_version": SCHEMA_VERSION, "indices": {}}
    with open(HISTORY_FILE, encoding="utf-8") as fh:
        raw = json.load(fh)

    # Migrate the old single-index shape without losing its existing history.
    if "index" in raw and "indices" not in raw:
        name = str(raw["index"]).strip()
        return {
            "schema_version": SCHEMA_VERSION,
            "indices": {name: {
                "baseline": {
                    "date": raw.get("baseline", {}).get("date"),
                    "symbols": _clean(raw.get("baseline", {}).get("symbols", [])),
                },
                "changes": raw.get("changes", []),
            }},
        }

    raw["schema_version"] = SCHEMA_VERSION
    raw.setdefault("indices", {})
    return raw


def save_history(history: dict) -> None:
    os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
    tmp = HISTORY_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(history, fh, indent=2, sort_keys=False)
        fh.write("\n")
    os.replace(tmp, HISTORY_FILE)



# Historical coverage is a first-class contract. A live snapshot is not a
# substitute for a missing historical interval; callers should report the gap.
MIN_FULL_2026_START = "2026-01-01"
REQUIRED_2026_INDEXES = (
    "nifty_50",
    "nifty_next_50",
    "nifty_midcap_150",
    "nifty_smallcap_250",
    "nifty_microcap_250",
    "nifty_total_market",
)

def coverage_gaps(history: dict, *, start: str = MIN_FULL_2026_START) -> dict[str, dict[str, str | None]]:
    """Describe where an index history fails the requested historical window."""
    out: dict[str, dict[str, str | None]] = {}
    for index_name in REQUIRED_2026_INDEXES:
        entry = (history.get("indices") or {}).get(index_name) or {}
        baseline = entry.get("baseline") or {}
        first = baseline.get("date")
        out[index_name] = {
            "required_start": start,
            "actual_start": first,
            "status": "covered" if first and str(first) <= start else "gap",
        }
    return out

def record_snapshot(
    index_name: str,
    previous_symbols,
    current_symbols,
    *,
    observed_on: str | None = None,
) -> tuple[list[str], list[str]]:
    """Record a membership delta from the previous CSV to the new CSV.

    On first sight of an index we establish its baseline from the previous
    committed/local CSV. Subsequent runs append only real set changes.
    """
    previous = _clean(previous_symbols)
    current = _clean(current_symbols)
    added = sorted(set(current) - set(previous))
    removed = sorted(set(previous) - set(current))
    history = load_history()
    entry = history["indices"].get(index_name)

    if entry is None:
        entry = {
            "baseline": {
                "date": observed_on or india_today(),
                "symbols": previous,
            },
            "changes": [],
        }
        history["indices"][index_name] = entry

    day = observed_on or india_today()
    if added or removed:
        changes = entry.setdefault("changes", [])
        if changes and changes[-1].get("date") == day:
            changes[-1]["added"] = sorted(set(changes[-1].get("added", [])) | set(added))
            changes[-1]["removed"] = sorted(set(changes[-1].get("removed", [])) | set(removed))
        else:
            changes.append({"date": day, "added": added, "removed": removed})

    save_history(history)
    return added, removed
