"""Regression for the production ValueError that took down the Screener.

"Above 50 EMA" and "Near 52W High" hold tick marks, not booleans. Under
pandas 3 those land in the string dtype, where sum() concatenates rather than
counts -- and an EMPTY column sums to '', so int(col.sum()) raised
``ValueError: invalid literal for int() with base 10: ''``.
"""
import pandas as pd
import pytest

from src.ui.components import to_bool_mask


def test_empty_string_column_counts_zero_not_valueerror():
    """The exact production failure: empty str-dtype column summed to ''."""
    empty = pd.Series([], dtype="str")
    with pytest.raises(ValueError):
        int(empty.sum())          # what the code used to do
    assert int(to_bool_mask(empty).sum()) == 0


def test_tick_column_counts_rather_than_concatenates():
    ticks = pd.Series(["✅", "❌", "✅", "✅"], dtype="str")
    with pytest.raises(ValueError):
        int(ticks.sum())          # concatenates to '✅❌✅✅'
    assert int(to_bool_mask(ticks).sum()) == 3


@pytest.mark.parametrize("dtype", ["str", "object"])
def test_mask_is_usable_for_boolean_indexing(dtype):
    df = pd.DataFrame({
        "Rank": [1, 2, 3, 4],
        "Above 50 EMA": pd.Series(["✅", "❌", "✅", "✅"], dtype=dtype),
        "Near 52W High": pd.Series(["✅", "✅", "❌", "✅"], dtype=dtype),
    })
    sel = df[to_bool_mask(df["Above 50 EMA"]) & to_bool_mask(df["Near 52W High"])]
    assert sel["Rank"].tolist() == [1, 4]


def test_real_booleans_still_work():
    assert int(to_bool_mask(pd.Series([True, False, True])).sum()) == 2


@pytest.mark.parametrize("value,expected", [
    ("✅", True), ("❌", False), ("True", True), ("1", True),
    ("true", True), ("yes", True), ("", False), ("—", False), (None, False),
])
def test_truthiness_values(value, expected):
    assert bool(to_bool_mask(pd.Series([value], dtype=object)).iloc[0]) is expected


def test_missing_column_yields_empty_mask():
    """view.get() on an absent column returns None; that must not explode."""
    df = pd.DataFrame({"Rank": [1, 2]})
    assert int(to_bool_mask(df.get("Above 50 EMA")).sum()) == 0


def test_mask_preserves_index_for_alignment():
    s = pd.Series(["✅", "❌"], index=[7, 9], dtype="str")
    assert to_bool_mask(s).index.tolist() == [7, 9]
