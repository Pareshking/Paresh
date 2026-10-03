import numpy as np
import pandas as pd
import pytest

from src.engine.backtester import _rolling_high_at


@pytest.mark.parametrize("idx", [0, 124, 125, 251, 252, 253, 269])
def test_signal_date_high_matches_full_history_rolling(idx: int) -> None:
    """The memory-saving single-date path must equal the canonical full matrix."""
    rng = np.random.default_rng(20261003)
    values = rng.uniform(10.0, 500.0, size=(270, 6))
    prices = pd.DataFrame(
        values,
        index=pd.bdate_range("2025-01-01", periods=270),
        columns=["A", "B", "C", "D", "E", "F"],
    )

    # Exercise rolling min_periods at the 125/126-observation boundary and
    # holes scattered throughout a 252-session window.
    prices.iloc[:125, 0] = np.nan
    prices.iloc[125, 0] = 101.0
    prices.iloc[:126, 1] = np.nan
    prices.iloc[126, 1] = 102.0
    prices.iloc[::11, 2] = np.nan
    prices.iloc[::17, 3] = np.nan
    prices.iloc[40, 4] = np.inf
    prices.iloc[60, 5] = -np.inf

    expected = prices.rolling(252, min_periods=126).max().iloc[idx]
    actual = _rolling_high_at(prices, idx)
    pd.testing.assert_series_equal(actual, expected, check_exact=True)


def test_single_date_high_matches_reference_for_every_row() -> None:
    rng = np.random.default_rng(376)
    prices = pd.DataFrame(
        rng.normal(100.0, 15.0, size=(310, 12)),
        index=pd.bdate_range("2019-01-01", periods=310),
        columns=[f"S{i}" for i in range(12)],
    )
    prices.iloc[::7, 1] = np.nan
    prices.iloc[:125, 2] = np.nan
    prices.iloc[125, 2] = 99.0
    prices.iloc[::19, 3] = np.nan

    reference = prices.rolling(252, min_periods=126).max()
    for idx in range(len(prices)):
        pd.testing.assert_series_equal(
            _rolling_high_at(prices, idx), reference.iloc[idx], check_exact=True
        )
