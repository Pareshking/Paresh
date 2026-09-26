"""The incremental top-up must extend the history, not duplicate it.

Found in the daily sync log of 2026-08-18, which said out loud:

    Price cache save failed (incremental): Duplicate column names found:
    [('INDIGO', 'Open'), ('INDIGO', 'High'), ('INDIGO', 'Low') ...
    Price cache updated with shape (500, 7500)

7500 columns where 3750 belonged -- one per series for the cached history and
another for the new sessions, each half NaN.

Production never hit this before: Streamlit Cloud wipes /tmp on restart, so the
loader always took the FULL download path. Seeding the cache from the published
snapshot is exactly what makes this path live in production, so the bug had to
be fixed in the same breath.
"""

import numpy as np
import pandas as pd
import pytest

from src.loaders import price_loader
from src.loaders.price_loader import (
    _coalesce_duplicate_columns,
    _normalise_ticker_level,
)

FIELDS = ["Open", "High", "Low", "Close", "Volume"]


def _frame(symbols, index, suffix="", start=0.0):
    cols = {(s + suffix, f): np.arange(len(index), dtype=float) + start
            for s in symbols for f in FIELDS}
    df = pd.DataFrame(cols, index=index)
    df.columns = pd.MultiIndex.from_tuples(df.columns, names=["Ticker", "Price"])
    return df


@pytest.fixture(autouse=True)
def _sandboxed_cache(tmp_path, monkeypatch):
    """The real merge writes the cache; point it at a temp file. Session
    filters that consult the clock are neutralised so the fixture dates stay."""
    monkeypatch.setattr(price_loader, "PRICES_FILE", str(tmp_path / "prices.parquet"))
    monkeypatch.setattr(price_loader, "_drop_phantom_sessions", lambda frame: frame)
    monkeypatch.setattr(price_loader, "_drop_unsettled_rows", lambda frame: frame)
    return tmp_path / "prices.parquet"


def _merge(cached, new_data):
    """The loader's own incremental merge -- not a restatement of it. (This
    helper used to re-implement the merge "in the order the loader now does
    it", so the tests passed whatever the loader actually did.)"""
    return price_loader._merge_and_save_cache(cached, new_data)


def test_yfinance_suffix_does_not_double_the_columns():
    syms = ["INDIGO", "CIPLA"]
    cached = _frame(syms, pd.bdate_range("2026-08-10", periods=5))
    new_data = _frame(syms, pd.bdate_range("2026-08-17", periods=2), suffix=".NS", start=100)

    combined = _merge(cached, new_data)

    assert combined.shape[1] == len(syms) * len(FIELDS)
    assert not combined.columns.duplicated().any()


def test_new_sessions_extend_the_same_series():
    """The point of the top-up: the newest close must be readable as a scalar."""
    cached = _frame(["INDIGO"], pd.bdate_range("2026-08-10", periods=5))
    new_data = _frame(["INDIGO"], pd.bdate_range("2026-08-17", periods=2),
                      suffix=".NS", start=100)

    combined = _merge(cached, new_data)
    close = combined[("INDIGO", "Close")]

    assert isinstance(close, pd.Series), "duplicate labels would give a DataFrame"
    assert len(close) == 7
    assert close.notna().all(), "no NaN holes where the two frames met"
    assert close.iloc[-1] == 101.0
    assert close.index.is_monotonic_increasing


def test_the_merged_frame_is_actually_written(_sandboxed_cache):
    """The original symptom was a parquet save that failed outright."""
    syms = ["INDIGO", "CIPLA"]
    cached = _frame(syms, pd.bdate_range("2026-08-10", periods=5))
    new_data = _frame(syms, pd.bdate_range("2026-08-17", periods=2), suffix=".NS")

    combined = _merge(cached, new_data)

    assert _sandboxed_cache.exists(), "the loader did not persist the merge"
    assert pd.read_parquet(_sandboxed_cache).shape == combined.shape == (7, 10)


def test_a_symbol_only_in_the_new_data_is_kept():
    cached = _frame(["INDIGO"], pd.bdate_range("2026-08-10", periods=5))
    new_data = _frame(["INDIGO", "NEWCO"], pd.bdate_range("2026-08-17", periods=2),
                      suffix=".NS")

    combined = _merge(cached, new_data)

    assert ("NEWCO", "Close") in combined.columns
    assert combined[("NEWCO", "Close")].dropna().shape[0] == 2


def test_coalesce_is_a_no_op_when_nothing_is_duplicated():
    frame = _frame(["INDIGO"], pd.bdate_range("2026-08-10", periods=3))
    assert _coalesce_duplicate_columns(frame) is frame


def test_coalesce_folds_disjoint_halves_together():
    """The backstop, exercised directly on a frame that is already broken."""
    idx = pd.bdate_range("2026-08-10", periods=4)
    left = pd.DataFrame({("INDIGO", "Close"): [1.0, 2.0, np.nan, np.nan]}, index=idx)
    right = pd.DataFrame({("INDIGO", "Close"): [np.nan, np.nan, 3.0, 4.0]}, index=idx)
    broken = pd.concat([left, right], axis=1)
    broken.columns = pd.MultiIndex.from_tuples(broken.columns, names=["Ticker", "Price"])
    assert broken.columns.duplicated().any()

    fixed = _coalesce_duplicate_columns(broken)

    assert not fixed.columns.duplicated().any()
    assert list(fixed[("INDIGO", "Close")]) == [1.0, 2.0, 3.0, 4.0]


@pytest.mark.parametrize("suffix", ["", ".NS"])
def test_normalise_is_idempotent(suffix):
    frame = _frame(["INDIGO"], pd.bdate_range("2026-08-10", periods=2), suffix=suffix)
    once = _normalise_ticker_level(frame)
    assert list(_normalise_ticker_level(once).columns) == list(once.columns)
    assert set(once.columns.get_level_values(0)) == {"INDIGO"}
