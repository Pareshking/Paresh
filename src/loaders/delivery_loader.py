"""
NSE Delivery & Bhavcopy Volume Loader with institutional accumulation surge metrics.
"""

import concurrent.futures
import io
import json
import os
from datetime import datetime, timedelta
from threading import Semaphore
from typing import Dict, Optional, Tuple
import numpy as np
import pandas as pd
import requests
import streamlit as st

from src.core.config import DELIVERY_FILE, DELIVERY_META_FILE, MCAP_PR_FILE, HTTP_HEADERS
from src.core.logger import logger

_MAX_WORKERS = 4
_RATE_LIMIT = Semaphore(_MAX_WORKERS)
KEEP_COLS = ["SYMBOL", "DATE1", "CLOSE_PRICE", "PREV_CLOSE", "TTL_TRD_QNTY", "DELIV_PER", "DELIV_QTY"]


def _write_meta(last_date_str: str, n_days: int, n_symbols: int) -> None:
    try:
        with open(DELIVERY_META_FILE, "w") as f:
            json.dump({
                "last_date": last_date_str,
                "n_days": n_days,
                "n_symbols": n_symbols,
                "saved_at": datetime.now().isoformat(),
            }, f)
    except Exception as e:
        logger.warning(f"Delivery meta write error: {e}")


def _read_meta() -> Optional[Dict]:
    try:
        with open(DELIVERY_META_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return None


def is_delivery_cache_fresh() -> bool:
    if not os.path.exists(DELIVERY_FILE):
        return False
    meta = _read_meta()
    if not meta:
        return False
    try:
        last = datetime.strptime(meta["last_date"], "%Y-%m-%d").date()
        return (datetime.now().date() - last).days <= 3
    except Exception:
        return False


def _fetch_single_day(target_date: datetime) -> Tuple[datetime, Optional[pd.DataFrame]]:
    date_str = target_date.strftime("%d%m%Y")
    url = f"https://nsearchives.nseindia.com/products/content/sec_bhavdata_full_{date_str}.csv"

    with _RATE_LIMIT:
        try:
            resp = requests.get(url, headers=HTTP_HEADERS, timeout=15)
            if resp.status_code != 200:
                return target_date, None

            df = pd.read_csv(io.StringIO(resp.text))
            df.columns = [c.strip() for c in df.columns]

            # Filter EQ series only
            df = df[df["SERIES"].astype(str).str.strip().isin(["EQ"])].copy()
            if df.empty:
                return target_date, None

            num_cols = ["CLOSE_PRICE", "PREV_CLOSE", "TTL_TRD_QNTY", "DELIV_PER", "DELIV_QTY"]
            for col in num_cols:
                if col in df.columns:
                    df[col] = df[col].astype(str).str.replace(",", "").str.strip()
                    df[col] = pd.to_numeric(df[col], errors="coerce")

            df["SYMBOL"] = df["SYMBOL"].astype(str).str.strip().str.upper()
            df["DATE1"] = target_date.date()
            df["Price_Chg_%"] = ((df["CLOSE_PRICE"] - df["PREV_CLOSE"]) / df["PREV_CLOSE"]) * 100

            keep = [c for c in KEEP_COLS + ["Price_Chg_%"] if c in df.columns]
            return target_date, df[keep]
        except Exception:
            return target_date, None


@st.cache_data(show_spinner=False, ttl=3600)
def fetch_delivery_data(lookback_calendar_days: int = 65) -> pd.DataFrame:
    """Fetches and consolidates NSE bhavcopy daily archives."""
    if is_delivery_cache_fresh():
        try:
            df = pd.read_parquet(DELIVERY_FILE)
            meta = _read_meta() or {}
            logger.info(
                f"Delivery cache hit: {meta.get('n_days', '?')} days, {meta.get('n_symbols', '?')} symbols"
            )
            return df
        except Exception as e:
            logger.warning(f"Delivery cache read failed: {e}")

    logger.info(f"Downloading {lookback_calendar_days} calendar days of delivery archives from NSE…")
    today = datetime.now()
    target_dates = [
        today - timedelta(days=i)
        for i in range(lookback_calendar_days)
        if (today - timedelta(days=i)).weekday() < 5
    ]

    all_data = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=_MAX_WORKERS) as pool:
        futures = {pool.submit(_fetch_single_day, d): d for d in target_dates}
        for fut in concurrent.futures.as_completed(futures):
            try:
                _, day_df = fut.result(timeout=20)
                if day_df is not None:
                    all_data.append(day_df)
            except Exception:
                pass

    if not all_data:
        logger.error("No delivery data fetched from NSE")
        return pd.DataFrame()

    master = pd.concat(all_data, ignore_index=True).sort_values(["SYMBOL", "DATE1"])

    try:
        master.to_parquet(DELIVERY_FILE, compression="snappy")
        _write_meta(str(master["DATE1"].max()), master["DATE1"].nunique(), master["SYMBOL"].nunique())
        logger.info(f"Delivery cached: {master['DATE1'].nunique()} trading days, {master['SYMBOL'].nunique()} stocks")
    except Exception as e:
        logger.warning(f"Delivery cache write failed: {e}")

    return master


