from pathlib import Path

import numpy as np
import pandas as pd

from src.engine.calendar_momentum import (
    apply_calendar_momentum,
    latest_as_of_date,
    _winsorised_cross_section_z,
)
from src.engine.momentum import MomentumEngine
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


def test_cross_section_z_fewer_than_3_obs_is_nan() -> None:
    # A row with fewer than 3 real observations must stay all-NaN —
    # the same contract the retired zscore_series enforced, now on the
    # production function that actually runs in the ranking pipeline.
    scores = pd.DataFrame({"A": [1.0], "B": [2.0], "C": [np.nan]})
    z = _winsorised_cross_section_z(scores)
    assert z.iloc[0].isna().all()


def test_cross_section_z_zero_variance_is_nan() -> None:
    # A constant cross-section (zero spread) must stay all-NaN.
    scores = pd.DataFrame({"A": [5.0, 5.0], "B": [5.0, 5.0], "C": [5.0, 5.0]})
    z = _winsorised_cross_section_z(scores)
    assert z.notna().sum().sum() == 0


def test_cross_section_z_normal_cross_section_is_finite() -> None:
    # A healthy cross-section must produce finite z-scores.
    rng = np.random.default_rng(0)
    data = {f"S{i}": rng.normal(0, 1, 30) for i in range(20)}
    scores = pd.DataFrame(data)
    z = _winsorised_cross_section_z(scores)
    assert np.isfinite(z.to_numpy()[z.notna().to_numpy()]).all()


def test_cross_section_z_nan_stocks_remain_nan() -> None:
    # NaN in a stock's score must propagate as NaN in the z-score.
    scores = pd.DataFrame({"A": [1.0, 2.0], "B": [3.0, np.nan], "C": [2.0, 4.0]})
    z = _winsorised_cross_section_z(scores)
    assert pd.isna(z.loc[z.index[1], "B"])


def test_weight_change_reuses_period_z_scores_without_recompute() -> None:
    # _compute_period_z_scores populates _period_z_scores; _apply_weight_composite
    # reads from it. Changing weights must produce a different composite but must
    # not alter _period_z_scores (proving the expensive Sharpe pass is not repeated).
    from src.engine.calendar_momentum import _compute_period_z_scores, _apply_weight_composite

    prices = _prices(rows=80, cols=5)
    calc = MomentumEngine(prices, weights=[0.2, 0.2, 0.2, 0.2, 0.2])
    _compute_period_z_scores(calc)

    z_before = {m: df.copy() for m, df in calc._period_z_scores.items()}
    scores_equal = _apply_weight_composite(calc, [0.2, 0.2, 0.2, 0.2, 0.2])
    scores_shifted = _apply_weight_composite(calc, [0.5, 0.3, 0.1, 0.05, 0.05])

    # z-scores unchanged across two weight applications
    for m, z in calc._period_z_scores.items():
        assert z.equals(z_before[m]), f"z-scores mutated for {m}M window"

    # composites differ when weights differ
    assert not scores_equal.equals(scores_shifted)


def test_decompose_fields_matches_extract_by_coverage_path() -> None:
    # Build a synthetic MultiIndex matching yfinance's (Ticker, Field) layout.
    import sys
    import types
    import unittest.mock as mock

    # price_loader imports yfinance at module level; stub it so the test can
    # import the two pure functions without a live yfinance installation.
    if "yfinance" not in sys.modules:
        sys.modules["yfinance"] = types.ModuleType("yfinance")
    if "src.loaders.price_loader" in sys.modules:
        del sys.modules["src.loaders.price_loader"]

    with mock.patch.dict(sys.modules, {"streamlit": mock.MagicMock()}):
        from src.loaders.price_loader import _decompose_fields, _extract_field

    tickers = ["RELIANCE.NS", "TCS.NS", "INFY.NS"]
    fields = ["Adj Close", "Close", "High", "Low", "Volume", "Open"]
    idx = pd.date_range("2025-01-01", periods=5, freq="B")
    rng = np.random.default_rng(42)

    cols = pd.MultiIndex.from_tuples(
        [(t, f) for t in tickers for f in fields], names=["Ticker", "Price"]
    )
    data = rng.uniform(100, 200, size=(5, len(cols)))
    df = pd.DataFrame(data, index=idx, columns=cols)

    # Swap levels so it's (Field, Ticker) as yfinance sometimes returns
    df_swapped = df.swaplevel(axis=1).sort_index(axis=1)

    for raw in (df, df_swapped):
        result = _decompose_fields(raw)

        # _decompose_fields must return all six field keys
        for key in ("adj_close", "close", "high", "low", "volume", "open"):
            assert key in result, f"Missing key '{key}'"
            assert not result[key].empty, f"Empty DataFrame for '{key}'"

        # Column count must equal the number of tickers
        assert result["adj_close"].shape[1] == len(tickers)
        assert result["high"].shape[1] == len(tickers)
        assert result["volume"].shape[1] == len(tickers)

        # Cross-validate adj_close values against _extract_field (old path)
        old_adj = _extract_field(raw, ["Adj Close", "AdjClose", "Close"])
        new_adj = result["adj_close"]
        shared_cols = sorted(set(old_adj.columns) & set(new_adj.columns))
        assert shared_cols, "No shared columns between old and new adj_close paths"
        np.testing.assert_allclose(
            old_adj[shared_cols].to_numpy(),
            new_adj[shared_cols].to_numpy(),
            rtol=1e-10,
            err_msg="adj_close values diverge between _decompose_fields and _extract_field",
        )


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
