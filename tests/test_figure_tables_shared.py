"""The `db-fig` figure tables go through the one shared renderer (TODO S112).

Both Dashboard figure tables -- "The book / Now / Nifty 500" and the momentum
health panel's "Last 12 months / Points" -- used to be a `<table>` format
string inside the view that drew them. They now go through
`theme.figure_table_html`, which is the fragment mode of the shared table
(docs/UI_ARCHITECTURE.md section 10).

Each assertion here is paired with one that the thing it searched actually
exists, so none of them can pass by matching nothing: the source files are
checked to be non-empty and to still draw a figure table, and the call is
proved by making the shared renderer the only thing that can produce it.
"""
from __future__ import annotations

import ast
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.ui import theme

VIEWS = Path(__file__).resolve().parents[1] / "src" / "ui" / "views"
FIGURE_TABLE_VIEWS = ("dashboard_view.py", "dashboard_panels.py")


def _source(name: str) -> str:
    text = (VIEWS / name).read_text(encoding="utf-8")
    assert len(text) > 1000, f"{name} read as {len(text)} bytes -- wrong path?"
    ast.parse(text)                      # it is the module, not a stray file
    return text


def test_the_views_no_longer_build_a_figure_table_themselves():
    """No `<table class="db-fig"` literal is left in a view."""
    seen_calls = 0
    for name in FIGURE_TABLE_VIEWS:
        src = _source(name)
        assert '<table class="db-fig"' not in src, (
            f"{name} still builds a db-fig table by hand")
        # ... and it does still draw one, through the shared renderer.
        assert "figure_table_html" in src, f"{name} draws no figure table at all"
        seen_calls += src.count("theme.figure_table_html(")
    assert seen_calls == 2, f"expected both figure tables, found {seen_calls}"


def test_the_shared_renderer_is_what_produces_the_dashboards_figure_tables(monkeypatch):
    """Break the shared renderer and both tables break: nothing else draws them."""
    from src.engine import book_risk as br
    from src.ui.views import dashboard_panels as dp
    from src.ui.views import dashboard_view as dv

    days = pd.bdate_range("2026-01-01", periods=200)
    rng = np.random.default_rng(3)
    m = rng.normal(0.0005, 0.01, 200)
    px = pd.DataFrame(
        {"AAA": 100 * np.cumprod(1 + 1.5 * m), "BBB": 100 * np.cumprod(1 + 0.5 * m)},
        index=days)
    bench = pd.Series(100 * np.cumprod(1 + m), index=days)
    res = br.book_risk(pd.Series({"AAA": 50, "BBB": 50}), px, bench)

    out = dv.book_risk_html(res, pd.Timestamp("2026-10-30"))
    assert '<table class="db-fig">' in out and "Volatility, a year" in out

    spreads = pd.DataFrame({
        "month": pd.period_range("2023-01", periods=36, freq="M").astype(str),
        "top": rng.normal(2.0, 4.0, 36),
        "bottom": rng.normal(0.0, 4.0, 36),
        "nifty500": rng.normal(1.0, 3.0, 36),
        "ew": rng.normal(1.2, 3.0, 36),
    })
    panel = dp.long_only_html(spreads)
    assert panel is not None, "the momentum health panel drew nothing to check"
    assert '<table class="db-fig">' in panel and "Last 12 months" in panel

    calls: list[tuple] = []
    real = theme.figure_table_html

    def spy(headers, rows, **kw):
        calls.append((tuple(headers), kw.get("align")))
        return real(headers, rows, **kw)

    monkeypatch.setattr(theme, "figure_table_html", spy)
    assert dv.book_risk_html(res, pd.Timestamp("2026-10-30")) == out
    assert dp.long_only_html(spreads) == panel
    assert [c[0] for c in calls] == [
        ("The book", "Now", "Nifty 500"), ("Last 12 months", "Points")]
    # Alignment is declared at the call site, never inferred from the header.
    assert [c[1] for c in calls] == [
        ("left", "right", "right"), ("left", "right")]


def test_the_markup_is_what_the_hand_built_format_strings_produced():
    """Byte-for-byte, against the markup the site shipped (S112 proof)."""
    assert theme.figure_table_html(
        ("The book", "Now", "Nifty 500"),
        [("Volatility, a year", ("16.9%", ""), ("12.4%", "mid")),
         ("Drawdown at the 30 Oct month-end", ("−8.1%", "down"), ("−9.1%", "mid")),
         ("Weight in the Nifty 100", ("5%", ""), ("", "mid"))],
        align=("left", "right", "right"),
    ) == (
        '<table class="db-fig"><thead><tr><th scope="col">The book</th>'
        '<th scope="col">Now</th><th scope="col">Nifty 500</th></tr></thead>'
        '<tbody><tr><td>Volatility, a year</td><td class="">16.9%</td>'
        '<td class="mid">12.4%</td></tr>'
        '<tr><td>Drawdown at the 30 Oct month-end</td><td class="down">−8.1%</td>'
        '<td class="mid">−9.1%</td></tr>'
        '<tr><td>Weight in the Nifty 100</td><td class="">5%</td>'
        '<td class="mid"></td></tr></tbody></table>')

    assert theme.figure_table_html(
        ("Last 12 months", "Points"),
        [("Top 50 against the Nifty 500", ("+15.7", "up")),
         ("Winners against losers (the factor, for reference)", ("+10.2", "up"))],
        align=("left", "right"),
    ) == (
        '<table class="db-fig"><thead><tr><th scope="col">Last 12 months</th>'
        '<th scope="col">Points</th></tr></thead><tbody>'
        '<tr><td>Top 50 against the Nifty 500</td><td class="up">+15.7</td></tr>'
        '<tr><td>Winners against losers (the factor, for reference)</td>'
        '<td class="up">+10.2</td></tr></tbody></table>')


def test_a_declared_side_the_stylesheet_does_not_give_is_written_into_the_markup():
    """The point of declaring it: a departure shows, it is not silently lost."""
    plain = theme.figure_table_html(("A", "B"), [("x", ("1", ""))])
    assert "text-align" not in plain                 # the stylesheet's own sides
    moved = theme.figure_table_html(
        ("A", "B"), [("x", ("1", ""))], align=("left", "center"))
    assert moved.count('style="text-align:center"') == 2   # the heading and the cell
    assert theme.figure_table_align(3) == ["left", "right", "right"]


def test_every_heading_and_cell_is_escaped():
    out = theme.figure_table_html(
        ("<b>h</b>", "x"), [("<i>&</i>", ('"q"', "up"))], align=("left", "right"))
    assert "<b>" not in out and "<i>" not in out
    assert "&lt;b&gt;h&lt;/b&gt;" in out and "&lt;i&gt;&amp;&lt;/i&gt;" in out
    assert "&quot;q&quot;" in out


def test_a_bad_shape_or_side_is_refused_rather_than_drawn_wrong():
    with pytest.raises(ValueError):
        theme.figure_table_html(("A", "B"), [("x",)])
    with pytest.raises(ValueError):
        theme.figure_table_html(("A", "B"), [], align=("left",))
    with pytest.raises(ValueError):
        theme.figure_table_html(("A", "B"), [], align=("left", "middle"))
