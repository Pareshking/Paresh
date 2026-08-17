import numpy as np
import pandas as pd

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
    target = pd.Timestamp("2026-08-14") - pd.DateOffset(months=6)
    assert prices.index[start] >= target

def test_backtester_missing_return_observation_not_zero_filled():
    dates = pd.bdate_range("2026-01-01", "2026-04-30")
    prices = pd.DataFrame({"A": np.linspace(100, 130, len(dates))}, index=dates)
    prices.iloc[20, 0] = np.nan
    log_returns = np.log(prices / prices.shift(1))
    score, _ = _calendar_period_sharpe(prices, log_returns, len(prices) - 1, 3)
    assert np.isfinite(score["A"])
    assert pd.isna(log_returns.iloc[20, 0])