@st.cache_data(show_spinner=False, ttl=86400)
def _load_nse_mcap_cached() -> Dict[str, float]:
    """Loads cached NSE PR market caps in Crores."""
    if not os.path.exists(MCAP_PR_FILE):
        return {}
    try:
        df = pd.read_parquet(MCAP_PR_FILE)
        return (df.set_index("Symbol")["MarketCap"] / 1e7).round(0).to_dict()
    except Exception:
        return {}


@st.cache_data(show_spinner=False, ttl=3600)
def compute_delivery_metrics(_master_df: pd.DataFrame) -> pd.DataFrame:
    """Computes daily and 20D rolling delivery and volume surge ratios."""
    if _master_df is None or _master_df.empty:
        return pd.DataFrame()

    nse_mcap = _load_nse_mcap_cached()
    df = _master_df.sort_values(["SYMBOL", "DATE1"]).copy()

    grp = df.groupby("SYMBOL")
    df["Del%_20D"] = grp["DELIV_PER"].transform(lambda x: x.rolling(20, min_periods=15).mean())
    df["Vol_20D"] = grp["TTL_TRD_QNTY"].transform(lambda x: x.rolling(20, min_periods=15).mean())
    if "DELIV_QTY" in df.columns:
        df["DelQty_20D"] = grp["DELIV_QTY"].transform(lambda x: x.rolling(20, min_periods=15).mean())

    df["Del%_Prev20D"] = grp["Del%_20D"].transform(lambda x: x.shift(20))
    df["Vol_Prev20D"] = grp["Vol_20D"].transform(lambda x: x.shift(20))

    latest_date = df["DATE1"].max()
    latest = df[df["DATE1"] == latest_date].copy()
    if latest.empty:
        return pd.DataFrame()

    latest["Del_Surge_Daily"] = (latest["DELIV_PER"] / latest["Del%_20D"].replace(0, np.nan)).round(2)
    latest["Vol_Surge_Daily"] = (latest["TTL_TRD_QNTY"] / latest["Vol_20D"].replace(0, np.nan)).round(2)
    latest["Del_Surge_20D"] = (latest["Del%_20D"] / latest["Del%_Prev20D"].replace(0, np.nan)).round(2)
    latest["Vol_Surge_20D"] = (latest["Vol_20D"] / latest["Vol_Prev20D"].replace(0, np.nan)).round(2)

    latest = latest.rename(columns={
        "CLOSE_PRICE": "CMP",
        "TTL_TRD_QNTY": "Volume",
        "DELIV_PER": "Del %",
        "Price_Chg_%": "Day Chg %",
        "Del%_20D": "Del% 20D Avg",
        "Vol_20D": "Vol 20D Avg",
        "Del%_Prev20D": "Del% Prev20D",
    })

    latest["Data Date"] = latest_date
    if nse_mcap:
        latest["Market Cap (Cr)"] = latest["SYMBOL"].map(nse_mcap)

    return latest.sort_values("Del_Surge_Daily", ascending=False).reset_index(drop=True)
