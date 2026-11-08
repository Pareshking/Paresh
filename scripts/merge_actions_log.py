#!/usr/bin/env python3
"""Union two copies of data/corporate_actions_log.json after a rebase conflict.

    python scripts/merge_actions_log.py <theirs.json> <ours.json> <out.json>

The log is append-only (scripts/check_corporate_actions.py): every event, keyed
"<date>:<symbol>", stays once seen. daily_sync and screener_sync both append to
it, and their conflict path used to keep one run's whole copy (`git checkout
--theirs -- data/`), so the other job's new events were lost with no error
(audit, 8 Nov 2026). This keeps every event from both copies; for an event in
both, the earliest `first_seen` wins and the rest of the newer copy's fields;
`last_checked` is the later of the two.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def _load(path: str) -> dict:
    p = Path(path)
    if not p.exists() or not p.read_text(encoding="utf-8").strip():
        return {"events": {}}
    return json.loads(p.read_text(encoding="utf-8"))


def merge(a: dict, b: dict) -> dict:
    out = {**a, **b}
    events = dict(a.get("events") or {})
    for key, ev in (b.get("events") or {}).items():
        if key in events:
            first = min(filter(None, [events[key].get("first_seen"), ev.get("first_seen")]), default=None)
            events[key] = {**events[key], **ev}
            if first:
                events[key]["first_seen"] = first
        else:
            events[key] = ev
    out["events"] = dict(sorted(events.items()))
    checked = [x for x in (a.get("last_checked"), b.get("last_checked")) if x]
    if checked:
        out["last_checked"] = max(checked)
    return out


def main(argv: list[str]) -> int:
    if len(argv) != 4:
        print(__doc__)
        return 2
    merged = merge(_load(argv[1]), _load(argv[2]))
    Path(argv[3]).write_text(json.dumps(merged, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"merged corporate-actions log: {len(merged['events'])} events")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
