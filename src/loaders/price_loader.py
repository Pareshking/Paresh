"""
Price history and OHLCV downloader with parquet caching and market regime detector.
"""

import os
import tempfile
import time
from datetime import datetime
from typing import List, Optional, Tuple, Union
import pandas as pd
import streamlit as st
import yfinance as yf

from src.core.config import PRICES_FILE
from src.core.logger import logger
from src.core.types import MarketRegime, RegimeData

# Configure yfinance timezone cache
try:
    _tz_cache_dir = os.path.join(tempfile.gettempdir(), "yf_tz_cache")
    os.makedirs(_tz_cache_dir, exist_ok=True)
    yf.set_tz_cache_location(_tz_cache_dir)
except Exception:
    pass


def _is_fresh(last_date: Union[datetime, pd.Timestamp, str]) -> bool:
    """Checks if the latest price date is <= 3 calendar days ago."""
    if isinstance(last_date, (pd.Timestamp, datetime)):
        dt = last_date.date()
    elif isinstance(last_date, str):
        dt = pd.to_datetime(last_date).date()
    else:
        return False
    return (datetime.now().date() - dt).days <= 3


def _extract_field(df: pd.DataFrame, field_names: List[str]) -> pd.DataFrame:
    """Extracts a specific price field across all symbols from any DataFrame layout."""
    if df is None or df.empty:
        return pd.DataFrame()

    if not isinstance(df.columns, pd.MultiIndex):
        # Flat DataFrame
        return df

    # Check MultiIndex level 1 (Ticker on lvl 0, Field on lvl 1)
    if df.columns.nlevels > 1:
        lvl1_vals = [str(x).strip().lower() for x in df.columns.get_level_values(1)]
        for target in field_names:
            t_low = target.lower()
            if t_low in lvl1_vals:
                idx = lvl1_vals.index(t_low)
                actual_label = df.columns.get_level_values(1)[idx]
                extracted = df.xs(actual_label, level=1, axis=1)
                extracted.columns = [str(c).replace(".NS", "").strip().upper() for c in extracted.columns]
                return extracted

        # Check MultiIndex level 0 (Field on lvl 0, Ticker on lvl 1)
        lvl0_vals = [str(x).strip().lower() for x in df.columns.get_level_values(0)]
        for target in field_names:
            t_low = target.lower()
            if t_low in lvl0_vals:
                idx = lvl0_vals.index(t_low)
                actual_label = df.columns.get_level_values(0)[idx]
                extracted = df.xs(actual_label, level=0, axis=1)
                extracted.columns = [str(c).replace(".NS", "").strip().upper() for c in extracted.columns]
                return extracted

    return pd.DataFrame(index=df.index)


def _clean_price_df(df: pd.DataFrame, symbols: Optional[List[str]] = None) -> pd.DataFrame:
    """Cleans trailing empty rows, deduplicates columns, and filters valid symbols."""
    if df is None or df.empty:
        return pd.DataFrame()
    out = df.loc[:, ~df.columns.duplicated()]
    # Drop rows at the end that are all NaN
    valid_idx = out.dropna(how="all").index
    if not valid_idx.empty:
        out = out.loc[:valid_idx[-1]]
    out = out.ffill()
    if symbols:
        valid_cols = [s.upper() for s in symbols if s.upper() in out.columns]
        if valid_cols:
            out = out[valid_cols]
    return out


