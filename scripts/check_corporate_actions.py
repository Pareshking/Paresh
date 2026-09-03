#!/usr/bin/env python3
"""Guard: flag corporate actions sitting in the price history as price moves.

A stock split, bonus issue or demerger can appear in an adjusted price series as
a single session of -50% or -79%. NSE's circuit limits make a move that size
impossible as an actual price move, so anything past the threshold is an action,
not a return -- and a momentum backtest reading it as a return records a
catastrophic loss that never happened.

Findings are appended to data/corporate_actions_log.json, which is append-only:
once a session is flagged it stays on the record with the date it was first
seen. That log is also the beginning of the corporate-actions history a proper
raw-price store would need.

    python scripts/check_corporate_actions.py            # report and log
    python scripts/check_corporate_actions.py --dry-run
    python scripts/check_corporate_actions.py --fail-on-new   # exit 1 on a new find
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.engine.corporate_actions import IMPLAUSIBLE_MOVE, detect, summarise  # noqa: E402
from src.loaders.price_loader import extract_ohlcv  # noqa: E402

LOG_PATH = Path("data/corporate_actions_log.json")


def _load(path: Path) -> dict:
    if not path.exists():
        return {"schema_version": 1, "threshold": IMPLAUSIBLE_MOVE, "events": {}}
    with path.open(encoding="utf-8") as fh:
        log = json.load(fh)
    if "events" not in log:
        raise ValueError(f"{path} is not a corporate-actions log")
    return log


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--log", default=str(LOG_PATH))
    ap.add_argument("--threshold", type=float, default=IMPLAUSIBLE_MOVE)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument(
        "--fail-on-new",
        action="store_true",
        help="Exit non-zero when a session is flagged for the first time, so a "
        "scheduled run surfaces it instead of burying it in a log.",
    )
    args = ap.parse_args()

    from src.core.config import PRICES_FILE

    if not Path(PRICES_FILE).exists():
        print(f"✗ no price cache at {PRICES_FILE}")
        return 1

    adj, *_ = extract_ohlcv(pd.read_parquet(PRICES_FILE))
    if adj.empty:
        print("✗ no adjusted closes to check")
        return 1

    found = detect(adj, threshold=args.threshold)
    info = summarise(found)
    print(
        f"→ scanned {adj.shape[0]} sessions x {adj.shape[1]} symbols "
        f"at +/-{args.threshold:.0%}"
    )

    if found.empty:
        print("✓ no implausible sessions")
        return 0

    log = _load(Path(args.log))
    events = dict(log.get("events", {}))
    new_keys: list[str] = []

    for _, row in found.iterrows():
        key = f"{row['Date']:%Y-%m-%d}:{row['Symbol']}"
        if key in events:
            continue
        new_keys.append(key)
        events[key] = {
            "date": f"{row['Date']:%Y-%m-%d}",
            "symbol": row["Symbol"],
            "move": round(float(row["Move %"]), 6),
            "ratio": round(float(row["Ratio"]), 6),
            "prev_close": round(float(row["Prev Close"]), 4),
            "close": round(float(row["Close"]), 4),
            "looks_like": row["Looks Like"],
            "kind": row["Kind"],
            "first_seen": date.today().isoformat(),
        }

    print(
        f"  {info['total']} flagged ({info['split_like']} split/bonus-like, "
        f"{info['unclassified']} unclassified), {len(new_keys)} new"
    )
    for _, row in found.iterrows():
        mark = "NEW " if f"{row['Date']:%Y-%m-%d}:{row['Symbol']}" in new_keys else "    "
        print(
            f"  {mark}{row['Date']:%Y-%m-%d}  {row['Symbol']:<12} "
            f"{row['Move %']:+7.1%}  ratio {row['Ratio']:.4f}  {row['Looks Like']}"
        )

    if info["unclassified"]:
        print(
            "\n  Unclassified sessions match no standard split ratio. The usual "
            "cause is a demerger or spin-off, which yfinance does NOT adjust "
            "for: the parent's price legitimately falls, but shareholders "
            "received stock in the new entity, so no economic loss occurred. "
            "The backtest still reads it as a loss."
        )

    log["events"] = dict(sorted(events.items()))
    log["threshold"] = args.threshold
    log["last_checked"] = date.today().isoformat()

    if args.dry_run:
        print("→ dry run; log not written")
    else:
        Path(args.log).parent.mkdir(parents=True, exist_ok=True)
        with Path(args.log).open("w", encoding="utf-8") as fh:
            json.dump(log, fh, indent=2)
            fh.write("\n")
        print(f"✓ wrote {args.log} ({len(events)} events on record)")

    if new_keys and args.fail_on_new:
        print(f"::warning::{len(new_keys)} newly flagged session(s)")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
