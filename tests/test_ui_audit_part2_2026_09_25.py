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
    assert ">Nifty Midcap 150<" in page and ">Nifty 50<" not in page


def test_rank_path_reads_oldest_to_now():
    out = []
    import src.ui.views.stock_view as sv

    orig = sv.st.markdown
    sv.st.markdown = lambda h, **k: out.append(str(h))
    try:
        sv._render_identity(pd.Series({"Symbol": "ABC", "Rank": 1, "Rank (-1M)": 2,
                                       "Rank (-3M)": 6}), total_stocks=750)
    finally:
        sv.st.markdown = orig
    page = "".join(out)
    assert page.index("#6") < page.index("#2") < page.index("<b>#1</b>")


def _peers_html(monkeypatch, rank_df, sym):
    """The peers card's table, as the stock page draws it."""
    frames = []
    monkeypatch.setattr(screener_table.st, "iframe", lambda h, **k: frames.append(str(h)))
    _capture(monkeypatch, stock_view)
    row = rank_df[rank_df["Symbol"] == sym].iloc[0]
    stock_view._render_peers(row, rank_df, None)
    assert len(frames) == 1, "the peers card draws one Screener table"
    return frames[0]


def test_peers_table_formats_float32_prices(monkeypatch):
    rank_df = pd.DataFrame({"Symbol": ["AAA", "BBB"], "Rank": [1, 2], "Industry": ["IT", "IT"],
                            "CMP": np.array([1234.5677, 99.0], dtype="float32")})
    html = _peers_html(monkeypatch, rank_df, "AAA")
    # The raw float stays in the sort key (data-v), never in the text shown.
    assert "₹1,235" in html and ">1234.5" not in html


def test_peers_tag_this_stock_even_below_the_top_eight(monkeypatch):
    """The peers card is the Screener's table, with this stock's row tagged."""
    n = 12
    rank_df = pd.DataFrame({"Symbol": [f"S{i}" for i in range(n)], "Rank": range(1, n + 1),
                            "Industry": ["IT"] * n, "CMP": [100.0] * n})
    html = _peers_html(monkeypatch, rank_df, "S11")
    assert html.count("<tr data-stock=") == stock_view.PEERS_SHOWN
    assert '<tr data-stock="S11" class="hl">' in html and "This stock" in html
    assert '<tr data-stock="S0">' in html


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
    pages = [
        charts._build_rrg_html(charts._script_json([])),
    ]
    for i, page in enumerate(pages):
        assert "function esc(" in page
        js = tmp_path / f"p{i}.js"
        js.write_text("\n".join(re.findall(r"<script>(.*?)</script>", page, re.S)))
        assert subprocess.run(["node", "--check", str(js)], capture_output=True).returncode == 0
