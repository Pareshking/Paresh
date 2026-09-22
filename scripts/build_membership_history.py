#!/usr/bin/env python3
"""Build point-in-time index membership histories from committed NSE snapshots.

The daily sync commits data/indices/*.csv. This module turns those snapshots
into append-only baseline + change histories. It supports every tracked
research index while preserving the legacy NIFTY Total Market output used by
existing V1 consumers.

No current universe is inferred and no symbol alias is invented. DUMMY and
other non-tradeable placeholders are filtered through the same central
predicate used by the live index loader.
"""

from __future__ import annotations

import argparse
import csv
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.market_time import ist_today  # noqa: E402
from src.engine.membership import (  # noqa: E402
    coverage,
    empty_history,
    load_history,
    record_snapshot,
    save_history,
)

ROOT = Path(__file__).resolve().parents[1]

TRACKED_INDEX_PATHS = {
    "nifty50": "data/indices/ind_nifty50list.csv",
    "nifty_next50": "data/indices/ind_niftynext50list.csv",
    "nifty_midcap150": "data/indices/ind_niftymidcap150list.csv",
    "nifty_smallcap250": "data/indices/ind_niftysmallcap250list.csv",
    "nifty_microcap250": "data/indices/ind_niftymicrocap250_list.csv",
    "nifty_total_market": "data/indices/ind_niftytotalmarket_list.csv",
}

# The five index universe histories requested for research/backtesting.
RESEARCH_INDEXES = tuple(
    name for name in TRACKED_INDEX_PATHS if name != "nifty_total_market"
)


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], capture_output=True, text=True, check=True, cwd=ROOT
    ).stdout


def _symbols_at(commit: str, path: str) -> list[str]:
    try:
        blob = _git("show", f"{commit}:{path}")
    except subprocess.CalledProcessError:
        return []
    rows = list(csv.DictReader(blob.splitlines()))
    if not rows:
        return []
    key = next(
        (k for k in rows[0].keys() if k.strip().lower() == "symbol"), None
    )
    if key is None:
        return []
    return [row[key] for row in rows if row.get(key)]


def build_history(
    path: str,
    history_path: str | Path,
    *,
    include_working_tree: bool = True,
) -> dict:
    """Reconstruct/append one index's membership history from Git snapshots."""
    log = _git(
        "log",
        "--follow",
        "--reverse",
        "--date=short",
        "--format=%H %ad",
        "--",
        path,
    ).strip()
    if not log:
        raise RuntimeError(f"no commit history for {path}")

    history_file = Path(history_path)
    history = load_history(history_file) if history_file.exists() else empty_history()
    history["index"] = index_name

    added = 0
    skipped = 0
    for line in log.splitlines():
        commit, day = line.split(None, 1)
        symbols = _symbols_at(commit, path)
        if not symbols:
            continue
        try:
            history, changed = record_snapshot(history, day, symbols)
        except ValueError:
            skipped += 1
            continue
        if changed:
            added += 1

    if include_working_tree:
        tree = ROOT / path
        if tree.exists():
            with tree.open(encoding="utf-8-sig") as fh:
                rows = list(csv.DictReader(fh))
            key = next(
                (k for k in (rows[0].keys() if rows else []) if k.strip().lower() == "symbol"),
                None,
            )
            if key:
                try:
                    history, changed = record_snapshot(
                        history,
                        ist_today(),
                        [row[key] for row in rows if row.get(key)],
                    )
                except ValueError:
                    skipped += 1
                else:
                    if changed:
                        added += 1

    first, last = coverage(history)
    if first is None:
        raise RuntimeError(f"no usable membership snapshots for {path}")

    if added:
        save_history(history, history_file)

    return {
        "index": history["index"],
        "path": path,
        "history_path": str(history_file),
        "first": first.isoformat(),
        "last": last.isoformat(),
        "snapshots_with_changes": len(history.get("changes") or []),
        "added_snapshots": added,
        "skipped_snapshots": skipped,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--history", default="data/membership_history.json")
    ap.add_argument("--path", default=TRACKED_INDEX_PATHS["nifty_total_market"])
    ap.add_argument("--all-research-indices", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if args.all_research_indices:
        specs = [
            (name, TRACKED_INDEX_PATHS[name])
            for name in RESEARCH_INDEXES
        ]
    else:
        specs = [("nifty_total_market", args.path)]

    for name, path in specs:
        target = (
            Path(args.history)
            if not args.all_research_indices
            else Path("data") / "membership" / f"{name}.json"
        )
        summary = build_history(
            path,
            target,
            index_name=name,
            include_working_tree=not args.dry_run,
            write=not args.dry_run,
        )
        )
        print(
            f"{name}: {summary['first']} -> {summary['last']} "
            f"changes={summary['snapshots_with_changes']} "
            f"added={summary['added_snapshots']}"
        )

    if args.dry_run:
        print("dry run; no files written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
