"""Freeze and change control for data/membership_history.json (protocol gate G8).

The history is rebuilt from NSE press releases and then appended to by the daily sync. This freezes the reconstruction:
a SHA-256 over everything up to FROZEN_THROUGH (each index's baseline and its changes dated on or before that day, plus
the aliases, caveats, name-change ledger and applied rules). Changes the daily sync appends after that day do not move
the hash. Any other edit does, and CI (`--check`) then fails until the edit is recorded with a reason.

    python freeze_history.py --check
    python freeze_history.py --write --reason "why the history changed"   # appends to the change log, then re-run G3 to G7

The freeze record is data/membership_history.freeze.json.
"""
import argparse, hashlib, json, os, sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
HISTORY = os.path.join(HERE, "..", "data", "membership_history.json")
FREEZE = os.path.join(HERE, "..", "data", "membership_history.freeze.json")
FROZEN_THROUGH = "2026-09-30"
PARTS = ("aliases", "caveats", "symbol_changes", "adjustments_applied")


def frozen_view(history: dict, through: str = FROZEN_THROUGH) -> dict:
    view = {"indices": {}}
    for key in sorted(history["indices"]):
        entry = history["indices"][key]
        view["indices"][key] = {"baseline": entry["baseline"],
                                "changes": [c for c in entry["changes"] if c["date"] <= through]}
    for part in PARTS:
        view[part] = history.get(part)
    return view


def digest(view: dict) -> str:
    return hashlib.sha256(json.dumps(view, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def summary(history: dict, through: str = FROZEN_THROUGH) -> dict:
    out = {}
    for key in sorted(history["indices"]):
        entry = history["indices"][key]
        state = set(entry["baseline"]["symbols"])
        changes = [c for c in entry["changes"] if c["date"] <= through]
        for c in changes:
            state = (state - set(c["removed"])) | set(c["added"])
        out[key] = {"first_date": entry["baseline"]["date"], "changes_through_freeze": len(changes),
                    "members_on_freeze_date": len(state)}
    return out


def check(history: dict, freeze: dict) -> list[str]:
    problems = []
    now = digest(frozen_view(history, freeze["frozen_through"]))
    if now != freeze["sha256"]:
        problems.append(f"the frozen history changed: {now[:12]} now, {freeze['sha256'][:12]} recorded. If the edit is "
                        "intended, re-run G3 to G7 and record it: python freeze_history.py --write --reason '...'")
    log = freeze.get("changelog") or []
    if not log or log[-1]["sha256_after"] != freeze["sha256"]:
        problems.append("the change log does not end at the recorded hash")
    for a, b in zip(log, log[1:]):
        if b["sha256_before"] != a["sha256_after"]:
            problems.append(f"change log is not continuous at {b['date_utc']}")
    return problems


def write(history: dict, freeze: dict | None, reason: str) -> dict:
    new = digest(frozen_view(history))
    log = list((freeze or {}).get("changelog") or [])
    if freeze and freeze["sha256"] == new:
        return freeze
    log.append({"date_utc": datetime.now(timezone.utc).date().isoformat(),
                "sha256_before": freeze["sha256"] if freeze else None, "sha256_after": new, "reason": reason})
    return {"frozen_through": FROZEN_THROUGH, "sha256": new, "indices": summary(history), "changelog": log,
            "note": "Hash covers each index's baseline and changes up to frozen_through, plus aliases, caveats, "
                    "symbol_changes and adjustments_applied. See nse_index_rebuild/freeze_history.py."}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--reason", default="")
    args = ap.parse_args(argv)
    history = json.load(open(HISTORY))
    freeze = json.load(open(FREEZE)) if os.path.exists(FREEZE) else None
    if args.write:
        if not args.reason.strip():
            sys.exit("--write needs --reason")
        out = write(history, freeze, args.reason.strip())
        json.dump(out, open(FREEZE, "w"), indent=2); open(FREEZE, "a").write("\n")
        print(f"frozen through {out['frozen_through']}: {out['sha256'][:12]} ({len(out['changelog'])} log entries)")
        return 0
    if freeze is None:
        print("no freeze record; run with --write --reason")
        return 1
    problems = check(history, freeze)
    for p in problems:
        print("PROBLEM:", p)
    print("frozen history unchanged" if not problems else f"{len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
