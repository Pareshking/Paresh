"""The composite backtest warmup was measured in months but spent as sessions.

MOMENTUM_WINDOWS are calendar months ([1, 3, 6, 9, 12]) and the scoring path
passes them straight to _calendar_period_sharpe. The warmup arithmetic
(min_needed, start_offset) is in trading sessions, so max(WINDOWS) = 12 meant a
12-MONTH formation window was warmed up over 12 TRADING DAYS. Two consequences,
both reproduced here:

  * the first rebalance landed at session 32, and because searchsorted clamps to
    0 the engine scored "12-month momentum" from whatever history existed;
  * with 70-100 sessions no rebalance produced a record, and building a frame
    from [] raised KeyError: ['Period Start'] instead of reporting no result.
"""
import numpy as np
import pandas as pd
import pytest

from src.engine.backtester import (
    SESSIONS_PER_MONTH,
    _calendar_period_sharpe,
    run_backtest,
)


def _prices(n: int, cols: int = 20, seed: int = 1) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2023-01-01", periods=n)
    return pd.DataFrame(
        100 + np.cumsum(rng.normal(0, 1, (n, cols)), axis=0),
        index=idx,
        columns=[f"S{i}" for i in range(cols)],
    )


def _composite(prices):
    return run_backtest(
        f"warmup-{len(prices)}-{prices.shape[1]}",
        prices,
        top_n=5,
        rebal_freq=21,
        ema_period=20,
        high_pct=0.0,
        cost_bps=0.0,
        buffer_n=5,
    )


@pytest.mark.parametrize("n", [70, 100, 150, 300])
def test_insufficient_history_is_refused_not_crashed(n):
    """These used to raise KeyError: ['Period Start'] or run on 32 sessions."""
    assert _composite(_prices(n)) is None


def test_sufficient_history_still_runs():
    assert _composite(_prices(400)) is not None


def test_warmup_reserves_a_full_twelve_month_formation_window():
    """12 months of sessions, not 12 sessions."""
    n = 500
    result = _composite(_prices(n))
    assert result is not None
    consumed = n - len(result["equity_curve"])
    assert consumed >= 12 * SESSIONS_PER_MONTH


def test_uncovered_calendar_window_is_unavailable_not_truncated():
    """A 12-month window over 40 sessions of data must be NaN, not a number.

    searchsorted clamps the start to 0, so without the explicit coverage check
    this returned a real-looking "12-month" Sharpe computed from 40 sessions.
    """
    prices = _prices(40, cols=3)
    log_ret = np.log(prices / prices.shift(1))

    sharpe, _ = _calendar_period_sharpe(prices, log_ret, end_idx=39, months=12)
    assert sharpe.isna().all()

    # A window the data does cover is still scored.
    covered, _ = _calendar_period_sharpe(prices, log_ret, end_idx=39, months=1)
    assert covered.notna().any()
