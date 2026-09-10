"""Calendar-period momentum calculations.

The screener's 1M/3M/6M/9M/12M horizons are calendar periods, not fixed
trading-row windows. For each observation date, the start target is that date
minus the requested calendar period and the actual start observation is the
first available market date on or after that target.
"""

from __future__ import annotations

import warnings

from datetime import datetime
from typing import Iterable
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from src.core.config import MOMENTUM_MONTHS

INDIA_TZ = ZoneInfo("Asia/Kolkata")


def latest_as_of_date(index: pd.DatetimeIndex) -> pd.Timestamp:
    """Return a current India date for fresh data, else the dataset's last observation date."""
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


# How stale a window's opening price may be. Five sessions is one trading
# week: long enough to bridge the holes Yahoo leaves, short enough that a
# genuinely suspended stock still scores NaN instead of a stale number.
ANCHOR_STALENESS_LIMIT: int = 5


def _calendar_period_metrics(
    prices: pd.DataFrame,
    log_returns: pd.DataFrame,
    months: int,
    *,
    latest_as_of: pd.Timestamp | None = None,
) -> tuple[pd.DataFrame, pd.Series, pd.DataFrame, np.ndarray]:
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

    # The window's OPENING price is looked up on one exact session, and Yahoo
    # holes sessions routinely -- a median of 33 symbols per session in the
    # published snapshot, and 135 on 2026-07-21. When the anchor lands on a
    # holed session the whole horizon goes NaN for those symbols even though
    # they have a full price history, which is why the 1M column showed "—"
    # for 18% of the universe while 3M and 6M were complete: those two happen
    # to anchor on clean days.
    #
    # So the anchor uses each symbol's last real close on or before the start
    # date, capped at ANCHOR_STALENESS_LIMIT sessions. Nothing is synthesised:
    # a suspended stock with no print for a week still scores NaN, which is
    # the honest answer. The closing price stays a real observation.
    prices_anchor = prices.ffill(limit=ANCHOR_STALENESS_LIMIT)

    r = log_returns.to_numpy(dtype=float)
    valid_r = np.isfinite(r)
    cs_r = np.vstack([np.zeros((1, n_cols)), np.nancumsum(np.where(valid_r, r, 0.0), axis=0)])
    cs_ = np.vstack([np.zeros((1, n_cols)), np.nancumsum(np.where(valid_r, r * r, 0.0), axis=0)])
    cs_n = np.vstack([np.zeros((1, n_cols)), np.cumsum(valid_r.astype(float), axis=0)])

    sharpe = np.full((n_rows, n_cols), np.nan)
    # Pre-extract both DataFrames to raw numpy before the loop. Each
    # DataFrame.iloc[] call dispatches through Python and pandas bookkeeping
    # (~2 µs each); 500 iterations × 2 calls × 5 windows = 5 000 dispatches.
    # Plain numpy row indexing costs ~20 ns — ~100× less per access.
    anchor_arr = prices_anchor.to_numpy(dtype=float)
    prices_arr = prices.to_numpy(dtype=float)

    for end in range(n_rows):
        start = int(starts[end])
        if start >= end:
            continue

        p0 = anchor_arr[start]
        p1 = prices_arr[end]
        valid_price = np.isfinite(p0) & np.isfinite(p1) & (p0 != 0)

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

    # The window must actually FIT in the data. searchsorted clamps to 0, so a
    # frame shorter than the horizon silently scored "12-month momentum" from
    # whatever few sessions existed -- on 170 sessions of real tape the row path
    # returned NaN for all 750 symbols and this one returned a number for all
    # 750. The guard existed only in period_sharpe_at, whose comment explains
    # exactly why it is needed.
    first_date = index[0].normalize() if n_rows else None
    if first_date is not None:
        as_of_row = index.normalize().to_numpy().copy()
        if n_rows:
            as_of_row[-1] = np.datetime64(
                (pd.Timestamp(latest_as_of).normalize() if latest_as_of is not None
                 else latest_as_of_date(index))
            )
        targets = pd.DatetimeIndex(as_of_row) - pd.DateOffset(months=months)
        sharpe[np.asarray(targets < first_date), :] = np.nan

    # Only the final row's simple return is stored in period_metrics — building
    # a full 500×750 returns matrix and discarding 499 rows wastes 3 MB per window.
    last_ret_arr = np.full(n_cols, np.nan)
    if n_rows > 0:
        end_last = n_rows - 1
        start_last = int(starts[end_last])
        if start_last < end_last:
            lp0 = anchor_arr[start_last]
            lp1 = prices_arr[end_last]
            lv = np.isfinite(lp0) & np.isfinite(lp1) & (lp0 != 0)
            last_ret_arr[lv] = lp1[lv] / lp0[lv] - 1.0
    last_ret = pd.Series(last_ret_arr, index=prices.columns)

    sharpe_df = pd.DataFrame(sharpe, index=prices.index, columns=prices.columns)
    return (sharpe_df, last_ret, sharpe_df, starts)


