"""
Automated Data Synchronization Script for NSE Momentum Terminal.
Executed locally or via GitHub Actions at 9:00 PM IST.
"""

import os
import sys
from datetime import datetime

# Determine if a full 2‑year refresh is required (weekly run)
FORCE_FULL = os.getenv("FORCE_FULL", "false").lower() == "true"
# Ensure repository root is in python path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from src.loaders.delivery_loader import fetch_delivery_data
from src.loaders.indices_loader import fetch_indices_data, sync_official_nse_indices
from src.loaders.mcap_loader import fetch_market_caps
from src.loaders.price_loader import fetch_price_history
from src.loaders.tv_loader import reconcile_and_update_tv_classification


def run_daily_sync() -> None:
    """Synchronizes all NSE market data, constituents, price histories, and delivery archives."""
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
    mcaps = fetch_market_caps(symbols, force_refresh=FORCE_FULL)
    print(f"Market cap cache updated for {len(mcaps)} tickers.")

    # 5b. Commit the result to the repository.
    # This job runs on GitHub Actions, where NSE is reachable. Production runs
    # on Streamlit Cloud, whose IP NSE refuses, so it cannot fetch the PR
    # archive itself and would otherwise fall back to 750 individual yfinance
    # lookups -- the slowest stage of a cold start. Writing the snapshot here
    # lets production read what this job already paid for.
    from src.core import startup_metrics as _metrics

    _facts = _metrics.snapshot().get("facts", {})
    _mcap_path = str(_facts.get("mcap_path") or "unknown")
    _as_of = _facts.get("mcap_pr_date")

    if _mcap_path == "repo_snapshot":
        # The loader fell through to the file THIS JOB wrote last time, which
        # means nothing new was fetched. Rewriting it would launder a stale
        # snapshot as a fresh one and reset nothing but the commit date.
        #
        # This is not hypothetical: on 2026-08-18 the 22:00 IST slot fired at
        # 22:29 and NSE had not yet published the PR archive -- the same file
        # fetched cleanly at 22:51 -- so the job read its own output and wrote
        # it straight back. A closed loop with no signal that the fetch failed.
        print(
            "::warning::Market caps came from the repository snapshot, not a "
            "fresh NSE fetch. The PR archive was unavailable at this hour. "
            "Leaving the snapshot untouched rather than re-committing stale "
            "data as if it were new."
        )
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

    # 6. Fetch delivery archives
    print("\n--- 6. Fetching NSE Delivery Bhavcopy Archives ---")
    deliv = fetch_delivery_data(force_refresh=FORCE_FULL)
    print(f"Delivery archive cache updated with {len(deliv)} records.")

    print(
        f"\n[{datetime.now():%Y-%m-%d %H:%M:%S}] All daily sync tasks completed successfully!"
    )


if __name__ == "__main__":
    run_daily_sync()
