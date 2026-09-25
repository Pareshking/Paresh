import numpy as np
import pandas as pd
import pytest

from src.engine.backtester import run_backtest


def test_benchmark_symbol_is_nifty_500():
    # Single source-of-truth benchmark required by the V1 research framework.
    from src.core.config import BENCHMARK_SYMBOL
    assert BENCHMARK_SYMBOL == "^CRSLDX"


def _prices(n=700, cols=10, seed=3):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range(end="2026-08-18", periods=n)
    return pd.DataFrame(
        100 * np.exp(np.cumsum(rng.normal(0.0005, 0.02, (n, cols)), axis=0)),
        index=idx, columns=[f"S{i}" for i in range(cols)],
    )


def test_the_benchmark_is_the_supplied_index_not_the_universe_mean():
    """Two different index series, same stocks: only the benchmark may move.

    This used to compare two hand-typed series with each other and never ran
    the backtester, so it could not fail.
    """
    px = _prices()
    kw = dict(top_n=4, rebal_freq=21, ema_period=20, high_pct=0.0,
              cost_bps=0.0, buffer_n=6)
    rising = pd.Series(np.linspace(100, 160, len(px)), index=px.index)
    falling = pd.Series(np.linspace(100, 70, len(px)), index=px.index)
    a = run_backtest("bench-rising", px, _benchmark_close=rising, **kw)
    b = run_backtest("bench-falling", px, _benchmark_close=falling, **kw)

    assert a["stats"]["total_return"] == pytest.approx(b["stats"]["total_return"])
    assert a["stats"]["bench_return"] > 0 > b["stats"]["bench_return"]
