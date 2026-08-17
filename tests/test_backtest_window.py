import inspect
import numpy as np
import pandas as pd
from src.engine.backtester import run_backtest
def test_backtest_months_limits_rebalance_window():
    idx = pd.bdate_range("2024-01-01", "2026-08-17")
    prices = pd.DataFrame({"A": np.linspace(100, 180, len(idx)), "B": np.linspace(100, 150, len(idx)), "C": np.linspace(100, 130, len(idx))}, index=idx)
    result = run_backtest("test-6m-window", prices, top_n=1, rebal_freq=21, ranking_method="Return (Classic Momentum)", lookback_ret=126, ema_period=20, high_pct=0.0, cost_bps=0.0, buffer_n=1, backtest_months=6)
    assert result is not None
    source = inspect.getsource(run_backtest)
    assert "backtest_months" in source
    assert "cutoff_date" in source
    assert "rebal_dates = [i for i in rebal_dates if dates[i] >= cutoff_date]" in source
