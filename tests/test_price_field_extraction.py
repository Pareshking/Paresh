"""Field extraction must follow ticker coverage, not the first name it spots.

This took production down twice, most visibly as "The momentum engine ranked 0
stocks" with the diagnostic reading:

    Universe: 750 symbols
    Price series loaded: 1, matching the universe: 1
    With any price history: 0

yfinance rate-limits a ticker and returns that ONE ticker unadjusted -- six
fields including "Adj Close" -- while the other 749 arrive auto-adjusted with
five fields and no "Adj Close" at all. _extract_field asked for "Adj Close"
first and took it because it appeared SOMEWHERE, so df.xs("Adj Close") yielded
a single all-NaN column and the whole screener emptied.

The fingerprint in the logs was "Price cache saved: 500 rows (3751 series)".
3751 is 749x5 + 1x6 -- not a clean tickers-by-fields grid.
"""
import numpy as np
import pandas as pd
import pytest

from src.loaders.price_loader import _extract_field

IDX = pd.bdate_range(end="2026-08-18", periods=10)
ADJUSTED = ["Open", "High", "Low", "Close", "Volume"]
UNADJUSTED = ["Open", "High", "Low", "Close", "Adj Close", "Volume"]


def _ticker_frame(ticker, fields, value):
    cols = pd.MultiIndex.from_product([[ticker], fields])
    data = (
        np.full((len(IDX), len(fields)), np.nan)
        if value is None
        else np.full((len(IDX), len(fields)), float(value))
    )
    return pd.DataFrame(data, index=IDX, columns=cols)


def _mixed(n_healthy=3, limited=("TATAPOWER.NS",)):
    frames = [
        _ticker_frame(f"S{i}.NS", ADJUSTED, 100 + i) for i in range(n_healthy)
    ]
    frames += [_ticker_frame(t, UNADJUSTED, None) for t in limited]
    return pd.concat(frames, axis=1)


def test_one_rate_limited_ticker_does_not_hijack_the_field_choice():
    """The exact production failure."""
    raw = _mixed()
    adj = _extract_field(raw, ["Adj Close", "AdjClose", "Close"])

    assert len(adj.columns) == 4, "healthy tickers must survive"
    assert adj.notna().sum().sum() > 0, "extraction must not be entirely NaN"


def test_the_healthy_tickers_carry_their_real_prices():
    raw = _mixed()
    adj = _extract_field(raw, ["Adj Close", "AdjClose", "Close"])
    for i in range(3):
        assert adj[f"S{i}"].dropna().unique().tolist() == [100.0 + i]


def test_the_ragged_column_count_is_the_shape_that_broke_it():
    raw = _mixed(n_healthy=3)
    assert len(raw.columns) == 3 * 5 + 6      # the 3751 pattern, in miniature
    assert len(raw.columns) % 5 != 0


def test_adj_close_still_wins_when_every_ticker_has_it():
    """Normal behaviour must not change: ties break on preference order."""
    raw = pd.concat([_ticker_frame(f"S{i}.NS", UNADJUSTED, 10 + i) for i in range(3)], axis=1)
    adj = _extract_field(raw, ["Adj Close", "AdjClose", "Close"])
    expected = raw.xs("Adj Close", level=1, axis=1)
    assert np.allclose(adj.values, expected.values)


def test_close_is_returned_when_requested_first():
    raw = pd.concat([_ticker_frame(f"S{i}.NS", UNADJUSTED, 10 + i) for i in range(3)], axis=1)
    close = _extract_field(raw, ["Close", "Adj Close"])
    expected = raw.xs("Close", level=1, axis=1)
    assert np.allclose(close.values, expected.values)


@pytest.mark.parametrize("n_limited", [1, 2, 5])
def test_coverage_wins_regardless_of_how_many_tickers_are_limited(n_limited):
    raw = _mixed(n_healthy=10, limited=tuple(f"L{i}.NS" for i in range(n_limited)))
    adj = _extract_field(raw, ["Adj Close", "AdjClose", "Close"])
    assert len(adj.columns) == 10 + n_limited
    assert adj.notna().sum().sum() > 0


def test_field_on_level_zero_still_works():
    """yfinance sometimes returns (Field, Ticker) rather than (Ticker, Field)."""
    cols = pd.MultiIndex.from_product([["Close", "Open"], ["S0.NS", "S1.NS"]])
    raw = pd.DataFrame(np.full((len(IDX), 4), 42.0), index=IDX, columns=cols)
    out = _extract_field(raw, ["Adj Close", "Close"])
    assert sorted(out.columns) == ["S0", "S1"]


def test_absent_field_yields_an_empty_frame_not_a_wrong_one():
    raw = pd.concat([_ticker_frame(f"S{i}.NS", ["Volume"], 1) for i in range(2)], axis=1)
    out = _extract_field(raw, ["Adj Close"])
    assert out.empty or len(out.columns) == 0


def test_extraction_feeds_a_non_empty_ranking():
    """End to end: the ragged frame must still produce a ranked screener."""
    from src.engine.momentum import MomentumEngine

    n, cols = 400, 6
    idx = pd.bdate_range(end="2026-08-18", periods=n)
    rng = np.random.default_rng(3)
    frames = []
    for i in range(cols):
        vals = 100 * np.exp(np.cumsum(rng.normal(0.0005, 0.012, n)))
        block = pd.DataFrame(
            np.column_stack([vals] * 5), index=idx,
            columns=pd.MultiIndex.from_product([[f"S{i}.NS"], ADJUSTED]),
        )
        frames.append(block)
    frames.append(
        pd.DataFrame(np.nan, index=idx,
                     columns=pd.MultiIndex.from_product([["LIMITED.NS"], UNADJUSTED]))
    )
    raw = pd.concat(frames, axis=1)

    adj = _extract_field(raw, ["Adj Close", "AdjClose", "Close"])
    info = pd.DataFrame({
        "Symbol": [f"S{i}" for i in range(cols)] + ["LIMITED"],
        "Industry": ["IT"] * (cols + 1),
    })
    calc = MomentumEngine(adj)
    rank_df = calc.get_rankings(info, pd.Series(dtype=float))

    assert not rank_df.empty, "the ragged frame must still rank"
    assert calc.ranking_diagnostics["price_columns"] == cols + 1
    assert calc.ranking_diagnostics["scored"] >= cols
