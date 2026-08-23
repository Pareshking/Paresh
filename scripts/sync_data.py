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

    # 4. Fetch and cache price histories (2Y)
    print("\n--- 4. Fetching and Caching 2Y OHLCV Price Histories ---")
    prices_df = fetch_price_history(symbols, period="2y", force_refresh=FORCE_FULL)
    print(f"Price cache updated with shape {prices_df.shape}.")

    # 5. Fetch market caps
    print("\n--- 5. Fetching Market Capitalizations ---")
    # Always fetch, never read the disk cache. _is_mcap_cache_fresh() accepts a
    # cache up to 30 hours old, and this job runs every 24 -- so the cache was
    # ALWAYS "fresh" and the daily sync committed yesterday's market caps every
    # single day, refreshing them only on the weekly FORCE_FULL run. The window
    # is sized for interactive app sessions; a job whose entire purpose is to
    # produce a current snapshot must not consult it. Prices keep FORCE_FULL:
    # that fetch is incremental by design and a daily full 2y re-download would
    # be both slow and rude.
    mcaps = fetch_market_caps(symbols, force_refresh=True)
    print(f"Market cap cache updated for {len(mcaps)} tickers.")

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

        from src.core.config import PRICES_FILE

        if os.path.exists(PRICES_FILE):
            frame = pd.read_parquet(PRICES_FILE)
            compact = frame.astype("float32", errors="ignore")
            out = os.path.join(os.path.dirname(PRICES_FILE), "prices_snapshot.parquet")
            compact.to_parquet(out, compression="zstd")
            mb = os.path.getsize(out) / 1024**2
            print(
                f"Price snapshot written: {len(frame)} rows, "
                f"{len(frame.columns)} series, {mb:.1f} MB -> {out}"
            )
        else:
            print("No price cache on disk; nothing to publish.")
    except Exception as exc:
        print(f"Price snapshot skipped: {type(exc).__name__}: {exc}")


    print(
        f"\n[{datetime.now():%Y-%m-%d %H:%M:%S}] All daily sync tasks completed successfully!"
    )


if __name__ == "__main__":
    run_daily_sync()
