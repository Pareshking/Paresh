"""
Price-frame helpers and the benchmark / market-regime readers.

There is no downloader here any more. Prices come from the Screener store, with
NSE for what Screener lacks (src/loaders/price_source.py); the benchmark comes
from data/benchmarks.csv (src/loaders/benchmark_store.py). The Yahoo download
path, its parquet cache and the yfinance dependency were removed on
13 Oct 2026 (TODO S10). What stays is the frame shaping that other modules
still use: extract_ohlcv and the field helpers behind it.
"""

from __future__ import annotations

from typing import Sequence

import pandas as pd
import streamlit as st

from src.core.config import BENCHMARK_SYMBOL
from src.core.tickers import normalise_symbol
from src.core.logger import logger
from src.core.types import MarketRegime, RegimeData


def _extract_field(df: pd.DataFrame, field_names: list[str]) -> pd.DataFrame:
    """Extracts a specific price field across all symbols from flat or MultiIndex DataFrames."""
    if df is None or df.empty:
        return pd.DataFrame()

    if not isinstance(df.columns, pd.MultiIndex):
        # Flat DataFrame -- the shape a vendor returns when a batch collapses
        # to a single ticker. Normalise the ticker labels the SAME way as the
        # MultiIndex branches below. Without this the columns keep their ".NS"
        # suffix, nothing matches the universe symbols, every Score maps to NaN,
        # and get_rankings drops all 750 rows -- a silent empty ranking rather
        # than an error.
        out = df.copy()
        out.columns = [
            normalise_symbol(c) for c in out.columns
        ]
        return out

    # MultiIndex. The field may sit on either level depending on how the
    # vendor grouped the response, so try level 1 (Ticker, Field) then level 0.
    if df.columns.nlevels > 1:
        for level in (1, 0):
            extracted = _extract_by_coverage(df, field_names, level)
            if extracted is not None:
                return extracted

    return pd.DataFrame(index=df.index)


def _extract_by_coverage(
    df: pd.DataFrame, field_names: list[str], level: int
) -> pd.DataFrame | None:
    """Pick the candidate field that covers the MOST tickers, not the first one present.

    This took production down twice, on the old Yahoo feed. The vendor
    rate-limited a ticker and returned that one ticker UNADJUSTED -- six
    fields including "Adj Close" -- while the other 749 came back auto-adjusted with five fields and no "Adj Close" at
    all. The old code took the first candidate name that appeared ANYWHERE, so
    "Adj Close" won on the strength of a single failed ticker and
    df.xs("Adj Close") returned exactly one all-NaN column.

    The screener then ranked 0 of 750 stocks. The giveaway in the logs was
    "Price cache saved: 500 rows (3751 series)" -- 3751 is 749x5 + 1x6, not a
    clean grid.

    Coverage decides, with the preference order breaking ties. When every
    ticker carries both fields the counts are equal and "Adj Close" still wins,
    so normal behaviour is unchanged.
    """
    labels = df.columns.get_level_values(level)
    lowered = [str(x).strip().lower() for x in labels]

    best_target = None
    best_coverage = 0
    for target in field_names:
        coverage = lowered.count(target.lower())
        if coverage > best_coverage:
            best_target, best_coverage = target, coverage

    if best_target is None or best_coverage == 0:
        return None

    n_tickers = len(set(df.columns.get_level_values(1 - level)))
    if best_coverage < n_tickers:
        logger.warning(
            "Price field '%s' covers only %d of %d tickers; the rest are missing "
            "this field entirely. Extracting the %d available.",
            best_target, best_coverage, n_tickers, best_coverage,
        )

    idx = lowered.index(best_target.lower())
    actual_label = labels[idx]
    extracted = df.xs(actual_label, level=level, axis=1)
    extracted.columns = [
        normalise_symbol(c) for c in extracted.columns
    ]
    return extracted