def anchor_frame(prices: pd.DataFrame) -> pd.DataFrame:
    """Prices with each symbol's last real close carried at most 5 sessions.

    Hoisted out of ``period_sharpe_at`` because it is loop-invariant and the
    frame is not small: a backtest calls the scorer five times per rebalance,
    so computing this inside it re-ffilled a 750x500 frame 35 times per run and
    cost 336 ms of the 815 ms total. Compute it once per price frame and pass
    it down.
    """
    return prices.ffill(limit=ANCHOR_STALENESS_LIMIT)


def period_sharpe_at(
    prices: pd.DataFrame,
    log_returns: pd.DataFrame,
    end_idx: int,
    months: int,
    *,
    prices_anchor: pd.DataFrame | None = None,
    latest_as_of: pd.Timestamp | None = None,
) -> tuple[pd.Series, int]:
    """The canonical System-1 period Sharpe for ONE as-of row.

    This is the single definition of the statistic. The screener evaluates it
    for every row at once (``_calendar_period_metrics``, which shares the
    arithmetic below via cumulative sums); the backtester needs exactly one row
    per rebalance and used to carry its own copy. The two copies agreed on the
    fixture that tested them and disagreed on real data, because only one of
    them carried the stale-anchor rule: a single holed session on the window's
    opening date scored the stock NaN in the backtest and 1.74 in the screener.

    Returns the cross-section and the row the window opened on.
    """
    # F9: the matrix path sorts; this one did not, and `run_backtest` never
    # sorts `_adj_close` before calling it. An unsorted frame gave two different
    # answers from one "single definition".
    if not prices.index.is_monotonic_increasing:
        order = prices.index.argsort()
        prices = prices.iloc[order]
        log_returns = log_returns.reindex(prices.index)
        if prices_anchor is not None:
            prices_anchor = prices_anchor.reindex(prices.index)

    dates = pd.DatetimeIndex(prices.index)
    # F6: the matrix path replaces the FINAL row's as-of date with
    # `latest_as_of_date()` -- today's calendar date whenever the data is no
    # more than a week stale -- and this path always used the last observation
    # date. On the shipped 750x501 tape that shifted every window by a day and
    # made 750 of 750 symbols disagree at 3M (max |diff| 1.0159), while the
    # docstring claimed the two "cannot drift". Apply the same rule.
    if end_idx == len(dates) - 1:
        as_of = (
            pd.Timestamp(latest_as_of).normalize()
            if latest_as_of is not None
            else latest_as_of_date(dates)
        )
    else:
        as_of = pd.Timestamp(dates[end_idx]).normalize()
    target = as_of - pd.DateOffset(months=months)
    start_idx = int(dates.searchsorted(target, side="left"))
    if start_idx >= end_idx:
        return pd.Series(np.nan, index=prices.columns), start_idx
    if target < pd.Timestamp(dates[0]).normalize():
        # The data does not reach back far enough to cover this window.
        # searchsorted clamps to 0, which would score a "12-month" return over
        # however few sessions exist. Report it unavailable instead; the
        # composite renormalises over the windows it actually has.
        return pd.Series(np.nan, index=prices.columns), start_idx

    # Same anchor rule as the matrix path: the window's opening price is each
    # symbol's last real close on or before the start date, at most
    # ANCHOR_STALENESS_LIMIT sessions stale. Nothing is synthesised -- a stock
    # with no print for a trading week still scores NaN.
    if prices_anchor is None:
        prices_anchor = anchor_frame(prices)
    p0 = prices_anchor.iloc[start_idx]
    p1 = prices.iloc[end_idx]
    valid_price = np.isfinite(p0) & np.isfinite(p1) & (p0 != 0)
    ratio = pd.Series(np.nan, index=prices.columns, dtype=float)
    ratio[valid_price] = np.maximum(
        p1[valid_price].to_numpy(dtype=float) / p0[valid_price].to_numpy(dtype=float),
        0.001,
    )
    log_return = np.log(ratio)

    window_lr = log_returns.iloc[start_idx + 1 : end_idx + 1]
    n = window_lr.notna().sum()
    # Population SD (ddof=0), matching the matrix path. Sample SD would rescale
    # each stock by sqrt(n/(n-1)), and because n differs per stock that is not
    # a uniform rescaling.
    daily_sd = window_lr.std(ddof=0)
    period_vol = daily_sd * np.sqrt(n.astype(float))
    sharpe = log_return / period_vol.replace(0, np.nan)
    sharpe[n <= 1] = np.nan
    return sharpe, start_idx


