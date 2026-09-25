"""
Market Breadth analytics: Moving Average Breadth and 52W High/Low Time Series.
"""

from __future__ import annotations

from typing import Any, Sequence

import numpy as np
import pandas as pd
import streamlit as st


# Suffix marking the companion count column for a breadth series.
OBSERVED_SUFFIX: str = "__observed"


@st.cache_data(show_spinner=False, ttl=3600)
def compute_ma_breadth(
    prices_hash: str,
    _prices: pd.DataFrame,
    sel_mas: Sequence[str],
    lookback: int = 126,
    ma_type: str = "SMA",
) -> pd.DataFrame:
    """Computes the % of stocks above specified moving averages over time."""
    if _prices is None or _prices.empty:
        return pd.DataFrame()

    ma_periods = {"10D": 10, "20D": 20, "50D": 50, "100D": 100, "200D": 200}
    results: dict[str, pd.Series] = {}

    for label in sel_mas:
        period = ma_periods.get(label, 50)
        mp = max(int(period * 0.8), 5)
        if ma_type == "EMA":
            ma = _prices.ewm(span=period, min_periods=mp).mean()
        else:
            ma = _prices.rolling(period, min_periods=mp).mean()

        # A stock that did not print is not a stock below its moving average.
        # `_prices > ma` is False wherever either side is NaN, and mean(axis=1)
        # then divided by the FULL column count -- so every missing print was
        # counted as a failure. Yahoo holes a median of 33 symbols per session
        # in this universe and 135 on 2026-07-21, so the reading was biased
        # down by roughly 4% on an ordinary day and 18% on a bad one, on a
        # number read as a market-regime signal.
        #
        # Mask the unobserved cells to NaN; mean(axis=1) skips them, which
        # divides by the stocks that actually have both a price and an MA.
        observed = _prices.notna() & ma.notna()
        above = (_prices > ma).where(observed).astype(float)
        results[label] = above.iloc[-lookback:].mean(axis=1) * 100
        # The DENOMINATOR, published alongside the percentage. Changing the
        # engine to divide by the observed stocks silently invalidated its only
        # caller, which still multiplied the ratio by the full column count and
        # printed a stock count that was wrong on 113 of 252 sessions (max 83
        # stocks out). A ratio without its denominator is not enough to render.
        results[f"{label}{OBSERVED_SUFFIX}"] = observed.iloc[-lookback:].sum(axis=1)

    return pd.DataFrame(results)


@st.cache_data(show_spinner=False, ttl=3600)
def compute_hl_timeseries(
    prices_hash: str,
    _prices: pd.DataFrame,
    window: int = 252,
    lookback: int = 126,
) -> pd.DataFrame:
    """
    Computes daily new highs and new lows time series over rolling window.
    """
    if _prices is None or _prices.empty:
        return pd.DataFrame()

    min_p = max(int(window * 0.6), 20)
    high_w = _prices.rolling(window, min_periods=min_p).max()
    low_w = _prices.rolling(window, min_periods=min_p).min()

    tol = _prices * 0.001
    is_high = (_prices >= high_w - tol).astype(float)
    is_low = (_prices <= low_w + tol).astype(float)

    # The denominator is the stocks that COULD register a high or low today:
    # a price and enough history for the rolling window. Counting every stock
    # with a price divided by names that cannot yet have a 52-week high, which
    # biased both percentages down -- the same error compute_ma_breadth fixed.
    n_stocks = (_prices.notna() & high_w.notna() & low_w.notna()).sum(axis=1)
    daily_highs = is_high.sum(axis=1)
    daily_lows = is_low.sum(axis=1)

    df = pd.DataFrame(
        {
            "New Highs": daily_highs,
            "New Lows": daily_lows,
            "Total Stocks": n_stocks,
            "% New Highs": (daily_highs / n_stocks.replace(0, np.nan) * 100).round(2).fillna(0),
            "% New Lows": (daily_lows / n_stocks.replace(0, np.nan) * 100).round(2).fillna(0),
            "Net New Highs": daily_highs - daily_lows,
        }
    )
    return df.iloc[-lookback:]


def get_recent_hl_events(
    prices_df: pd.DataFrame,
    rank_df: pd.DataFrame,
    window: int = 252,
    lookback: int = 20,
) -> pd.DataFrame:
    """Finds exact stocks hitting new highs or new lows with dates, CMP, and industry."""
    if prices_df is None or prices_df.empty:
        return pd.DataFrame()

    min_p = max(int(window * 0.6), 20)
    high_w = prices_df.rolling(window, min_periods=min_p).max()
    low_w = prices_df.rolling(window, min_periods=min_p).min()

    tol = prices_df * 0.001
    is_high = prices_df >= high_w - tol
    is_low = prices_df <= low_w + tol

    sub_high = is_high.iloc[-lookback:]
    sub_low = is_low.iloc[-lookback:]

    ind_map = (
        rank_df.set_index("Symbol")["Industry"].to_dict()
        if "Industry" in rank_df.columns
        else {}
    )
    ret_map = (
        rank_df.set_index("Symbol")["3M Return"].to_dict()
        if "3M Return" in rank_df.columns
        else {}
    )
    rk_map = (
        rank_df.set_index("Symbol")["Rank"].to_dict()
        if "Rank" in rank_df.columns
        else {}
    )

    records: list[dict[str, Any]] = []
    for dt in reversed(sub_high.index):
        dt_str = pd.to_datetime(dt).strftime("%d %b %Y")
        # Highs
        h_series = sub_high.loc[dt]
        for sym in h_series[h_series].index:
            cmp_val = (
                float(prices_df.loc[dt, sym]) if sym in prices_df.columns else np.nan
            )
            records.append(
                {
                    "Date": dt_str,
                    "Event": "🟢 52W High",
                    "Symbol": sym,
                    "Industry": ind_map.get(sym, "—"),
                    "CMP": cmp_val,
                    "3M Return": ret_map.get(sym, np.nan),
                    "Rank": rk_map.get(sym, np.nan),
                }
            )
        # Lows
        l_series = sub_low.loc[dt]
        for sym in l_series[l_series].index:
            cmp_val = (
                float(prices_df.loc[dt, sym]) if sym in prices_df.columns else np.nan
            )
            records.append(
                {
                    "Date": dt_str,
                    "Event": "🔴 52W Low",
                    "Symbol": sym,
                    "Industry": ind_map.get(sym, "—"),
                    "CMP": cmp_val,
                    "3M Return": ret_map.get(sym, np.nan),
                    "Rank": rk_map.get(sym, np.nan),
                }
            )

    return pd.DataFrame(records)
