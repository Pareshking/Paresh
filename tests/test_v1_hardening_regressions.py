from pathlib import Path

import numpy as np
import pandas as pd

from src.engine.calendar_momentum import apply_calendar_momentum, latest_as_of_date
from src.engine.momentum import MomentumEngine, zscore_series
from src.engine.portfolio import _shrunk_cov
from src.ui.components import compute_signals
from src.core.types import MarketRegime


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
    assert latest.isna().all()


def test_portfolio_covariance_does_not_turn_missing_returns_into_zero() -> None:
    returns = pd.DataFrame(
        {"A": [0.01, 0.02, np.nan, 0.04], "B": [0.02, 0.01, 0.03, 0.02]}
    )
    cov = _shrunk_cov(returns)
    complete = returns.dropna(how="any")
    assert cov.shape == (2, 2)
    assert np.isfinite(cov.to_numpy()).all()
    assert np.isfinite(_shrunk_cov(complete).to_numpy()).all()
    expected = _shrunk_cov(complete)
    assert np.allclose(cov.to_numpy(), expected.to_numpy())






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
        root / "src/loaders/price_loader.py",
        root / "src/ui/views/qualified_view.py",
    ]
    offenders = [
        str(p.relative_to(root))
        for p in paths
        if ".ffill(" in p.read_text(encoding="utf-8")
    ]
    assert offenders == []


def test_zscore_small_cross_section_remains_missing() -> None:
    s = pd.Series([1.0, 2.0, np.nan])
    assert zscore_series(s).isna().all()


def test_historical_dataset_as_of_date_uses_last_observation() -> None:
    idx = pd.date_range("2022-01-03", periods=10, freq="B")
    assert latest_as_of_date(idx) == idx[-1].normalize()


def test_compute_signals_handles_pyarrow_backed_string_flags() -> None:
    rank_df = pd.DataFrame(
        {
            "Symbol": ["A", "B", "C"],
            "Rank": [1, 2, 3],
            "Above 50 EMA": pd.Series(["True", "False", "True"], dtype="string[pyarrow]"),
            "Near 52W High": pd.Series(["True", "True", "False"], dtype="string[pyarrow]"),
            "Composite Rank": pd.Series([1.0, np.nan, 3.0], dtype="float64"),
        }
    )
    signals = compute_signals(rank_df, MarketRegime.BULLISH, 1.0, 50.0)
    assert isinstance(signals, list)