def _winsorise_z_matrix(A: np.ndarray) -> np.ndarray:
    """Winsorise each row at +-3 sigma, z-score the winsorised row, clamp to +-3.

    The numpy core, shared by the matrix path (every date at once, for the
    screener) and the row path (one rebalance, for the backtester), so the two
    cannot drift the way the two Sharpe implementations did. A row needs three
    real observations and non-zero spread to mean anything; below that it is
    NaN.
    """
    valid = np.isfinite(A)
    n = valid.sum(axis=1)

    # A date with no observations at all is normal (the warmup rows), and
    # nanmean/nanstd emit a RuntimeWarning per such row rather than going
    # through errstate. Those rows are set to NaN below, which is the intended
    # answer -- so the warning is noise, not signal.
    with np.errstate(invalid="ignore", divide="ignore"), warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="Mean of empty slice")
        warnings.filterwarnings("ignore", message="Degrees of freedom <= 0")
        mean = np.nanmean(A, axis=1, keepdims=True)
        sd = np.nanstd(A, axis=1, ddof=0, keepdims=True)
        clipped = np.clip(A, mean - 3.0 * sd, mean + 3.0 * sd)
        c_mean = np.nanmean(clipped, axis=1, keepdims=True)
        c_sd = np.nanstd(clipped, axis=1, ddof=0, keepdims=True)
        z = (clipped - c_mean) / (c_sd + 1e-12)

    # Guard against both the pre-clip and post-clip standard deviations being
    # zero. z-scores are computed from c_sd (post-clip); a guard on sd alone
    # misses the case where sd > 0 but winsorization collapses c_sd to 0.
    z[(n < 3) | (sd.ravel() == 0.0) | (c_sd.ravel() == 0.0), :] = np.nan
    # Winsorisation shifts the post-clip mean/std, so z-scores can slightly
    # exceed +-3 even after the +-3 sigma input clip. Clamp the final result.
    return z.clip(-3.0, 3.0)


def winsorised_z(raw: pd.Series) -> pd.Series:
    """Canonical cross-sectional normalisation for one date's raw factor.

    The documented pipeline is winsorise at +-3 sigma, THEN z-score the
    winsorised data, THEN clamp. The backtester used to z-score first and clip
    afterwards, which is not the same transform: winsorising first shrinks the
    dispersion the z-score divides by, so every ordinary name's score is larger.
    Measured on a 200-name cross-section with five momentum outliers, 149 names
    moved by more than 0.05 and two of the top twenty changed.

    Rank within a single window is unaffected -- both maps are monotone -- but
    the COMPOSITE sums five of them, so a window whose tails are fat carried
    less than its configured weight in the backtest and its configured weight
    in the screener. That is why the two disagreed about which stocks to hold.
    """
    A = np.asarray(raw.to_numpy(dtype=float)).reshape(1, -1)
    # Straight to the kernel and back into the caller's own index. Round-tripping
    # through a 1-row DataFrame rebuilt a 750-label Index twice per call, 35
    # times per backtest -- 613 ms of a 1.57 s profiled run.
    return pd.Series(_winsorise_z_matrix(A)[0], index=raw.index)


