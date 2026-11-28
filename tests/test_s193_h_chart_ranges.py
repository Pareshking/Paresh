"""S193 item H: every time-range chart states the range it opens on, and why (owner, 23 Nov 2026: "Go with
your recommendation on all", "12M"; docs/archive/S193_ITEM_H_2026-11-23.md).

Recent movement ("lately") opens on 12M, a record on its full span ("all"); Market's Nifty 500 against its
10-month average is the one stated exception (3Y). The stock chart's and Market's period pickers are chips
in the chart that redraw in place. scripts/layout_audit.mjs checks in a browser that each chart opens on
the range stated here and has a readout at rest.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.ui import dash_charts as dc
from src.ui import lw_chart, stock_chart

ROOT = Path(__file__).resolve().parents[1]


# ── The kit ──────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("bad", [
    {"default": "6M", "why": "lately"},            # lately opens on 12M
    {"default": "3Y", "why": "record"},            # a record opens on all of it
    {"default": "3Y", "why": "fixed"},             # an exception says why
    {"default": "12M"},                            # no reason
    {"default": "1Y", "why": "lately"},            # 12M, not 1Y (glossary 6)
    {"default": "12M", "why": "lately", "chips": ["3M", "6M"]},   # the default is a chip
])
def test_a_range_that_breaks_the_rule_is_refused(bad):
    with pytest.raises(ValueError):
        dc.frame_html("lines", {"dates": ["2026-11-20"], "series": [], "range": bad})


def test_kinds_that_are_one_question_carry_their_range():
    assert dc.RANGE_BY_KIND["breadth"] == {"default": "12M", "why": "lately", "chips": ["6M", "12M", "3Y"]}
    for kind in ("growth", "btgrowth", "rel"):
        assert dc.RANGE_BY_KIND[kind]["default"] == "all"
    html = dc.frame_html("breadth", {"dates": ["2026-11-20"], "n500": [1.0], "a200": [50.0]})
    assert '"range":{"default":"12M","why":"lately"' in html
    # The chips are the spec's, no longer a hard-coded 3Y in the frame's HTML.
    assert 'aria-pressed="true">3Y' not in html and "data-range=" not in html


def test_a_value_axis_range_is_still_a_list():
    spec = {"values": [1.0], "labels": ["2017"], "full": ["2017"], "unit": "x", "range": [-10, 10]}
    assert dc.with_range("bars", spec) is spec


def test_the_kit_marks_what_it_drew_and_keeps_no_end_labels_or_tooltip():
    js = (ROOT / "static" / "dash_charts.js").read_text(encoding="utf-8")
    for attr in ("rangeDefault", "rangeFrom", "rangeTo", "rangeFirst", "rangeShown"):
        assert attr in js
    assert "s.end" not in js                                   # the dead end-label option (H3)
    assert "className='tip'" not in js and ".tip" not in dc.CSS   # the mouse box that repeated the readout


def test_chart_text_is_12px_or_more_and_on_the_type_scale():
    from src.ui.tokens import TYPE, resolve
    steps = {float(v[:-2]) for v in TYPE.values()}
    for name, css in (("dash_charts", dc.CSS), ("lw_chart", lw_chart.chart_html(
            [{"series": [{"name": "x", "data": [("2026-11-19", 1.0), ("2026-11-20", 2.0)]}]}]))):
        sizes = [float(x) for x in re.findall(r"font-size:\s*([\d.]+)px", resolve(css))]
        assert sizes and min(sizes) >= 12, (name, sorted(set(sizes)))
        assert set(sizes) <= steps, (name, sorted(set(sizes) - steps))
    assert "fontSize:parseFloat('12px')" in resolve(lw_chart._JS) and "fontSize:11" not in lw_chart._JS


def test_market_questions_font_sizes_are_type_steps():
    from src.ui.tokens import TYPE
    src = (ROOT / "src" / "ui" / "views" / "market_questions_view.py").read_text(encoding="utf-8")
    px = {float(x) for x in re.findall(r"font-size:\s*([\d.]+)px", src)}
    assert px <= {float(v[:-2]) for v in TYPE.values()}, sorted(px)


# ── Every lines and bars chart states its range ──────────────────────────────

# Date charts whose spec is built outside this change's files: each must state `range` in its own PR
# (S193 H; listed for the owner of those files). The list may only shrink.
PENDING: set = set()   # emptied in PR 2 (S193 H): every date chart states its range


def _calls():
    for f in sorted((ROOT / "src").rglob("*.py")):
        tree = ast.parse(f.read_text(encoding="utf-8"))
        for fn in ast.walk(tree):
            if not isinstance(fn, ast.FunctionDef):
                continue
            for n in ast.walk(fn):
                if (isinstance(n, ast.Call) and len(n.args) > 1 and isinstance(n.args[0], ast.Constant)
                        and n.args[0].value in ("lines", "bars")
                        and getattr(n.func, "attr", getattr(n.func, "id", "")) in ("render", "Chart")):
                    a = n.args[1]
                    ok = isinstance(a, ast.Dict) and any(
                        isinstance(k, ast.Constant) and k.value == "range" and not isinstance(v, ast.List)
                        for k, v in zip(a.keys, a.values))
                    yield f.name, fn.name, ok


def test_every_lines_or_bars_chart_states_its_range():
    missing = {(f, fn) for f, fn, ok in _calls() if not ok}
    assert missing <= PENDING, f"a date chart with no stated range: {sorted(missing - PENDING)}"
    assert {f for f, _, ok in _calls() if ok} >= {"market_view.py", "market_questions_view.py"}


# ── Market: one 12M series, chips 3M · 6M · 12M in the frame ─────────────────

@pytest.fixture
def captured(monkeypatch):
    got = []
    monkeypatch.setattr(dc, "render", lambda kind, spec, **fill: got.append((kind, dc.with_range(kind, spec), fill)))
    return got


def test_market_pickers_moved_into_the_charts(captured):
    from src.ui.views import market_view as mv
    src = (ROOT / "src" / "ui" / "views" / "market_view.py").read_text(encoding="utf-8")
    assert "br_lb_days" not in src and '"Period"' not in src
    assert mv.PERIOD == {"default": "12M", "why": "lately", "chips": ["3M", "6M", "12M"]} and mv._lookback(pd.bdate_range("2025-06-30", "2026-06-30")) == len(pd.bdate_range("2025-06-30", "2026-06-30"))
    idx = pd.bdate_range(end="2026-11-20", periods=252)
    mv._participation_chart(pd.DataFrame({"50D": 50.0, "200D": 40.0}, index=idx), "EMA", None)
    mv._highs_lows_chart(pd.DataFrame({"% New Highs": 2.0, "% New Lows": 1.0}, index=idx), True)
    (k1, s1, _), (k2, s2, _) = captured
    assert (k1, k2) == ("lines", "bars")
    assert s1["range"] == s2["range"] == mv.PERIOD and s1["yrange"] == [0, 100]
    assert len(s2["dates"]) == len(s2["values"]) == 252


def test_market_breadth_and_weekly_highs_open_on_12m_the_ten_month_average_on_3y(captured):
    from src.ui.views import market_questions_view as mq
    idx = pd.bdate_range(end="2026-11-20", periods=1100)
    bench = pd.Series(np.linspace(20000, 24000, len(idx)), index=idx)
    share = pd.Series(55.0, index=idx)
    weekly = share.resample("W-FRI").last() - 50
    mq._breadth_charts(bench, share, weekly, None, True, "750")
    mq._trend_charts(bench, {"Nifty Midcap 150": bench * 1.1})
    by = {f.get("label"): (k, s) for k, s, f in captured}
    assert by["Nifty Total Market and the share of stocks above their 200D EMA"][1]["range"]["default"] == "12M"
    k, w = by["Net new 52-week highs each week"]
    assert w["range"] == {"default": "12M", "why": "lately", "chips": ["12M", "3Y"]} and len(w["dates"]) > 150
    ten = by["Nifty Total Market’s monthly closes and its 10-month average"][1]["range"]
    assert ten["default"] == "3Y" and ten["why"] == "fixed" and "10-month" in ten["note"]
    assert by["Each size index against Nifty Total Market over the year"][1]["range"]["default"] == "12M"


# ── The stock chart: three years sent once, chips in the frame ───────────────

def _stock():
    idx = pd.bdate_range("2023-01-02", "2026-11-20")
    close = pd.Series(np.linspace(100, 300, len(idx)), index=idx)
    market = pd.Series(np.linspace(100, 150, len(idx)), index=idx)
    return close, pd.Series(1e5, index=idx), market


def test_the_stock_chart_sends_three_years_and_states_12m():
    close, vol, market = _stock()
    panes, has_vol, ranges = stock_chart.chart_panes_all(close, vol, market)
    assert has_vol and ranges["default"] == "12M" and ranges["why"] == "lately"
    assert [c[0] for c in ranges["chips"]] == ["6M", "12M", "3Y", "All"]   # All restored S239
    # Each chip starts where the old per-range chart started, and RS is 100 there again.
    for lab, start in ranges["chips"]:
        old, _ = stock_chart.price_chart_panes(close, vol, market, stock_chart.RANGES[lab])
        assert start == old[0]["series"][0]["data"][0][0]
        cut = lw_chart.slice_panes(panes, start)
        assert cut[2]["series"][0]["data"][0][1] == pytest.approx(100.0)
        assert cut[2]["series"][0]["data"][-1][1] == pytest.approx(old[2]["series"][0]["data"][-1][1])
    html = lw_chart.chart_html(panes, one_line=True, label="x", ranges=ranges)
    assert "const RANGES={" in html and "class='rg'" in html and "rangeDefault" in html


def test_the_stock_page_has_no_streamlit_range_picker():
    for rel in ("src/ui/stock_chart.py", "src/ui/views/stock_view.py"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert "segmented_control" not in text and "sp_range_" not in text, rel


def test_the_stock_heading_follows_the_range():
    text = (ROOT / "src" / "ui" / "views" / "stock_view.py").read_text(encoding="utf-8")
    assert "sp-price-h" in text and "follow=follow" in text
    assert stock_chart.RANGE_WORDS == {"6M": "6 months", "12M": "12 months", "3Y": "3 years", "All": "the whole record"}


# ── Dashboard: momentum's lead is its whole record; the month's track fits 520 px ───

def test_momentum_lead_bars_are_the_whole_record():
    from src.ui.views import dashboard_home_view as dh
    months = [str(p) for p in pd.period_range("2021-12", "2026-10", freq="M")]
    sp = pd.DataFrame({"month": months, "top": 1.0, "nifty500": 0.5})
    bars = dh._lead_bars(sp, None)
    assert len(bars["values"]) == len(months) == 59 and bars["full"][0] == "Dec 2021"
    assert bars["dates"][0] == "2021-12-31" and bars["dates"][-1] == "2026-10-31"
    assert dh.LEAD_RANGE == {"default": "all", "why": "record"} and dh.FLOWS_RANGE["default"] == "12M"
    assert '"range":{"default":"all","why":"record"}' in dc.frame_html("bars", {**bars, "range": dh.LEAD_RANGE})


@pytest.mark.parametrize("lo,hi,step", [(-1.2, 2.3, 0.25), (-7.0, 7.0, 0.25), (-7.2, 7.4, 0.5), (-30.0, 25.0, 1.0)])
def test_the_month_track_takes_a_coarser_step_rather_than_pass_520px(lo, hi, step):
    from src.ui.views import dashboard_home_view as dh
    a, b, s = dh._month_scale(lo, hi)
    assert s == step and a <= lo and b >= hi and (b - a) / s * 8 <= 520
    assert float(np.round(-a / s, 9)).is_integer()     # the zero line falls on a line boundary


def test_portfolio_and_indices_state_their_ranges():
    from src.ui.views import indices_view as iv
    from src.ui.views import portfolio_page as pp
    assert pp.MONTH_RANGE["default"] == "all" and pp.DAY_RANGE["why"] == "fixed" and "20 sessions" in pp.DAY_RANGE["note"]
    assert iv.PE_RANGE == {"default": "all", "why": "record", "chips": ["3Y", "5Y", "all"]}
    for r in (pp.MONTH_RANGE, pp.DAY_RANGE, iv.PE_RANGE, iv.SIZE_RANGE):
        dc.check_range(r)
