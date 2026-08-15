"""
Market Capitalization loader with 3-tier fallback architecture:
1. NSE PR Bhavcopy zip (single request covering ~2800 stocks)
2. Cached yfinance market caps (parquet)
3. Multi-threaded live yfinance scraper with multiple fallbacks
"""

import concurrent.futures
import io
import os
import time
import zipfile
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import numpy as np
import pandas as pd
import requests
import yfinance as yf

from src.core.config import MCAP_PR_FILE, MCAPS_FILE, HTTP_HEADERS
from src.core.logger import logger


def _fetch_mcap_from_pr_zip(target_date: datetime) -> Dict[str, float]:
    """Download NSE Bhavcopy PR zip and extract mcap*.csv."""
    zip_date = target_date.strftime("%d%m%y")
    csv_date = target_date.strftime("%d%m%Y")
    zip_url = f"https://archives.nseindia.com/archives/equities/bhavcopy/pr/PR{zip_date}.zip"
    csv_filename = f"mcap{csv_date}.csv"

    try:
        resp = requests.get(zip_url, headers=HTTP_HEADERS, timeout=15)
        if resp.status_code != 200:
            return {}

        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            names = zf.namelist()
            match = (
                csv_filename
                if csv_filename in names
                else next((n for n in names if n.lower().startswith("mcap")), None)
            )
            if not match:
                return {}

            with zf.open(match) as f:
                df = pd.read_csv(f)

        df.columns = df.columns.str.strip()
        col_sym = next((c for c in df.columns if "symbol" in c.lower()), None)
        col_mcap = next((c for c in df.columns if "market cap" in c.lower()), None)

        if not col_sym or not col_mcap:
            return {}

        df[col_sym] = df[col_sym].astype(str).str.strip().str.upper()
        df[col_mcap] = pd.to_numeric(
            df[col_mcap].astype(str).str.strip().str.replace(",", ""),
            errors="coerce",
        )
        df = df[df[col_mcap].notna() & (df[col_mcap] > 0)]

        result = df.set_index(col_sym)[col_mcap].to_dict()
        logger.info(f"Loaded NSE PR market cap: {len(result)} stocks for {target_date.date()}")
        return result
    except Exception as e:
        logger.debug(f"PR mcap fetch failed for {target_date.date()}: {e}")
        return {}


def _is_mcap_cache_fresh() -> bool:
    if not os.path.exists(MCAP_PR_FILE):
        return False
    try:
        df = pd.read_parquet(MCAP_PR_FILE)
        if df.empty:
            return False
        last = pd.Timestamp(df["LastUpdated"].max())
        return (datetime.now() - last).total_seconds() < 108000  # 30 hours
    except Exception:
        return False


def _fetch_single_mcap(symbol: str) -> Tuple[str, float]:
    """Single ticker market cap fetcher with 3 fallbacks."""
    time.sleep(0.04)
    ticker_name = symbol + ".NS" if not symbol.endswith(".NS") else symbol
    tkr = yf.Ticker(ticker_name)

    # Method 1: fast_info.market_cap
    try:
        mcap = getattr(tkr.fast_info, "market_cap", None)
        if mcap and not (isinstance(mcap, float) and np.isnan(mcap)):
            return symbol, float(mcap)
    except Exception:
        pass

    # Method 2: price * shares
    try:
        p = getattr(tkr.fast_info, "last_price", None)
        s = getattr(tkr.fast_info, "shares", None)
        if p and s:
            return symbol, float(p * s)
    except Exception:
        pass

    # Method 3: info dict
    try:
        mcap = tkr.info.get("marketCap")
        if mcap:
            return symbol, float(mcap)
    except Exception:
        pass

    return symbol, np.nan


def _fetch_mcaps_yfinance(symbols: List[str]) -> Dict[str, float]:
    """Multi-threaded yfinance market cap scraper."""
    if not symbols:
        return {}

    result = {}
    failed = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        futs = {pool.submit(_fetch_single_mcap, s): s for s in symbols}
        for f in concurrent.futures.as_completed(futs):
            try:
                sym, mc = f.result(timeout=25)
                if mc is not None and not np.isnan(mc):
                    result[sym] = mc
                else:
                    failed.append(futs[f])
            except Exception:
                failed.append(futs[f])

    for sym in failed:
        try:
            _, mc = _fetch_single_mcap(sym)
            if mc is not None and not np.isnan(mc):
                result[sym] = mc
        except Exception:
            pass

    return result


def fetch_market_caps(symbols: List[str], force_refresh: bool = False) -> pd.Series:
    """
    Fetches market caps in Rs for requested symbols.
    """
    master: Dict[str, float] = {}

    # Layer 1: NSE PR cache
    if not force_refresh and _is_mcap_cache_fresh():
        try:
            cache = pd.read_parquet(MCAP_PR_FILE)
            master = cache.set_index("Symbol")["MarketCap"].to_dict()
            logger.info(f"NSE PR market cap cache hit: {len(master)} stocks")
        except Exception as e:
            logger.warning(f"NSE PR cache read error: {e}")
            master = {}

    # Layer 1b: Live NSE PR Bhavcopy zip
    if not master:
        logger.info("Attempting live NSE PR zip for market caps…")
        for i in range(7):
            td = datetime.now() - timedelta(days=i)
            if td.weekday() >= 5:
                continue
            nse_map = _fetch_mcap_from_pr_zip(td)
            if nse_map:
                master.update(nse_map)
                try:
                    cache_df = pd.DataFrame([
                        {"Symbol": k, "MarketCap": v, "LastUpdated": datetime.now()}
                        for k, v in nse_map.items()
                    ])
                    cache_df.to_parquet(MCAP_PR_FILE, compression="snappy")
                except Exception:
                    pass
                break

    # Layer 2: yfinance disk cache
    missing = [s for s in symbols if s not in master]
    if missing and not force_refresh and os.path.exists(MCAPS_FILE):
        try:
            yf_cache = pd.read_parquet(MCAPS_FILE)
            yf_cache["LastUpdated"] = pd.to_datetime(yf_cache["LastUpdated"])
            cutoff = datetime.now() - timedelta(hours=30)
            fresh = yf_cache[
                yf_cache["Symbol"].isin(missing) & (yf_cache["LastUpdated"] > cutoff)
            ]
            if not fresh.empty:
                yf_cached_map = fresh.set_index("Symbol")["MarketCap"].to_dict()
                master.update(yf_cached_map)
                missing = [s for s in symbols if s not in master]
        except Exception as e:
            logger.warning(f"yfinance mcap cache read error: {e}")

    # Layer 3: Live yfinance fetch
    if missing:
        logger.info(f"Fetching market caps from yfinance for {len(missing)} stocks…")
        yf_map = _fetch_mcaps_yfinance(missing)
        master.update(yf_map)

        if yf_map:
            try:
                new_rows = pd.DataFrame([
                    {"Symbol": k, "MarketCap": v, "LastUpdated": datetime.now()}
                    for k, v in yf_map.items()
                ])
                if os.path.exists(MCAPS_FILE):
                    existing = pd.read_parquet(MCAPS_FILE)
                    existing = existing[~existing["Symbol"].isin(yf_map.keys())]
                    updated = pd.concat([existing, new_rows], ignore_index=True)
                else:
                    updated = new_rows
                updated.to_parquet(MCAPS_FILE, compression="snappy")
            except Exception:
                pass

    vmap = {s: master[s] for s in symbols if s in master}
    return pd.Series(vmap)
