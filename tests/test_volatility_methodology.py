import numpy as np
import pandas as pd

from src.engine.portfolio import PortfolioOptimizer


def _returns(periods=80):
    idx = pd.bdate_range("2026-01-01", periods=periods)
    a = np.tile([0.01, -0.01], periods // 2)
    b = np.tile([0.02, -0.02], periods // 2)
    return pd.DataFrame({"A": a, "B": b}, index=idx)


def test_inverse_volatility_uses_63_sessions_and_sqrt_252():
    returns = _returns()
    opt = PortfolioOptimizer(returns)
    weights = opt.inverse_volatility(["A", "B"], window=63)
    # Volatility ratio is 1:2, so inverse-vol weights are 2:1.
    assert np.isclose(weights["A"], 2.0 / 3.0)
    assert np.isclose(weights["B"], 1.0 / 3.0)


def test_volatility_target_reports_annualized_realized_volatility():
    returns = _returns()
    opt = PortfolioOptimizer(returns)
    weights = pd.Series({"A": 0.5, "B": 0.5})
    _, scale, realised = opt.volatility_target(weights, target_vol=0.25, window=63)
    expected_daily = 0.015
    expected_annual = expected_daily * np.sqrt(252)
    expected_scale = min(1.0, max(0.10, 0.25 / expected_annual))
    assert np.isclose(realised, expected_annual)
    assert np.isclose(scale, expected_scale)


def test_zero_volatility_falls_back_to_equal_weight():
    idx = pd.bdate_range("2026-01-01", periods=80)
    returns = pd.DataFrame({"A": 0.01, "B": 0.01}, index=idx)
    opt = PortfolioOptimizer(returns)
    weights = opt.inverse_volatility(["A", "B"], window=63)
    assert np.isclose(weights.sum(), 1.0)
    assert np.all(np.isfinite(weights.values))
    assert np.isclose(weights["A"], 0.5)
    assert np.isclose(weights["B"], 0.5)
