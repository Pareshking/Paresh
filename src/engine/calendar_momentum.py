"""Calendar-period momentum calculations.

The screener's 1M/3M/6M/9M/12M horizons are calendar periods, not fixed
trading-row windows. For each observation date, the start target is that date
minus the requested calendar period and the actual start observation is the
first available market date on or after that target.
"""

from __future__ import annotations

from datetime import datetime
from typing import Iterable
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from src.core.config import MOMENTUM_MONTHS

INDIA_TZ = ZoneInfo("Asia/Kolkata")


def latest_as_of_date(index: pd.DatetimeIndex) -> pd.Timestamp:
    """Return today's India date, unless the supplied data is newer."""
    today = pd.Timestamp(datetime.now(INDIA_TZ).date())
    last_data_date = pd.Timestamp(index[-1]).normalize()
    # Use today's calendar date for genuinely current data (including weekends
    # and short exchange holidays), but anchor historical/stale datasets to
    # their actual last observation so test and offline datasets cannot acquire
    # a multi-year synthetic lookback horizon.
    if today - last_data_date > pd.Timedelta(days=7):
        return last_data_date
    return max(today, last_data_date)


def calendar_start_positions(
    index: pd.DatetimeIndex,
    months: int,
    *,
    latest_as_of: pd.Timestamp | None = None,
) -> np.ndarray:
    """Return first available observation on/after each calendar target date."""
    idx = pd.DatetimeIndex(index)
    if idx.empty:
        return np.array([], dtype=int)

    as_of = idx.normalize().to_series(index=np.arange(len(idx)))
    as_of.iloc[-1] = (
        pd.Timestamp(latest_as_of).normalize()
        if latest_as_of is not None
        else latest_as_of_date(idx)
    )
    targets = pd.DatetimeIndex(as_of.to_numpy()) - pd.DateOffset(months=months)
    return np.searchsorted(idx.values, targets.values, side="left")


def _calendar_period_metrics(
    prices: pd.DataFrame,
    log_returns: pd.DataFrame,
    months: int,
    *,
    latest_as_of: pd.Timestamp | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, np.ndarray]:
    """Calculate V1 System-1 metrics over a calendar-defined rolling window.

    The approved V1 period-scale Sharpe is preserved. Only the economic
    horizon and observation count are calendar-defined; the volatility math
    remains unchanged.
    """
    prices = prices.sort_index()
    log_returns = log_returns.reindex(index=prices.index, columns=prices.columns)
    index = pd.DatetimeIndex(prices.index)
    n_rows, n_cols = prices.shape
    starts = calendar_start_positions(index, months, latest_as_of=latest_as_of)

    r = log_returns.to_numpy(dtype=float)
    valid_r = np.isfinite(r)
    cs_r = np.vstack([np.zeros((1, n_cols)), np.nancumsum(np.where(valid_r, r, 0.0), axis=0)])
    cs_ = np.vstack([np.zeros((1, n_cols)), np.nancumsum(np.where(valid_r, r * r, 0.0), axis=0)])
    cs_n = np.vstack([np.zeros((1, n_cols)), np.cumsum(valid_r.astype(float), axis=0)])

    score = np.full((n_rows, n_cols), np.nan)
    returns = np.full((n_rows, n_cols), np.nan)
    sharpe = np.full((n_rows, n_cols), np.nan)

    for end in range(n_rows):
        start = int(starts[end])
        if start >= end:
            continue

        p0 = prices.iloc[start].to_numpy(dtype=float)
        p1 = prices.iloc[end].to_numpy(dtype=float)
        valid_price = np.isfinite(p0) & np.isfinite(p1) & (p0 != 0)
        returns[end, valid_price] = p1[valid_price] / p0[valid_price] - 1.0

        rs = cs_r[end + 1] - cs_r[start + 1]
        rs2 = cs_[end + 1] - cs_[start + 1]
        rn = cs_n[end + 1] - cs_n[start + 1]
        mean_r = rs / np.where(rn > 0, rn, np.nan)
        population_var = (rs2 / np.where(rn > 0, rn, np.nan)) - (mean_r * mean_r)
        daily_sd = np.sqrt(np.maximum(population_var, 0.0))
        period_vol = daily_sd * np.sqrt(rn)

        log_return = np.full(n_cols, np.nan)
        log_return[valid_price] = np.log(np.maximum(p1[valid_price] / p0[valid_price], 0.001))
        sharpe[end] = log_return / np.where(period_vol > 0, period_vol, np.nan)
        score[end] = sharpe[end]

    return (
        pd.DataFrame(score, index=prices.index, columns=prices.columns),
        pd.DataFrame(returns, index=prices.index, columns=prices.columns),
        pd.DataFrame(sharpe, index=prices.index, columns=prices.columns),
        starts,
    )


def apply_calendar_momentum(calc) -> pd.DataFrame:
    """Apply the canonical 1M/3M/6M/9M/12M System-1 horizons."""
    scores_by_period: dict[int, pd.DataFrame] = {}
    calc.period_metrics = {}
    calc.period_dates = {}
    as_of = latest_as_of_date(pd.DatetimeIndex(calc.prices.index)) if not calc.prices.empty else None

    for months in MOMENTUM_MONTHS:
        score, ret, sharpe, starts = _calendar_period_metrics(
            calc.prices, calc.log_ret, months, latest_as_of=as_of
        )
        z_rows = []
        for _, row in score.iterrows():
            clean = row.dropna()
            if len(clean) < 3 or float(clean.std(ddof=0)) == 0.0:
                z_rows.append(pd.Series(np.nan, index=score.columns))
                continue
            raw_mean = float(clean.mean())
            raw_std = float(clean.std(ddof=0))
            clipped = clean.clip(raw_mean - 3.0 * raw_std, raw_mean + 3.0 * raw_std)
            clipped_std = float(clipped.std(ddof=0))
            z = (clipped - float(clipped.mean())) / (clipped_std + 1e-12)
            z_rows.append(z.reindex(score.columns))
        z_score = pd.DataFrame(z_rows, index=score.index, columns=score.columns).clip(-3.0, 3.0)
        scores_by_period[months] = z_score

        if not calc.prices.empty:
            end = len(calc.prices) - 1
            start = int(starts[end])
            target = as_of - pd.DateOffset(months=months)
            calc.period_dates[months] = {
                "months": months,
                "target_start": target,
                "actual_start": pd.Timestamp(calc.prices.index[start]) if start < len(calc.prices) else pd.NaT,
                "end": pd.Timestamp(calc.prices.index[end]),
                "as_of": as_of,
                "return_observations": end - start,
            }
            calc.period_metrics[months] = {
                "return": ret.iloc[end],
                "sharpe": sharpe.iloc[end],
                "score": z_score.iloc[end] if not z_score.empty else pd.Series(dtype=float),
            }

    total_weight = sum(calc.weights)
    norm_weights = [w / total_weight for w in calc.weights] if total_weight > 0 else [0.2] * len(MOMENTUM_MONTHS)
    composite = pd.DataFrame(0.0, index=calc.prices.index, columns=calc.prices.columns)
    available_weight = pd.DataFrame(0.0, index=calc.prices.index, columns=calc.prices.columns)

    for months, weight in zip(MOMENTUM_MONTHS, norm_weights):
        scores = scores_by_period[months]
        composite = composite.add(scores.fillna(0.0) * weight)
        available_weight = available_weight.add(scores.notna().astype(float) * weight)

    calc.momentum_scores = composite.div(available_weight.replace(0.0, np.nan))
    return calc.momentum_scores
