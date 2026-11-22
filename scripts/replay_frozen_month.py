#!/usr/bin/env python3
"""Replay a frozen month from its evidence bundle and check it (S185).

    python scripts/replay_frozen_month.py --system 750 --month 2026-11
    python scripts/replay_frozen_month.py --bundle freeze_750_2026-11.zip

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


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--system", help="ledger key: 750, nano, combined, 1000, shadow_<book>")
    ap.add_argument("--month", help="YYYY-MM")
    ap.add_argument("--bundle", type=Path, help="a local bundle instead of R2's")
    args = ap.parse_args()
    if args.bundle:
        data = args.bundle.read_bytes()
    elif args.system and args.month:
        data = freeze_bundle.fetch(args.system, args.month)
    else:
        ap.error("give --bundle, or --system and --month")
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


if __name__ == "__main__":
    raise SystemExit(main())
