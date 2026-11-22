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

from src.engine.momentum import ATR_DERIVED_COLUMNS
from src.ui import screener_table

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
    return screener_table.table_html(frame, None, density)


def _widths(html: str) -> tuple[int, int]:
    head = re.search(r'<tr class="hdr">(.*?)</tr></thead>', html, re.S)
    body = re.search(r"<tbody><tr[^>]*>(.*?)</tr>", html, re.S)
    assert head and body, "table rows not found"
    return len(re.findall(r"<th[ >]", head.group(1))), len(re.findall(r"<td[ >]", body.group(1)))


@pytest.mark.parametrize("density", DENSITIES)
@pytest.mark.parametrize("with_risk", [True, False])
def test_headers_and_cells_stay_aligned(monkeypatch, density, with_risk):
    html = _render(monkeypatch, _frame(with_risk), density)
    headers, cells = _widths(html)
    assert headers == cells, (
        f"{density} (risk={with_risk}): {headers} headers over {cells} cells"
    )


@pytest.mark.parametrize("density", DENSITIES)
def test_no_risk_column_survives_without_atr(monkeypatch, density):
    """Absent ATR must take the LABELS with it, not leave a column of dashes."""
    html = _render(monkeypatch, _frame(with_risk=False), density)
    for label in ("Stop loss", "Chandelier exit"):
        assert label not in html, f"{density}: '{label}' survived without ATR"


def test_risk_columns_still_render_when_atr_is_present(monkeypatch):
    """The drop is conditional, not a deletion: Yahoo's ranking still shows them."""
    html = _render(monkeypatch, _frame(with_risk=True), "Full Quant (35)")
    assert "Stop loss" in html and "₹210" in html
    assert "Chandelier exit" in html and "₹224" in html


def test_the_drop_is_keyed_to_the_canonical_column_names():
    """Guards the typo that let 'Chandelier Exit' ship as a live stop."""
    assert "Chand Exit" in ATR_DERIVED_COLUMNS
    assert "Stop Loss" in ATR_DERIVED_COLUMNS


# ── The single-stock page renders the same three values as tiles ─────────────

def test_stock_page_shows_no_stop_levels_even_if_a_frame_carries_them():
    """The app has no stops (owner, 2026-09-27, and again on 22 Nov 2026, STOCK_REQUIREMENTS row 50):
    the levels section ignores Stop Loss, Chand Exit and ATR columns (tests/test_stock_page_v2.py
    checks the whole page)."""
    import src.ui.views.stock_view as sv
    from src.ui import stock_lines as sl
    from src.ui import watchlist_lines as wl

    row = pd.Series({"Symbol": "X", "CMP": 240.0, "52W High": 272.0, "% High": -11.8, "ATH": 847.0,
                     "ATH Date": "2018-10-16", "52W High Date": "2026-09-07", "% 50 EMA": -2.0,
                     "Above 50 EMA": False, "Near 52W High": True,
                     "Stop Loss": 210.0, "Chand Exit": 224.0, "ATR": 13.5, "ATR %": 5.7})
    lad = sl.ladder(row, None, 0.8)
    html = "".join(sv.rules_html(row, None, None, wl.Lines(20, 40, 20), 0.8, lad, False, None, None, [], None))
    assert "52W high" in html                                  # the rest still renders
    for label in ("Stop Loss", "Stop loss", "Chandelier", "Chand Exit", "ATR (14", "₹210", "₹224"):
        assert label not in html, label


# ── The density label must not become a second, drifting copy of the count ───

@pytest.mark.parametrize("density", DENSITIES)
@pytest.mark.parametrize("with_risk", [True, False])
def test_column_count_matches_the_table_it_describes(monkeypatch, density, with_risk):
    """The density label's count is read from the table, not typed."""
    frame = _frame(with_risk)
    html = _render(monkeypatch, frame, density)
    _, cells = _widths(html)
    assert screener_table.column_count(density, frame.columns) == cells
