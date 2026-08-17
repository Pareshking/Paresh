import numpy as np
import pandas as pd

from src.engine.calendar_momentum import _calendar_period_metrics, calendar_start_positions


def _prices(start="2025-08-01", end="2026-08-20"):
    dates = pd.bdate_range(start, end)
    # 15-Aug-2026 is Saturday; remove it explicitly if present in future
    dates = dates[~((dates.month == 8) & (dates.day == 15))]
    values = np.exp(np.linspace(5.0, 5.5, len(dates)))
    return pd.DataFrame({"RELIANCE": values}, index=dates)


def test_calendar_12m_uses_first_trading_day_on_or_after_target():
    prices = _prices()
    log_returns = np.log(prices / prices.shift(1))
    score, returns, sharpe, r2, starts = _calendar_period_metrics(prices, log_returns, 12)

    end = len(prices) - 1
    target = prices.index[end] - pd.DateOffset(months=12)
    expected_start = prices.index.searchsorted(target, side="left")

    assert starts[end] == expected_start
    assert prices.index[expected_start] == pd.Timestamp("2025-08-18")
    expected_return = prices.iloc[end, 0] / prices.iloc[expected_start, 0] - 1
    assert np.isclose(returns.iloc[end, 0], expected_return)


def test_calendar_windows_are_not_fixed_21_63_126_189_252_rows():
    prices = _prices()
    log_returns = np.log(prices / prices.shift(1))
    _, _, _, _, starts = _calendar_period_metrics(prices, log_returns, 12)
    end = len(prices) - 1
    actual_rows = end - starts[end] + 1
    assert actual_rows != 253  # fixed 252-return convention would imply 253 prices


def test_start_position_uses_calendar_months():
    idx = pd.DatetimeIndex(["2025-08-14", "2025-08-18", "2026-08-14"])
    starts = calendar_start_positions(idx, 12)
    assert starts[-1] == 0  # 2025-08-14 is exactly the calendar target
