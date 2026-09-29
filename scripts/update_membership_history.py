"""Refresh point-in-time membership history from synchronized NSE CSVs."""
from __future__ import annotations
import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
from src.core.config import INDICES_LOCAL
from src.core.tickers import is_tradeable_symbol
from src.core.membership_history import load_history, save_history

INDEX_KEYS = {name: name.lower().replace(" ", "_") for name in INDICES_LOCAL}
INDIA = ZoneInfo("Asia/Kolkata")

def clean(values):
    return sorted({str(v).strip().upper() for v in values if is_tradeable_symbol(v)})

def main():
    history = load_history()
    observed = datetime.now(INDIA).date().isoformat()
    changes = {}
    for index_name, path in INDICES_LOCAL.items():
        if not os.path.exists(path):
            continue
        frame = pd.read_csv(path)
        frame.columns = [str(c).strip() for c in frame.columns]
        sym_col = next((c for c in frame.columns if c.lower() in ("symbol", "ticker")), None)
        if not sym_col:
            continue
        current = clean(frame[sym_col].tolist())
        key = INDEX_KEYS[index_name]
        entry = history["indices"].get(key)
        if entry is None:
            history["indices"][key] = {"baseline": {"date": observed, "symbols": current}, "changes": []}
            changes[key] = {"added": [], "removed": []}
            continue
        previous = set(clean(entry.get("baseline", {}).get("symbols", [])))
        for event in entry.get("changes", []):
            previous.update(clean(event.get("added", [])))
            previous.difference_update(clean(event.get("removed", [])))
        added = sorted(set(current) - previous)
        removed = sorted(previous - set(current))
        if added or removed:
            events = entry.setdefault("changes", [])
            if events and events[-1].get("date") == observed:
                events[-1]["added"] = sorted(set(events[-1].get("added", [])) | set(added))
                events[-1]["removed"] = sorted(set(events[-1].get("removed", [])) | set(removed))
            else:
                events.append({"date": observed, "added": added, "removed": removed})
        changes[key] = {"added": added, "removed": removed}
    save_history(history)
    for key, delta in changes.items():
        if delta["added"] or delta["removed"]:
            print("[MEMBERSHIP]", key, "+", len(delta["added"]), "-", len(delta["removed"]))

if __name__ == "__main__":
    main()
