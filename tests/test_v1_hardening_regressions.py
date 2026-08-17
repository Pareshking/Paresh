from pathlib import Path

import numpy as np
import pandas as pd

from src.engine.calendar_momentum import apply_calendar_momentum
from src.engine.momentum import MomentumEngine
from src.engine.portfolio import _shrunk_cov


def _prices(rows: int = 80, cols: int = 3) -> pd.DataFrame:
    idx = pd.date_range("2026-01-01", periods=rows, freq="B")
    base = np.arange(rows, dtype=float) + 100.0
    data = {f"S{i}": base * (1.0 + 0.01 * i) for i in range(cols)}
    return pd.DataFrame(data, index=idx)


def test_calendar_cross_section_missing_factor_is_not_synthetic_zero() -> None:
    prices = _prices()
    prices.iloc[-1, 2] = np.nan
    calc = MomentumEngine(prices, weights=[1.0, 0.0, 0.0, 0.0, 0.0])
    apply_calendar_momentum(calc)
    latest = calc.momentum_scores.iloc[-1]
    # Only two valid stocks remain in the latest 1M cross-section; the
    # canonical minimum of three observations means the factor is unavailable.
    assert latest.isna().all()


def test_portfolio_covariance_does_not_turn_missing_returns_into_zero() -> None:
    returns = pd.DataFrame(
        {
            "A": [0.01, 0.02, np.nan, 0.04],
            "B": [0.02, 0.01, 0.03, 0.02],
        }
    )
    cov = _shrunk_cov(returns)
    complete = returns.dropna(how="any")
    assert cov.shape == (2, 2)
    assert np.isfinite(cov.to_numpy()).all()
    assert not np.isclose(cov.loc["A", "A"], _shrunk_cov(returns.fillna(0.0)).loc["A", "A"])
    assert np.isfinite(_shrunk_cov(complete).to_numpy()).all()


def test_residual_alpha_uses_paired_benchmark_observations() -> None:
    prices = _prices(90, 2)
    calc = MomentumEngine(prices)
    benchmark = pd.Series(np.linspace(0.001, 0.01, len(prices)), index=prices.index)
    benchmark.iloc[20:25] = np.nan
    ranks = calc.calculate_residual_momentum(benchmark_returns=benchmark, months=1)
    assert ranks.notna().sum() == 2


def test_industry_relative_singleton_has_no_peer_benchmark() -> None:
    prices = _prices(80, 2)
    calc = MomentumEngine(prices)
    calc.momentum_scores = pd.DataFrame(
        {"S0": [1.0], "S1": [2.0]}, index=[prices.index[-1]]
    )
    rank_df = pd.DataFrame(
        {"Symbol": ["S0", "S1"], "Industry": ["Only", "Other"]}
    )
    ranks = calc.calculate_industry_relative(rank_df)
    assert ranks.notna().sum() == 0


def test_runtime_contains_no_removed_r2_production_tokens() -> None:
    root = Path(__file__).resolve().parents[1]
    paths = [root / "app.py", *sorted((root / "src").rglob("*.py"))]
    forbidden = ("R²", "R^2", "R2", "Sharpe × R")
    offenders = []
    for path in paths:
        text = path.read_text(encoding="utf-8")
        if any(token in text for token in forbidden):
            offenders.append(str(path.relative_to(root)))
    assert offenders == []


def test_known_price_paths_do_not_forward_fill_prices_or_benchmark_returns() -> None:
    root = Path(__file__).resolve().parents[1]
    paths = [
        root / "src/engine/momentum.py",
        root / "src/loaders/price_loader.py",
        root / "src/ui/views/qualified_view.py",
    ]
    offenders = [str(p.relative_to(root)) for p in paths if ".ffill(" in p.read_text(encoding="utf-8")]
    assert offenders == []
