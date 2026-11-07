"""The Screener table's group headers, colour rule and glyphs (owner, 7 Nov).

The group row was counted per group wherever its columns sat, so in Core
(r1 r3 r6 r12 dd3) "3M" spanned 3M and 6M Ret and "12M" sat over Max DD 3M.
These tests read the rendered table: every group label must sit over exactly
the columns it names.
"""
from __future__ import annotations

import re

import pandas as pd
import pytest

from src.ui import screener_table as st_
from src.ui.views import ranking_view as rv

DENSITIES = ("Executive (11)", "Core (17)", "Full Quant (35)")


def _row(**over) -> dict:
    row = {
        "Rank": 1, "Symbol": "HEG", "Company Name": "HEG Ltd", "Industry": "Capital Goods",
        "CMP": 237.0, "Market Cap (Cr)": 9_150.0, "Indices": "MID150",
        **{f"{w}M Return": 0.1 for w in st_.PERIOD_WINDOWS},
        **{f"{w}M Sharpe": -1.17 for w in st_.PERIOD_WINDOWS},
        **{f"Max DD {w}M": -9.1 for w in st_.PERIOD_WINDOWS},
        "% High": 0.0, "% ATH": -2.7, "% 50 EMA": -2.0, "Volume": "High",
        "Above 50 EMA": True, "Near 52W High": False, "At ATH": False,
        "Rank Δ 1M": 3, "Rank Δ 3M": -2, "Data Gap": "🟢", "FFill %": 0.0,
        "Horizons Scored": 5,
    }
    row.update(over)
    return row


def _html(density: str, **kw) -> str:
    return st_.table_html(pd.DataFrame([_row()]), None, density, **kw)


@pytest.mark.parametrize("density", DENSITIES)
def test_every_group_label_sits_over_its_own_columns(density):
    keys = [c[0] for c in st_.columns_for(density)]
    groups = st_.column_groups(keys)
    assert sum(n for _, n, _ in groups) == len(keys)
    group_of = {k: g for g, ks in st_._QUANT_GROUPS for k in ks}
    i = 0
    for label, n, _ in groups:
        span = keys[i:i + n]
        i += n
        if label in ("Returns",):
            assert all(k.startswith("r") and k[1:].isdigit() for k in span), span
        elif label == "Risk":
            assert all(k.startswith(("dd", "sh")) for k in span), span
        elif label:
            assert {group_of[k] for k in span} == {label}, (label, span)


def test_core_groups_returns_and_risk_and_never_repeats_a_window():
    labels = [g for g, _, _ in st_.column_groups([c[0] for c in st_.columns_for("Core (17)")])]
    assert "Returns" in labels and "Risk" in labels
    assert not {"1M", "3M", "6M", "12M"} & set(labels)
    assert len(labels) == len(set(labels))


def test_full_quant_keeps_its_window_groups():
    labels = [g for g, _, _ in st_.column_groups([c[0] for c in st_.columns_for("Full Quant (35)")])]
    for w in st_.PERIOD_WINDOWS:
        assert f"{w}M factor momentum" in labels


@pytest.mark.parametrize("density", DENSITIES)
def test_the_group_row_spans_every_column_and_pins_rank_and_symbol(density):
    html = _html(density)
    grp = re.search(r'<tr class="grp-row">(.*?)</tr>', html, re.S).group(1)
    spans = [int(n) for n in re.findall(r'colspan="(\d+)"', grp)]
    assert sum(spans) == len(st_.columns_for(density, pd.DataFrame([_row()]).columns))
    assert re.match(r'<th colspan="2" class="grp pin">Identity</th>', grp)


def test_sharpe_is_coloured_by_its_sign_and_drawdown_is_plain():
    html = _html("Full Quant (35)")
    assert '<td class="n neg" data-v="-1.17">−1.17</td>' in html
    assert re.search(r'<td class="n" data-v="-9.1">−9.1%</td>', html)
    assert "td.sharpe" not in html


def test_signs_are_true_minus_and_a_peak_reads_new_high():
    html = _html("Full Quant (35)")
    body = html.split("<tbody>")[1]
    assert not re.search(r">-\d", body), "a hyphen-minus reached a cell"
    assert ">New high<" in body          # % 52W HI at 0
    assert ">−2.7%<" in body             # % ATH, plain


def test_pass_and_fail_are_glyphs_not_coloured_dots():
    body = _html("Full Quant (35)").split("<tbody>")[1]
    for dot in ("🟢", "⚪", "🔴", "🔥", "⚡"):
        assert dot not in body, dot
    assert "✓" in body and "✗" in body


def test_the_phone_line_under_the_symbol_is_the_industry_alone():
    html = _html("Core (17)")
    assert '<span class="sub">Capital Goods</span>' in html
    assert 'title="Open HEG Ltd"' in html


def test_the_trend_header_has_a_phone_label():
    assert '<span class="lbl-m">60D</span>' in _html("Core (17)")


def test_the_header_arrow_names_the_sort_the_rows_arrive_in():
    html = _html("Core (17)", sort_key="d1m", sort_desc=True)
    head = re.search(r'<tr class="hdr">(.*?)</tr>', html, re.S).group(1)
    on = re.findall(r'<th class="[^"]*\bon\b[^"]*"[^>]*>(.*?)</th>', head)
    assert len(on) == 1 and "1M Δ" in on[0] and "↓" in on[0]
    assert 'data-dir="desc"' in head


def test_an_unknown_sort_key_falls_back_to_rank():
    head = re.search(r'<tr class="hdr">(.*?)</tr>', _html("Executive (11)", sort_key="d3m"), re.S).group(1)
    on = re.findall(r'<th class="[^"]*\bon\b[^"]*"[^>]*>(.*?)</th>', head)
    assert len(on) == 1 and "Rank" in on[0]


def test_the_movers_heading_names_the_session_a_month_back():
    idx = pd.bdate_range("2026-09-01", "2026-11-06")
    px = pd.DataFrame({"A": range(len(idx))}, index=idx, dtype=float)
    assert rv._movers_heading(px) == "Since 6 Oct (one month)"
    # 6 Oct is a holiday in this calendar: the next session is named.
    assert rv._movers_heading(px.drop(pd.Timestamp("2026-10-06"))) == "Since 7 Oct (one month)"
    assert rv._movers_heading(None) == "In the last month"


def test_headers_sort_from_the_keyboard_and_say_how_they_are_sorted():
    """Pre-launch audit F20 (WCAG 2.1.1/4.1.2), owner unparked item 13."""
    html = _html("Core (17)")
    for needle in ("th.tabIndex=0", "aria-sort", "e.key==='Enter'||e.key===' '",
                   "thead th:focus-visible"):
        assert needle in html, needle
