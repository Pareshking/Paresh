"""A symbol-namespace mismatch must not masquerade as "nothing qualified".

The ranking is joined by symbol: rank_df["Symbol"].map(score_by_symbol). If the
price columns are keyed differently from the universe -- "RELIANCE.NS" against
"RELIANCE" -- every Score maps to NaN, get_rankings drops all 750 rows, and the
app reports an empty screener with no indication that the data was fine and only
the labels disagreed.

_extract_field normalised the labels on both MultiIndex branches but returned a
flat frame untouched, and _clean_price_df skipped its symbol filter entirely
when nothing matched, so the mismatch travelled silently to the ranking.
"""
import numpy as np
import pandas as pd

from src.engine.momentum import MomentumEngine
from src.loaders.price_loader import extract_ohlcv

SYMBOLS = ["RELIANCE", "TCS"]


def _index(n=10):
    return pd.bdate_range(end="2026-08-18", periods=n)


def _values(n=10, cols=2, seed=0):
    return np.random.default_rng(seed).normal(100, 1, (n, cols))


def test_flat_frame_labels_are_normalised_like_multiindex_ones():
    """yfinance returns a flat frame when a batch collapses to one ticker."""
    idx = _index()
    flat = pd.DataFrame(_values(), index=idx, columns=["RELIANCE.NS", "TCS.NS"])
    adj, *_ = extract_ohlcv(flat, SYMBOLS)
    assert list(adj.columns) == SYMBOLS


def test_multiindex_frame_still_normalises():
    idx = _index()
    mi = pd.DataFrame(
        _values(cols=4), index=idx,
        columns=pd.MultiIndex.from_product([["RELIANCE.NS", "TCS.NS"], ["Close", "High"]]),
    )
    adj, *_ = extract_ohlcv(mi, SYMBOLS)
    assert sorted(adj.columns) == sorted(SYMBOLS)


def test_flat_and_multiindex_agree():
    """The two shapes must not disagree about what a symbol is called."""
    idx = _index()
    flat = pd.DataFrame(_values(), index=idx, columns=["RELIANCE.NS", "TCS.NS"])
    mi = pd.DataFrame(
        _values(cols=4), index=idx,
        columns=pd.MultiIndex.from_product([["RELIANCE.NS", "TCS.NS"], ["Close", "High"]]),
    )
    a, *_ = extract_ohlcv(flat, SYMBOLS)
    b, *_ = extract_ohlcv(mi, SYMBOLS)
    assert sorted(a.columns) == sorted(b.columns)


def test_engine_tolerates_suffixed_price_columns():
    """MomentumEngine normalises ticker labels in __init__, so a suffixed price
    frame still ranks. This is the defence that rules a namespace mismatch OUT
    as the cause of an empty ranking -- asserted so the normalisation is not
    quietly dropped later, which would turn good data into an empty screener."""
    n, cols = 300, 4
    idx = pd.bdate_range(end="2026-08-18", periods=n)
    rng = np.random.default_rng(5)
    prices = pd.DataFrame(
        100 + np.cumsum(rng.normal(0, 1, (n, cols)), axis=0),
        index=idx, columns=[f"S{i}.NS" for i in range(cols)],   # suffixed
    )
    info = pd.DataFrame({
        "Symbol": [f"S{i}" for i in range(cols)],                # bare
        "Industry": ["T"] * cols,
    })
    calc = MomentumEngine(prices)
    rank_df = calc.get_rankings(info, pd.Series(dtype=float))

    assert not rank_df.empty
    assert calc.ranking_diagnostics["symbols_matching_prices"] == cols


def test_thin_history_is_distinguishable_from_a_mismatch():
    """The two empty-ranking causes must not look alike in the diagnostics."""
    n, cols = 20, 4          # far below the 63-observation floor
    idx = pd.bdate_range(end="2026-08-18", periods=n)
    rng = np.random.default_rng(5)
    prices = pd.DataFrame(
        100 + np.cumsum(rng.normal(0, 1, (n, cols)), axis=0),
        index=idx, columns=[f"S{i}" for i in range(cols)],
    )
    info = pd.DataFrame({"Symbol": [f"S{i}" for i in range(cols)], "Industry": ["T"] * cols})
    calc = MomentumEngine(prices)
    rank_df = calc.get_rankings(info, pd.Series(dtype=float))
    diag = calc.ranking_diagnostics

    assert rank_df.empty
    assert diag["symbols_matching_prices"] == cols   # labels agree ...
    assert diag["meeting_min_observations"] == 0     # ... the history is thin


def test_diagnostics_confirm_alignment_on_a_healthy_run():
    n, cols = 300, 4
    idx = pd.bdate_range(end="2026-08-18", periods=n)
    rng = np.random.default_rng(5)
    prices = pd.DataFrame(
        100 + np.cumsum(rng.normal(0, 1, (n, cols)), axis=0),
        index=idx, columns=[f"S{i}" for i in range(cols)],
    )
    info = pd.DataFrame({"Symbol": [f"S{i}" for i in range(cols)], "Industry": ["T"] * cols})
    calc = MomentumEngine(prices)
    rank_df = calc.get_rankings(info, pd.Series(dtype=float))

    assert not rank_df.empty
    assert calc.ranking_diagnostics["symbols_matching_prices"] == cols
