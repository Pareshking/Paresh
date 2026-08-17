"""
Quantitative Multi-System Momentum Engine — Hardened Production Core.

Systems:
  1. Multi-Window Sharpe & Sortino Momentum (Winsorized Z-score across 5 lookbacks)
  2. Vectorized Exponential Regression (annualized OLS slope with analytical 1D convolution)
  3. Residual / Idiosyncratic Alpha (Market-beta stripped alpha)
  4. Industry-Relative Momentum (Sector-neutral outperformance)
  5. Momentum Acceleration (Short-term velocity vs long-term baseline)
"""

from __future__ import annotations

from typing import Any, Sequence

import numpy as np
import pandas as pd
from scipy.ndimage import convolve1d

from src.core.config import DEFAULT_LOOKBACK_WEIGHTS, MOMENTUM_WINDOWS
from src.core.logger import logger
from src.engine.calendar_momentum import (
    _calendar_period_metrics,
    calendar_start_positions,
    latest_as_of_date,
)


def clean_holidays(df: pd.DataFrame | None) -> pd.DataFrame:
    """Drops dates where >70% of the universe has NaN (market holidays).

    A malformed/sparse upstream cache must never cause the entire price history
    to disappear. If every row would be classified as an exchange-wide holiday,
    retain the original rows and let downstream calculations handle their
    stock-specific missing observations explicitly.
    """
    if df is None or df.empty:
        return df if df is not None else pd.DataFrame()
    n_cols = df.shape[1]
    limit = max(int(n_cols * 0.70), 1)
    count = df.isna().sum(axis=1)
    holidays = count > limit
    n_dropped = int(holidays.sum())
    if n_dropped > 0:
        logger.debug(f"Holiday cleanup: dropped {n_dropped} rows")
    if n_dropped == len(df):
        logger.warning(
            "Holiday cleanup would remove the entire dataset; preserving rows "
            "to avoid converting an upstream sparse/malformed cache into an empty "
            "production price history."
        )
        return df.copy()
    # Remove exchange-wide missing dates only; preserve stock-specific NaNs.
    return df.loc[~holidays]


def compute_ffill_pct(raw_df: pd.DataFrame | None) -> pd.Series:
    """Computes per-stock % of rows that were gap-filled after dropping holidays."""
    if raw_df is None or raw_df.empty:
        return pd.Series(dtype=float)
    n_cols = raw_df.shape[1]
    limit = max(int(n_cols * 0.70), 1)
    count = raw_df.isna().sum(axis=1)
    cleaned = raw_df.loc[count <= limit]
    if cleaned.empty:
        return pd.Series(dtype=float)
    n_rows = len(cleaned)
    nan_per_col = cleaned.isna().sum()
    return (nan_per_col / max(n_rows, 1) * 100).round(1)


def winsorize_series(s: pd.Series, std_limit: float = 3.0) -> pd.Series:
    """Winsorizes cross-sectional series to +/- std_limit standard deviations."""
    if s.empty or s.isna().all():
        return s
    clean = s.dropna()
    if len(clean) < 3 or clean.std(ddof=0) == 0:
        return s
    mean, std = float(clean.mean()), float(clean.std(ddof=0))
    lower, upper = mean - std_limit * std, mean + std_limit * std
    return s.clip(lower=lower, upper=upper)


def zscore_series(s: pd.Series, winsorize: bool = True) -> pd.Series:
    """Calculates cross-sectional Z-scores with optional 3-sigma winsorization."""
    if s.empty or s.isna().all():
        return s
    clean = s.dropna()
    if len(clean) < 3 or clean.std(ddof=0) == 0:
        return pd.Series(np.nan, index=s.index)
    if winsorize:
        clean = winsorize_series(clean, std_limit=3.0)
    mean_val = float(clean.mean())
    std_val = float(clean.std(ddof=0))
    z = (clean - mean_val) / (std_val + 1e-12)
    return z.reindex(s.index)


