#!/usr/bin/env python3
"""Freeze newly closed months into the track record ledger.

Run monthly. Every month it writes is written ONCE: re-running this script,
today or next year, must not change a single number already in the file. That
is the entire contract -- see src/engine/track_record.py for why.

    python scripts/update_track_record.py              # write closed months
    python scripts/update_track_record.py --dry-run    # report, write nothing
    python scripts/update_track_record.py --force      # rewrite history (loud)
    python scripts/update_track_record.py --system nano --extra-prices prices_extra.parquet

--system picks the record: 750 (default, data/track_record.json), nano or
combined (their own ledgers, from October 2026). Each is scored on its own
point-in-time membership (src/engine/systems.py).
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.config import BENCHMARK_SYMBOL  # noqa: E402
from src.engine.backtester import run_backtest  # noqa: E402
from src.engine.parity_audit import compare_monthly_ledger  # noqa: E402
from src.engine.track_record import (  # noqa: E402
    TRACK_RECORD_CONFIG,
    config_fingerprint,
    finalize_months,
    load_ledger,
    months_to_cover,
    save_ledger,
    summary_stats,
)
from src.engine.corporate_actions import load_events  # noqa: E402
from src.engine import systems  # noqa: E402
from src.engine.extra_universe import SYSTEM_750, SYSTEM_NANO, SYSTEMS  # noqa: E402
from src.engine.membership import describe  # noqa: E402
from src.loaders import former_members, nse_prices  # noqa: E402
from src.loaders import extra_universe_loader as xl  # noqa: E402
from src.loaders.indices_loader import fetch_indices_data  # noqa: E402
from src.loaders.price_loader import (  # noqa: E402
    extract_ohlcv,
    fetch_benchmark_history,
    fetch_price_history,
)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--system", default=SYSTEM_750, choices=list(SYSTEMS))
    ap.add_argument("--ledger", default=None,
                    help="defaults to the system's own ledger")
    ap.add_argument("--extra-prices", default=None,
                    help="prices_extra.parquet for Nano Cap stocks (else downloaded)")
    ap.add_argument("--indices", nargs="+", default=["NIFTY TOTAL MARKET"])
    ap.add_argument(
        "--period",
        default="5y",
        help="Price history to fetch. Must cover inception plus a 12-month "
        "formation window before it.",
    )
    ap.add_argument("--prices", choices=["screener", "nse", "yahoo"], default=None,
                    help="price basis: screener (Screener's closes, NSE's where it has none; "
                    "the 750's default), nse (NSE closes as published, data/nse_prices) or "
                    "yahoo (restated adjusted closes; the default for Nano Cap and Combined)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument(
        "--note",
        default="",
        help="Why a --force rebuild was done; stored in the ledger's `rebuilds` log.",
    )
    ap.add_argument(
        "--force",
        action="store_true",
        help="Rewrite months already recorded. This destroys the record's "
        "immutability guarantee; use only for a deliberate rebuild.",
    )
    args = ap.parse_args()

    system = args.system
    ledger_file = args.ledger or str(systems.ledger_path(system))
    start = systems.inception(system)
    print(f"→ system: {system} · ledger {ledger_file} · inception {start}")

    core: list[str] = []
    if system != SYSTEM_NANO:
        print(f"→ universe: {args.indices}")
        idx_info = fetch_indices_data(args.indices)
        core = idx_info["Symbol"].unique().tolist() if not idx_info.empty else []
    extra: list[str] = []
    if system != SYSTEM_750:
        extra = [s for s in xl.members()["Symbol"] if s not in set(core)]
    symbols = core + extra
    if not symbols:
        print("✗ universe is empty; refusing to write a record from no data")
        return 1
    print(f"  {len(symbols)} symbols ({len(core)} in the 750, {len(extra)} Nano Cap)")

    parts = []
    if core:
        parts.append(fetch_price_history(core, period=args.period))
    if extra:
        ep = (pd.read_parquet(args.extra_prices) if args.extra_prices and Path(args.extra_prices).exists()
              else xl.download(extra))
        parts.append(ep.loc[:, [c for c in ep.columns if c[0] in set(extra)]])
    parts = [p for p in parts if p is not None and not p.empty]
    raw = pd.concat(parts, axis=1).sort_index() if parts else pd.DataFrame()
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
    months = months_to_cover(as_of, start)
    print(f"→ data as of {as_of:%d %b %Y}; covering {months} completed months "
          f"back to {start}")
    if months <= 0:
        print("  nothing has closed since inception yet")
        return 0

    # Point-in-time index membership, where we have it. Without this the
    # backtest scores every month against TODAY's constituent list.
    membership = systems.membership_for(system)
    if membership:
        info = describe(membership)
        print(f"→ membership history: {info['first']} → {info['last']}, "
              f"{info['current_size']} constituents, "
              f"{info['total_churn']} additions/removals recorded")
    else:
        print("→ no membership history; months will use the current universe")

    # The index's former members need prices too, or the record is scored
    # against survivors only (data/former_member_prices.parquet, kept by
    # scripts/sync_former_member_prices.py).
    cfg = dict(TRACK_RECORD_CONFIG)
    basis = args.prices or ("screener" if system == SYSTEM_750 else "yahoo")
    actions = load_events()
    if basis in ("screener", "nse"):
        # Screener's closes, as on the live ranking (owner, 2026-10-01); NSE's closes as
        # published, adjusted only for splits, bonuses and demergers, fill what Screener
        # lacks, and Yahoo's frame only what neither has. Yahoo's corporate-action log
        # corrects Yahoo, so it is not applied to these series.
        nse, info = nse_prices.basis_frame(adj_close, membership, months=months,
                                           screener="auto" if basis == "screener" else None)
        if nse is None:
            print(f"✗ price basis unavailable ({info.get('why')}); refusing to freeze "
                  "months on a different basis under the NSE fingerprint (use --prices yahoo)")
            return 1
        if basis == "screener" and info["basis"] != nse_prices.BASIS_SCREENER:
            print("✗ Screener's store is unavailable; refusing to freeze months on another basis "
                  "under the Screener fingerprint (use --prices nse to choose NSE deliberately)")
            return 1
        cfg["prices"] = info["basis"]
        print(f"→ prices: {info['basis']}"
              + (f" ({info.get('share_of_cells_from_screener', 0):.0%} of cells from Screener; NSE only: "
                 f"{len(info.get('base_only_names', []))} names)" if info.get("screener") else "")
              + f"; NSE file {info['symbols_priced']} of {info['symbols_wanted']} "
              f"names, sessions to {info['last_session_on_file']} on file "
              f"(frame to {info['frame_last_session']}); from the other source: "
              f"{', '.join(info['other_source_names'] + info['other_source_history']) or 'none'}")
        # A frozen month needs NSE's own closes through its last session, not the other
        # source's moves carried over a gap: refuse a file that lags it by days.
        if pd.Timestamp(info["last_session_on_file"]) < as_of - pd.Timedelta(days=3):
            print(f"✗ the NSE file ends {info['last_session_on_file']}, behind the price data "
                  f"({as_of:%Y-%m-%d}); run scripts/sync_nse_prices.py --update first")
            return 1
        # The window is counted back from the frame's end, and NSE's file is the
        # earlier to reach a new month: on the first working day Yahoo's cache has no
        # bar yet but NSE's first session of the month is already on R2.
        as_of = pd.Timestamp(nse.index[-1])
        months = months_to_cover(as_of, start)
        print(f"→ NSE sessions through {as_of:%d %b %Y}; covering {months} completed months")
        adj_close, actions = nse, []
    else:
        cfg["prices"] = "yahoo_adjusted"
        print("→ prices: Yahoo adjusted closes (restated)")
    n_before = adj_close.shape[1]
    adj_close = former_members.with_former_members(adj_close, membership)
    unpriceable = [s for s in former_members.unavailable() if s not in adj_close.columns]
    print(f"→ former members priced: {adj_close.shape[1] - n_before} added to the "
          f"{n_before}-stock frame; unpriceable: "
          f"{', '.join(unpriceable) or 'none'}")

    fingerprint = config_fingerprint(**cfg)
    print(f"  config fingerprint: {fingerprint}")

    result = run_backtest(
        f"trackrecord_{system}_{as_of:%Y%m%d}_{months}",
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
        _actions=actions,
    )
    if result is None:
        print("✗ backtest produced no result (insufficient history?)")
        return 1

    stats = result["stats"]
    pit_from = stats.get("pit_from")
    print(f"→ survivorship-free rebalances: {stats.get('pit_periods', 0)} of "
          f"{stats.get('pit_periods', 0) + stats.get('current_universe_periods', 0)}"
          + (f", from {pit_from}" if pit_from else ""))

    ledger = load_ledger(ledger_file, start)
    before = len(ledger.get("months", {}))
    prior_months = dict(ledger.get("months", {}))

    # Read-only comparison of both frozen return series. Drift is diagnostic:
    # stored closed months remain authoritative and are never silently rewritten.
    parity = compare_monthly_ledger(
        ledger, result["equity_curve"], result["benchmark"]
    )
    counts = parity["counts"]
    print(
        "→ frozen-ledger parity: "
        f"{counts['match']} match, {counts['drift']} drift, "
        f"{counts['missing_recomputed_period']} missing periods, "
        f"{counts['not_comparable']} not comparable "
        f"(tolerance ±{parity['tolerance']:.4%})"
    )
    for row in parity["rows"]:
        if row["status"] == "drift":
            series = row.get("drifted_series", [])
            details = ", ".join(
                f"{name} {row[f'{name}_stored']:+.2%} → "
                f"{row[f'{name}_recomputed']:+.2%} "
                f"(Δ {row[f'{name}_drift']:+.2%})"
                for name in series
            )
            print(f"  ! drift {row['month']}: {details} — stored value stands")
        elif row["status"] == "missing_recomputed_period":
            print(
                f"  ! missing recomputed data for {row['month']}: "
                f"{', '.join(row['missing_series'])}"
            )
        elif row["status"] == "not_comparable":
            print(f"  ! {row['month']}: ledger row has no comparable returns")

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

    if args.force and added:
        # A rebuild replaces frozen numbers, so the file says so: when, which
        # months, what they were struck under before, and what they are now.
        replaced = sorted({m.get("config") for m in prior_months.values() if m.get("config")})
        ledger.setdefault("rebuilds", []).append({
            "on": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "months": added,
            "replaced_configs": replaced,
            "config": fingerprint,
            "prices": cfg["prices"],
            "membership": ("point in time" + (f" from {pit_from}" if pit_from else "")),
            "former_members_unpriceable": unpriceable,
            "previous_values": {k: prior_months[k]["strategy"] for k in added if k in prior_months},
            "note": args.note,
        })
    # One basis for the whole file, or none claimed: a ledger that mixes months struck
    # on different bases must not label them all with one.
    configs = {m.get("config") for m in ledger["months"].values()}
    if configs <= {fingerprint}:
        ledger["price_basis"] = cfg["prices"]
    else:
        ledger.pop("price_basis", None)
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

    save_ledger(ledger, ledger_file)
    s = summary_stats(ledger)
    print(f"✓ wrote {ledger_file}: {s['months']} months, "
          f"{s['first']} → {s['last']}, total {s['total_return']:+.2%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