def extract_ohlcv(
    prices_df: pd.DataFrame,
    symbols: Optional[List[str]] = None,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Extracts (Adj Close, Close, High, Low, Volume) DataFrames from raw yfinance price data.
    """
    if prices_df is None or prices_df.empty:
        empty = pd.DataFrame()
        return empty, empty, empty, empty, empty

    adj_close = _extract_field(prices_df, ["Adj Close", "AdjClose", "Close"])
    close_p = _extract_field(prices_df, ["Close", "Adj Close", "AdjClose"])
    high_p = _extract_field(prices_df, ["High"])
    low_p = _extract_field(prices_df, ["Low"])
    vol_p = _extract_field(prices_df, ["Volume", "Vol"])

    # Fallbacks if some fields missing
    if adj_close.empty and not close_p.empty:
        adj_close = close_p.copy()
    if close_p.empty and not adj_close.empty:
        close_p = adj_close.copy()
    if high_p.empty and not close_p.empty:
        high_p = close_p.copy()
    if low_p.empty and not close_p.empty:
        low_p = close_p.copy()
    if vol_p.empty and not close_p.empty:
        vol_p = pd.DataFrame(0.0, index=close_p.index, columns=close_p.columns)

    adj_close = _clean_price_df(adj_close, symbols)
    close_p = _clean_price_df(close_p, symbols)
    high_p = _clean_price_df(high_p, symbols)
    low_p = _clean_price_df(low_p, symbols)
    vol_p = _clean_price_df(vol_p, symbols)

    return adj_close, close_p, high_p, low_p, vol_p


def fetch_price_history(
    symbols: List[str],
    period: str = "2y",
    force_refresh: bool = False,
) -> pd.DataFrame:
    """
    Downloads daily historical OHLCV data for symbols using yfinance with parquet caching.
    """
    if not symbols:
        return pd.DataFrame()

    # ── Check Disk Cache ──
    if not force_refresh and os.path.exists(PRICES_FILE):
        try:
            df = pd.read_parquet(PRICES_FILE)
            if not df.empty and _is_fresh(df.index[-1]):
                if isinstance(df.columns, pd.MultiIndex):
                    existing = {
                        str(c).replace(".NS", "").upper()
                        for c in df.columns.get_level_values(0).unique()
                    }
                else:
                    existing = {str(c).replace(".NS", "").upper() for c in df.columns}
                if not ({s.upper() for s in symbols} - existing):
                    logger.info(f"Price cache hit: {len(existing)} stocks")
                    return df
                logger.info("Price cache incomplete — fetching missing tickers")
        except Exception as e:
            logger.warning(f"Price cache read failed: {e}")

    # ── Batch Download ──
    yf_symbols = [s + ".NS" if not s.upper().endswith(".NS") else s for s in symbols]
    logger.info(f"Downloading prices for {len(yf_symbols)} stocks (period={period})…")

    BATCH_SIZE = 100
    all_batches = []
    for batch_start in range(0, len(yf_symbols), BATCH_SIZE):
        batch = yf_symbols[batch_start : batch_start + BATCH_SIZE]
        batch_num = batch_start // BATCH_SIZE + 1
        total_batches = (len(yf_symbols) + BATCH_SIZE - 1) // BATCH_SIZE
        logger.debug(f"Downloading batch {batch_num}/{total_batches} ({len(batch)} tickers)")

        try:
            batch_data = yf.download(
                batch,
                period=period,
                progress=False,
                group_by="ticker",
                threads=True,
            )
            if batch_data is not None and not batch_data.empty:
                all_batches.append(batch_data)
        except Exception as e:
            logger.warning(f"Batch {batch_num} error: {e}")

        if batch_start + BATCH_SIZE < len(yf_symbols):
            time.sleep(1.5)

    if not all_batches:
        logger.error("All price download batches returned empty")
        return pd.DataFrame()

    data = pd.concat(all_batches, axis=1) if len(all_batches) > 1 else all_batches[0]

    # Retry missing symbols individually
    if isinstance(data.columns, pd.MultiIndex) and not data.empty:
        got = set(data.columns.get_level_values(0).unique())
        missing = [t for t in yf_symbols if t not in got]
        if missing:
            logger.info(f"Retrying {len(missing)} missing tickers individually…")
            for tkr in missing:
                try:
                    s = yf.download(tkr, period=period, progress=False, threads=False)
                    if not s.empty:
                        if s.index.tz is not None:
                            s.index = s.index.tz_localize(None)
                        if isinstance(s.columns, pd.MultiIndex):
                            lvl0 = s.columns.get_level_values(0).tolist()
                            lvl1 = s.columns.get_level_values(1).tolist()
                            price_fields = {"Open", "High", "Low", "Close", "Adj Close", "Volume"}
                            if all(v in price_fields for v in lvl1):
                                mi = pd.MultiIndex.from_arrays(
                                    [[tkr] * len(lvl1), lvl1], names=["Ticker", "Price"]
                                )
                            else:
                                mi = pd.MultiIndex.from_arrays(
                                    [[tkr] * len(lvl0), lvl0], names=["Ticker", "Price"]
                                )
                            s.columns = mi
                        else:
                            mi = pd.MultiIndex.from_product(
                                [[tkr], s.columns], names=["Ticker", "Price"]
                            )
                            s.columns = mi
                        data = pd.concat([data, s], axis=1)
                except Exception as ex:
                    logger.debug(f"Failed retry for {tkr}: {ex}")

    if data.empty:
        return data

    # Clean timezones and deduplicate index
    if data.index.tz is not None:
        data.index = data.index.tz_localize(None)
    if data.index.duplicated().any():
        data = data[~data.index.duplicated(keep="last")]

    # Normalize column names
    if isinstance(data.columns, pd.MultiIndex):
        tickers = [str(c).replace(".NS", "").strip().upper() for c in data.columns.get_level_values(0)]
        prices = list(data.columns.get_level_values(1))
        names = data.columns.names if data.columns.names[0] else ["Ticker", "Price"]
        data.columns = pd.MultiIndex.from_arrays([tickers, prices], names=names)
    else:
        data.columns = [str(c).replace(".NS", "").strip().upper() for c in data.columns]

    data = data.dropna(how="all")

    # Save to parquet cache
    try:
        data.to_parquet(PRICES_FILE, compression="snappy")
        logger.info(f"Price cache saved: {len(data)} rows ({len(data.columns)} series)")
    except Exception as e:
        logger.warning(f"Price cache save failed: {e}")

    return data


@st.cache_data(show_spinner=False, ttl=3600)
def get_market_regime(benchmark_symbol: str = "^CRSLDX") -> RegimeData:
    """
    Computes market regime by comparing benchmark index price with its 200 DMA.
    Falls back to Nifty 50 (^NSEI) if Nifty 500 (^CRSLDX) is unavailable.
    """
    try:
        nifty = yf.download(benchmark_symbol, period="1y", progress=False)
        if nifty.empty and benchmark_symbol != "^NSEI":
            nifty = yf.download("^NSEI", period="1y", progress=False)

        if nifty.empty:
            return RegimeData(status=MarketRegime.UNKNOWN, current_price=0.0, dma_200=0.0, distance_pct=0.0)

        if nifty.index.tz is not None:
            nifty.index = nifty.index.tz_localize(None)

        if isinstance(nifty.columns, pd.MultiIndex):
            close_df = _extract_field(nifty, ["Close", "Adj Close", "AdjClose"])
            close_s = close_df.iloc[:, 0] if not close_df.empty else nifty.iloc[:, 0]
        else:
            close_s = nifty["Close"] if "Close" in nifty.columns else nifty.iloc[:, 0]

        price = float(close_s.iloc[-1])
        dma = float(close_s.rolling(200, min_periods=100).mean().iloc[-1])
        dist = ((price - dma) / dma * 100) if dma > 0 else 0.0
        status = MarketRegime.BULLISH if price >= dma else MarketRegime.BEARISH

        return RegimeData(
            status=status,
            current_price=price,
            dma_200=dma,
            distance_pct=dist,
        )
    except Exception as e:
        logger.warning(f"Failed to fetch market regime: {e}")
        return RegimeData(status=MarketRegime.UNKNOWN, current_price=0.0, dma_200=0.0, distance_pct=0.0)
