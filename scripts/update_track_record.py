#!/usr/bin/env python3
"""Freeze newly closed months into the track record ledger.

Run monthly. Every month it writes is written ONCE: re-running this script,
today or next year, must not change a single number already in the file. That
is the entire contract -- see src/engine/track_record.py for why.

    python scripts/update_track_record.py              # write closed months
    python scripts/update_track_record.py --dry-run    # report, write nothing
    python scripts/update_track_record.py --force      # rewrite history (loud)
    python scripts/update_track_record.py --system nano
    python scripts/update_track_record.py --shadow

--system picks the record: 750 (default, data/track_record.json), nano or
combined (their own ledgers, from October 2026). Each is scored on its own
point-in-time membership (src/engine/systems.py).

--shadow freezes the Recommendation's shadow record instead: the 750 under
SHADOW_CONFIG, in data/track_record_shadow.json, from November 2026 (owner,
12 Oct 2026). It is never traded and never changes the live records.
"""

from __future__ import annotations

import argparse
from datetime import datetime, UTC
import io
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.config import BENCHMARK_SYMBOL  # noqa: E402
from src.engine.backtester import run_backtest  # noqa: E402
from src.engine.parity_audit import compare_monthly_ledger, load_accepted_drift  # noqa: E402
from src.engine.parity_audit import freeze_refusal  # noqa: E402
from src.engine.track_record import (  # noqa: E402
    BREADTH_INDEX,
    SHADOW_CASH_YIELD,
    SHADOW_SWITCH_COST,
    SHADOWS,
    breadth_on,
    overlay_month,
    TRACK_RECORD_CONFIG,
    config_fingerprint_for_month,
    finalize_months,
    load_ledger,
    months_to_cover,
    run_backtest_kwargs,
    save_ledger,
    summary_stats,
)
from src.engine import systems  # noqa: E402
from src.engine.model_record import record_sector_map  # noqa: E402
from src.engine.extra_universe import SYSTEM_750, SYSTEM_1000, SYSTEM_NANO, SYSTEMS  # noqa: E402
from src.engine.systems import unpriced_members  # noqa: E402,F401  (also read as utr.unpriced_members)
from src.engine.membership import describe  # noqa: E402
from src.engine import freeze_bundle  # noqa: E402
from src.loaders import former_members, nse_prices, price_source  # noqa: E402
from src.loaders import extra_universe_loader as xl  # noqa: E402
from src.loaders.indices_loader import fetch_indices_data  # noqa: E402
from src.loaders.price_loader import fetch_benchmark_history  # noqa: E402


def record_setup(system: str, shadow: bool = False,
                 ledger: str | None = None) -> tuple[str, str, pd.Period, dict]:
    """(system, ledger file, inception, configuration) for one record.

    The shadow record is the 750's universe and membership under its own pinned
    configuration, ledger and inception; every other record is its system's own.
    """
    if shadow:
        if system != SYSTEM_750:
            raise SystemExit("--shadow is the Nifty 750's; it takes no --system")
        book = SHADOWS[_shadow_key(shadow)]
        return system, ledger or str(book.ledger_path), book.inception, dict(book.config)
    return (system, ledger or str(systems.ledger_path(system)), systems.inception(system),
            dict(TRACK_RECORD_CONFIG))


def _shadow_key(shadow) -> str:
    """`--shadow` alone is the Recommendation (the workflow's first call); else its key."""
    key = "recommendation" if shadow is True else str(shadow)
    if key not in SHADOWS:
        raise SystemExit(f"--shadow {key!r}: one of {', '.join(SHADOWS)}")
    return key


