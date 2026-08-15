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

    # 6. Fetch delivery archives
    print("\n--- 6. Fetching NSE Delivery Bhavcopy Archives ---")
    deliv = fetch_delivery_data(force_refresh=FORCE_FULL)
    print(f"Delivery archive cache updated with {len(deliv)} records.")

    print(
        f"\n[{datetime.now():%Y-%m-%d %H:%M:%S}] All daily sync tasks completed successfully!"
    )


if __name__ == "__main__":
    run_daily_sync()