def _clean_price_df(df: pd.DataFrame, symbols: Sequence[str] | None = None) -> pd.DataFrame:
    """Cleans trailing empty rows, deduplicates columns, and filters valid symbols."""
    if df is None or df.empty:
        return pd.DataFrame()
    out = df.loc[:, ~df.columns.duplicated()].copy()
    # Drop rows at the end that are all NaN
    valid_idx = out.dropna(how="all").index
    if not valid_idx.empty:
        out = out.loc[: valid_idx[-1]]
    # Preserve security-specific NaNs; do not manufacture zero-return observations.
    if symbols:
        valid_cols = [s.upper() for s in symbols if s.upper() in out.columns]
        if valid_cols:
            out = out[valid_cols]
        else:
            # Not one requested symbol is present. Silently returning the
            # unfiltered frame lets a symbol-namespace mismatch travel all the
            # way to the ranking, where it looks like "no stock qualified".
            logger.warning(
                "No requested symbol matched the price columns (%d columns, "
                "e.g. %s vs requested %s). Returning the frame unfiltered; the "
                "ranking will be empty if these labels do not match.",
                len(out.columns),
                list(out.columns[:3]),
                [str(x).upper() for x in list(symbols)[:3]],
            )
    return out


def _decompose_fields(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Decompose a MultiIndex price DataFrame into per-field DataFrames in one pass.

    The old path called _extract_by_coverage six times, each invoking
    get_level_values + a linear label scan across all columns. For a
    750-symbol × 5-field frame (3 750 columns) that is roughly 45 000 string
    comparisons. This function does it in two get_level_values calls + one O(m)
    dict build, then six O(1) dict lookups.

    Returns an empty dict for flat DataFrames — callers fall back to
    _extract_field per-field in that case (flat frames are rare in practice).
    """
    if not isinstance(df.columns, pd.MultiIndex):
        return {}

    KNOWN_FIELDS = {
        "adj close", "adjclose", "close", "high", "low", "volume", "vol", "open"
    }

    lv0_raw = df.columns.get_level_values(0)
    lv1_raw = df.columns.get_level_values(1)
    lv0 = [str(x).strip().lower() for x in lv0_raw]
    lv1 = [str(x).strip().lower() for x in lv1_raw]

    # Identify which level carries price field names vs ticker names.
    n_known_lv1 = sum(1 for x in lv1 if x in KNOWN_FIELDS)
    n_known_lv0 = sum(1 for x in lv0 if x in KNOWN_FIELDS)
    if n_known_lv1 >= n_known_lv0:
        field_labels, ticker_raw = lv1, lv0_raw
    else:
        field_labels, ticker_raw = lv0, lv1_raw

    # Build field-name → column-position list in one scan.
    field_to_cols: dict[str, list[int]] = {}
    for i, fl in enumerate(field_labels):
        field_to_cols.setdefault(fl, []).append(i)

    n_tickers = len(set(ticker_raw))

    def _pick(candidates: list[str]) -> pd.DataFrame:
        best_name: str | None = None
        best_pos: list[int] = []
        for cand in candidates:
            pos = field_to_cols.get(cand.strip().lower(), [])
            if len(pos) > len(best_pos):
                best_name, best_pos = cand, pos
        if not best_pos:
            return pd.DataFrame(index=df.index)
        if len(best_pos) < n_tickers:
            logger.warning(
                "Price field '%s' covers only %d of %d tickers; the rest are "
                "missing this field entirely. Extracting the %d available.",
                best_name, len(best_pos), n_tickers, len(best_pos),
            )
        out = df.iloc[:, best_pos].copy()
        out.columns = [normalise_symbol(ticker_raw[i]) for i in best_pos]
        return out

    return {
        "adj_close": _pick(["Adj Close", "AdjClose", "Close"]),
        "close":     _pick(["Close", "Adj Close", "AdjClose"]),
        "high":      _pick(["High"]),
        "low":       _pick(["Low"]),
        "volume":    _pick(["Volume", "Vol"]),
        "open":      _pick(["Open"]),
    }


def extract_ohlcv(
    prices_df: pd.DataFrame,
    symbols: Sequence[str] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Extracts (Adj Close, Close, High, Low, Volume, Open) DataFrames from a
    (ticker, field) price frame. Open is last so existing five-value unpacking keeps
    working where it is still used.
    """
    if prices_df is None or prices_df.empty:
        empty = pd.DataFrame()
        return empty, empty, empty, empty, empty, empty

    if isinstance(prices_df.columns, pd.MultiIndex):
        fields = _decompose_fields(prices_df)
        adj_close = fields.get("adj_close", pd.DataFrame())
        close_p   = fields.get("close",     pd.DataFrame())
        high_p    = fields.get("high",      pd.DataFrame())
        low_p     = fields.get("low",       pd.DataFrame())
        vol_p     = fields.get("volume",    pd.DataFrame())
        open_p    = fields.get("open",      pd.DataFrame())
    else:
        # Flat DataFrame — rare (single-ticker response). _extract_field handles
        # this by returning all columns; the field-name argument is ignored.
        open_p    = _extract_field(prices_df, ["Open"])
        adj_close = _extract_field(prices_df, ["Adj Close", "AdjClose", "Close"])
        close_p   = _extract_field(prices_df, ["Close", "Adj Close", "AdjClose"])
        high_p    = _extract_field(prices_df, ["High"])
        low_p     = _extract_field(prices_df, ["Low"])
        vol_p     = _extract_field(prices_df, ["Volume", "Vol"])

    # Fallbacks if some fields are missing
    if adj_close.empty and not close_p.empty:
        adj_close = close_p.copy()
    if close_p.empty and not adj_close.empty:
        close_p = adj_close.copy()
    if high_p.empty and not close_p.empty:
        high_p = close_p.copy()
    if low_p.empty and not close_p.empty:
        low_p = close_p.copy()
    if open_p.empty and not close_p.empty:
        open_p = close_p.copy()
    if vol_p.empty and not close_p.empty:
        vol_p = pd.DataFrame(0.0, index=close_p.index, columns=close_p.columns)

    adj_close = _clean_price_df(adj_close, symbols)
    close_p   = _clean_price_df(close_p,   symbols)
    high_p    = _clean_price_df(high_p,    symbols)
    low_p     = _clean_price_df(low_p,     symbols)
    vol_p     = _clean_price_df(vol_p,     symbols)
    open_p    = _clean_price_df(open_p,    symbols)

    return adj_close, close_p, high_p, low_p, vol_p, open_p


@st.cache_data(show_spinner=False, ttl=3600)
def fetch_benchmark_history(
    period: str = "2y", symbol: str = BENCHMARK_SYMBOL
) -> pd.Series:
    """Return a benchmark price series, the V1 benchmark by default.

    Read from data/benchmarks.csv (NSE's daily index closes, Screener's for
    older history), not Yahoo (owner, 2026-10-02). Same signature and the same
    empty-series contract as before, so no caller changes.
    """
    from src.loaders import benchmark_store

    try:
        return benchmark_store.history(period=period, symbol=symbol)
    except Exception as e:
        logger.warning(f"Failed to read benchmark {symbol}: {e}")
        return pd.Series(dtype=float, name=symbol)


@st.cache_data(show_spinner=False, ttl=3600)
def get_market_regime(benchmark_symbol: str = BENCHMARK_SYMBOL) -> RegimeData:
    """
    Computes market regime by comparing benchmark index price with its 200 DMA.
    Reuses fetch_benchmark_history (2y window, already cached) so no second
    HTTP round-trip is needed at cold start.
    """
    try:
        # The argument is honoured rather than decorative: this read
        # BENCHMARK_SYMBOL internally, so asking for any other index
        # silently returned the Nifty 500 regime under that index's name.
        close_s = fetch_benchmark_history(period="2y", symbol=benchmark_symbol)

        if close_s is None or close_s.empty:
            return RegimeData(
                status=MarketRegime.UNKNOWN,
                current_price=0.0,
                dma_200=0.0,
                distance_pct=0.0,
            )

        close_s = pd.to_numeric(close_s, errors="coerce").dropna()
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
        logger.warning(f"Failed to compute market regime: {e}")
        return RegimeData(
            status=MarketRegime.UNKNOWN,
            current_price=0.0,
            dma_200=0.0,
            distance_pct=0.0,
        )