def add_overlay(ledger: dict, added: list[str], book, curve: pd.Series, closes: pd.DataFrame,
                breadth_membership: dict | None) -> list[str]:
    """For a book with a breadth rule, the overlay of each newly frozen month, beside it.

    The signal is the close of the last session before the month, as for the
    engine's own book. Returns what it printed, for the log.
    """
    if not book.breadth_rule or not added:
        return []
    threshold, low = book.breadth_rule
    lines, months = [], ledger["months"]
    for key in sorted(added):
        period = pd.Period(key, freq="M")
        signal_close = closes.index[closes.index.to_period("M") < period]
        if len(signal_close) == 0:
            continue
        signal_day = signal_close[-1]
        breadth = breadth_on(closes, breadth_membership, signal_day)
        prev = months.get(str(period - 1), {}).get("overlay", {}).get("exposure", 1.0)
        exposure = 1.0 if breadth is None or breadth > threshold else low
        ret = overlay_month(curve, period, exposure, prev)
        months[key]["overlay"] = {
            "rule": f"{low:.0%} invested when breadth <= {threshold:.0%}",
            "signal": signal_day.strftime("%Y-%m-%d"),
            "breadth": None if breadth is None else round(breadth, 4),
            "exposure": exposure,
            "strategy": None if ret is None else round(ret, 6),
            "cash_yield": SHADOW_CASH_YIELD,
            "switch_cost": SHADOW_SWITCH_COST,
        }
        lines.append(f"  overlay {key}: breadth "
                     f"{'n/a' if breadth is None else f'{breadth:.1%}'} on {signal_day:%d %b %Y}"
                     f" -> {exposure:.0%} invested, {'n/a' if ret is None else f'{ret:+.2%}'}")
    return lines


def _keep_exposure(tradebook) -> None:
    """The 750 book's industry and size at each rebalance the file lacks (src/engine/book_exposure.py)."""
    import json
    from src.engine import book_exposure as bx
    try:
        membership = json.loads((Path(__file__).resolve().parents[1] / "data" / "membership_history.json").read_text())
        syms = sorted(set(tradebook["Symbol"].astype(str))) if tradebook is not None and len(tradebook) else []
        new = bx.exposure(tradebook, record_sector_map(syms), membership)
        kept = bx.load()
        out = bx.merge(kept, new)
        if len(out) != len(kept):
            bx.save(out)
            print(f"→ book exposure: {out['date'].nunique()} rebalances kept ({out['date'].nunique() - kept['date'].nunique() if len(kept) else out['date'].nunique()} new)")
    except Exception as exc:  # the ledger is what matters; never stop a freeze over this
        print(f"::warning::book exposure not updated: {exc}")


