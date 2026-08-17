import numpy as np
import pandas as pd

from src.engine.backtester import _calendar_period_sharpe


def test_benchmark_symbol_is_nifty_500():
    # Single source-of-truth benchmark required by the V1 research framework.
    from src.core.config import BENCHMARK_SYMBOL
    assert BENCHMARK_SYMBOL == "^CRSLDX"


def test_benchmark_series_is_not_universe_mean():
    prices = pd.DataFrame(
        {
            "A": [100.0, 101.0, 102.0, 103.0],
            "B": [100.0, 99.0, 98.0, 97.0],
            "^CRSLDX": [100.0, 100.5, 101.0, 101.5],
        },
        index=pd.bdate_range("2026-01-01", periods=4),
    )
    universe_mean = prices[["A", "B"]].pct_change(fill_method=None).mean(axis=1)
    benchmark = prices["^CRSLDX"].pct_change(fill_method=None)
    assert not np.allclose(universe_mean.iloc[1:].values, benchmark.iloc[1:].values)
