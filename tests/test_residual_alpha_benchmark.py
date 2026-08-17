import numpy as np
import pandas as pd
from src.engine.momentum import MomentumEngine

def make_data():
    idx = pd.bdate_range("2026-01-01", periods=100)
    prices = pd.DataFrame({"A":100*(1.001**np.arange(100)), "B":100*(0.999**np.arange(100))}, index=idx)
    # Varying benchmark returns are required because zero benchmark variance must correctly produce NaN alpha.
    benchmark = pd.Series(100*np.cumprod(1 + 0.0005 + 0.001*np.sin(np.arange(100))), index=idx, name="^CRSLDX")
    return prices, benchmark

def test_default_residual_alpha_uses_external_benchmark(monkeypatch):
    prices, benchmark = make_data()
    from src.loaders import price_loader
    monkeypatch.setattr(price_loader, "fetch_benchmark_history", lambda period="2y": benchmark)
    ranks = MomentumEngine(prices).calculate_residual_momentum(months=None, window=63)
    assert ranks.notna().sum() == 2
    assert ranks["A"] < ranks["B"]

def test_explicit_residual_benchmark_is_supported():
    prices, benchmark = make_data()
    ranks = MomentumEngine(prices).calculate_residual_momentum(benchmark_returns=benchmark.pct_change(fill_method=None), months=None, window=63)
    assert ranks.notna().sum() == 2

def test_constant_benchmark_returns_are_rejected():
    prices, benchmark = make_data()
    constant = pd.Series(0.0005, index=benchmark.index)
    ranks = MomentumEngine(prices).calculate_residual_momentum(benchmark_returns=constant, months=None, window=63)
    assert ranks.isna().all()
