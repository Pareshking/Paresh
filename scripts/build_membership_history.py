#!/usr/bin/env python3
"""Extract point-in-time index membership from git history.

The daily sync commits data/indices/*.csv on every run, so the repository has
been recording who was in the index all along -- nobody was reading it. This
walks those commits oldest-first and folds each into data/membership_history.json.

Run it once to bootstrap, then daily to append. It is append-only and
idempotent: a snapshot on or before the last recorded date is skipped, and a day
whose membership is unchanged writes nothing.

    python scripts/build_membership_history.py            # bootstrap + append
    python scripts/build_membership_history.py --dry-run
"""

from __future__ import annotations

import argparse
import csv
import io
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.engine.membership import (  # noqa: E402
    DEFAULT_INDEX,
    HISTORY_PATH,
    coverage,
    describe,
    load_history,
    record_snapshot,
    save_history,
)

TRACKED = "data/indices/ind_niftytotalmarket_list.csv"


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], capture_output=True, text=True, check=True
    ).stdout


def _symbols_at(commit: str, path: str) -> list[str]:
    try:
        blob = _git("show", f"{commit}:{path}")
    except subprocess.CalledProcessError:
        return []
    rows = list(csv.DictReader(io.StringIO(blob)))
    key = next(
        (k for k in (rows[0].keys() if rows else []) if k.strip().lower() == "symbol"),
        None,
    )
    if key is None:
        return []
    return [r[key] for r in rows if r.get(key)]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--history", default=str(HISTORY_PATH))
    ap.add_argument("--path", default=TRACKED)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    log = _git(
        "log", "--follow", "--reverse", "--date=short", "--format=%H %ad", "--", args.path
    ).strip()
    if not log:
        print(f"✗ no commit history for {args.path}")
        return 1

    commits = [line.split(None, 1) for line in log.splitlines()]
    print(f"→ {len(commits)} commits touching {args.path}")

    history = load_history(args.history)
    _, last = coverage(history)
    if last is not None:
        print(f"  history already covers through {last}")

    added = 0
    skipped = 0
    for commit, day in commits:
        symbols = _symbols_at(commit, args.path)
        if not symbols:
            print(f"  ! {day} {commit[:8]}: unreadable, skipped")
            continue
        try:
            history, changed = record_snapshot(history, day, symbols)
        except ValueError:
            # Already covered, or out of order. Append-only by design.
            skipped += 1
            continue
        if changed:
            added += 1
            print(f"  + {day} {commit[:8]}: recorded")

    # The working tree is newer than the newest commit whenever the sync has run
    # but not yet committed. Fold it in so a same-day run is not a day behind.
    tree = Path(args.path)
    if tree.exists():
        rows = list(csv.DictReader(tree.open(encoding="utf-8-sig")))
        key = next(
            (k for k in (rows[0].keys() if rows else []) if k.strip().lower() == "symbol"),
            None,
        )
        if key:
            today = _git("log", "-1", "--date=short", "--format=%ad").strip() or None
            from datetime import date as _date
            try:
                history, changed = record_snapshot(
                    history, _date.today(), [r[key] for r in rows if r.get(key)]
                )
                if changed:
                    added += 1
                    print(f"  + {_date.today()} (working tree): recorded")
            except ValueError:
                skipped += 1

    info = describe(history)
    print(
        f"→ {info['index']}: {info['first']} → {info['last']}, "
        f"{info['current_size']} constituents, "
        f"{info['snapshots_with_changes']} change events, "
        f"{info['total_churn']} total additions/removals"
    )
    print(f"  {added} snapshot(s) recorded, {skipped} already covered")

    if args.dry_run:
        print("→ dry run; nothing written")
        return 0
    if added == 0:
        print("→ nothing new; file untouched")
        return 0

    save_history(history, args.history)
    print(f"✓ wrote {args.history}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
