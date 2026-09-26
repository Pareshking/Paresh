"""The screener table must not print a column of em dashes, or lose alignment.

A ranking built from closing prices carries no ATR, so `Stop Loss` and
`Chand Exit` are removed from the frame upstream. The table's headers and cells
are three pairs of hand-written HTML strings, so dropping a cell without
dropping its `<th>` -- or dropping a `<th>` without dropping the group label
above it -- shifts every column to its right by one and is invisible to any
test that only asks whether the page rendered.

This counts them: sub-header `<th>`s, data-row `<td>`s and the summed colspans
of the group row must agree, with the risk columns present and absent.
"""
from __future__ import annotations

import re

import pandas as pd
import pytest
import streamlit as st

from src.engine.momentum import ATR_DERIVED_COLUMNS
from src.ui.theme import render_master_screener_table

DENSITIES = ("Executive (11)", "Core (17)", "Full Quant (35)")


def _frame(with_risk: bool) -> pd.DataFrame:
    row = {
        "Rank": 1, "Symbol": "HEG", "Industry": "Capital Goods", "CMP": 237.0,
        "Market Cap (Cr)": 9_150.0, "Score": 71.2, "Indices": "MID150",
        "1M Return": -0.085, "3M Return": 0.218, "6M Return": 0.325,
        "9M Return": 0.41, "12M Return": 0.52,
        "1M Sharpe": 0.4, "3M Sharpe": 1.1, "6M Sharpe": 1.3,
        "9M Sharpe": 1.2, "12M Sharpe": 1.4,
        "Max DD 1M": -4.2, "Max DD 3M": -9.1, "Max DD 6M": -12.0,
        "Max DD 9M": -15.0, "Max DD 12M": -21.0,
        "% High": -12.9, "% ATH": -72.0, "% 50 EMA": -2.0,
        "Volume": "Normal", "Above 50 EMA": False, "Near 52W High": False,
        "At ATH": False, "Rank Δ 1M": 3, "Rank Δ 3M": -2,
        "Data Gap": "🟢", "FFill %": 0.0, "Horizons": 5,
    }
    if with_risk:
        row |= {"Stop Loss": 210.0, "Chand Exit": 224.0, "ATR": 13.5, "ATR %": 5.7}
    return pd.DataFrame([row])


def _render(monkeypatch, frame: pd.DataFrame, density: str) -> str:
    captured: list[str] = []
    monkeypatch.setattr(st, "iframe", lambda html, **kw: captured.append(html))
    render_master_screener_table(frame, density=density)
    assert captured, f"{density}: nothing was rendered"
    return captured[0]


def _widths(html: str) -> tuple[int, int, int]:
    group = re.search(r'<tr class="group-header-row">(.*?)</tr>', html, re.S)
    sub = re.search(r'<tr class="sub-header-row">(.*?)</tr>', html, re.S)
    body = re.search(r'<tr class="screener-row">(.*?)</tr>', html, re.S)
    assert group and sub and body, "table rows not found"
    spans = sum(
        int(m) if m else 1
        for m in re.findall(r'<th(?:[^>]*?colspan="(\d+)")?[^>]*>', group.group(1))
    )
    return spans, len(re.findall(r"<th", sub.group(1))), len(re.findall(r"<td", body.group(1)))


@pytest.mark.parametrize("density", DENSITIES)
@pytest.mark.parametrize("with_risk", [True, False])
def test_headers_and_cells_stay_aligned(monkeypatch, density, with_risk):
    html = _render(monkeypatch, _frame(with_risk), density)
    spans, headers, cells = _widths(html)
    assert headers == cells, (
        f"{density} (risk={with_risk}): {headers} headers over {cells} cells"
    )
    assert spans == headers, (
        f"{density} (risk={with_risk}): group row spans {spans} of {headers} columns"
    )


@pytest.mark.parametrize("density", DENSITIES)
def test_no_risk_column_survives_without_atr(monkeypatch, density):
    """Absent ATR must take the LABELS with it, not leave a column of dashes."""
    html = _render(monkeypatch, _frame(with_risk=False), density)
    for label in ("STOP LOSS", "CHAND EXIT", "RISK & EXITS"):
        assert label not in html, f"{density}: '{label}' survived without ATR"


@pytest.mark.parametrize("density", ["Core (17)", "Full Quant (35)"])
def test_risk_columns_still_render_when_atr_is_present(monkeypatch, density):
    """The drop is conditional, not a deletion: Yahoo's ranking still shows them."""
    html = _render(monkeypatch, _frame(with_risk=True), density)
    assert "STOP LOSS" in html
    assert "₹210" in html
    if density.startswith("Full"):
        assert "CHAND EXIT" in html and "₹224" in html


def test_the_drop_is_keyed_to_the_canonical_column_names():
    """Guards the typo that let 'Chandelier Exit' ship as a live stop."""
    assert "Chand Exit" in ATR_DERIVED_COLUMNS
    assert "Stop Loss" in ATR_DERIVED_COLUMNS


# ── The single-stock page renders the same three values as tiles ─────────────

def test_stock_page_drops_the_atr_tiles_when_there_is_no_atr(monkeypatch):
    """Three tiles printing an em dash under a formula is not a key level."""
    import src.ui.views.stock_view as sv

    captured: list[str] = []
    monkeypatch.setattr(sv.st, "markdown", lambda html, **kw: captured.append(html))

    sv._render_price_ladder(pd.Series({
        "52W High": 272.0, "% High": -12.9, "ATH": 847.0, "% ATH": -72.0,
        "ATH Date": "2018-10-16", "52W High Date": "2026-09-07", "% 50 EMA": -2.0,
    }))
    html = "".join(captured)
    assert "52W High" in html, "the tiles that do not need ATR must survive"
    for label in ("Stop Loss", "Chandelier Exit", "2×ATR"):
        assert label not in html, f"'{label}' rendered with no ATR behind it"


def test_stock_page_keeps_the_atr_tiles_when_atr_is_present(monkeypatch):
    import src.ui.views.stock_view as sv

    captured: list[str] = []
    monkeypatch.setattr(sv.st, "markdown", lambda html, **kw: captured.append(html))

    sv._render_price_ladder(pd.Series({
        "52W High": 272.0, "% High": -12.9, "ATH": 847.0, "% ATH": -72.0,
        "% 50 EMA": -2.0, "Stop Loss": 210.0, "Chand Exit": 224.0,
        "ATR": 13.5, "ATR %": 5.7,
    }))
    html = "".join(captured)
    assert "Stop Loss" in html and "Chandelier Exit" in html
    assert "210" in html and "224" in html


# ── The density label must not become a second, drifting copy of the count ───

@pytest.mark.parametrize("density", DENSITIES)
@pytest.mark.parametrize("with_risk", [True, False])
def test_column_count_matches_the_table_it_describes(monkeypatch, density, with_risk):
    """`Full Quant (35)` sat over a 36-column table. Read the count, don't type it."""
    from src.ui.theme import screener_column_count

    frame = _frame(with_risk)
    html = _render(monkeypatch, frame, density)
    _, headers, _ = _widths(html)
    assert screener_column_count(density, frame.columns) == headers
