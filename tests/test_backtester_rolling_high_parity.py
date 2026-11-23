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


def test_production_scale_signal_dates_match_full_history_reference() -> None:
    """Exercise the optimized lookup at 750-symbol / ~16-year scale."""
    rng = np.random.default_rng(20261003)
    rows, cols = 4200, 750
    values = rng.lognormal(mean=4.5, sigma=0.35, size=(rows, cols))
    prices = pd.DataFrame(
        values,
        index=pd.bdate_range("2010-01-04", periods=rows),
        columns=[f"S{i:03d}" for i in range(cols)],
    )
    # Representative price-history holes; no symbol gets silently filled.
    prices.iloc[::37, 4] = np.nan
    prices.iloc[::113, 81] = np.nan
    prices.iloc[:125, 749] = np.nan
    reference = prices.rolling(252, min_periods=126).max()
    month_ends = (
        pd.Series(np.arange(rows), index=prices.index)
        .groupby(prices.index.to_period("M"))
        .last()
        .astype(int)
        .tolist()
    )
    for idx in month_ends:
        pd.testing.assert_series_equal(
            _rolling_high_at(prices, idx), reference.iloc[idx], check_exact=True
        )


def test_non_finite_values_count_as_missing_as_pandas_rolling_treats_them() -> None:
    """pandas rolling turns +-inf into NaN before it aggregates (S204, 23 Nov 2026).

    So an inf is neither the high nor an observation towards min_periods. These
    columns sit exactly on the 126-observation boundary, where counting an inf
    as an observation would turn NaN into a number.
    """
    rows = 252
    prices = pd.DataFrame(
        np.nan, index=pd.bdate_range("2024-01-01", periods=rows), columns=list("ABCDEF")
    )
    tail = slice(rows - 126, rows)
    prices.iloc[tail, 0] = 50.0                    # exactly 126 finite: a high
    prices.iloc[tail, 1] = 50.0
    prices.iloc[rows - 126, 1] = np.inf            # 125 finite + inf: NaN in pandas
    prices.iloc[tail, 2] = 50.0
    prices.iloc[rows - 126, 2] = -np.inf           # 125 finite + -inf: NaN in pandas
    prices.iloc[:, 3] = 40.0
    prices.iloc[100, 3] = np.inf                   # inf is not the high: 40.0
    prices.iloc[:, 4] = -np.inf                    # nothing finite: NaN
    prices.iloc[:, 5] = 10.0
    prices.iloc[7, 5] = 99.0                       # an ordinary high inside the window

    expected = prices.rolling(252, min_periods=126).max().iloc[rows - 1]
    actual = _rolling_high_at(prices, rows - 1)
    pd.testing.assert_series_equal(actual, expected, check_exact=True)
    assert np.isnan(actual["B"]) and np.isnan(actual["C"]) and actual["D"] == 40.0


def test_float32_input_gives_the_float64_high_pandas_gives() -> None:
    prices = pd.DataFrame(
        np.random.default_rng(5).uniform(1, 9, size=(300, 4)).astype("float32"),
        index=pd.bdate_range("2023-01-02", periods=300),
    )
    expected = prices.rolling(252, min_periods=126).max().iloc[299]
    pd.testing.assert_series_equal(_rolling_high_at(prices, 299), expected, check_exact=True)
