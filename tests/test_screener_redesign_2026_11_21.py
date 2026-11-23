"""Screener redesign (S151, owner approved 21 Nov 2026: "With all your decisions").

Rules from docs/SCREENER_REQUIREMENTS.md: one date for "a month ago" on every
page (decision A), no internal names, one industry name map, the book's lines
named, a data line with no source, and the Nano Cap / Combined footnote.
"""
from __future__ import annotations

import re

import pandas as pd
import pytest

from src.engine import dashboard_insights as di
from src.engine.calendar_momentum import rank_history_position
from src.ui import screener_table as st_
from src.ui.industry_names import INDUSTRY_SHORT, short_industry
from src.ui.views import ranking_view as rv


@pytest.mark.parametrize("drop", [None, "2026-10-20", "2026-08-20"])
@pytest.mark.parametrize("months", [1, 3])
def test_a_rank_n_months_ago_is_read_on_the_dashboards_date(drop, months):
    idx = pd.bdate_range("2026-06-01", "2026-11-20")
    if drop:
        idx = idx.drop(pd.Timestamp(drop))
    want = di.on_or_before(idx, di.trail_dates(idx[-1])[f"{months}m"])
    assert idx[rank_history_position(idx, months)] == want


def test_a_holiday_reads_the_session_before_not_after():
    idx = pd.bdate_range("2026-09-01", "2026-11-20").drop(pd.Timestamp("2026-10-20"))
    assert idx[rank_history_position(idx, 1)] == pd.Timestamp("2026-10-19")


def test_the_engine_reads_past_ranks_with_the_same_rule():
    import inspect

    from src.engine import momentum
    src = inspect.getsource(momentum)
    assert "rank_history_position(score_idx" in src
    assert "hist_starts" not in src


def _row(**kw):
    base = {"Symbol": "AAA", "Rank": 5, "CMP": 100.0, "Score": 2.0, "Qualified Rank": 20,
            "Qualified (-3M)": 30, "Qualified (-1M)": None, "Rank (-3M)": 52, "Rank (-1M)": 9,
            "Rank Δ 1M": 4, "Indices": "MICRO250", "Industry": "Fast Moving Consumer Goods",
            "Held": True, "Above 50 EMA": True, "Near 52W High": True, "% 50 EMA": 3.0, "% High": -1.0,
            "Market Cap (Cr)": 1000.0, "Volume": "Normal"}
    return base | kw


def test_the_table_names_indices_and_industries_as_every_page_does():
    html = st_.table_html(pd.DataFrame([_row()]), None, "Full Quant (35)")
    body = html.split("<tbody>")[1]
    assert "Microcap 250" in body and "MICRO250" not in body
    assert ">FMCG<" in body and "Fast Moving Consumer" not in body.split('title="')[0]


def test_past_ranks_are_numbers_and_out_means_not_qualified():
    html = st_.table_html(pd.DataFrame([_row()]), None, "Full Quant (35)")
    row = html.split('<tr data-stock="AAA"')[1].split("</tr>")[0]
    for v in (52, 9, 30):
        assert re.search(rf'<td class="n past" data-v="{v}(\.0)?">{v}</td>', row), v
    assert '<td class="n past" data-v="">Out</td>' in row
    assert "▲" not in row and "▼" not in row


def test_the_book_line_is_named_on_its_row():
    html = st_.table_html(pd.DataFrame([_row()]), None, "Core (17)")
    assert "The book buys to here: the 20th qualified" in html
    html40 = st_.table_html(pd.DataFrame([_row(**{"Qualified Rank": 40})]), None, "Core (17)")
    assert "A holding is kept to here: the 40th qualified" in html40


def test_big_movers_adds_places_moved_and_other_views_do_not():
    keys = [c[0] for c in st_.columns_for("Core (17)")]
    assert "d1m" not in keys
    moved = [c[0] for c in st_.columns_for("Core (17)", movers=True)]
    assert moved[moved.index("p1") + 1] == "d1m"


def test_qualified_trail_columns_drop_when_the_trail_is_missing():
    keys = [c[0] for c in st_.columns_for("Full Quant (35)", pd.Index(["Rank", "Symbol"]))]
    assert "q3" not in keys and "q1" not in keys and "qrank" in keys


def test_one_industry_map_for_every_page():
    from src.ui.views import dashboard_home_view, sector_view
    assert dashboard_home_view.SHORT is INDUSTRY_SHORT
    assert sector_view.SHORT_NAMES is INDUSTRY_SHORT
    assert short_industry("Consumer Durables") == "Durables"
    assert short_industry(None) == "" and short_industry("nan") == ""


def test_the_title_answers_who_leads_and_can_be_bought():
    df = pd.DataFrame({
        "Symbol": list("ABCD"), "Rank": [1, 2, 3, 60],
        "Rank (-1M)": [70, 2, 3, 10],
        "Above 50 EMA": [True, True, False, True], "Near 52W High": [True, True, True, True],
    })
    # "a month ago", not "this month": the comparison is with the rank a month back (glossary 9).
    assert rv.screener_title(df) == "2 of the top 3 can be bought; 1 of the 3 were not in the top 3 a month ago."
    assert rv.screener_title(df.drop(columns="Rank (-1M)")) == "2 of the top 3 can be bought."


def test_the_data_line_names_no_source(monkeypatch):
    monkeypatch.setattr(rv, "data_freshness", lambda: [
        {"label": "Ranked from", "as_of": "Personal", "stale": True},
        {"label": "Market caps", "as_of": "18 Nov", "stale": True}])
    idx = pd.bdate_range("2026-11-02", "2026-11-20")
    df = pd.DataFrame({"Symbol": ["A"], "Short History": ["No"], "Data Gap": ["🟢"]})
    line = rv.data_line(df, pd.DataFrame({"A": 1.0}, index=idx))
    # The source the prices come from, named once (S173 rule 7); never the internal path (21 Nov).
    assert line.count("Data to 20 Nov 2026 · NSE.") == 1
    assert "Personal" not in line and "release files" not in line
    assert "Market caps are to 18 Nov" in line


def test_the_nano_and_combined_footnote_names_what_is_not_ranked():
    head, body = rv.system_note("Nano Cap", ["A", "B"], ["A", "B", "C"], nano=True)
    assert head == "Nano Cap · 2 of 3 stocks ranked among themselves."
    assert body == "1 too new to rank (under three months of prices): C."
    head, body = rv.system_note("Combined", ["A"], ["A"], nano=False)
    assert head.endswith("as one list.") and body == ""
    many = [f"S{i:02d}" for i in range(14)]
    assert rv.system_note("Nano Cap", [], many, nano=True)[1].endswith(" and more.")


def test_no_capitals_in_group_labels():
    html = st_.table_html(pd.DataFrame([_row()]), None, "Full Quant (35)")
    grp = re.search(r'<tr class="grp-row">(.*?)</tr>', html, re.S).group(1)
    assert "uppercase" not in html.split("thead tr.grp-row th{top:0")[1].split("}")[0]
    assert not re.search(r">[A-Z]{3,}[ <]", grp)


def test_the_qualified_place_is_named_where_it_stands_alone():
    head = lambda d: re.search(r'<tr class="hdr">(.*?)</tr>', st_.table_html(pd.DataFrame([_row()]), None, d), re.S).group(1)
    assert "Qualified #" in head("Core (17)")
    full = head("Full Quant (35)")
    assert "Qualified #" not in full and ">Now<" in full
