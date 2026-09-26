"""Regressions from the line-by-line UI audit, part 2 (2026-09-25)."""
import re
import shutil
import subprocess

import numpy as np
import pandas as pd
import pytest

from src.engine.momentum import CARRIED_MARK
from src.ui import charts, components, screener_table
from src.ui.views import breadth_view, stock_view


def _capture(monkeypatch, module):
    out = []
    monkeypatch.setattr(module.st, "markdown", lambda h, **k: out.append(str(h)))
    monkeypatch.setattr(module.st, "html", lambda h, **k: out.append(str(h)))
    return out


def test_stock_page_index_badges_are_exact_tags(monkeypatch):
    """MID150/SMALL250/MICRO250/NN50 all contain "50"; they each wore "N50"."""
    out = _capture(monkeypatch, stock_view)
    row = pd.Series({"Symbol": "ABC", "Rank": 5, "Indices": "MID150", "Industry": "IT"})
    stock_view._render_identity(row, total_stocks=750)
    page = "".join(out)
    assert ">MID150<" in page and ">N50<" not in page


def test_rank_ring_shows_standing_not_raw_score():
    top = stock_view._rank_ring(1, 750, 1.0)
    bottom = stock_view._rank_ring(750, 750, 0.0)
    offset = lambda svg: float(re.findall(r'stroke-dashoffset="([\d.]+)"', svg)[0])
    assert offset(top) < offset(bottom)


def test_peers_table_formats_float32_prices(monkeypatch):
    out = _capture(monkeypatch, stock_view)
    df = pd.DataFrame({"Symbol": ["AAA"], "CMP": np.array([1234.5677], dtype="float32")})
    stock_view._render_peers_table(df, highlight_sym="AAA")
    assert "₹1,235" in out[0] and "1234.56" not in out[0]


def test_ranking_row_float32_nan_drawdown_is_a_dash():
    row = {"Symbol": "YNG", "Rank": 9, "CMP": 100.0,
           "Max DD 12M": np.float32("nan"), "12M Return": np.nan}
    html = screener_table._row_html(row, screener_table.columns_for("Core"), {})
    assert "nan" not in html.lower()


def test_gap_count_sees_a_gap_that_also_carries_the_mark():
    df = pd.DataFrame({"Data Gap": ["🔴", "🔴" + CARRIED_MARK, "", CARRIED_MARK]})
    assert components.gap_count(df) == 2


def test_breadth_by_index_matches_exact_tags():
    df = pd.DataFrame({"Symbol": ["A", "B", "C", "D"],
                       "Indices": ["N50", "NN50", "MID150", "SMALL250,MICRO250"]})
    assert breadth_view.index_members(df, "NIFTY 50") == ["A"]
    assert breadth_view.index_members(df, "NIFTY NEXT 50") == ["B"]
    assert breadth_view.index_members(df, "NIFTY MIDCAP 150") == ["C"]
    assert breadth_view.index_members(df, "NIFTY MICROCAP 250") == ["D"]


@pytest.mark.skipif(shutil.which("node") is None, reason="needs node to parse the page scripts")
def test_chart_pages_escape_names_and_still_parse(tmp_path, monkeypatch):
    evil = "</b><img src=x onerror=alert(1)>"
    pages = [
        charts._build_treemap_html(charts._script_json([{"name": evil, "children": []}]), "3M Return", "Mcap"),
        charts._build_rrg_html(charts._script_json([])),
    ]
    got = []
    monkeypatch.setattr(charts.st, "iframe", lambda h, **k: got.append(h))
    charts.render_correlation_heatmap(pd.DataFrame(np.eye(2), index=["A", evil], columns=["A", evil]), ["A", evil], 2)
    pages += got
    for i, page in enumerate(pages):
        assert "function esc(" in page
        js = tmp_path / f"p{i}.js"
        js.write_text("\n".join(re.findall(r"<script>(.*?)</script>", page, re.S)))
        assert subprocess.run(["node", "--check", str(js)], capture_output=True).returncode == 0
