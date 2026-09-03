#!/usr/bin/env python3
"""Freeze newly closed months into the track record ledger.

Run monthly. Every month it writes is written ONCE: re-running this script,
today or next year, must not change a single number already in the file. That
is the entire contract -- see src/engine/track_record.py for why.

    python scripts/update_track_record.py              # write closed months
    python scripts/update_track_record.py --dry-run    # report, write nothing
    python scripts/update_track_record.py --force      # rewrite history (loud)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.config import BENCHMARK_SYMBOL  # noqa: E402
from src.engine.backtester import run_backtest  # noqa: E402
from src.engine.track_record import (  # noqa: E402
    INCEPTION,
    LEDGER_PATH,
    TRACK_RECORD_CONFIG,
    config_fingerprint,
    drift_report,
    finalize_months,
    load_ledger,
    months_to_cover,
    save_ledger,
    summary_stats,
)
from src.engine.corporate_actions import load_events  # noqa: E402
from src.engine.membership import HISTORY_PATH, describe, load_history  # noqa: E402
from src.loaders.indices_loader import fetch_indices_data  # noqa: E402
from src.loaders.price_loader import (  # noqa: E402
    extract_ohlcv,
    fetch_benchmark_history,
    fetch_price_history,
)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ledger", default=str(LEDGER_PATH))
    ap.add_argument("--indices", nargs="+", default=["NIFTY TOTAL MARKET"])
    ap.add_argument(
        "--period",
        default="5y",
        help="Price history to fetch. Must cover inception plus a 12-month "
        "formation window before it.",
    )
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument(
        "--force",
        action="store_true",
        help="Rewrite months already recorded. This destroys the record's "
        "immutability guarantee; use only for a deliberate rebuild.",
    )
    args = ap.parse_args()

    print(f"→ universe: {args.indices}")
    idx_info = fetch_indices_data(args.indices)
    if idx_info.empty:
        print("✗ universe is empty; refusing to write a record from no data")
        return 1
    symbols = idx_info["Symbol"].unique().tolist()
    print(f"  {len(symbols)} symbols")

    raw = fetch_price_history(symbols, period=args.period)
    if raw.empty:
        print("✗ no price history")
        return 1
    adj_close, *_ = extract_ohlcv(raw, symbols)
    if adj_close.empty:
        print("✗ no adjusted closes")
        return 1

    benchmark = fetch_benchmark_history(period=args.period)
    if benchmark.empty:
        print(f"✗ benchmark {BENCHMARK_SYMBOL} unavailable; refusing to record "
              "a strategy return with no benchmark beside it")
        return 1

    as_of = pd.Timestamp(adj_close.index[-1])
    months = months_to_cover(as_of)
    print(f"→ data as of {as_of:%d %b %Y}; covering {months} completed months "
          f"back to {INCEPTION}")
    if months <= 0:
        print("  nothing has closed since inception yet")
        return 0

    # Point-in-time index membership, where we have it. Without this the
    # backtest scores every month against TODAY's constituent list.
    membership = None
    try:
        membership = load_history(HISTORY_PATH)
        if membership.get("baseline"):
            info = describe(membership)
            print(f"→ membership history: {info['first']} → {info['last']}, "
                  f"{info['current_size']} constituents, "
                  f"{info['total_churn']} additions/removals recorded")
        else:
            membership = None
            print("→ no membership history; months will use the current universe")
    except (ValueError, OSError) as exc:
        print(f"  ! membership history unreadable ({exc}); using current universe")
        membership = None

    cfg = dict(TRACK_RECORD_CONFIG)
    fingerprint = config_fingerprint(**cfg)
    print(f"  config fingerprint: {fingerprint}")

    result = run_backtest(
        f"trackrecord_{as_of:%Y%m%d}_{months}",
        adj_close,
        top_n=cfg["top_n"],
        rebal_freq=cfg["rebal_freq"],
        ema_period=cfg["ema_period"],
        high_pct=cfg["high_pct"],
        weight_method=cfg["weight_method"],
        config_weights=cfg["config_weights"],
        cost_bps=cfg["cost_bps"],
        buffer_n=cfg["buffer_n"],
        _benchmark_close=benchmark,
        backtest_months=months,
        _membership=membership,
        _actions=load_events(),
    )
    if result is None:
        print("✗ backtest produced no result (insufficient history?)")
        return 1

    stats = result["stats"]
    pit_from = stats.get("pit_from")
    print(f"→ survivorship-free rebalances: {stats.get('pit_periods', 0)} of "
          f"{stats.get('pit_periods', 0) + stats.get('current_universe_periods', 0)}"
          + (f", from {pit_from}" if pit_from else ""))

    ledger = load_ledger(args.ledger)
    before = len(ledger.get("months", {}))

    for row in drift_report(ledger, result["equity_curve"]):
        print(f"  ! drift {row['month']}: stored {row['stored']:+.2%} vs "
              f"recomputed {row['recomputed']:+.2%} — stored value stands")

    ledger, added, skipped = finalize_months(
        ledger,
        result["equity_curve"],
        result["benchmark"],
        fingerprint=fingerprint,
        as_of=as_of,
        data_as_of=as_of,
        pit_from=pit_from,
        force=args.force,
    )

    print(f"→ {before} months on file; {len(added)} added, {len(skipped)} "
          f"already frozen")
    for key in added:
        e = ledger["months"][key]
        b = e["benchmark"]
        print(f"  + {key}  strategy {e['strategy']:+.2%}"
              + (f"  bench {b:+.2%}  alpha {e['alpha']:+.2%}" if b is not None else ""))

    if args.dry_run:
        print("→ dry run; nothing written")
        return 0
    if not added and not args.force:
        print("→ no new closed months; file untouched")
        return 0

    save_ledger(ledger, args.ledger)
    s = summary_stats(ledger)
    print(f"✓ wrote {args.ledger}: {s['months']} months, "
          f"{s['first']} → {s['last']}, total {s['total_return']:+.2%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
