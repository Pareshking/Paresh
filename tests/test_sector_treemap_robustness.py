"""Sector treemap must degrade, never crash, and never fabricate tile sizes."""
import numpy as np
import pandas as pd
import pytest

from src.ui.charts import render_sector_treemap


def _frame(n: int = 6) -> pd.DataFrame:
    return pd.DataFrame({
        "Symbol": [f"S{i}" for i in range(n)],
        "Industry": (["Fin", "Fin", "IT", "IT", "Auto", "Auto"] * 2)[:n],
        "Sector": (["Financial", "Financial", "Tech", "Tech", "Auto", "Auto"] * 2)[:n],
        "3M Return": np.linspace(-0.2, 0.3, n),
        "6M Return": np.linspace(-0.1, 0.4, n),
        "Market Cap (Cr)": np.linspace(500, 90000, n),
        "CMP": np.linspace(100, 2000, n),
        "Rank": np.arange(1, n + 1),
        "Score": np.linspace(-1, 2, n),
    })


@pytest.mark.parametrize("drop", [
    "Market Cap (Cr)", "3M Return", "Score", "Industry", "CMP", "Rank",
])
def test_missing_column_does_not_raise(drop):
    render_sector_treemap(_frame().drop(columns=[drop]))


@pytest.mark.parametrize("kwargs", [
    {"size_by": "Market Cap"},
    {"size_by": "Momentum"},
    {"size_by": "3M Return"},
    {"size_by": "6M Return", "return_col": "6M Return"},
    {"taxonomy_col": "Sector"},
    {"taxonomy_col": "TV_Industry"},          # taxonomy absent from the frame
])
def test_control_combinations_do_not_raise(kwargs):
    render_sector_treemap(_frame(), **kwargs)


@pytest.mark.parametrize("n", [0, 1, 2])
def test_small_and_empty_universes_do_not_raise(n):
    render_sector_treemap(_frame(n))


def test_all_nan_taxonomy_does_not_raise():
    df = _frame()
    df["Industry"] = np.nan
    render_sector_treemap(df)


def test_market_cap_sizing_never_fabricates_a_size():
    """A stock with unknown market cap must be excluded, not given one.

    Filling a flat 1000 Cr rendered an unknown-cap stock as a mid-size tile;
    because tile area IS the datum in a market-cap treemap, that silently
    misstated the composition of the map.
    """
    captured = {}
    df = _frame()
    df.loc[df.index[:2], "Market Cap (Cr)"] = np.nan

    import src.ui.charts as charts

    real_treemap = charts.px.treemap

    def spy(data_frame, **kwargs):
        captured["values"] = data_frame[kwargs["values"]].tolist()
        captured["symbols"] = data_frame["Symbol"].tolist()
        return real_treemap(data_frame, **kwargs)

    charts.px.treemap = spy
    try:
        render_sector_treemap(df, size_by="Market Cap")
    finally:
        charts.px.treemap = real_treemap

    # The two unknown-cap stocks are absent rather than sized at 1000.
    assert captured["symbols"] == ["S2", "S3", "S4", "S5"]
    assert 1000 not in captured["values"]
    assert all(v > 0 and np.isfinite(v) for v in captured["values"])


def test_market_cap_sizing_with_no_known_caps_renders_nothing():
    df = _frame()
    df["Market Cap (Cr)"] = np.nan
    import src.ui.charts as charts
    real_treemap = charts.px.treemap
    calls = []
    charts.px.treemap = lambda *a, **k: calls.append(1)
    try:
        render_sector_treemap(df, size_by="Market Cap")
    finally:
        charts.px.treemap = real_treemap
    assert calls == [], "must not draw a treemap with no real market caps"
