"""Refresh point-in-time membership history from synchronized NSE CSVs."""
from __future__ import annotations
import os
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
from src.core.config import INDICES_LOCAL, RECORDED_INDICES_LOCAL
from src.core.tickers import is_tradeable_symbol
from src.core.membership_history import load_history, save_history
from src.engine import nifty1000_backfill

# The ranked lists and the recorded-only ones (Nifty 1000, S175): both are point in time from here.
RECORDED = {**INDICES_LOCAL, **RECORDED_INDICES_LOCAL}
INDEX_KEYS = {name: name.lower().replace(" ", "_") for name in RECORDED}
INDIA = ZoneInfo("Asia/Kolkata")
# Indices whose record starts before the first list we hold (owner, 21 Nov 2026: Nifty 1000 from 1 Nov).
BACKFILL = {"nifty_1000": nifty1000_backfill.reconstruct}

def clean(values):
    return sorted({str(v).strip().upper() for v in values if is_tradeable_symbol(v)})

def main():
    history = load_history()
    observed = datetime.now(INDIA).date().isoformat()
    changes = {}
    for index_name, path in RECORDED.items():
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
        if entry is None and key in BACKFILL and "nifty_total_market" in history["indices"]:
            # First sight of an index the owner wants from an earlier date: rebuilt from that
            # date by its own rule, with a note that it is a reconstruction (S175).
            history["indices"][key] = BACKFILL[key](history["indices"]["nifty_total_market"], current, observed)
            changes[key] = {"added": current, "removed": []}
            continue
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

def rebuild_nifty_1000() -> int:
    """`--rebuild-nifty-1000`: rebuild the reconstructed stretch by the rule in nifty1000_backfill (S196)."""
    history = load_history()
    entry = history["indices"].get("nifty_1000")
    if entry is None:
        print("no nifty_1000 entry to rebuild")
        return 1
    new = nifty1000_backfill.rebuild(entry, history["indices"]["nifty_total_market"])
    if new == entry:
        print("nifty_1000 entry already follows the rule")
        return 0
    history["indices"]["nifty_1000"] = new
    save_history(history)
    print("[MEMBERSHIP] nifty_1000 rebuilt:", [(c["date"], c["added"], c["removed"]) for c in new["changes"]])
    return 0


if __name__ == "__main__":
    import sys
    if "--rebuild-nifty-1000" in sys.argv[1:]:
        raise SystemExit(rebuild_nifty_1000())
    main()
