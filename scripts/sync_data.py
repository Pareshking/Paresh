"""
Automated Data Synchronization Script for NSE Momentum Terminal.
Executed locally or via GitHub Actions at 9:00 PM IST.
"""

import os
import sys
from datetime import datetime

# The weekly run sets this; it no longer changes what the sync fetches.
FORCE_FULL = os.getenv("FORCE_FULL", "false").lower() == "true"
# Ensure repository root is in python path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from src.loaders.indices_loader import fetch_indices_data, sync_official_nse_indices
from src.loaders.mcap_loader import fetch_market_caps
from src.loaders.tv_loader import reconcile_and_update_tv_classification


def _precompute_rankings(symbols, universe_df, mcaps, out_name=None) -> None:
    """Rank the Screener frame the app will rank, and stamp it with its own contract.

    Runs the SAME two functions the app runs -- src/engine/pipeline -- so the
    published table is what production would have computed, not a second
    implementation that agrees today and drifts next month.

    The corporate-action neutralisation is applied here too, and in the same
    order, because production applies it before the engine ever sees a price.
    Skipping it would publish a table ranked across phantom crashes that the
    live path has already removed, and the two would disagree on exactly the
    names the guard exists for.
    """
    from src.core.config import PRICES_FILE, RANKINGS_SNAPSHOT_ASSET
    from src.core.config import DEFAULT_LOOKBACK_WEIGHTS
    from src.engine.corporate_actions import adjust_ohlc, load_events
    from src.engine import pipeline
    from src.loaders import price_source, screener_loader
    from src.loaders.ranking_store import contract, write_snapshot

    here = os.path.dirname(PRICES_FILE)

    # out_name: another system's file (Nano Cap, Combined;
    # scripts/precompute_systems.py). Default: the 750's.
    #
    # Which history to rank. The app asks the same function
    # (price_source.ranking_frames), so the two cannot drift onto different
    # data while the contract still matches. Screener first, NSE for what it
    # lacks; no Yahoo (owner, 2026-10-02).
    from src.loaders import nse_prices

    store = screener_loader.load_store()
    if store is None or store.empty:
        store = price_source.fetch_screener_store()
    src = price_source.ranking_frames(store, list(symbols), nse_prices.middle_close(symbols))
    if src is None:
        print("Neither Screener nor NSE can serve a ranking frame; skipping.")
        return
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
    out = os.path.join(here, out_name or RANKINGS_SNAPSHOT_ASSET)
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

    # 4. (Removed 2026-10-02.) The Yahoo price download and the zero-volume
    # calendar learning that read it. Prices come from Screener's store
    # (scripts/sync_screener.py, its own workflow) and NSE's committed file;
    # the owner retired Yahoo as a source.

    # 5b. Commit the result to the repository.
    # This job runs on GitHub Actions, where NSE is reachable. Whether
    # production on Streamlit Cloud can reach it too is NOT established -- the
    # claim that NSE refuses that host traces back to the same silent failure
    # that turned out to be our own logging bug, so treat it as unverified
    # until someone reads mcap_path from a live session. Either way, writing
    # the snapshot here is worth it: production reads one committed file.
    from src.core import startup_metrics as _metrics

    _facts = _metrics.snapshot().get("facts", {})
    _mcap_path = str(_facts.get("mcap_path") or "unknown")
    _as_of = _facts.get("mcap_pr_date")

    # If the loader fell through to the file THIS JOB wrote last time,
    # nothing new was fetched: rewriting it as-is would launder a stale
    # snapshot as a fresh one (2026-08-18: NSE's archive was not yet
    # published at 22:29 IST). There is no second door any more -- the Yahoo
    # sweep went with Yahoo (owner, 2026-10-02) -- so the file stands.
    # Still the repo snapshot means NSE did not answer, so the committed file
    # stands as it is -- undated, but not re-dated to today either.
    if _mcap_path == "repo_snapshot":
        print("No fresh market caps from NSE; snapshot left untouched.")
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

    # 5b. All-time highs from Screener's whole history (about ten years).
    #
    # Production ranks on a shorter window because every calendar-momentum
    # pass walks that frame row by row. This job has no such constraint, so it
    # takes the high once a day from the store and commits one row per symbol.
    print("\n--- 5b. Computing All-Time Highs ---")
    try:
        from src.core.config import REPO_ATH_FILE
        from src.loaders import screener_loader
        from src.loaders.ath_loader import build_ath_snapshot

        store = screener_loader.load_store()
        snapshot = build_ath_snapshot(symbols, store if store is not None and not store.empty else None)
        if snapshot.empty:
            print("No long-history highs returned; leaving the ATH snapshot untouched.")
        else:
            os.makedirs(os.path.dirname(REPO_ATH_FILE), exist_ok=True)
            snapshot.to_csv(REPO_ATH_FILE, index=False)
            print(
                f"All-time-high snapshot written: {len(snapshot)} symbols "
                f"(Screener closes) -> {REPO_ATH_FILE}"
            )
    except Exception as exc:
        # A failure here must not cost the rest of the sync. Production falls
        # back to its in-memory window and labels the column accordingly.
        print(f"All-time-high snapshot skipped: {type(exc).__name__}: {exc}")

    # 5d. Precompute the ranking.
    #
    # Thirty of the eighty-nine seconds of a production cold start were spent
    # here, deriving five calendar-period passes and every signal column over
    # 750 symbols while a reader watched a spinner. It is the same arithmetic
    # on the same frame every time, and this job holds that frame on a runner
    # where nobody is waiting. The frame is price_source.ranking_frames -- the
    # same call the app makes -- so production's fingerprint check matches.
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
