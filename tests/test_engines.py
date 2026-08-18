"""
Unit tests for quantitative engines: MomentumEngine, PortfolioOptimizer, Backtester, and Breadth.
"""

import os
import sys
import numpy as np
import pandas as pd
import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(__file__, "../.."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.engine.momentum import MomentumEngine
from src.engine.portfolio import PortfolioOptimizer
from src.engine.backtester import run_backtest
from src.engine.breadth import compute_ma_breadth, compute_hl_timeseries


@pytest.fixture
def sample_market_data():
    # Seeded, and a real price PATH rather than independent draws. The old
    # fixture called np.random.lognormal with no seed, so every run tested a
    # different market -- test_backtester passed or failed on the draw. It also
    # produced i.i.d. prices with no autocorrelation, which is not something a
    # momentum strategy can meaningfully rank.
    #
    # 760 sessions because the backtest reports the last 6 COMPLETED months and
    # reserves a full 12-month formation window before them.
    n_periods = 760
    dates = pd.date_range("2022-01-01", periods=n_periods, freq="B")
    symbols = ["TCS", "INFY", "RELIANCE", "HDFCBANK", "ICICIBANK", "ITC"]
    rng = np.random.default_rng(20260818)
    drifts = np.linspace(0.0008, -0.0002, len(symbols))  # dispersion to rank on
    steps = rng.normal(drifts, 0.012, (n_periods, len(symbols)))
    prices = pd.DataFrame(
        50.0 * np.exp(np.cumsum(steps, axis=0)), index=dates, columns=symbols
    )
    highs = prices * 1.01
    lows = prices * 0.99
    vols = pd.DataFrame(100000, index=dates, columns=symbols)
    return prices, highs, lows, vols, symbols


def test_momentum_engine(sample_market_data):
    prices, highs, lows, vols, symbols = sample_market_data
    calc = MomentumEngine(
        prices, high_df=highs, low_df=lows, close_df=prices, volume_df=vols
    )
    calc.calculate_sharpe_momentum()
    assert calc.momentum_scores is not None
    assert calc.momentum_scores.shape == prices.shape

    idx_info = pd.DataFrame(
        {
            "Symbol": symbols,
            "Company Name": symbols,
            "Industry": ["IT", "IT", "Energy", "Banking", "Banking", "FMCG"],
            "Indices": ["N50"] * len(symbols),
        }
    )
    mcaps = pd.Series({s: 1e11 for s in symbols})
    rankings = calc.get_rankings(idx_info, mcaps)
    assert not rankings.empty
    assert "Rank" in rankings.columns
    assert len(rankings) == len(symbols)


def test_portfolio_optimizer(sample_market_data):
    prices, _, _, _, symbols = sample_market_data
    log_rets = np.log(prices / prices.shift(1).replace(0, np.nan))
    sec_map = dict(
        zip(symbols, ["IT", "IT", "Energy", "Banking", "Banking", "FMCG"])
    )
    opt = PortfolioOptimizer(log_rets, sector_map=sec_map)

    w_eq = opt.equal_weight(symbols)
    assert np.isclose(w_eq.sum(), 1.0)

    w_iv = opt.inverse_volatility(symbols)
    assert np.isclose(w_iv.sum(), 1.0)

    w_erc = opt.equal_risk_contribution(symbols)
    assert np.isclose(w_erc.sum(), 1.0)

    w_constr = opt.apply_constraints(w_eq, sector_cap=0.40, stock_cap=0.25)
    assert np.isclose(w_constr.sum(), 1.0)
    assert (w_constr <= 0.25 + 1e-6).all()


def test_backtester(sample_market_data):
    prices, _, _, _, _ = sample_market_data
    bt = run_backtest("test_hash", prices, top_n=3, rebal_freq=21, lookback_ret=63)
    assert bt is not None
    assert "stats" in bt
    assert "equity_curve" in bt
    assert bt["stats"]["n_periods"] > 0
