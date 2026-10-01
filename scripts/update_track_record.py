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
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.config import BENCHMARK_SYMBOL  # noqa: E402
from src.engine.backtester import run_backtest  # noqa: E402
from src.engine.actions import plan_rebalance  # noqa: E402
from src.engine.pipeline import price_fingerprint, ranking_as_of  # noqa: E402
from src.loaders import ranking_store  # noqa: E402
from src.ui.canonical_book import current_book  # noqa: E402
from src.ui.views.actions_view import next_rebalance, rebalance_dates_for_view  # noqa: E402
from src.engine.parity_audit import compare_monthly_ledger  # noqa: E402
from src.engine.track_record import (  # noqa: E402
    TRACK_RECORD_CONFIG,
    calendar_month_returns,
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

def _json_safe(value):
    """Convert pandas/numpy audit output to strict JSON primitives."""
    if value is None or value is pd.NA or value is pd.NaT:
        return None
    if isinstance(value, (pd.Timestamp, pd.Period)):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, np.generic):
        return _json_safe(value.item())
    if isinstance(value, float) and not np.isfinite(value):
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _frame_records(frame: pd.DataFrame) -> list[dict]:
    """Serialize a frame while preserving date fields and representing NaN as null."""
    return json.loads(frame.to_json(orient="records", date_format="iso", double_precision=15))


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
        "--report-json",
        default=None,
        help="Write a machine-readable, read-only replay/ledger parity snapshot.",
    )
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
    # Preserve the raw acquisition frame: record_run() must receive the same
    # input as the Portfolio/Actions/Backtest adapters and build its canonical
    # NSE/Screener basis itself. The updater's replay below is compared against it.
    raw_adj_close = adj_close.copy()
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
        stateful_history=True,
        history_start=start.start_time,
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

    if args.report_json:
        # Compare the updater's replay against the actual canonical adapter used
        # by Portfolio, Actions and Backtest. Both receive the same raw acquired
        # prices; current_book/record_run applies the canonical price/membership
        # path independently rather than trusting the updater's prepared frame.
        canonical_book, canonical_result = current_book(raw_adj_close, benchmark, system)
        replay_book = result.get("live_book")
        required = [
            "Symbol", "Entry Date", "Entry Price", "Price Now", "Weight %",
            "Rank at Entry", "Rank at Rebalance",
        ]
        book_parity = {
            "exact_match": False,
            "missing_from_replay": [],
            "additional_in_replay": [],
            "field_mismatches": {},
            "replay_weight_sum_pct": None,
            "canonical_weight_sum_pct": None,
        }
        if isinstance(replay_book, pd.DataFrame) and not replay_book.empty and not canonical_book.empty:
            left = replay_book.copy()
            right = canonical_book.copy()
            left["Symbol"] = left["Symbol"].astype(str)
            right["Symbol"] = right["Symbol"].astype(str)
            ls, rs = set(left["Symbol"]), set(right["Symbol"])
            book_parity["missing_from_replay"] = sorted(rs - ls)
            book_parity["additional_in_replay"] = sorted(ls - rs)
            li = left.drop_duplicates("Symbol").set_index("Symbol").sort_index()
            ri = right.drop_duplicates("Symbol").set_index("Symbol").sort_index()
            common = sorted(set(li.index) & set(ri.index))
            for col in required:
                if col == "Symbol" or col not in li.columns or col not in ri.columns:
                    continue
                if col in {"Entry Price", "Price Now", "Weight %", "Rank at Entry", "Rank at Rebalance"}:
                    lv = pd.to_numeric(li.loc[common, col], errors="coerce")
                    rv = pd.to_numeric(ri.loc[common, col], errors="coerce")
                    diff = (lv - rv).abs()
                    mismatches = diff.gt(1e-8) | (lv.isna() != rv.isna())
                    book_parity["field_mismatches"][col] = {
                        "count": int(mismatches.sum()),
                        "max_abs_difference": float(diff.max()) if diff.notna().any() else None,
                    }
                elif col == "Entry Date":
                    lv = pd.to_datetime(li.loc[common, col], errors="coerce").dt.normalize()
                    rv = pd.to_datetime(ri.loc[common, col], errors="coerce").dt.normalize()
                    book_parity["field_mismatches"][col] = {
                        "count": int(((lv != rv) | (lv.isna() != rv.isna())).sum()),
                        "max_abs_difference": None,
                    }
                else:
                    lv = li.loc[common, col].astype(str).replace("NaT", "")
                    rv = ri.loc[common, col].astype(str).replace("NaT", "")
                    book_parity["field_mismatches"][col] = {
                        "count": int((lv != rv).sum()),
                        "max_abs_difference": None,
                    }
            book_parity["replay_weight_sum_pct"] = float(pd.to_numeric(left.get("Weight %"), errors="coerce").sum())
            book_parity["canonical_weight_sum_pct"] = float(pd.to_numeric(right.get("Weight %"), errors="coerce").sum())
            book_parity["exact_match"] = (
                not book_parity["missing_from_replay"]
                and not book_parity["additional_in_replay"]
                and all(v["count"] == 0 for v in book_parity["field_mismatches"].values())
            )
        else:
            book_parity["error"] = "Replay or canonical current book is empty."

        snap_frame, snap_meta = ranking_store.fetch_snapshot(system=system)
        snap_columns = [
            c for c in (
                "Symbol", "Rank", "CMP", "Price", "Industry", "Company Name",
                "1M Return", "3M Return", "6M Return", "12M Return",
            ) if isinstance(snap_frame, pd.DataFrame) and c in snap_frame.columns
        ]
        snap_symbols = (
            sorted(snap_frame["Symbol"].astype(str).unique().tolist())
            if isinstance(snap_frame, pd.DataFrame) and "Symbol" in snap_frame.columns
            else []
        )
        membership_summary = describe(membership) if membership else {}
        ledger_months = ledger.get("months", {})
        strategy_monthly = calendar_month_returns(result["equity_curve"])
        benchmark_monthly = calendar_month_returns(result["benchmark"])
        curve_index = result["equity_curve"].index.union(result["benchmark"].index).sort_values()

        rank_as_of = ranking_as_of(raw_adj_close)
        if rank_as_of is None:
            rank_as_of = pd.Timestamp(
                (snap_meta or {}).get("price_as_of")
                or (snap_meta or {}).get("as_of")
                or raw_adj_close.index[-1]
            )
        else:
            rank_as_of = pd.Timestamp(rank_as_of)
        canonical_live_meta = (canonical_result or {}).get("live_meta") or {}
        book_as_of = pd.Timestamp(canonical_live_meta.get("as_of") or as_of)
        legacy_check, legacy_fill = next_rebalance(rank_as_of)
        corrected_basis, corrected_check, corrected_fill = rebalance_dates_for_view(
            rank_as_of, book_as_of, model_book=True
        )
        current_changes = (canonical_result or {}).get("month_changes")
        def _change_symbols(action: str) -> list[str]:
            if not isinstance(current_changes, pd.DataFrame) or current_changes.empty:
                return []
            if "Action" not in current_changes.columns or "Symbol" not in current_changes.columns:
                return []
            return sorted(
                current_changes.loc[
                    current_changes["Action"].eq(action), "Symbol"
                ].astype(str).tolist()
            )

        actions_alignment = {
            "ranking_as_of": str(rank_as_of.date()),
            "canonical_book_as_of": str(book_as_of.date()),
            "legacy_preview_check_date": str(legacy_check.date()),
            "legacy_preview_fill_date": str(legacy_fill.date()),
            "corrected_preview_check_date": str(corrected_check.date()),
            "corrected_preview_fill_date": str(corrected_fill.date()),
            "legacy_fill_already_reflected_in_book": (
                canonical_live_meta.get("fill_date") is not None
                and pd.Timestamp(canonical_live_meta["fill_date"]).normalize()
                == legacy_fill.normalize()
            ),
            "canonical_fill_date": (
                str(pd.Timestamp(canonical_live_meta["fill_date"]).date())
                if canonical_live_meta.get("fill_date") is not None else None
            ),
            "canonical_fill_orders": {
                "buys": _change_symbols("🟢 BOUGHT"),
                "sells": _change_symbols("🔴 SOLD"),
                "holds": _change_symbols("⚪ HELD"),
            },
            "next_preview": None,
            "note": (
                "The preview is for the next scheduled rebalance and uses the last "
                "published ranking snapshot; its order sets are not expected to equal "
                "the already-executed canonical fill."
            ),
        }
        if (
            isinstance(snap_frame, pd.DataFrame) and not snap_frame.empty
            and isinstance(canonical_book, pd.DataFrame) and not canonical_book.empty
        ):
            actions_plan = plan_rebalance(
                snap_frame,
                canonical_book["Symbol"].astype(str).tolist(),
                top_n=int(cfg["top_n"]),
                buffer_n=int(cfg["buffer_n"]),
                stock_cap=0.05,
                sector_cap=0.30,
            )
            actions_alignment["next_preview"] = {
                "buys": sorted(map(str, actions_plan.buys)),
                "sells": sorted(map(str, actions_plan.sells)),
                "holds": sorted(map(str, actions_plan.holds)),
                "target_weights_pct": {
                    str(k): float(v) * 100.0
                    for k, v in actions_plan.weights.items()
                },
                "turnover": float(actions_plan.turnover),
                "next_in_line": list(map(str, actions_plan.next_in_line)),
            }

        report = {
            "schema_version": 1,
            "system": system,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "baseline": {
                "inception": str(start),
                "data_as_of": str(pd.Timestamp(as_of).date()),
                "raw_price_start": str(pd.Timestamp(raw_adj_close.index[0]).date()),
                "raw_price_end": str(pd.Timestamp(raw_adj_close.index[-1]).date()),
                "raw_price_rows": int(len(raw_adj_close.index)),
                "raw_price_symbols": int(len(raw_adj_close.columns)),
                "canonical_price_start": str(pd.Timestamp(adj_close.index[0]).date()),
                "canonical_price_end": str(pd.Timestamp(adj_close.index[-1]).date()),
                "price_basis": cfg["prices"],
                "config_fingerprint": fingerprint,
                "price_fingerprint": price_fingerprint(adj_close),
                "symbol_fingerprint": hashlib.sha256(
                    "\n".join(sorted(map(str, adj_close.columns))).encode("utf-8")
                ).hexdigest(),
                "actions_digest": ranking_store.actions_digest(actions),
                "price_rows": int(len(adj_close.index)),
                "price_symbols": int(len(adj_close.columns)),
                "price_start": str(pd.Timestamp(adj_close.index[0]).date()),
                "price_end": str(pd.Timestamp(adj_close.index[-1]).date()),
                "membership": membership_summary,
                "ranking_snapshot": {
                    "available": isinstance(snap_frame, pd.DataFrame) and not snap_frame.empty,
                    "rows": int(len(snap_frame)) if isinstance(snap_frame, pd.DataFrame) else 0,
                    "symbols": snap_symbols,
                    "metadata": snap_meta,
                    "selected_columns": snap_columns,
                    "rows_data": (
                        json.loads(snap_frame[snap_columns].to_json(
                            orient="records", date_format="iso", double_precision=15
                        )) if snap_columns else []
                    ),
                },
            },
            "ledger": {
                "month_count": len(ledger_months),
                "first_month": min(ledger_months) if ledger_months else None,
                "last_month": max(ledger_months) if ledger_months else None,
                "months": ledger_months,
            },
            "monthly_parity": parity,
            "current_book_parity": book_parity,
            "actions_plan_alignment": actions_alignment,
            "replay": {
                "strategy_monthly_returns": {str(k): float(v) for k, v in strategy_monthly.items()},
                "benchmark_monthly_returns": {str(k): float(v) for k, v in benchmark_monthly.items()},
                "live_book": json.loads(replay_book.to_json(orient="records", date_format="iso", double_precision=15))
                    if isinstance(replay_book, pd.DataFrame) else [],
                "canonical_book": json.loads(canonical_book.to_json(orient="records", date_format="iso", double_precision=15))
                    if isinstance(canonical_book, pd.DataFrame) else [],
                "tradebook": json.loads(result["tradebook"].to_json(orient="records", date_format="iso", double_precision=15))
                    if isinstance(result.get("tradebook"), pd.DataFrame) else [],
                "closed_trades": json.loads(result["closed_trades"].to_json(orient="records", date_format="iso", double_precision=15))
                    if isinstance(result.get("closed_trades"), pd.DataFrame) else [],
                "equity_curve": [
                    {
                        "date": str(pd.Timestamp(d).date()),
                        "strategy_equity": (
                            float(result["equity_curve"].loc[d])
                            if d in result["equity_curve"].index else None
                        ),
                        "benchmark_equity": (
                            float(result["benchmark"].loc[d])
                            if d in result["benchmark"].index else None
                        ),
                    } for d in curve_index
                ],
                "canonical_live_meta": (canonical_result or {}).get("live_meta", {}),
            },
        }
        args_path = Path(args.report_json)
        args_path.parent.mkdir(parents=True, exist_ok=True)
        args_path.write_text(
            json.dumps(_json_safe(report), indent=2, allow_nan=False),
            encoding="utf-8",
        )
        print(
            "→ canonical current-book parity: "
            + json.dumps(_json_safe(book_parity), sort_keys=True, allow_nan=False)
        )
        print(
            "→ ranking snapshot baseline: "
            + json.dumps(_json_safe(report["baseline"]["ranking_snapshot"]), sort_keys=True, allow_nan=False)
        )
        print(
            "→ Actions date/order alignment: "
            + json.dumps(_json_safe(actions_alignment), sort_keys=True, allow_nan=False)
        )
        display_cols = [
            c for c in ("Symbol", "Entry Date", "Entry Price", "Price Now", "Weight %",
                        "Rank at Entry", "Rank at Rebalance")
            if isinstance(canonical_book, pd.DataFrame) and c in canonical_book.columns
        ]
        print(
            "→ canonical current book: "
            + json.dumps(_json_safe(canonical_book[display_cols].to_dict("records")), allow_nan=False)
        )
        print(f"→ machine-readable parity snapshot: {args_path}")

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