def _normalize_ticker_cols(df: pd.DataFrame | None) -> pd.DataFrame | None:
    if df is None or df.empty:
        return df
    res = df.copy()
    res.columns = [str(c).replace(".NS", "").strip().upper() for c in res.columns]
    return res


class MomentumEngine:
    """
    Hardened Production Quantitative Momentum Engine.
    Vectorized calculations across 5 lookback windows with zero look-ahead bias.
    """

    WINDOWS: list[int] = MOMENTUM_WINDOWS
    DEFAULT_WEIGHTS: list[float] = DEFAULT_LOOKBACK_WEIGHTS

    def __init__(
        self,
        prices_df: pd.DataFrame,
        *,
        high_df: pd.DataFrame | None = None,
        low_df: pd.DataFrame | None = None,
        close_df: pd.DataFrame | None = None,
        volume_df: pd.DataFrame | None = None,
        weights: Sequence[float] | None = None,
        market_cap_weights: pd.Series | None = None,
    ):
        self.ffill_pct: pd.Series = compute_ffill_pct(prices_df)

        cleaned_p = clean_holidays(prices_df)
        norm_p = _normalize_ticker_cols(cleaned_p)
        self.prices: pd.DataFrame = norm_p if norm_p is not None else pd.DataFrame()
        
        if high_df is not None:
            norm_h = _normalize_ticker_cols(clean_holidays(high_df))
            self.high: pd.DataFrame = norm_h if norm_h is not None else self.prices
        else:
            self.high = self.prices

        if low_df is not None:
            norm_l = _normalize_ticker_cols(clean_holidays(low_df))
            self.low: pd.DataFrame = norm_l if norm_l is not None else self.prices
        else:
            self.low = self.prices

        if close_df is not None:
            norm_c = _normalize_ticker_cols(clean_holidays(close_df))
            self.close: pd.DataFrame = norm_c if norm_c is not None else self.prices
        else:
            self.close = self.prices

        if volume_df is not None:
            self.volume: pd.DataFrame | None = _normalize_ticker_cols(clean_holidays(volume_df))
        else:
            self.volume = None

        self.weights: list[float] = list(weights) if weights is not None else list(self.DEFAULT_WEIGHTS)
        self._mcap_weights: pd.Series | None = market_cap_weights

        # Pre-calculate daily log returns
        self.log_ret: pd.DataFrame = np.log(self.prices / self.prices.shift(1).replace(0, np.nan))
        self._valid_counts: pd.Series = self.prices.notna().sum()

        self.momentum_scores: pd.DataFrame | None = None
        self.exp_reg_scores: pd.DataFrame | None = None
        self.residual_ranks: pd.Series | None = None
        self.ind_rel_ranks: pd.Series | None = None
        self.vol_mgd_ranks: pd.Series | None = None
        self.period_metrics: dict[int, dict[str, pd.Series]] = {}

    @staticmethod
    def _mp(window: int) -> int:
        return window

    def _annualized_sharpe(self, w: int) -> pd.DataFrame:
        """Compute annualized period Sharpe without an  multiplier."""
        log_ret_w = np.log(self.prices / self.prices.shift(w).replace(0, np.nan)).replace([np.inf, -np.inf], np.nan)
        daily_vol_w = (self.log_ret.rolling(w, min_periods=w).std(ddof=0) * np.sqrt(w)).replace(0, np.nan)
        return (log_ret_w / daily_vol_w).replace([np.inf, -np.inf], np.nan)

    def calculate_sharpe_momentum(self) -> pd.DataFrame:
        """Compatibility entry point for the canonical calendar-month System-1 engine."""
        from src.engine.calendar_momentum import apply_calendar_momentum
        return apply_calendar_momentum(self)

    def calculate_exp_regression(self, window: int = 126) -> pd.DataFrame:
        """Calculate annualized rolling exponential-regression slope without synthetic fills."""
        log_p = np.log(self.prices.clip(lower=0.01))
        n = int(window)
        score = pd.DataFrame(np.nan, index=log_p.index, columns=log_p.columns, dtype=float)
        if n < 2 or len(log_p) < n:
            self.exp_reg_scores = score
            return score
