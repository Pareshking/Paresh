"""`pipeline.ranked_prices` must equal `build_engine(...).prices`, exactly.

The Portfolio page reads one frame off the engine -- `calc.prices` -- and
nothing else, so it now takes that frame from `ranked_prices` instead of paying
1.3 s to build an engine it never scores with (S115, 10 Nov 2026). The page's
every figure is computed from that frame, so if the cheap path ever returned a
different one the page would report different numbers. These tests are what
stops that: same index, same columns, same values, on frames that exercise the
two things the preparation does -- carrying a straggler's last print and
trimming a half-published tail -- plus the holiday rows it drops.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.engine import pipeline


def _frame(n_days: int = 320, n_syms: int = 12) -> pd.DataFrame:
    idx = pd.bdate_range("2024-01-01", periods=n_days)
    rng = np.random.default_rng(7)
    data = 100 + np.cumsum(rng.normal(0, 1, size=(n_days, n_syms)), axis=0)
    return pd.DataFrame(data, index=idx,
                        columns=[f"SYM{i:02d}" for i in range(n_syms)])


def _engine_prices(close: pd.DataFrame) -> pd.DataFrame:
    idx_info = pd.DataFrame({"Symbol": list(close.columns),
                             "Index Name": ["NIFTY TOTAL MARKET"] * close.shape[1]})
    mcaps = pd.Series(1e11, index=close.columns)
    calc = pipeline.build_engine(close, close, close, close,
                                 close * 0 + 1000, idx_info, mcaps)
    return calc.prices


def _same(a: pd.DataFrame, b: pd.DataFrame) -> None:
    pd.testing.assert_frame_equal(a, b, check_exact=True)


def test_plain_frame():
    close = _frame()
    _same(pipeline.ranked_prices(close, close, close, close, close * 0 + 1000),
          _engine_prices(close))


def test_a_carried_straggler():
    close = _frame()
    # Two symbols have no print on the newest session: few enough to be carried
    # on their last print rather than hold the session back.
    close.iloc[-1, [2, 5]] = np.nan
    assert pipeline.carried_symbols(close), "the fixture must exercise carrying"
    _same(pipeline.ranked_prices(close, close, close, close, close * 0 + 1000),
          _engine_prices(close))


def test_a_half_published_tail_is_trimmed_the_same_way():
    close = _frame()
    # The newest session has almost nothing in it: the ranking walks back.
    close.iloc[-1, 1:] = np.nan
    assert pipeline.last_ranked_session(close) == len(close.index) - 2
    cheap = pipeline.ranked_prices(close, close, close, close, close * 0 + 1000)
    _same(cheap, _engine_prices(close))
    assert cheap.index[-1] == close.index[-2]


def test_a_holiday_row_is_dropped_the_same_way():
    close = _frame()
    close.iloc[100, :] = np.nan          # exchange-wide: >70% NaN
    cheap = pipeline.ranked_prices(close, close, close, close, close * 0 + 1000)
    _same(cheap, _engine_prices(close))
    assert close.index[100] not in cheap.index


@pytest.mark.parametrize("empty", [pd.DataFrame(), None])
def test_nothing_in_gives_an_empty_frame_not_a_crash(empty):
    assert pipeline.ranked_prices(empty).empty
