"""Raw Yahoo OHLCV acquisition and read-time project adjustment for R2.

This module is isolated from the canonical V1 price loader. It captures the
vendor's unadjusted OHLCV bytes and applies project corporate actions only in
memory when a caller explicitly requests an adjusted research frame.
"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

import pandas as pd
import yfinance as yf

from src.engine.corporate_actions import adjust_ohlc, load_events
from src.loaders.price_loader import _decompose_fields, _clean_price_df
from src.core.tickers import normalise_symbol

RAW_FIELDS = ("Open", "High", "Low", "Close", "Volume")


def _normalise_batch(data: pd.DataFrame) -> pd.DataFrame:
    if data is None or data.empty:
        return pd.DataFrame()
    frame = data.copy()
    if getattr(frame.index, "tz", None) is not None:
        frame.index = frame.index.tz_localize(None)
    if frame.index.duplicated().any():
        frame = frame[~frame.index.duplicated(keep="last")]
    if isinstance(frame.columns, pd.MultiIndex):
        tickers = [normalise_symbol(c) for c in frame.columns.get_level_values(0)]
        fields = list(frame.columns.get_level_values(1))
        frame.columns = pd.MultiIndex.from_arrays(
            [tickers, fields], names=["Ticker", "Price"]
        )
    return frame.sort_index()


def download_raw_ohlcv(symbols: Sequence[str], *, period: str = "10y") -> pd.DataFrame:
    """Download unadjusted Yahoo OHLCV for the supplied symbols."""
    yf_symbols = [
        s if str(s).upper().endswith(".NS") else f"{s}.NS" for s in symbols
    ]
    batches: list[pd.DataFrame] = []
    for start in range(0, len(yf_symbols), 100):
        batch = yf_symbols[start : start + 100]
        data = yf.download(
            batch, period=period, progress=False, group_by="ticker",
            threads=True, auto_adjust=False,
        )
        if data is not None and not data.empty:
            batches.append(data)
    if not batches:
        return pd.DataFrame()
    data = _normalise_batch(pd.concat(batches, axis=1))
    if data.empty or not isinstance(data.columns, pd.MultiIndex):
        return data
    keep = [col for col in data.columns if str(col[1]).strip() in RAW_FIELDS]
    return data.loc[:, keep]


def read_raw_ohlcv(path: str | Path) -> pd.DataFrame:
    return _normalise_batch(pd.read_parquet(path))


def adjusted_from_raw(raw: pd.DataFrame, symbols: Sequence[str] | None = None):
    """Return the V1-style adjusted frames without rewriting raw evidence."""
    if raw is None or raw.empty:
        empty = pd.DataFrame()
        return empty, empty, empty, empty, empty, []
    if not isinstance(raw.columns, pd.MultiIndex):
        raise ValueError("raw Yahoo evidence must use (Ticker, Price) columns")
    fields = _decompose_fields(raw)
    close = _clean_price_df(fields.get("close", pd.DataFrame()), symbols)
    high = _clean_price_df(fields.get("high", pd.DataFrame()), symbols)
    low = _clean_price_df(fields.get("low", pd.DataFrame()), symbols)
    volume = _clean_price_df(fields.get("volume", pd.DataFrame()), symbols)
    adjusted, applied = adjust_ohlc(
        {"adj_close": close.copy(), "close": close, "high": high, "low": low},
        load_events(),
    )
    return adjusted["adj_close"], adjusted["close"], adjusted["high"], adjusted["low"], volume, applied
