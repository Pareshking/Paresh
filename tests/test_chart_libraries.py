"""Chart libraries are served once from ./static, not copied into each frame (audit F60)."""
from src.ui import charts, highcharts_lib, lw_chart


def test_libraries_are_in_the_static_folder():
    for name in ("highstock.js", "highcharts-more.js", "highcharts-heatmap.js",
                 "lightweight-charts.standalone.production.js", "HIGHCHARTS_LICENSE.txt"):
        assert (highcharts_lib._STATIC / name).stat().st_size > 300, name


def test_frames_load_the_library_by_address_with_a_pinned_fallback():
    out = lw_chart.chart_html([{"series": [{"name": "x", "data": [("2026-11-05", 1.0), ("2026-11-06", 2.0)]}]}])
    assert len(out) < 50_000                                   # was ~170 KB with the library inlined
    assert 'app/static/lightweight-charts.standalone.production.js' in out
    assert "lightweight-charts@5.2.1" in out and "window.LightweightCharts" in out
    hc = highcharts_lib.lib("highcharts-heatmap.js")
    assert hc.index("highstock.js") < hc.index("highcharts-heatmap.js")
    assert "highcharts@13.1.1/modules/heatmap.js" in hc and "</script>" not in hc
    assert len(charts._build_rrg_html("{}", "Leading: A.")) < 50_000


def test_streamlit_serves_the_static_folder():
    import tomllib
    with open(".streamlit/config.toml", "rb") as f:
        assert tomllib.load(f)["server"]["enableStaticServing"] is True
