"""The shared chart component: data in, one self-contained document out."""
import numpy as np
import pandas as pd

from src.ui import lw_chart as lw


def test_series_points_drops_nan_and_keeps_one_point_per_day():
    idx = pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-02", "2026-01-05"])
    pts = lw.series_points(idx, [1.0, np.nan, 3.0, 4.0])
    assert pts == [("2026-01-01", 1.0), ("2026-01-02", 3.0), ("2026-01-05", 4.0)]


def test_series_points_scales_fractions_to_percent():
    (day, value), = lw.series_points(pd.to_datetime(["2026-01-01"]), [-0.119], scale=100.0)
    assert day == "2026-01-01" and abs(value + 11.9) < 1e-9


def test_the_document_carries_the_library_and_the_data_and_no_cdn():
    html = lw.chart_html([{"height": 200, "series": [
        {"name": "Strategy", "type": "line", "fmt": "rupee",
         "data": [("2026-01-01", 2e6), ("2026-02-01", 2.1e6)]}]}])
    assert "TradingView Lightweight Charts" in html          # vendored, inlined
    assert '"value":2100000.0' in html and "Strategy" in html
    assert "cdn" not in html.split("</script>")[1].lower()   # nothing loaded from the network
    assert "subscribeCrosshairMove" in html                  # the hover legend


def test_a_script_closing_tag_in_a_series_name_cannot_break_out():
    html = lw.chart_html([{"series": [{"name": "</script><img src=x onerror=alert(1)>",
                                       "data": [("2026-01-01", 1.0), ("2026-01-02", 2.0)]}]}])
    assert "</script><img" not in html


def test_nothing_is_drawn_for_a_single_point(monkeypatch):
    drawn = []
    monkeypatch.setattr(lw.st, "iframe", lambda *a, **k: drawn.append(a))
    lw.render([{"series": [{"name": "x", "data": [("2026-01-01", 1.0)]}]}])
    assert not drawn
