"""One normaliser, called from everywhere.

The expression lived inline ten times plus in two helper functions spelled
differently -- _normalize_ticker_cols in the engine, _normalise_ticker_level in
the loader. That is the surface the duplicate-column bug lived on: the
incremental merge normalised one frame and not the other, the labels
disagreed, and a vertical concat produced 7,500 columns where 3,750 belonged.

Two frames can only be merged safely if the same code labelled both.
"""
import pathlib

import pandas as pd
import pytest

from src.core.tickers import normalise_columns, normalise_symbol

SRC = pathlib.Path(__file__).resolve().parents[1] / "src"


@pytest.mark.parametrize(("raw", "want"), [
    ("INDIGO.NS", "INDIGO"),
    ("indigo.ns", "INDIGO"),
    ("  Indigo.Ns  ", "INDIGO"),
    ("INDIGO", "INDIGO"),
    ("M.NS.CO", "M.NS.CO"),      # .NS mid-name is part of the name
    ("BAJAJ-AUTO.NS", "BAJAJ-AUTO"),
])
def test_symbols_normalise(raw, want):
    assert normalise_symbol(raw) == want


def test_case_is_folded_before_the_suffix_is_stripped():
    """The bug every inline copy shared.

    .replace(".NS", "").strip().upper() leaves a lowercase ".ns" untouched and
    returns "INDIGO.NS" -- two labels for one stock. Yahoo sends uppercase, so
    it never fired; it was one casing change from firing.
    """
    assert normalise_symbol("indigo.ns") == "INDIGO"


def test_normalisation_is_idempotent():
    once = normalise_symbol("TCS.NS")
    assert normalise_symbol(once) == once


def test_multiindex_touches_only_the_ticker_level():
    cols = pd.MultiIndex.from_tuples(
        [("INDIGO.NS", "Close"), ("INDIGO.NS", "Open")], names=["Ticker", "Price"]
    )
    df = pd.DataFrame([[1.0, 2.0]], columns=cols)

    out = normalise_columns(df, level=0)

    assert list(out.columns.get_level_values(0)) == ["INDIGO", "INDIGO"]
    assert list(out.columns.get_level_values(1)) == ["Close", "Open"]


def test_flat_columns_are_handled():
    df = pd.DataFrame([[1.0, 2.0]], columns=["INDIGO.NS", "tcs.ns"])
    assert list(normalise_columns(df).columns) == ["INDIGO", "TCS"]


def test_empty_frame_is_returned_untouched():
    empty = pd.DataFrame()
    assert normalise_columns(empty) is empty


def test_no_inline_copies_survive_in_src():
    """The consolidation itself, guarded.

    A new inline copy is how the twelve accumulated. If one reappears, the
    invariant that two frames were labelled by the same code is gone again.
    """
    offenders = [
        f"{p.relative_to(SRC)}:{i}"
        for p in SRC.glob("**/*.py")
        if p.name != "tickers.py"
        for i, line in enumerate(p.read_text().splitlines(), 1)
        if '.replace(".NS"' in line and not line.lstrip().startswith("#")
    ]
    assert not offenders, f"inline ticker normalisation reappeared: {offenders}"
