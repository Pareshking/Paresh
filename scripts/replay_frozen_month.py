#!/usr/bin/env python3
"""Replay a frozen month from its evidence bundle and check it (S185).

    python scripts/replay_frozen_month.py --system 750 --month 2026-11
    python scripts/replay_frozen_month.py --bundle freeze_750_2026-11.zip
    python scripts/replay_frozen_month.py --frozen-since <git ref>

`--frozen-since` replays every month that gained a `freeze_revision` in any
data/track_record*.json since that commit (the monthly workflow passes the
commit it checked out, so each run checks exactly the months it froze).

Reads the month's bundle (R2's current revision of record/freezes/<system> for
that month, or a local file), re-runs run_backtest on the bundle's own inputs and
checks, against the frozen ledger row and data/record_books.json:

  1. the bundle's members match their sha256 (read() refuses otherwise);
  2. the bundle is the revision the ledger row names (freeze_revision);
  3. the replay's strategy and benchmark returns equal the bundle's to 1e-12,
     and the ledger's rounded values exactly;
  4. the replay's book equals the stored book, name for name.

Exits 0 when every check holds, 1 otherwise. Reads only; writes nothing.
`--system` takes the ledger's key: 750, nano, combined, 1000, shadow, shadow_high90...
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.engine import freeze_bundle  # noqa: E402

TOL = 1e-12


def _ledger_path(system: str) -> Path:
    return ROOT / "data" / ("track_record.json" if system == "750" else f"track_record_{system}.json")


def check(data: bytes, *, ledger: dict | None, books: dict) -> list[str]:
    """The failed checks (empty: the month replays exactly)."""
    bundle = freeze_bundle.read(data)
    meta = bundle["meta"]
    system, month = meta["system"], meta["month"]
    failures = []
    revision = hashlib.sha256(data).hexdigest()
    row = (ledger or {}).get("months", {}).get(month)
    if row is None:
        failures.append(f"{system} {month}: no ledger row")
    elif row.get("freeze_revision") not in (None, revision):
        failures.append(f"{system} {month}: ledger names revision {row.get('freeze_revision')}, "
                        f"bundle is {revision}")
    got = freeze_bundle.replay(bundle)
    want = meta["results"]
    for name in ("strategy", "benchmark"):
        a, b = got[name], want[name]
        if (a is None) != (b is None) or (a is not None and abs(a - b) > TOL):
            failures.append(f"{system} {month}: {name} replays {a!r}, bundle holds {b!r}")
    if row is not None:
        for name in ("strategy", "benchmark", "alpha"):
            if got["ledger"][name] != row.get(name):
                failures.append(f"{system} {month}: ledger {name} {row.get(name)!r}, "
                                f"replay {got['ledger'][name]!r}")
    stored = books.get(system, {}).get(month, {}).get("book", meta["book"])
    diff = freeze_bundle.book_differences(stored, got["book"])
    if diff:
        failures.append(f"{system} {month}: book differs {json.dumps(diff)}")
    return failures


def _frozen(ledger: dict | None) -> set[str]:
    return {m for m, row in (ledger or {}).get("months", {}).items() if row.get("freeze_revision")}


def frozen_since(ref: str, root: Path = ROOT) -> list[tuple[str, str]]:
    """(system, month) for each month frozen with a bundle in the working ledgers but not at `ref`."""
    known = subprocess.run(["git", "cat-file", "-e", f"{ref}^{{commit}}"], cwd=root,
                           capture_output=True)
    if known.returncode != 0:  # else every ledger would look new and every month replay
        raise SystemExit(f"Unknown commit {ref!r}: fetch it first.")
    out = []
    for path in sorted((root / "data").glob("track_record*.json")):
        now = json.loads(path.read_text(encoding="utf-8"))
        rel = path.relative_to(root).as_posix()
        shown = subprocess.run(["git", "show", f"{ref}:{rel}"], cwd=root,
                               capture_output=True, text=True)
        before = json.loads(shown.stdout) if shown.returncode == 0 else None
        system = freeze_bundle.system_key(path)
        out += [(system, m) for m in sorted(_frozen(now) - _frozen(before))]
    return out


def _report(data: bytes) -> int:
    system = freeze_bundle.read(data)["meta"]["system"]
    path = _ledger_path(system)
    ledger = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
    failures = check(data, ledger=ledger, books=freeze_bundle.load_books())
    for line in failures:
        print(f"FAIL  {line}")
    if failures:
        return 1
    meta = freeze_bundle.read(data)["meta"]
    print(f"PASS  {meta['system']} {meta['month']}: strategy {meta['results']['strategy']:+.6%}, "
          f"book of {sum(len(v) for v in freeze_bundle.holdings(meta['book']).values())} holdings "
          "replays exactly from its bundle")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--system", help="ledger key: 750, nano, combined, 1000, shadow_<book>")
    ap.add_argument("--month", help="YYYY-MM")
    ap.add_argument("--bundle", type=Path, help="a local bundle instead of R2's")
    ap.add_argument("--frozen-since", metavar="REF",
                    help="replay every month frozen since this git commit")
    args = ap.parse_args()
    if args.frozen_since:
        months = frozen_since(args.frozen_since)
        if not months:
            print(f"No month frozen since {args.frozen_since}; nothing to replay.")
            return 0
        worst = 0
        for system, month in months:
            try:
                worst = max(worst, _report(freeze_bundle.fetch(system, month)))
            except Exception as exc:  # a missing or unreadable bundle is a failure, named
                print(f"FAIL  {system} {month}: bundle not read from R2 ({exc})")
                worst = 1
        print(f"Replayed {len(months)} month(s): {'all pass' if worst == 0 else 'FAILURES above'}")
        return worst
    if args.bundle:
        data = args.bundle.read_bytes()
    elif args.system and args.month:
        data = freeze_bundle.fetch(args.system, args.month)
    else:
        ap.error("give --bundle, --system and --month, or --frozen-since")
    return _report(data)

if __name__ == "__main__":
    raise SystemExit(main())
