"""The four alternative systems, MVO and Delivery are gone. Keep them gone.

None of the removed ranking systems ever fed the composite Rank -- they
produced extra columns and a Multi-Strategy tab. Each carried its own failure
modes: MVO silently degraded to Equal Weight on any exception while still
reporting itself as MVO (audit F1), and residual alpha reached out to Yahoo
mid-calculation, making a compute method's cost depend on a third party.

A re-import or a stray column reference would resurrect a half-wired feature,
so this asserts the absence rather than trusting it.
"""
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
CODE = [p for p in list((ROOT / "src").glob("**/*.py"))
        + list((ROOT / "scripts").glob("*.py")) + [ROOT / "app.py"]]


@pytest.mark.parametrize("name", [
    "calculate_exp_regression",
    "calculate_residual_momentum",
    "calculate_industry_relative",
    "calculate_momentum_acceleration",
    "get_multi_strategy_overlay",
])
def test_the_engine_no_longer_exposes_the_removed_systems(name):
    from src.engine.momentum import MomentumEngine
    assert not hasattr(MomentumEngine, name)


def test_mvo_is_gone_from_the_portfolio_engine():
    from src.engine.portfolio import PortfolioOptimizer
    assert not hasattr(PortfolioOptimizer, "mean_variance")


def test_the_surviving_weighting_schemes_still_work():
    """Removal must not have taken the good ones with it."""
    import numpy as np
    import pandas as pd
    from src.engine.portfolio import PortfolioOptimizer

    idx = pd.date_range("2025-01-01", periods=200, freq="B")
    rng = np.random.default_rng(7)
    syms = [f"S{i}" for i in range(5)]
    log_ret = pd.DataFrame(rng.normal(0, 0.01, (len(idx), len(syms))), index=idx, columns=syms)
    opt = PortfolioOptimizer(log_ret, sector_map={s: "X" for s in syms})

    assert np.isclose(opt.equal_weight(syms).sum(), 1.0)
    assert np.isclose(opt.inverse_volatility(syms).sum(), 1.0)


def test_the_weight_method_enum_offers_only_what_exists():
    from src.core.types import WeightMethod
    assert {m.value for m in WeightMethod} == {"Equal Weight", "Inverse Volatility"}


@pytest.mark.parametrize("token", [
    "strategy_view", "delivery_view", "delivery_loader",
    "mean_variance", "MVO (Mean-Variance)",
    "calculate_residual_momentum", "calculate_exp_regression",
])
def test_no_module_still_imports_or_calls_the_removed_code(token):
    offenders = [
        f"{p.relative_to(ROOT)}:{i}"
        for p in CODE
        for i, line in enumerate(p.read_text().splitlines(), 1)
        if token in line and not line.lstrip().startswith("#")
    ]
    assert not offenders, f"{token} still referenced at {offenders}"


def test_the_deleted_modules_are_actually_deleted():
    for rel in ("src/ui/views/strategy_view.py",
                "src/ui/views/delivery_view.py",
                "src/loaders/delivery_loader.py"):
        assert not (ROOT / rel).exists(), f"{rel} is still on disk"


def test_the_app_still_imports_cleanly():
    """The tab tuple and the tab list must still line up after two removals."""
    import importlib
    importlib.import_module("app")
