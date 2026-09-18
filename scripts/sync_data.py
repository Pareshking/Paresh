"""
Automated Data Synchronization Script for NSE Momentum Terminal.
Executed locally or via GitHub Actions at 9:00 PM IST.
"""

import os
import sys
import time
from datetime import datetime

# Determine if a full 2‑year refresh is required (weekly run)
FORCE_FULL = os.getenv("FORCE_FULL", "false").lower() == "true"
# How much of the universe Yahoo must cover before its sweep may replace the
# committed snapshot. A thin result would trade coverage for a date, and the
# caps exist to say which size bucket a stock is in -- a stock with no cap at
# all is worse than one whose cap is a day old.
MIN_MCAP_COVERAGE = float(os.getenv("UMIYA_MIN_MCAP_COVERAGE", "0.9"))
# Ensure repository root is in python path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from src.loaders.indices_loader import fetch_indices_data, sync_official_nse_indices
from src.core.market_time import recent_trading_days
from src.loaders.mcap_loader import (
    fetch_mcaps_from_yfinance,
    fetch_market_caps,
)
from src.loaders.price_loader import fetch_price_history
from src.loaders.tv_loader import reconcile_and_update_tv_classification


def _precompute_rankings(symbols, universe_df, mcaps) -> None:
    """Rank the published snapshot, and stamp the answer with its own contract.

    Runs the SAME two functions the app runs -- src/engine/pipeline -- so the
    published table is what production would have computed, not a second
    implementation that agrees today and drifts next month.

    The corporate-action neutralisation is applied here too, and in the same
    order, because production applies it before the engine ever sees a price.
    Skipping it would publish a table ranked across phantom crashes that the
    live path has already removed, and the two would disagree on exactly the
    names the guard exists for.
    """
    import pandas as pd

    from src.core.config import PRICES_FILE, RANKINGS_SNAPSHOT_ASSET
    from src.core.config import DEFAULT_LOOKBACK_WEIGHTS
    from src.engine.corporate_actions import adjust_ohlc, load_events
    from src.engine import pipeline
    from src.loaders import price_source, screener_loader
    from src.loaders.price_loader import extract_ohlcv
    from src.loaders.ranking_store import contract, write_snapshot

    here = os.path.dirname(PRICES_FILE)
    snapshot_path = os.path.join(here, "prices_snapshot.parquet")
    if not os.path.exists(snapshot_path):
        print("No published snapshot to rank; skipping.")
        return

    raw = pd.read_parquet(snapshot_path)
    adj_close, close_p, high_p, low_p, vol_p, _open_p = extract_ohlcv(raw, list(symbols))
    if adj_close is None or adj_close.empty:
        print("Snapshot produced no usable prices; skipping.")
        return

    # Which history to rank. The app asks the same module, so the two cannot
    # drift onto different sources while the contract still matches.
    src = price_source.from_yahoo(adj_close, close_p, high_p, low_p, vol_p)
    if price_source.preferred() == "screener":
        store = screener_loader.load_store()
        if store is None or store.empty:
            store = price_source.fetch_screener_store()
        chosen = price_source.from_screener(store) if store is not None else None
        if chosen is not None:
            keep = [c for c in chosen.close.columns if c in set(symbols)]
            chosen.adj_close = chosen.close = chosen.close[keep]
            chosen.volume = chosen.volume.reindex(columns=keep)
            src = chosen
        else:
            print("Screener history not usable yet; ranking from Yahoo.")
    print(f"Ranking source: {src.source} "
          f"({src.adj_close.shape[0]} sessions x {src.adj_close.shape[1]} symbols, "
          f"52-week high on {src.high_basis})")
    for note in src.notes:
        print(f"  note: {note}")

    # Screener already carries its corporate-action adjustments, so this is a
    # no-op there and must stay one -- measured, 0 events applied to the
    # screener frame against 38 to Yahoo's, because _step_is_still_present sees
    # the step is already gone. Running it anyway costs nothing and keeps one
    # code path.
    frames, applied = adjust_ohlc(
        {"adj_close": src.adj_close, "close": src.close,
         "high": src.high if src.high is not None else src.close,
         "low": src.low if src.low is not None else src.close},
        load_events(),
    )
    adj_close, close_p = frames["adj_close"], frames["close"]
    high_p = frames["high"] if src.intraday else None
    low_p = frames["low"] if src.intraday else None
    vol_p = src.volume
    print(f"Corporate actions neutralised before ranking: {len(applied)}")

    idx_info = universe_df
    weights = tuple(float(w) for w in DEFAULT_LOOKBACK_WEIGHTS)
    total = sum(weights) or 1.0
    weights = tuple(w / total for w in weights)

    calc = pipeline.build_engine(
        adj_close, high_p, low_p, close_p, vol_p, idx_info, mcaps,
        corporate_actions=applied,
    )
    _calc, rank_df = pipeline.rank_with_weights(
        calc, weights, idx_info, mcaps, close_p,
        high_p if high_p is not None else close_p,
        intraday=src.intraday,
    )
    if rank_df is None or rank_df.empty:
        print("Ranking came back empty; publishing nothing.")
        return

    # The date the ENGINE stopped on, not the frame's last row. The two differ
    # whenever the vendor is still publishing the newest session, and stamping
    # the later one would label this table with a session it never scored.
    as_of = pipeline.ranking_as_of(adj_close)

    terms = contract(
        price_fingerprint=pipeline.price_fingerprint(adj_close),
        symbols_fingerprint=pipeline.symbols_fingerprint(symbols),
        weights=weights,
        pipeline_version=pipeline.PIPELINE_VERSION,
        universe=list(universe_df["Symbol"].unique()) if "Symbol" in universe_df else [],
        price_as_of=as_of,
        price_source=src.source,
        # What was ACTUALLY neutralised, not what the log holds. This job
        # re-scans for corporate actions AFTER publishing, so the log the app
        # reads can already have grown past this table -- and the price
        # fingerprint cannot see the difference.
        applied_actions=applied,
    )
    out = os.path.join(here, RANKINGS_SNAPSHOT_ASSET)
    write_snapshot(out, rank_df, terms)
    mb = os.path.getsize(out) / 1024**2
    print(
        f"Ranking precomputed: {len(rank_df)} rows, {len(rank_df.columns)} columns, "
        f"{mb:.2f} MB -> {out} (as of {as_of})"
    )


