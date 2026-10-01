#!/usr/bin/env python3
"""Download NSE's daily bundles into a local cache (resumable).

    python scripts/fetch_nse_history.py --since 2024-09-30 --cache data_cache/nse_bundles

A holiday answers 404 and is remembered, so a re-run only fetches what is
missing. Stops if NSE refuses. See src/loaders/nse_history.py.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.loaders.nse_history import fetch_days, weekdays  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--since", default="2024-09-30")
    ap.add_argument("--until", default=None, help="default: today")
    ap.add_argument("--cache", default="data_cache/nse_bundles")
    ap.add_argument("--pause", type=float, default=1.0)
    args = ap.parse_args()
    until = date.fromisoformat(args.until) if args.until else date.today()
    days = weekdays(date.fromisoformat(args.since), until)
    print(f"{len(days)} weekdays from {days[0]} to {days[-1]} -> {args.cache}", flush=True)
    tally = fetch_days(days, Path(args.cache), pause=args.pause, log=lambda m: print(m, flush=True))
    print("done", tally, flush=True)
    return 1 if tally["blocked"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
