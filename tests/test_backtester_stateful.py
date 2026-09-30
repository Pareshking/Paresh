"""Tests for stateful portfolio reconstruction in the backtest engine."""

import numpy as np
import pandas as pd

from src.engine.backtester import _build_rebalance_schedule


def test_stateful_schedule_keeps_pre_window_rebalances_for_portfolio_state():
    dates = pd.date_range("2024-01-01", "2026-09-30", freq="B")
    prices = pd.DataFrame({"AAA": np.linspace(100.0, 200.0, len(dates))}, index=dates)

    stateful = _build_rebalance_schedule(
        prices, start_offset=300, rebal_freq=21, backtest_months=6,
        stateful_history=True,
    )
    window_only = _build_rebalance_schedule(
        prices, start_offset=300, rebal_freq=21, backtest_months=6,
        stateful_history=False,
    )

    assert stateful is not None
    assert window_only is not None

    stateful_dates = [dates[i + 1] for i in stateful[0]]
    window_dates = [dates[i + 1] for i in window_only[0]]
    current_month_start = pd.Timestamp(dates[-1]).replace(day=1)
    window_start = current_month_start - pd.DateOffset(months=6)
    window_end = current_month_start - pd.Timedelta(days=1)

    assert window_dates
    assert all(window_start <= d <= window_end for d in window_dates)
    assert all(d <= window_end for d in stateful_dates)
    assert any(d < window_start for d in stateful_dates)
    assert len(stateful_dates) > len(window_dates)


def test_stateful_schedule_still_stops_at_completed_window():
    dates = pd.date_range("2024-01-01", "2026-09-30", freq="B")
    prices = pd.DataFrame({"AAA": np.linspace(100.0, 200.0, len(dates))}, index=dates)

    schedule = _build_rebalance_schedule(
        prices, start_offset=300, rebal_freq=21, backtest_months=6,
        stateful_history=True,
    )

    assert schedule is not None
    _, _, last_sim_idx, window_end = schedule
    assert dates[last_sim_idx] <= window_end
