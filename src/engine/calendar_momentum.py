"""Calendar-period momentum calculations.

The screener's 1M/3M/6M/9M/12M horizons are calendar periods, not fixed
21/63/126/189/252-row windows.  For each observation date, the start target is
that date minus the requested calendar period and the actual start observation
is the first available market date on or after that target (Google-style
historical-series semantics).

This module deliberately changes only the period/date selection and the
existing System-1 period statistics. Other V1 metrics that use explicit
trading-day windows are left untouched for the subsequent metric audit.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# Keep the existing integer keys for downstream/UI compatibility.
PERIODS: dict[int, int] = {
    21: 1,   # 1M
    63: 3,   # 3M
    126: 6,  # 6M
    189: 9,  # 9M
    252: 12, # 12M
}


def calendar_start_positions(index: pd.DatetimeIndex, months: int) -> np.ndarray:
    """Return first available observation on/after each calendar target date."""
    idx = pd.DatetimeIndex(index)
    if idx.empty:
        return np.array([], dtype=int)
    targets = idx - pd.DateOffset(months=months)
    return np.searchsorted(idx.values, targets.values, side="left")


def _calendar_period_metrics(
    prices: pd.DataFrame,
    log_returns: pd.DataFrame,
    months: int,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, np.ndarray]:
    """Calculate V1 System-1 metrics over a calendar-defined rolling window.

    Returns score, simple return, period-scale Sharpe, R² and start positions.
    The existing V1 Sharpe structure is preserved, but its volatility window
    uses the actual number of daily return observations rather than a fixed
    21/63/126/189/252 count.
    """
    prices = prices.sort_index()
    log_returns = log_returns.reindex(index=prices.index, columns=prices.columns)
    index = pd.DatetimeIndex(prices.index)
    n_rows, n_cols = prices.shape

    starts = calendar_start_positions(index, months)

    y = np.log(prices.clip(lower=0.01)).to_numpy(dtype=float)
    r = log_returns.to_numpy(dtype=float)
    valid_y = np.isfinite(y)
    valid_r = np.isfinite(r)

    # Prefix sums let us support calendar-variable windows without forcing
    # every period back to a fixed trading-row count.
    cs_r = np.vstack([np.zeros((1, n_cols)), np.nancumsum(np.where(valid_r, r, 0.0), axis=0)])
    cs_r2 = np.vstack([np.zeros((1, n_cols)), np.nancumsum(np.where(valid_r, r * r, 0.0), axis=0)])
    cs_rn = np.vstack([np.zeros((1, n_cols)), np.cumsum(valid_r.astype(float), axis=0)])

    x = np.arange(n_rows, dtype=float)
    cs_y = np.vstack([np.zeros((1, n_cols)), np.nancumsum(np.where(valid_y, y, 0.0), axis=0)])
    cs_y2 = np.vstack([np.zeros((1, n_cols)), np.nancumsum(np.where(valid_y, y * y, 0.0), axis=0)])
    cs_xy = np.vstack([np.zeros((1, n_cols)), np.nancumsum(np.where(valid_y, y * x[:, None], 0.0), axis=0)])
    cs_yn = np.vstack([np.zeros((1, n_cols)), np.cumsum(valid_y.astype(float), axis=0)])

    score = np.full((n_rows, n_cols), np.nan)
    returns = np.full((n_rows, n_cols), np.nan)
    sharpe = np.full((n_rows, n_cols), np.nan)
    r2 = np.full((n_rows, n_cols), np.nan)

    for end in range(n_rows):
        start = int(starts[end])
        if start >= end:
            continue

        p0 = prices.iloc[start].to_numpy(dtype=float)
        p1 = prices.iloc[end].to_numpy(dtype=float)
        valid_price = np.isfinite(p0) & np.isfinite(p1) & (p0 != 0)
        returns[end, valid_price] = p1[valid_price] / p0[valid_price] - 1.0

        # Daily-return observations are start+1 ... end. N is the actual
        # number of valid daily observations in this calendar window.
        rs = cs_r[end + 1] - cs_r[start + 1]
        rs2 = cs_r2[end + 1] - cs_r2[start + 1]
        rn = cs_rn[end + 1] - cs_rn[start + 1]
        mean_r = rs / np.where(rn > 0, rn, np.nan)
        sample_var = (rs2 - rn * mean_r * mean_r) / np.where(rn > 1, rn - 1, np.nan)
        daily_sd = np.sqrt(np.maximum(sample_var, 0.0))

        # Preserve V1's existing period-scale Sharpe form. The key correction
        # is that sqrt(N) now uses the actual number of observations.
        period_vol = daily_sd * np.sqrt(rn)
        log_return = np.full(n_cols, np.nan)
        log_return[valid_price] = np.log(np.maximum(p1[valid_price] / p0[valid_price], 0.001))
        sharpe[end] = log_return / np.where(period_vol > 0, period_vol, np.nan)

        # R² of log price against observation time. Correlation is invariant to
        # shifting the time origin, so the global row index is sufficient.
        ys = cs_y[end + 1] - cs_y[start]
        ys2 = cs_y2[end + 1] - cs_y2[start]
        xys = cs_xy[end + 1] - cs_xy[start]
        yn = cs_yn[end + 1] - cs_yn[start]

        x_sum = (end + start + 1) * (end - start) / 2.0
        x2_sum = (
            end * (end + 1) * (2 * end + 1)
            - (start - 1) * start * (2 * start - 1)
        ) / 6.0

        cov_num = xys - x_sum * ys / np.where(yn > 0, yn, np.nan)
        var_x = x2_sum - x_sum * x_sum / np.where(yn > 0, yn, np.nan)
        var_y = ys2 - ys * ys / np.where(yn > 0, yn, np.nan)
        corr2 = cov_num * cov_num / np.where(
            (var_x > 0) & (var_y > 0), var_x * var_y, np.nan
        )
        r2[end] = np.clip(corr2, 0.0, 1.0)
        score[end] = sharpe[end] * r2[end]

    frame_index = prices.index
    return (
        pd.DataFrame(score, index=frame_index, columns=prices.columns),
        pd.DataFrame(returns, index=frame_index, columns=prices.columns),
        pd.DataFrame(sharpe, index=frame_index, columns=prices.columns),
        pd.DataFrame(r2, index=frame_index, columns=prices.columns),
        starts,
    )


def apply_calendar_momentum(calc) -> pd.DataFrame:
    """Replace V1 System-1 period calculations with calendar-defined windows.

    The MomentumEngine instance is intentionally accepted rather than typed so
    this is a narrow compatibility layer: all other MomentumEngine systems stay
    unchanged until their separate metric audit.
    """
    scores_by_period: dict[int, pd.DataFrame] = {}
    calc.period_metrics = {}
    calc.period_dates = {}

    for key, months in PERIODS.items():
        score, ret, sharpe, r2, starts = _calendar_period_metrics(
            calc.prices, calc.log_ret, months
        )

        # Match V1's cross-sectional normalization and clipping.
        mean_ = score.mean(axis=1)
        std_ = score.std(axis=1).replace(0, np.nan)
        z_score = score.sub(mean_, axis=0).div(std_, axis=0).clip(-3.0, 3.0)
        scores_by_period[key] = z_score

        if not calc.prices.empty:
            end = len(calc.prices) - 1
            start = int(starts[end])
            target = pd.Timestamp(calc.prices.index[end]) - pd.DateOffset(months=months)
            calc.period_dates[key] = {
                "months": months,
                "target_start": target,
                "actual_start": pd.Timestamp(calc.prices.index[start]) if start < len(calc.prices) else pd.NaT,
                "end": pd.Timestamp(calc.prices.index[end]),
                "return_observations": int(
                    np.isfinite(calc.log_ret.iloc[start + 1 : end + 1].to_numpy()).sum()
                ),
            }
            calc.period_metrics[key] = {
                "return": ret.iloc[end],
                "sharpe": sharpe.iloc[end],
                "r2": r2.iloc[end],
                "score": z_score.iloc[end] if not z_score.empty else pd.Series(dtype=float),
            }

    total_weight = sum(calc.weights)
    norm_weights = [w / total_weight for w in calc.weights] if total_weight > 0 else [0.2] * 5

    composite = pd.DataFrame(0.0, index=calc.prices.index, columns=calc.prices.columns)
    available_weight = pd.DataFrame(0.0, index=calc.prices.index, columns=calc.prices.columns)

    for key, weight in zip(PERIODS, norm_weights):
        scores = scores_by_period[key]
        composite = composite.add(scores.fillna(0.0) * weight)
        available_weight = available_weight.add(scores.notna().astype(float) * weight)

    calc.momentum_scores = composite.div(available_weight.replace(0.0, np.nan))
    return calc.momentum_scores
