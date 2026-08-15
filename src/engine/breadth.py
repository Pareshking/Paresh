"""
Market Breadth analytics: Moving Average Breadth and 52W High/Low Time Series.
"""


import numpy as np
import pandas as pd
import streamlit as st


@st.cache_data(show_spinner=False, ttl=3600)
def compute_ma_breadth(
    prices_hash: str,
    _prices: pd.DataFrame,
    sel_mas: tuple[str, ...],
    lookback: int = 126,
    ma_type: str = "SMA",
) -> pd.DataFrame:
    """Computes the % of stocks above specified moving averages over time."""
    if _prices is None or _prices.empty:
        return pd.DataFrame()

    ma_periods = {"10D": 10, "20D": 20, "50D": 50, "100D": 100, "200D": 200}
    results = {}

    for label in sel_mas:
        period = ma_periods.get(label, 50)
        mp = max(int(period * 0.8), 5)
        if ma_type == "EMA":
            ma = _prices.ewm(span=period, min_periods=mp).mean()
        else:
            ma = _prices.rolling(period, min_periods=mp).mean()

        above = (_prices > ma).astype(float)
        results[label] = above.iloc[-lookback:].mean(axis=1) * 100

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

    n_stocks = _prices.notna().sum(axis=1)
    daily_highs = is_high.sum(axis=1)
    daily_lows = is_low.sum(axis=1)

    df = pd.DataFrame({
        "New Highs": daily_highs,
        "New Lows": daily_lows,
        "Total Stocks": n_stocks,
        "% New Highs": (daily_highs / n_stocks * 100).round(2),
        "% New Lows": (daily_lows / n_stocks * 100).round(2),
        "Net New Highs": daily_highs - daily_lows,
    })
    return df.iloc[-lookback:]


def compute_industry_breadth(
    prices_df: pd.DataFrame,
    industry_map: dict[str, str],
    period: int = 50,
    ma_type: str = "EMA",
) -> pd.Series:
    """Computes the % of stocks in each industry above a specific moving average."""
    if prices_df.empty:
        return pd.Series(dtype=float)

    if ma_type == "EMA":
        ma = prices_df.ewm(span=period, min_periods=max(int(period * 0.8), 5)).mean()
    else:
        ma = prices_df.rolling(period, min_periods=max(int(period * 0.8), 5)).mean()

    above_ma = (prices_df.iloc[-1] > ma.iloc[-1])
    ind_breadth: dict[str, list[float]] = {}
    for sym, val in above_ma.items():
        ind = industry_map.get(sym)
        if ind:
            ind_breadth.setdefault(ind, []).append(float(val))

    return pd.Series({k: np.mean(v) * 100 for k, v in ind_breadth.items()}).sort_values(ascending=False)


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
    is_high = (prices_df >= high_w - tol)
    is_low = (prices_df <= low_w + tol)

    sub_high = is_high.iloc[-lookback:]
    sub_low = is_low.iloc[-lookback:]

    ind_map = rank_df.set_index("Symbol")["Industry"].to_dict() if "Industry" in rank_df.columns else {}
    ret_map = rank_df.set_index("Symbol")["3M Return"].to_dict() if "3M Return" in rank_df.columns else {}
    rk_map = rank_df.set_index("Symbol")["Rank"].to_dict() if "Rank" in rank_df.columns else {}

    records = []
    for dt in reversed(sub_high.index):
        dt_str = pd.to_datetime(dt).strftime("%d %b %Y")
        # Highs
        h_series = sub_high.loc[dt]
        for sym in h_series[h_series].index:
            cmp_val = float(prices_df.loc[dt, sym]) if sym in prices_df.columns else np.nan
            records.append({
                "Date": dt_str,
                "Event": "🟢 52W High",
                "Symbol": sym,
                "Industry": ind_map.get(sym, "—"),
                "CMP": cmp_val,
                "3M Return": ret_map.get(sym, np.nan),
                "Rank": rk_map.get(sym, np.nan),
            })
        # Lows
        l_series = sub_low.loc[dt]
        for sym in l_series[l_series].index:
            cmp_val = float(prices_df.loc[dt, sym]) if sym in prices_df.columns else np.nan
            records.append({
                "Date": dt_str,
                "Event": "🔴 52W Low",
                "Symbol": sym,
                "Industry": ind_map.get(sym, "—"),
                "CMP": cmp_val,
                "3M Return": ret_map.get(sym, np.nan),
                "Rank": rk_map.get(sym, np.nan),
            })

    return pd.DataFrame(records)
