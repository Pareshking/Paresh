import numpy as np
import pandas as pd
import pytest

from src.engine.backtester import _calendar_period_sharpe

def test_backtester_12m_uses_calendar_start_not_252_rows():
    dates = pd.bdate_range("2025-08-01", "2026-08-14")
    prices = pd.DataFrame({"A": np.exp(np.linspace(5, 5.5, len(dates)))}, index=dates)
    log_returns = np.log(prices / prices.shift(1))
    score, start = _calendar_period_sharpe(prices, log_returns, len(prices) - 1, 12)
    assert prices.index[start] == pd.Timestamp("2025-08-14")
    assert np.isfinite(score["A"])
    assert len(prices) - 1 - start != 252

def test_backtester_6m_uses_calendar_start():
    dates = pd.bdate_range("2025-08-01", "2026-08-14")
    prices = pd.DataFrame({"A": np.exp(np.linspace(5, 5.5, len(dates)))}, index=dates)
    log_returns = np.log(prices / prices.shift(1))
    _, start = _calendar_period_sharpe(prices, log_returns, len(prices) - 1, 6)
    target = pd.Timestamp("2026-08-14") - pd.DateOffset(months=6)   # a Saturday
    # The first session on or after the target -- not merely any later one.
    assert prices.index[start] == prices.index[prices.index >= target][0]
    assert prices.index[start] == pd.Timestamp("2026-02-16")

def test_backtester_missing_return_observation_not_zero_filled():
    dates = pd.bdate_range("2026-01-01", "2026-04-30")
    prices = pd.DataFrame({"A": np.linspace(100, 130, len(dates))}, index=dates)
    # Inside the 3-month window. The hole used to sit at row 20 (2026-01-29),
    # one session BEFORE the window opens, so it never reached the statistic.
    prices.iloc[-20, 0] = np.nan
    log_returns = np.log(prices / prices.shift(1))
    end = len(prices) - 1
    score, start = _calendar_period_sharpe(prices, log_returns, end, 3)
    window = log_returns["A"].iloc[start + 1 : end + 1]
    assert window.isna().any()                      # the hole is inside the window
    observed = window.dropna()
    expected = (np.log(prices["A"].iloc[end] / prices["A"].iloc[start])
                / (observed.std(ddof=0) * np.sqrt(len(observed))))
    assert score["A"] == pytest.approx(expected)
    zero_filled, _ = _calendar_period_sharpe(prices, log_returns.fillna(0.0), end, 3)
    assert zero_filled["A"] != pytest.approx(score["A"])   # the fill would show
