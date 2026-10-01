"""The stock chart: candles from a real range, a dark line from a close-only source."""
import numpy as np
import pandas as pd
import pytest

from src.ui import stock_chart as SC
from src.ui.stock_chart import ChartUnavailable, build_panes

N = 300
IDX = pd.bdate_range(end="2026-08-18", periods=N)
_RNG = np.random.default_rng(3)
CLOSE = pd.Series(100 * np.exp(np.cumsum(_RNG.normal(0.001, 0.015, N))), index=IDX)
OPEN = CLOSE.shift(1).fillna(CLOSE.iloc[0])
HIGH = pd.concat([OPEN, CLOSE], axis=1).max(axis=1) * 1.01
LOW = pd.concat([OPEN, CLOSE], axis=1).min(axis=1) * 0.99
VOL = pd.Series(_RNG.integers(1e5, 5e6, N).astype(float), index=IDX)


def _panes(**kw):
    panes, _ = build_panes(CLOSE, open_=OPEN, high=HIGH, low=LOW, **kw)
    return panes


def test_price_and_rs_are_separate_panes():
    assert len(_panes(volume=VOL, rs=pd.Series(100.0, index=IDX))) == 2


def test_candles_use_the_real_open():
    first = _panes(volume=VOL)[0]["series"][0]["data"][0]
    assert len(first) == 5 and first[1] == pytest.approx(float(OPEN.iloc[0]))


def test_overlays_are_drawn_only_when_asked():
    plain = _panes(volume=VOL)[0]["series"]
    assert [s["type"] for s in plain].count("line") == 0
    withma = _panes(volume=VOL, overlays={"20 EMA": CLOSE.ewm(span=20).mean()})[0]["series"]
    assert [s["name"] for s in withma if s["type"] == "line"] == ["20 EMA"]


def test_volume_is_a_bar_series_coloured_by_the_session():
    vol = _panes(volume=VOL)[0]["series"][-1]
    assert vol["type"] == "histogram" and vol["volume"] is True
    assert len(vol["colors"]) == len(vol["data"])
    assert len(set(vol["colors"])) == 2


def test_absent_volume_is_stated_not_silently_dropped():
    panes, has_volume = build_panes(CLOSE, open_=OPEN, high=HIGH, low=LOW)
    assert has_volume is False and all(not s.get("volume") for s in panes[0]["series"])
    _, zero = build_panes(CLOSE, open_=OPEN, high=HIGH, low=LOW, volume=VOL * 0)
    assert zero is False


def test_a_missing_bar_degrades_to_a_flat_close_not_a_dropped_session():
    high = HIGH.copy()
    high.iloc[10] = np.nan
    panes, _ = build_panes(CLOSE, open_=OPEN, high=high, low=LOW)
    assert len(panes[0]["series"][0]["data"]) == N


def test_empty_prices_raise_rather_than_render_nothing():
    with pytest.raises(ChartUnavailable):
        build_panes(pd.Series(dtype=float))


def test_a_close_only_source_draws_a_dark_line_not_a_column_of_dojis():
    panes, _ = build_panes(CLOSE, volume=VOL)
    price = panes[0]["series"][0]
    assert price["type"] == "line" and price["color"] == SC.INK


def test_the_price_line_outweighs_its_overlays():
    panes, _ = build_panes(CLOSE, volume=VOL, overlays={"20 EMA": CLOSE})
    s = panes[0]["series"]
    assert s[0]["width"] >= s[1]["width"]


def test_an_all_nan_range_column_is_not_intraday():
    empty = pd.Series(np.nan, index=IDX)
    panes, _ = build_panes(CLOSE, open_=OPEN, high=empty, low=empty, volume=VOL)
    assert panes[0]["series"][0]["type"] == "line"


def test_half_a_candle_chart_is_not_a_candle_chart():
    high = HIGH.copy()
    low = LOW.copy()
    high.iloc[: N // 2 + 5] = np.nan
    low.iloc[: N // 2 + 5] = np.nan
    panes, _ = build_panes(CLOSE, open_=OPEN, high=high, low=low, volume=VOL)
    assert panes[0]["series"][0]["type"] == "line"


def test_a_mostly_present_range_still_draws_candles():
    high = HIGH.copy()
    high.iloc[:20] = np.nan
    panes, _ = build_panes(CLOSE, open_=OPEN, high=high, low=LOW, volume=VOL)
    assert panes[0]["series"][0]["type"] == "candlestick"


def test_volume_without_an_open_is_coloured_by_the_previous_close():
    panes, _ = build_panes(CLOSE, volume=VOL)
    colors = panes[0]["series"][-1]["colors"]
    assert len(set(colors)) == 2


def test_a_close_only_source_still_gets_its_rs_pane():
    panes, _ = build_panes(CLOSE, volume=VOL, rs=pd.Series(100.0, index=IDX))
    assert len(panes) == 2 and panes[1]["series"][0]["name"] == "RS vs Nifty 500"