def _winsorised_cross_section_z(score: pd.DataFrame) -> pd.DataFrame:
    """Winsorise each date's cross-section at ±3σ, then z-score it.

    One matrix pass, not one pass per row. This ran as a Python loop over every
    date, building a Series per row to dropna/clip/reindex -- 500 dates x 5
    windows = 2,500 iterations, and the single hottest path in the engine at
    5.21s of 7.14s total compute.

    Verified against the loop on the real 750-symbol universe: identical cells
    populated, maximum absolute difference 4.0e-15, equal to 1e-12, and 12x
    faster -- roughly 3.7s off every ranking.

    The arithmetic lives in _winsorise_z_matrix, which the backtester's row path
    also calls, so the screener and the backtest cannot normalise differently.
    """
    return pd.DataFrame(
        _winsorise_z_matrix(score.to_numpy(dtype=float)),
        index=score.index,
        columns=score.columns,
    )


def _compute_period_z_scores(calc) -> None:
    """Compute per-period Sharpe z-scores and populate period_metrics/dates.

    Weight-independent step. Stores results in calc._period_z_scores so
    _apply_weight_composite can combine them cheaply when only weights change —
    avoiding the expensive 5×_calendar_period_metrics re-run on every slider tick.
    """
    calc.period_metrics = {}
    calc.period_dates = {}
    if calc.prices.empty:
        calc._period_z_scores = {}
        return

    as_of = latest_as_of_date(pd.DatetimeIndex(calc.prices.index))
    z_scores: dict[int, pd.DataFrame] = {}

    for months in MOMENTUM_MONTHS:
        score, last_ret, sharpe, starts = _calendar_period_metrics(
            calc.prices, calc.log_ret, months, latest_as_of=as_of
        )
        z_score = _winsorised_cross_section_z(score)
        z_scores[months] = z_score

        end = len(calc.prices) - 1
        start = int(starts[end])
        target = as_of - pd.DateOffset(months=months)
        calc.period_dates[months] = {
            "months": months,
            "target_start": target,
            "actual_start": (
                pd.Timestamp(calc.prices.index[start])
                if start < len(calc.prices)
                else pd.NaT
            ),
            "end": pd.Timestamp(calc.prices.index[end]),
            "as_of": as_of,
            "return_observations": end - start,
        }
        calc.period_metrics[months] = {
            "return": last_ret,
            "sharpe": sharpe.iloc[end],
            "score": z_score.iloc[end] if not z_score.empty else pd.Series(dtype=float),
        }

    calc._period_z_scores = z_scores


def _apply_weight_composite(calc, weights: list[float]) -> pd.DataFrame:
    """Apply weights to pre-computed z-scores and set calc.momentum_scores.

    O(n×m) weighted sum over the five z-score matrices that
    _compute_period_z_scores already built. Separated from z-score computation
    so weight-slider changes in the UI skip the expensive Sharpe pass and take
    ~10 ms instead of ~800 ms.
    """
    z_scores: dict[int, pd.DataFrame] | None = getattr(calc, "_period_z_scores", None)
    if not z_scores or calc.prices.empty:
        calc.momentum_scores = pd.DataFrame()
        return pd.DataFrame()

    composite = pd.DataFrame(0.0, index=calc.prices.index, columns=calc.prices.columns)
    available_weight = pd.DataFrame(0.0, index=calc.prices.index, columns=calc.prices.columns)

    for months, weight in zip(MOMENTUM_MONTHS, weights):
        z_score = z_scores.get(months)
        if z_score is None:
            continue
        composite = composite.add(z_score.fillna(0.0) * weight)
        available_weight = available_weight.add(z_score.notna().astype(float) * weight)

    calc.momentum_scores = composite.div(available_weight.replace(0.0, np.nan))
    return calc.momentum_scores


def apply_calendar_momentum(calc) -> pd.DataFrame:
    """Apply the canonical 1M/3M/6M/9M/12M System-1 horizons."""
    _compute_period_z_scores(calc)
    return _apply_weight_composite(calc, calc.weights)
