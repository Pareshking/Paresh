"""Regression tests: calculate_residual_momentum must use ^CRSLDX, not universe mean."""

import numpy as np
import pandas as pd
import pytest

from src.engine.momentum import MomentumEngine


def _prices(n=100, seed=42):
    rng = np.random.default_rng(seed)
    # End near today so calendar 6M lookback (latest_as_of_date → today) stays within data.
    idx = pd.bdate_range(end="2026-08-15", periods=n)
    return pd.DataFrame(
        {
            "A": 100.0 * np.cumprod(1 + rng.normal(0.001, 0.020, n)),
            "B": 100.0 * np.cumprod(1 + rng.normal(0.0005, 0.015, n)),
            "C": 100.0 * np.cumprod(1 + rng.normal(-0.001, 0.025, n)),
        },
        index=idx,
    )


def _bmk_rets(n=100, seed=99):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range(end="2026-08-15", periods=n)
    prices = pd.Series(
        100.0 * np.cumprod(1 + rng.normal(0.0008, 0.012, n)),
        index=idx,
    )
    return prices.pct_change(fill_method=None).dropna()


def test_stored_benchmark_used_instead_of_universe_mean():
    """Engine with benchmark_rets stored produces same ranks as explicit kwarg call."""
    prices = _prices()
    bmk = _bmk_rets()

    engine_stored = MomentumEngine(prices, benchmark_rets=bmk)
    engine_explicit = MomentumEngine(prices)

    ranks_stored = engine_stored.calculate_residual_momentum(months=None, window=60)
    ranks_explicit = engine_explicit.calculate_residual_momentum(
        benchmark_returns=bmk, months=None, window=60
    )

    pd.testing.assert_series_equal(ranks_stored, ranks_explicit)


def test_stored_benchmark_differs_from_universe_mean():
    """Stored-benchmark ranks must differ from what universe-mean fallback would give."""
    prices = _prices()
    bmk = _bmk_rets()

    universe_mean = prices.pct_change(fill_method=None).mean(axis=1)

    # Benchmark must be meaningfully different from the universe mean for this test to be valid.
    assert not np.allclose(
        bmk.reindex(universe_mean.dropna().index).dropna().values,
        universe_mean.dropna().values[: len(bmk.dropna())],
        atol=1e-6,
    ), "Benchmark and universe mean are identical — test is not meaningful"

    engine_bm = MomentumEngine(prices, benchmark_rets=bmk)
    engine_um = MomentumEngine(prices, benchmark_rets=universe_mean)

    ranks_bm = engine_bm.calculate_residual_momentum(months=None, window=60)
    ranks_um = engine_um.calculate_residual_momentum(months=None, window=60)

    assert not ranks_bm.equals(ranks_um), (
        "Residual alpha ranks must differ when benchmark differs from universe mean"
    )


def test_no_benchmark_returns_nan():
    """Without a stored or explicit benchmark, residual alpha must return all NaN."""
    prices = _prices()
    engine = MomentumEngine(prices)  # no benchmark_rets

    ranks = engine.calculate_residual_momentum(months=None, window=60)

    assert ranks.isna().all(), (
        "Expected all-NaN when no benchmark is available — universe mean must not be used"
    )


def test_explicit_kwarg_overrides_stored_benchmark():
    """Explicit benchmark_returns kwarg takes priority over the stored one."""
    prices = _prices()
    bmk_stored = _bmk_rets(seed=99)
    bmk_explicit = _bmk_rets(seed=77)

    engine = MomentumEngine(prices, benchmark_rets=bmk_stored)

    ranks_stored = engine.calculate_residual_momentum(months=None, window=60)
    ranks_explicit = engine.calculate_residual_momentum(
        benchmark_returns=bmk_explicit, months=None, window=60
    )
    ranks_same_as_stored = engine.calculate_residual_momentum(
        benchmark_returns=bmk_stored, months=None, window=60
    )

    # Explicit with different series should differ from stored
    assert not ranks_stored.equals(ranks_explicit)
    # Explicit with same series as stored should be equal
    pd.testing.assert_series_equal(ranks_stored, ranks_same_as_stored)


def test_get_multi_strategy_overlay_uses_stored_benchmark():
    """get_multi_strategy_overlay propagates the stored benchmark to residual alpha."""
    prices = _prices(n=120)
    bmk = _bmk_rets(n=120)

    rank_df = pd.DataFrame(
        {
            "Symbol": list(prices.columns),
            "Industry": ["Sector1", "Sector1", "Sector2"],
            "Rank": [1, 2, 3],
        }
    )

    engine_with_bm = MomentumEngine(prices, benchmark_rets=bmk)
    engine_with_bm.calculate_sharpe_momentum()
    overlay_with_bm = engine_with_bm.get_multi_strategy_overlay(rank_df, top_n=2)

    engine_no_bm = MomentumEngine(prices)
    engine_no_bm.calculate_sharpe_momentum()
    overlay_no_bm = engine_no_bm.get_multi_strategy_overlay(rank_df, top_n=2)

    # With benchmark: Residual Rank should be populated
    assert "Residual Rank" in overlay_with_bm.columns
    assert not overlay_with_bm["Residual Rank"].isna().all(), (
        "Residual Rank must not be all NaN when benchmark is stored in engine"
    )

    # Without benchmark: Residual Rank must be all NaN
    assert overlay_no_bm["Residual Rank"].isna().all(), (
        "Residual Rank must be all NaN when no benchmark is available"
    )
