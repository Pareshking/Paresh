"""The shared chart component: data in, one self-contained document out."""


from src.ui import lw_chart as lw


def test_the_document_loads_the_library_and_carries_the_data():
    html = lw.chart_html([{"height": 200, "series": [
        {"name": "Strategy", "type": "line", "fmt": "rupee",
         "data": [("2026-01-01", 2e6), ("2026-02-01", 2.1e6)]}]}])
    assert "app/static/lightweight-charts.standalone.production.js" in html   # served once (F60)
    assert '"value":2100000.0' in html and "Strategy" in html
    assert "TradingView Lightweight Charts" not in html     # no longer inlined
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


def test_the_library_is_v5_and_the_logo_is_off():
    html = lw.chart_html([{"series": [{"name": "x", "data": [("2026-01-01", 1.0), ("2026-01-02", 2.0)]}]}])
    lib = (lw._STATIC / "lightweight-charts.standalone.production.js").read_text(encoding="utf-8")
    assert "Lightweight Charts™ v5." in lib and "lightweight-charts@5" in html
    assert "attributionLogo:false" in html
    # v4's per-type factories are gone in v5; every series goes through addSeries
    assert not any(f"add{t}Series(" in html.split("const SPEC=")[1]
                   for t in ("Line", "Area", "Histogram", "Baseline", "Candlestick"))


def test_a_pane_never_draws_two_lines_in_one_colour():
    """Breadth passes ink twice in its palette; the second line takes a spare."""
    out = lw._distinct([{"name": "a", "color": lw.INK}, {"name": "b", "color": lw.GREY},
                        {"name": "c", "color": lw.INK}])
    colours = [s["color"] for s in out]
    assert len(set(colours)) == 3 and colours[:2] == [lw.INK, lw.GREY]
