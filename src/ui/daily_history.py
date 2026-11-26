"""Daily price history for the readings that reach a year or more back (S193 B).

Owner, 23 Nov 2026 ("Fix, I am with your recommendation"): a reading a year or
more back comes from a daily frame, not Screener's sparse store, and windows are
counted in sessions or calendar days, not rows. Screener's store holds about ten
closes a month before Jul 2025 (PRICE_PIPELINE, "Screener's history is sparse"),
so a "200D EMA" a year ago spanned about sixteen months and "five sessions" two
to three weeks.

The ranking frame (`price_source.keep_and_fill`) is already daily from NSE's
committed file (30 Sep 2024) on. `frame` fills the rest of its span from NSE's
long daily file by `price_source.daily_history`, read only for the ranking's
columns; when the long file cannot be read the ranking frame is used as it is,
which is still daily for every reading a year back. One frame per price state
and universe, shared by every session (st.cache_resource), as the price frames
are; the memory guard's `st.cache_resource.clear()` drops it.

The track record, the model book and every figure that must agree with them
keep reading the deep frame (S193 A4); this is only for history readings.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from src.core.logger import logger
from src.engine.pipeline import known_fingerprint, price_fingerprint, remember_fingerprint


@st.cache_resource(show_spinner=False, ttl=3600, max_entries=2)
def _built(fingerprint: str, _prices: pd.DataFrame):
    """(daily frame, its fingerprint), or (None, None) when the long file adds nothing.

    Kept on disk too (S233 (2)): every pull clears this cache, and the fill costs ~7 s of a cold page
    (Dashboard, Market, Portfolio, Stock, Sectors). The disk key is the ranking frame's and the long
    file's columns' whole-value fingerprints and the code, so any change to either rebuilds."""
    from src.core import disk_memo
    from src.loaders import nse_long

    long = nse_long.load_columns(_prices.columns, start=pd.DatetimeIndex(_prices.index)[0])
    key = disk_memo.digest("daily_history", fingerprint, price_fingerprint(long) if long is not None else "-",
                           disk_memo.code_fingerprint())
    return disk_memo.get("daily_history", key, lambda: _fill(_prices, long))


def _fill(_prices: pd.DataFrame, long):
    from src.loaders import price_source

    out, report = price_source.daily_history(_prices, long)
    if out is _prices:
        logger.info("Daily history: nothing filled from the long NSE file (%s).", report.get("skipped") or "no gap")
        return None, None
    logger.info("Daily history: %s prices filled from the long NSE file for %s stocks, %s sessions added, "
                "%s intervals kept as they were.", report.get("cells"), report.get("symbols"),
                report.get("sessions_added"), report.get("intervals_refused"))
    return out, price_fingerprint(out)


def frame(prices: pd.DataFrame | None) -> pd.DataFrame | None:
    """`prices` (the ranking frame) daily over its whole span; `prices` itself when that cannot be built."""
    if prices is None or prices.empty:
        return prices
    try:
        out, fp = _built(known_fingerprint(prices), prices)
    except Exception as exc:  # noqa: BLE001  the ranking frame is daily for a year back
        logger.warning("Daily history unavailable (%s); the ranking frame is used.", type(exc).__name__)
        return prices
    if out is None:
        return prices
    view = out.copy(deep=False)       # the shared frame is never handed out (app._shared)
    remember_fingerprint(view, fp)
    return view


@st.cache_data(show_spinner=False, ttl=3600, max_entries=64)
def _long_column(symbol: str) -> pd.DataFrame | None:
    from src.loaders import nse_long

    return nse_long.load_columns([symbol])


def stock_close(symbol: str, prices: pd.DataFrame | None) -> pd.Series:
    """One stock's closes from `prices` (the ranking frame), daily over its whole span."""
    if prices is None or symbol not in prices.columns:
        return pd.Series(dtype=float)
    own = prices[[symbol]]
    try:
        from src.loaders import price_source

        filled, _ = price_source.daily_history(own, _long_column(symbol))
    except Exception as exc:  # noqa: BLE001
        logger.warning("Daily history for %s unavailable (%s).", symbol, type(exc).__name__)
        filled = own
    return filled[symbol].dropna()
