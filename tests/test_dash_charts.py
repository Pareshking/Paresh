"""The Dashboard's chart frames (S151, v8)."""

import math
from pathlib import Path

import pytest

from src.ui import dash_charts as dc


def test_every_kind_writes_a_frame_with_the_theme_written_in():
    for kind in dc.KINDS:
        html = dc.frame_html(kind, {"x": 1}, label="L", note="N", n=10, step=2)
        assert "var(--c-" not in html, kind            # a frame cannot see the page's variables
        assert "app/static/dash_charts.js?v=" in html and f'DashCharts.render("{kind}"' in html


def test_unknown_kind_and_bad_numbers_are_refused():
    with pytest.raises(ValueError):
        dc.frame_html("pie", {})
    with pytest.raises(ValueError):
        dc.frame_html("bars", {"values": [math.nan]})


def test_the_spec_cannot_close_its_script():
    html = dc.frame_html("bars", {"labels": ["</script><b>x"]}, label="L")
    assert "</script><b>" not in html


def test_the_kit_draws_every_kind():
    js = (Path(__file__).resolve().parents[1] / "static" / "dash_charts.js").read_text(encoding="utf-8")
    for kind in dc.KINDS:
        assert f"R.{kind} = " in js
    assert "window.DashCharts" in js
