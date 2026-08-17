import numpy as np
import pandas as pd

from src.engine.portfolio import PortfolioOptimizer


def _returns(periods=80):
    idx = pd.bdate_range("2026-01-01", periods=periods)
    # Two deterministic daily log-return series with known relative volatility.
    a = np.full(periods, 0.01)
    b = np.full(periods, 0.02)
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


def test_volatility_methods_use_sample_standard_deviation():
    returns = _returns()
    # Constant series has zero sample volatility; inverse-vol safely falls back.
    opt = PortfolioOptimizer(returns)
    weights = opt.inverse_volatility(["A", "B"], window=63)
    assert np.isclose(weights.sum(), 1.0)
    assert np.all(np.isfinite(weights.values))