def run_daily_sync() -> None:
    """Synchronizes all NSE market data, constituents and price histories."""
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Starting daily automated sync...")

    # 1. Sync official index constituents
    print("\n--- 1. Syncing Official NSE Index Constituents ---")
    sync_res = sync_official_nse_indices(force=True)
    print(
        f"Synced {sync_res.get('total_stocks', 0)} total unique stocks across indices."
    )

    # 2. Load universe
    print("\n--- 2. Loading Market Universe ---")
    universe_df = fetch_indices_data(["NIFTY TOTAL MARKET"])
    if universe_df.empty:
        print("[ERROR] Universe load returned empty.")
        sys.exit(1)

    symbols = universe_df["Symbol"].unique().tolist()
    print(f"Universe contains {len(symbols)} tickers.")

    # 3. Reconcile TradingView taxonomy
    print("\n--- 3. Reconciling TradingView Taxonomy ---")
    reconcile_and_update_tv_classification(universe_df)

    # ORDER MATTERS: market caps BEFORE prices.
    #
    # The market-cap fetch is what asks NSE for a bhavcopy, and a 200 is the
    # exchange confirming the market traded that day. Running it after the
    # price fetch meant the newest session -- the only one the vendor has not
    # finished publishing, and so the only one at risk -- was judged on
    # coverage alone and dropped before the confirmation existed. The run of
    # 2026-09-17 did exactly that, seconds apart:
    #
    #   20:27:22  Dropping 1 session(s) ... (2026-09-17 at 20%)
    #             Trading days confirmed by NSE: +1 new, 4 on record.
    #
    # Same shape as the 2026-09-16 failure this record was added to fix, one
    # day later, because writing the answer down is useless if it is written
    # after the decision it was meant to inform. Market caps do not depend on
    # prices, so the swap costs nothing.

    # 5. Fetch market caps
    print("\n--- 5. Fetching Market Capitalizations ---")
    # Always fetch, never read the disk cache. The cache window used to be 30
    # hours against a 24-hour cadence, so the cache was ALWAYS "fresh" and this
    # job committed yesterday's market caps every single day, refreshing them
    # only on the weekly FORCE_FULL run. The window is now 22 hours
    # (MCAP_CACHE_MAX_AGE_S) which fixes that on its own, but this job does not
    # rely on it: a run whose entire purpose is a current snapshot should fetch,
    # not consult a heuristic sized for interactive sessions -- and it stays
    # correct if the cadence or the window ever changes. Prices keep FORCE_FULL:
    # that fetch is incremental by design and a daily full 2y re-download would
    # be both slow and rude.
    mcaps = fetch_market_caps(symbols, force_refresh=True)
    print(f"Market cap cache updated for {len(mcaps)} tickers.")

    # 5a. Write down which date NSE just confirmed.
    #
    # The fetch above downloads a bhavcopy for a specific date and walks back
    # until one answers with 200. That answer IS the exchange saying the market
    # traded that day, and it was being thrown away: on 2026-09-16 this job
    # dropped the 09-16 price row at 20% coverage three seconds before fetching
    # NSE's bhavcopy FOR 09-16. Recording it costs no extra request.
    try:
        from src.core import startup_metrics as _m
        from src.loaders.trading_days import record_confirmed

        _facts = _m.snapshot().get("facts", {})
        _seen = {
            str(_facts[k]) for k in ("mcap_pr_date", "mcap_pr_fetched_date")
            if _facts.get(k)
        }
        if _seen:
            _added, _total = record_confirmed(_seen)
            print(
                f"Trading days confirmed by NSE: +{_added} new, {_total} on record."
            )
    except Exception as exc:
        print(f"Trading-day record skipped: {type(exc).__name__}: {exc}")

    # 4. Fetch and cache price histories (the ARCHIVE window)
    #
    # NOTE: lengthening this only takes effect on a FORCE_FULL run. The
    # incremental path tops the cache up from its last date forward and never
    # backfills earlier history, so a longer period against an existing shorter
    # cache returns the shorter cache unchanged. The weekly full sync
    # (FORCE_FULL=true) is what actually deepens the archive.
    from src.core.config import PRICE_ARCHIVE_PERIOD, PRICE_HEAL_DAYS

    print(f"\n--- 4. Fetching and Caching {PRICE_ARCHIVE_PERIOD.upper()} OHLCV Price Histories ---")
    # heal_days re-asks for history this cache already holds. Yahoo backfills
    # an Indian close days after the session and restates a split-adjusted
    # series for weeks afterwards, and the incremental path -- which asks only
    # from the last cached date FORWARD -- can never see either. The published
    # snapshot carries 572 such holes across 337 symbols to prove it.
    #
    # It is the same single request with an earlier start, so it costs one job
    # nothing and no reader anything. Skipped on a FORCE_FULL run, which is
    # re-downloading the whole window regardless.
    prices_df = fetch_price_history(
        symbols,
        period=PRICE_ARCHIVE_PERIOD,
        force_refresh=FORCE_FULL,
        heal_days=0 if FORCE_FULL else PRICE_HEAL_DAYS,
    )
    print(f"Price cache updated with shape {prices_df.shape}.")

    # 4a. Let the calendar learn the holidays the volume test found.
    #
    # The zero-volume test reads something no coverage threshold can: a session
    # where every priced symbol is flat at zero volume is one on which nothing
    # changed hands, and two of the four it found sat at 100% vendor coverage.
    # Writing them down turns a test that must re-derive the answer from the
    # whole frame on every read into a fact the calendar simply knows -- and
    # one a human can audit, which a heuristic buried in a loader is not.
    #
    # This is evidence, not an assertion of an NSE holiday. The source string
    # says exactly what was observed and at what coverage, so a wrong entry can
    # be traced to the run that made it rather than appearing as an anonymous
    # date somebody once decided was closed. record_closed already refuses any
    # date NSE published a bhavcopy for, so the exchange still outranks this.
    try:
        from src.core import startup_metrics as _m
        from src.loaders.trading_days import record_closed

        _facts = _m.snapshot().get("facts", {})
        _dead = [d for d in str(_facts.get("price_zero_trade_dates") or "").split(",") if d]
        if _dead:
            _cov = dict(
                part.split(":", 1)
                for part in str(_facts.get("price_zero_trade_coverage") or "").split(",")
                if ":" in part
            )
            for _day in _dead:
                _pct = _cov.get(_day, "?")
                added, total = record_closed(
                    [_day],
                    source=f"zero-volume evidence ({_pct}% priced, all flat at zero volume)",
                )
                if added:
                    print(f"Calendar learned {_day} is a non-session ({_pct}% priced); {total} on record.")
        else:
            print("No zero-volume non-sessions found in this frame.")
    except Exception as exc:
        # Strictly an enrichment: the volume test already dropped these rows
        # from the frame this run, with or without the calendar entry.
        print(f"Calendar learning skipped: {type(exc).__name__}: {exc}")

    # 5b. Commit the result to the repository.
    # This job runs on GitHub Actions, where NSE is reachable. Whether
    # production on Streamlit Cloud can reach it too is NOT established -- the
    # claim that NSE refuses that host traces back to the same silent failure
    # that turned out to be our own logging bug, so treat it as unverified
    # until someone reads mcap_path from a live session. Either way, writing
    # the snapshot here is worth it: production reads one committed file
    # instead of making 750 individual yfinance lookups, the slowest stage of
    # a cold start.
    from src.core import startup_metrics as _metrics

    _facts = _metrics.snapshot().get("facts", {})
    _mcap_path = str(_facts.get("mcap_path") or "unknown")
    _as_of = _facts.get("mcap_pr_date")

    if _mcap_path == "repo_snapshot":
        # The loader fell through to the file THIS JOB wrote last time, which
        # means nothing new was fetched. Rewriting it as-is would launder a
        # stale snapshot as a fresh one and reset nothing but the commit date.
        #
        # This is not hypothetical: on 2026-08-18 the 22:00 IST slot fired at
        # 22:29 and NSE had not yet published the PR archive -- the same file
        # fetched cleanly at 22:51 -- so the job read its own output and wrote
        # it straight back. A closed loop with no signal that the fetch failed.
        #
        # A second door, for when the first genuinely will not open.
        #
        # Do NOT read this branch as evidence that NSE blocks CI. That was
        # believed here for months and it was false: the archive answered every
        # request, and a logging bug in _fetch_mcap_from_pr_zip threw the parsed
        # result away, which looked identical to a refusal from out here.
        # Measured 2026-08-19 from two different hosts: HTTP 200 and a valid
        # 644,058 byte zip.
        #
        # So this fires for the cases that remain real -- an outage, a genuine
        # 403, an archive still unpublished at this hour. Yahoo answers fine;
        # the daily prices come from there. It is skipped everywhere else only
        # because market cap has no bulk endpoint, so it costs one request per
        # company and the LIVE app cannot spend 750 of those on a cold start.
        print(
            "::warning::No market caps from NSE; asking Yahoo for the full "
            "universe instead so the caps still carry a date."
        )
        _started = time.perf_counter()
        _yf_caps = fetch_mcaps_from_yfinance(symbols)
        _elapsed = time.perf_counter() - _started
        _coverage = len(_yf_caps) / max(len(symbols), 1)
        print(
            f"Yahoo market cap sweep: {len(_yf_caps)}/{len(symbols)} resolved "
            f"({_coverage:.0%}) in {_elapsed:.0f}s"
        )

        if _coverage >= MIN_MCAP_COVERAGE:
            # Adopted WHOLESALE, never merged with the older snapshot. Keeping
            # yesterday's rows for whatever Yahoo missed would put two
            # different days under one AsOf, which is the exact dishonesty the
            # guard above exists to prevent.
            mcaps = _yf_caps
            _mcap_path = "yfinance_sweep"
            _as_of = recent_trading_days(1)[0].isoformat()
        else:
            print(
                f"::warning::Yahoo covered only {_coverage:.0%} of the universe, "
                f"below the {MIN_MCAP_COVERAGE:.0%} required to replace the "
                "snapshot. Leaving the existing one untouched."
            )

    # Still the repo snapshot means neither door opened, so the committed file
    # stands as it is -- undated, but not re-dated to today either.
    if _mcap_path == "repo_snapshot":
        print("No fresh market caps from either source; snapshot left untouched.")
    elif len(mcaps) > 0:
        import pandas as pd

        from src.core.config import REPO_MCAP_FILE

        os.makedirs(os.path.dirname(REPO_MCAP_FILE), exist_ok=True)
        snapshot = (
            pd.DataFrame({"Symbol": mcaps.index, "MarketCap": mcaps.values})
            .dropna()
            .sort_values("Symbol")
        )
        snapshot = snapshot[snapshot["MarketCap"] > 0]
        # Stamp the trade date this snapshot represents, so production can say
        # how old its market caps are instead of presenting them undated.
        snapshot["AsOf"] = _as_of or ""
        # Which door the number came in through. NSE publishes the official
        # figure; Yahoo derives it from price x its own share count, and a
        # reader comparing the two deserves to know which they are looking at.
        snapshot["Source"] = _mcap_path
        snapshot.to_csv(REPO_MCAP_FILE, index=False)
        print(
            f"Repository market cap snapshot written: {len(snapshot)} symbols "
            f"(source={_mcap_path}, as of {_as_of or 'undated'}) -> {REPO_MCAP_FILE}"
        )
    else:
        print("No market caps resolved; leaving the repository snapshot untouched.")

    # 5b. All-time highs from a long history.
    #
    # Production runs the screener on a two-year window because every
    # calendar-momentum pass walks that frame row by row, so a ten-year window
    # would multiply the cold start rather than the storage. This job has no
    # such constraint -- nobody waits on it -- so it pays the ten-year download
    # once a day and commits one row per symbol. Production then gets a genuine
    # all-time high for the price of reading a small CSV.
    print("\n--- 5b. Computing All-Time Highs ---")
    try:
        from src.core.config import ATH_HISTORY_PERIOD, REPO_ATH_FILE
        from src.loaders.ath_loader import build_ath_snapshot

        snapshot = build_ath_snapshot(symbols, ATH_HISTORY_PERIOD)
        if snapshot.empty:
            print("No long-history highs returned; leaving the ATH snapshot untouched.")
        else:
            os.makedirs(os.path.dirname(REPO_ATH_FILE), exist_ok=True)
            snapshot.to_csv(REPO_ATH_FILE, index=False)
            print(
                f"All-time-high snapshot written: {len(snapshot)} symbols "
                f"over {ATH_HISTORY_PERIOD} -> {REPO_ATH_FILE}"
            )
    except Exception as exc:
        # A failure here must not cost the rest of the sync. Production falls
        # back to its in-memory window and labels the column accordingly.
        print(f"All-time-high snapshot skipped: {type(exc).__name__}: {exc}")

    # 5c. Publish the price history for production to seed from.
    #
    # Written as float32 + zstd: 18.7 MB becomes 10.5 MB, and prices carry
    # nowhere near seven significant figures of meaning. The workflow uploads
    # this as a release asset rather than committing it -- 10.5 MB a day is
    # ~2.5 GB a year of git history against GitHub's ~1 GB soft limit.
    print("\n--- 5c. Publishing Price Snapshot ---")
    try:
        import pandas as pd

        from src.core.config import PRICE_HISTORY_PERIOD, PRICES_FILE
        from src.loaders.price_loader import _read_local_price_cache

        if os.path.exists(PRICES_FILE):
            # Through the SAME guards the app reads with, not a bare
            # read_parquet. Everything published here is consumed by something
            # that does not re-check: the app's cold start, the monthly
            # track-record freeze, and _precompute_rankings, which reads the
            # snapshot file straight back off disk.
            #
            # A bare read shipped four non-sessions -- 2026-01-15, 2026-05-01,
            # 2026-05-28, 2026-06-26, every priced symbol flat at zero volume,
            # two of them at 100% vendor coverage. The app stripped them on
            # read and the precomputed ranking did not, so the two would have
            # ranked different frames while the contract matched: a wrong
            # answer served fast, which is worse than no artifact at all.
            frame = _read_local_price_cache()
            if frame is None or frame.empty:
                frame = pd.read_parquet(PRICES_FILE)
            compact = frame.astype("float32", errors="ignore")
            here = os.path.dirname(PRICES_FILE)

            # The full archive, for jobs where nobody is waiting: the monthly
            # track-record freeze and any long backtest.
            archive = os.path.join(here, "prices_archive.parquet")
            compact.to_parquet(archive, compression="zstd")
            a_mb = os.path.getsize(archive) / 1024**2
            print(
                f"Price ARCHIVE written: {len(frame)} rows, "
                f"{len(frame.columns)} series, {a_mb:.1f} MB -> {archive}"
            )

            # The app's cold-start snapshot: only the trailing screener window.
            # The screener walks this frame row by row, so shipping the whole
            # archive here would slow every cold start for data the screener
            # never reads.
            years = float(str(PRICE_HISTORY_PERIOD).rstrip("y") or 2)
            cutoff = frame.index.max() - pd.DateOffset(years=int(years))
            recent = compact.loc[compact.index >= cutoff]
            out = os.path.join(here, "prices_snapshot.parquet")
            recent.to_parquet(out, compression="zstd")
            mb = os.path.getsize(out) / 1024**2
            print(
                f"Price snapshot written: {len(recent)} rows "
                f"(trailing {PRICE_HISTORY_PERIOD}), "
                f"{len(recent.columns)} series, {mb:.1f} MB -> {out}"
            )
        else:
            print("No price cache on disk; nothing to publish.")
    except Exception as exc:
        print(f"Price snapshot skipped: {type(exc).__name__}: {exc}")

    # 5d. Precompute the ranking from the snapshot just published.
    #
    # Thirty of the eighty-nine seconds of a production cold start were spent
    # here, deriving five calendar-period passes and every signal column over
    # 750 symbols while a reader watched a spinner. It is the same arithmetic
    # on the same frame every time, and this job already holds that frame on a
    # runner where nobody is waiting.
    #
    # Ranked from `recent` -- the exact bytes published as prices.parquet --
    # and NOT from the ten-year archive. The contract production checks is a
    # fingerprint of the frame that was ranked, so ranking anything other than
    # what production will seed from would miss on every single cold start.
    print("\n--- 5d. Precomputing the Ranking ---")
    try:
        _precompute_rankings(symbols, universe_df, mcaps)
    except Exception as exc:
        # Strictly an accelerator. Production computes the ranking itself when
        # this is missing, which is what it did before this step existed.
        print(f"Ranking precompute skipped: {type(exc).__name__}: {exc}")

    print(
        f"\n[{datetime.now():%Y-%m-%d %H:%M:%S}] All daily sync tasks completed successfully!"
    )


if __name__ == "__main__":
    run_daily_sync()
