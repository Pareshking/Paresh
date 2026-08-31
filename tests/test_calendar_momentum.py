import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd

from src.engine.calendar_momentum import _calendar_period_metrics, calendar_start_positions


def _prices(start="2025-08-01", end="2026-08-14"):
    dates = pd.bdate_range(start, end)
    # 15-Aug-2025 was a Friday NSE holiday; remove it from the synthetic market data.
    dates = dates[dates != pd.Timestamp("2025-08-15")]
    values = np.exp(np.linspace(5.0, 5.5, len(dates)))
    return pd.DataFrame({"RELIANCE": values}, index=dates)


def test_calendar_12m_uses_first_trading_day_on_or_after_target():
    prices = _prices()
    log_returns = np.log(prices / prices.shift(1))
    _, returns, _, starts = _calendar_period_metrics(
        prices, log_returns, 12, latest_as_of=pd.Timestamp("2026-08-17")
    )

    end = len(prices) - 1
    target = pd.Timestamp("2026-08-17") - pd.DateOffset(months=12)
    expected_start = prices.index.searchsorted(target, side="left")

    assert target == pd.Timestamp("2025-08-17")
    assert starts[end] == expected_start
    assert prices.index[expected_start] == pd.Timestamp("2025-08-18")
    expected_return = prices.iloc[end, 0] / prices.iloc[expected_start, 0] - 1
    # returns is now a Series (last row only); index 0 → "RELIANCE"
    assert np.isclose(returns.iloc[0], expected_return)


def test_calendar_windows_are_not_fixed_21_63_126_189_252_rows():
    prices = _prices()
    log_returns = np.log(prices / prices.shift(1))
    _, _, _, starts = _calendar_period_metrics(
        prices, log_returns, 12, latest_as_of=pd.Timestamp("2026-08-17")
    )
    end = len(prices) - 1
    actual_rows = end - starts[end] + 1
    assert actual_rows != 253


def test_start_position_uses_calendar_as_of_date():
    idx = pd.DatetimeIndex(["2025-08-14", "2025-08-18", "2026-08-14"])
    starts = calendar_start_positions(
        idx, 12, latest_as_of=pd.Timestamp("2026-08-17")
    )
    assert starts[-1] == 1


def test_calendar_metric_returns_four_values_without_r2():
    prices = _prices()
    log_returns = np.log(prices / prices.shift(1))
    result = _calendar_period_metrics(
        prices, log_returns, 3, latest_as_of=pd.Timestamp("2026-08-17")
    )
    assert len(result) == 4

