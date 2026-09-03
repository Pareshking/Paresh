"""The TradingView chart, and the fallback that keeps a failure from going blank.

Plotly's drag selects a zoom box, so on a phone reading the chart rearranged it.
Lightweight Charts pans on drag and zooms on pinch, which is what a price chart
should do. But it is a THIRD-PARTY COMPONENT, and a component that fails to load
renders as blank space rather than an error -- so every failure here must fall
back to Plotly. A prettier chart is not worth an empty one.
"""
import numpy as np
import pandas as pd
import pytest

from src.ui import lightweight_chart as LW
from src.ui.lightweight_chart import ChartUnavailable, render_lightweight_chart

N = 300
IDX = pd.bdate_range(end="2026-08-18", periods=N)
_RNG = np.random.default_rng(3)
CLOSE = pd.Series(100 * np.exp(np.cumsum(_RNG.normal(0.001, 0.015, N))), index=IDX)
OPEN = CLOSE.shift(1).fillna(CLOSE.iloc[0])
HIGH = pd.concat([OPEN, CLOSE], axis=1).max(axis=1) * 1.01
LOW = pd.concat([OPEN, CLOSE], axis=1).min(axis=1) * 0.99
VOL = pd.Series(_RNG.integers(1e5, 5e6, N).astype(float), index=IDX)


@pytest.fixture
def captured(monkeypatch):
    import streamlit_lightweight_charts as slc

    box = {}
    monkeypatch.setattr(
        slc, "renderLightweightCharts",
        lambda charts, key=None: box.update(charts=charts, key=key),
    )
    monkeypatch.setattr(LW.st, "caption", lambda *a, **k: box.setdefault("caption", a[0]))
    return box


def _render(captured, **kw):
    render_lightweight_chart("TEST", CLOSE, open_=OPEN, high=HIGH, low=LOW, **kw)
    return captured["charts"]


def test_price_and_rs_are_separate_panes(captured):
    charts = _render(captured, volume=VOL, rs=pd.Series(100.0, index=IDX))
    assert len(charts) == 2


def test_candles_use_the_real_open(captured):
    """Plotly synthesised open as the previous close, drawing close-to-close
    bodies -- not what a candle means."""
    charts = _render(captured, volume=VOL)
    first = charts[0]["series"][0]["data"][0]
    assert set(first) == {"time", "open", "high", "low", "close"}
    assert first["open"] == pytest.approx(float(OPEN.iloc[0]))


def test_overlays_are_drawn_only_when_asked(captured):
    plain = _render(captured, volume=VOL)
    assert [s["type"] for s in plain[0]["series"]].count("Line") == 0

    withma = _render(captured, volume=VOL,
                     overlays={"20 EMA": CLOSE.ewm(span=20).mean()})
    assert [s["type"] for s in withma[0]["series"]].count("Line") == 1


def test_volume_sits_on_its_own_hidden_scale(captured):
    charts = _render(captured, volume=VOL)
    hist = [s for s in charts[0]["series"] if s["type"] == "Histogram"][0]
    assert hist["options"]["priceScaleId"] == "volume"
    assert hist["priceScale"]["visible"] is False
    assert hist["priceScale"]["scaleMargins"]["top"] == 0.8


def test_volume_bars_are_coloured_by_the_session(captured):
    charts = _render(captured, volume=VOL)
    hist = [s for s in charts[0]["series"] if s["type"] == "Histogram"][0]
    colours = {row["color"] for row in hist["data"]}
    assert len(colours) == 2


def test_absent_volume_is_stated_not_silently_dropped(captured):
    charts = _render(captured, volume=pd.Series(np.nan, index=IDX))
    assert not [s for s in charts[0]["series"] if s["type"] == "Histogram"]
    assert "Volume unavailable" in captured.get("caption", "")


def test_zero_volume_counts_as_absent(captured):
    """extract_ohlcv substitutes zeros when the field is missing entirely."""
    charts = _render(captured, volume=pd.Series(0.0, index=IDX))
    assert not [s for s in charts[0]["series"] if s["type"] == "Histogram"]


def test_a_missing_bar_degrades_to_a_flat_close_not_a_dropped_session(captured):
    high = HIGH.copy(); high.iloc[5] = np.nan
    render_lightweight_chart("TEST", CLOSE, open_=OPEN, high=high, low=LOW, volume=VOL)
    data = captured["charts"][0]["series"][0]["data"]
    assert len(data) == N            # the session survives
    assert data[5]["high"] >= data[5]["close"]


def test_empty_prices_raise_rather_than_render_nothing():
    with pytest.raises(ChartUnavailable):
        render_lightweight_chart("TEST", pd.Series(dtype=float))


def test_a_component_failure_raises_so_the_caller_can_fall_back(monkeypatch):
    import streamlit_lightweight_charts as slc

    def _boom(charts, key=None):
        raise RuntimeError("frontend did not load")

    monkeypatch.setattr(slc, "renderLightweightCharts", _boom)
    with pytest.raises(ChartUnavailable):
        render_lightweight_chart("TEST", CLOSE, open_=OPEN, high=HIGH, low=LOW)


def test_render_stock_chart_falls_back_to_plotly(monkeypatch):
    """The whole point of the guard: a broken component must not blank the page."""
    from src.ui import charts

    monkeypatch.setattr(
        charts, "render_lightweight_chart", None, raising=False
    )

    import src.ui.lightweight_chart as lw
    monkeypatch.setattr(
        lw, "render_lightweight_chart",
        lambda *a, **k: (_ for _ in ()).throw(ChartUnavailable("no frontend")),
    )

    used = {}
    monkeypatch.setattr(charts, "render_candlestick_drilldown",
                        lambda *a, **k: used.setdefault("plotly", True))

    class _C:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def segmented_control(self, *a, **k): return "6M"
        def pills(self, *a, **k): return ["20 EMA"]
    monkeypatch.setattr(charts.st, "columns", lambda *a, **k: [_C(), _C()])
    monkeypatch.setattr(charts.st, "warning", lambda *a, **k: None)

    rank_df = pd.DataFrame([{"Symbol": "TEST", "Rank": 1}])
    charts.render_stock_chart("TEST", rank_df, CLOSE.to_frame("TEST"))
    assert used.get("plotly") is True