def _code_sha() -> str:
    sha = os.environ.get("GITHUB_SHA")
    if sha:
        return sha
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"],
                                       cwd=Path(__file__).resolve().parents[1], text=True).strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def _archive_months(added, ledger, *, system_key, as_of, frame, benchmark, membership,
                    store_bytes, store_source, kwargs, sector_map, actions, backtest_months,
                    cfg, fingerprint, result, force, publish=True, publisher=None,
                    books_path=None):
    """Build and publish one evidence bundle per added month (S185); return the books.

    Raises on any failure, before anything is written. On success each added
    month's ledger row gets `freeze_revision` (the bundle's sha256 on R2) and
    `screener_store_sha256`, and the returned books (data/record_books.json)
    hold the month's tradebook rows. `publish=False` (--no-archive) records the
    month with no freeze_revision.
    """
    from src.engine.track_record import calendar_month_returns

    if publish and publisher is None:
        from src.storage.r2 import R2Config
        R2Config.from_env()  # raises when R2 is not configured: no freeze without evidence
        publisher = freeze_bundle.publish
    code_sha = _code_sha()
    strat = calendar_month_returns(result["equity_curve"])
    bench = calendar_month_returns(result["benchmark"])
    store_sha = freeze_bundle._sha(store_bytes)
    books = freeze_bundle.load_books(books_path or freeze_bundle.BOOKS_PATH)
    revisions = {}
    with tempfile.TemporaryDirectory() as tmp:
        for month in added:
            period = pd.Period(month, freq="M")
            row = ledger["months"][month]
            book_rows = freeze_bundle.month_book(result.get("tradebook"), month)
            data = freeze_bundle.build(
                system=system_key, month=month, as_of=as_of, frame=frame, benchmark=benchmark,
                membership=membership, screener_store=store_bytes, screener_source=store_source,
                kwargs=kwargs, sector_map=sector_map, actions=list(actions or []),
                backtest_months=backtest_months, cfg=cfg, fingerprint=fingerprint(period),
                results={"strategy": float(strat.loc[period]),
                         "benchmark": float(bench.loc[period]) if period in bench.index else None,
                         "ledger_strategy": row["strategy"], "ledger_benchmark": row["benchmark"],
                         "ledger_alpha": row["alpha"]},
                book=book_rows, code_sha=code_sha,
            )
            revision = publisher(data, system=system_key, month=month, code_sha=code_sha,
                                 workdir=Path(tmp)) if publish else None
            revisions[month] = (revision, book_rows)
            print(f"  evidence {month}: {len(data):,} bytes, "
                  + (f"R2 revision {revision[:16]}" if revision else "NOT published (--no-archive)"))
    for month, (revision, book_rows) in revisions.items():
        ledger["months"][month]["freeze_revision"] = revision
        ledger["months"][month]["screener_store_sha256"] = store_sha
        freeze_bundle.add_book(books, system=system_key, month=month,
                               as_of=pd.Timestamp(as_of).strftime("%Y-%m-%d"),
                               freeze_revision=revision, screener_store_sha256=store_sha,
                               book=book_rows, force=force)
    return books


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--system", default=SYSTEM_750, choices=list(SYSTEMS))
    ap.add_argument("--shadow", nargs="?", const=True, default=False,
                    help="a shadow record instead of the live one: alone, the Recommendation "
                         f"(750, from Nov 2026); or one of: {', '.join(SHADOWS)}")
    ap.add_argument("--ledger", default=None,
                    help="defaults to the system's own ledger")
    ap.add_argument("--extra-prices", default=None,
                    help="ignored; kept so older workflow calls still parse")
    ap.add_argument("--indices", nargs="+", default=["NIFTY TOTAL MARKET"])
    ap.add_argument(
        "--period",
        default="5y",
        help="Benchmark history to read. Must cover inception plus a 12-month "
        "formation window before it.",
    )
    ap.add_argument("--prices", choices=["screener", "nse"], default="screener",
                    help="price basis: screener (Screener's closes, NSE's where it has none; "
                    "the default for every system) or nse (NSE closes as published, "
                    "data/nse_prices). No Yahoo basis since 2026-10-02.")
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
    ap.add_argument(
        "--no-archive",
        action="store_true",
        help="Freeze without publishing the month's evidence bundle to R2 (a local "
        "run with no R2 credentials). The month is recorded with no freeze_revision. "
        "Never used by the scheduled job (S185).",
    )
    args = ap.parse_args()

    system, ledger_file, start, cfg = record_setup(args.system, args.shadow, args.ledger)
    book = SHADOWS[_shadow_key(args.shadow)] if args.shadow else None
    print(f"→ system: {system}{f' (shadow record: {book.name})' if book else ''} · ledger {ledger_file} "
          f"· inception {start}")

    core: list[str] = []
    if system != SYSTEM_NANO:
        print(f"→ universe: {args.indices}")
        idx_info = fetch_indices_data(args.indices)
        core = idx_info["Symbol"].unique().tolist() if not idx_info.empty else []
    extra: list[str] = []
    if system != SYSTEM_750:
        listed = xl.nifty_1000_members() if system == SYSTEM_1000 else xl.members()
        extra = [s for s in listed["Symbol"] if s not in set(core)]
    symbols = core + extra
    if not symbols:
        print("✗ universe is empty; refusing to write a record from no data")
        return 1
    print(f"  {len(symbols)} symbols ({len(core)} in the 750, {len(extra)} "
          f"{'Nano Cap' if system == SYSTEM_1000 else '₹2,000 Cr list'})")

    # Screener's store holds both the 750 and the Nano Cap list; it is the
    # frame's base, and basis_frame below lays NSE under it (owner, 2026-10-02:
    # Screener first, NSE second, no Yahoo).
    # The raw bytes, fetched once: the frame is built from them and the same bytes
    # go into the month's evidence bundle (S185), never a second download that the
    # nightly job may have replaced in between.
    store_bytes, store_source = price_source.fetch_screener_store_bytes()
    try:
        store = pd.read_parquet(io.BytesIO(store_bytes)) if store_bytes else None
    except Exception as exc:  # noqa: BLE001
        print(f"✗ Screener's store is unreadable ({type(exc).__name__}); refusing to freeze")
        return 1
    if store is None or store.empty or not isinstance(store.columns, pd.MultiIndex):
        print(f"✗ Screener's store is unavailable ({store_source}); refusing to freeze months without it")
        return 1
    print(f"  Screener store: {len(store_bytes):,} bytes from {store_source}, "
          f"sha256 {freeze_bundle._sha(store_bytes)[:16]}")
    closes = store.xs("Close", axis=1, level=-1)
    closes.index = pd.DatetimeIndex(closes.index).normalize()
    closes = closes[~closes.index.duplicated(keep="last")].sort_index()
    adj_close = closes[[s for s in symbols if s in closes.columns]].astype(float)
    if adj_close.empty:
        print("✗ no Screener closes for this universe")
        return 1
    print(f"  Screener closes for {adj_close.shape[1]} of {len(symbols)} symbols")

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
    basis = args.prices
    if basis in ("screener", "nse"):
        # Screener's closes, as on the live ranking (owner, 2026-10-01); NSE's closes as
        # published, adjusted only for splits, bonuses and demergers, fill what Screener
        # lacks, and Yahoo's frame only what neither has. Yahoo's corporate-action log
        # corrects Yahoo, so it is not applied to these series.
        nse, info = nse_prices.basis_frame(adj_close, membership, months=months,
                                           screener=store if basis == "screener" else None)
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
        # The window is counted back from the frame's end, and NSE's file can be
        # the earlier to reach a new month: its first session of the month may be
        # on file before Screener's store has that bar.
        as_of = pd.Timestamp(nse.index[-1])
        months = months_to_cover(as_of, start)
        print(f"→ NSE sessions through {as_of:%d %b %Y}; covering {months} completed months")
        adj_close, actions = nse, []
    n_before = adj_close.shape[1]
    adj_close = former_members.with_former_members(adj_close, membership)
    unpriceable = [s for s in former_members.unavailable() if s not in adj_close.columns]
    print(f"→ former members priced: {adj_close.shape[1] - n_before} added to the "
          f"{n_before}-stock frame; unpriceable: "
          f"{', '.join(unpriceable) or 'none'}")

    # The Nifty 1000's ~250 extra members are still being priced (S175): a month is
    # frozen only when every member of its signal close has a close that day, so a
    # book is never formed from the part of the index we happen to hold.
    if system == SYSTEM_1000:
        # Only the months this run will freeze: a past month already in the ledger is
        # the record, and a close lost from it later must not block every new month.
        frozen = set() if args.force else set(load_ledger(ledger_file, start).get("months") or {})
        gaps = unpriced_members(adj_close, membership, start, months, skip=frozen)
        if gaps:
            for day, names in gaps.items():
                print(f"✗ {day}: {len(names)} Nifty 1000 member(s) without a close: "
                      f"{', '.join(names[:20])}{' …' if len(names) > 20 else ''}")
            print("✗ refusing to freeze the Nifty 1000 until every member is priced")
            return 1

    # Per month: a forward-dated rule (members_only_scoring_from) is part of
    # the fingerprint only of the months it governs (track_record.config_for_month).
    def fingerprint(period):
        return config_fingerprint_for_month(cfg, period)
    print(f"  config fingerprint (current month): {fingerprint(pd.Period(as_of, freq='M'))}")

    # Every argument of this call goes into the month's evidence bundle (S185).
    run_kwargs = run_backtest_kwargs(cfg)
    sector_map = record_sector_map(adj_close.columns, system)
    result = run_backtest(
        f"trackrecord_{system}{f'_shadow_{book.key}' if book else ''}_{as_of:%Y%m%d}_{months}",
        adj_close,
        **run_kwargs,
        sector_map=sector_map,
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

    # Read-only comparison of both frozen return series. Stored closed months
    # remain authoritative and are never silently rewritten; a red comparison
    # (a drift not accepted) stops a new month being struck below (S92).
    parity = compare_monthly_ledger(
        ledger, result["equity_curve"], result["benchmark"], accepted=load_accepted_drift(system=system)
    )
    counts = parity["counts"]
    print(
        "→ frozen-ledger parity: "
        f"{counts['match']} match, {counts['accepted']} accepted, {counts['drift']} drift, "
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

    if book is not None and book.breadth_rule:
        from src.engine import index_universe as iu
        for line in add_overlay(ledger, added, book, result["equity_curve"], adj_close,
                                iu.index_history(BREADTH_INDEX)):
            print(line)

    # S92 (owner, 7 Nov 2026): no month is struck while the replay disagrees
    # with a frozen month the owner has not accepted. October 2026 was struck
    # on 3 Nov with September already drifting here, on a Screener store that
    # carried BSE closes (S89). A --force rebuild is the deliberate exception.
    refusal = freeze_refusal(parity)
    if refusal and added and not args.force:
        print(f"✗ refusing to freeze {', '.join(added)}: {refusal}")
        return 1

    if args.force and added:
        # A rebuild replaces frozen numbers, so the file says so: when, which
        # months, what they were struck under before, and what they are now.
        replaced = sorted({m.get("config") for m in prior_months.values() if m.get("config")})
        ledger.setdefault("rebuilds", []).append({
            "on": datetime.now(UTC).strftime("%Y-%m-%d"),
            "months": added,
            "replaced_configs": replaced,
            # `fingerprint` is per month since the forward-dated rules (audit,
            # 8 Nov 2026: storing the function made the rebuild unwritable).
            "config": sorted({fingerprint(pd.Period(k, freq="M")) for k in added}),
            "prices": cfg["prices"],
            "membership": ("point in time" + (f" from {pit_from}" if pit_from else "")),
            "former_members_unpriceable": unpriceable,
            "previous_values": {k: prior_months[k]["strategy"] for k in added if k in prior_months},
            "note": args.note,
        })
    # One basis for the whole file, or none claimed: a ledger that mixes months struck
    # on different bases must not label them all with one.
    # Each month against its own fingerprint (a set of strings against a set
    # holding the function was always False, so price_basis was always dropped).
    if all(m.get("config") == fingerprint(pd.Period(k, freq="M")) for k, m in ledger["months"].items()):
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
    books = None
    # Beside the ledger it describes (data/record_books.json for the scheduled job).
    books_path = Path(ledger_file).with_name(freeze_bundle.BOOKS_PATH.name)
    if added:
        # S185: no month is frozen without its evidence. The bundles are published
        # first; a failure writes nothing (no ledger, no book) and fails the step.
        try:
            books = _archive_months(
                added, ledger, system_key=freeze_bundle.system_key(ledger_file), as_of=as_of,
                frame=adj_close, benchmark=benchmark, membership=membership,
                store_bytes=store_bytes, store_source=store_source, kwargs=run_kwargs,
                sector_map=sector_map, actions=actions, backtest_months=months, cfg=cfg,
                fingerprint=fingerprint, result=result, force=args.force,
                publish=not args.no_archive, books_path=books_path,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"✗ refusing to freeze {', '.join(added)}: the evidence bundle was not "
                  f"published ({type(exc).__name__}: {exc}); nothing written")
            return 1
    if system == SYSTEM_750 and not book:
        _keep_exposure(result.get("tradebook"))
    if not added and not args.force:
        print("→ no new closed months; file untouched")
        return 0

    if books is not None:
        freeze_bundle.save_books(books, books_path)
    save_ledger(ledger, ledger_file)
    s = summary_stats(ledger)
    print(f"✓ wrote {ledger_file}: {s['months']} months, "
          f"{s['first']} → {s['last']}, total {s['total_return']:+.2%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
