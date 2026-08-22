"""A number in a table has a unit, and the renderer has to know which one.

`render_saas_table` inferred it from magnitude: a value at or below 1.0 was
treated as a fraction, anything larger as an already-scaled percentage. The
inference is wrong in both directions and fails on the rows a momentum desk
cares about most -- a stock that gained 131% (Return % == 1.31) printed as
"+1.3%", and an 0.8% drawdown (Max DD 3M == -0.8) printed as "-80.0%".
"""
import types

import pandas as pd
import pytest

from src.ui import theme
from src.ui.theme import percent_unit, render_saas_table


def _render(df: pd.DataFrame, monkeypatch) -> str:
    captured: dict[str, str] = {}
    monkeypatch.setattr(
        theme,
        "st",
        types.SimpleNamespace(
            iframe=lambda html, height=None: captured.setdefault("html", html),
            info=lambda *a, **k: None,
        ),
    )
    render_saas_table(df, key="test")
    return captured["html"]


@pytest.mark.parametrize("column", [
    "Return %", "Strategy Net", "Benchmark", "Alpha vs Benchmark",
    "Total Return", "CAGR", "Win Rate", "Max Drawdown",
    "1M Return", "3M Return", "6M Return", "9M Return", "12M Return",
])
def test_fraction_columns_are_declared(column):
    assert percent_unit(column) == "fraction"


@pytest.mark.parametrize("column", [
    "Turnover %", "Cost Drag %", "Weight %", "% High", "% ATH", "% 50 EMA",
    "% 20 EMA", "% 52W High", "ATR %", "FFill %", "Del %",
    "Max DD 1M", "Max DD 3M", "Max DD 12M",
])
def test_scaled_columns_are_declared(column):
    assert percent_unit(column) == "scaled"


def test_undeclared_columns_still_fall_back_to_the_guess():
    assert percent_unit("Sharpe") is None
    assert percent_unit("Symbol") is None


def test_a_multibagger_is_not_printed_as_a_rounding_error(monkeypatch):
    """+131.4% must not render as "+1.3%"."""
    html = _render(pd.DataFrame({"Symbol": ["CUPID"], "Return %": [1.3142]}), monkeypatch)
    assert "+131.4%" in html
    assert "+1.3%" not in html


def test_a_total_loss_keeps_its_sign_and_scale(monkeypatch):
    html = _render(pd.DataFrame({"Symbol": ["X"], "Return %": [-0.4271]}), monkeypatch)
    assert "-42.7%" in html


def test_a_small_drawdown_is_not_inflated_a_hundredfold(monkeypatch):
    html = _render(pd.DataFrame({"Symbol": ["X"], "Max DD 3M": [-0.8]}), monkeypatch)
    assert "-0.8%" in html
    assert "-80.0%" not in html


def test_turnover_stays_a_percentage(monkeypatch):
    html = _render(pd.DataFrame({"Symbol": ["X"], "Turnover %": [45.0]}), monkeypatch)
    assert "45.0%" in html


def test_entry_and_exit_prices_keep_their_paise(monkeypatch):
    """The blotter's two prices must reproduce the return printed beside them."""
    html = _render(
        pd.DataFrame(
            {
                "Symbol": ["CUPID"],
                "Entry Price": [157.65],
                "Exit Price": [168.40],
                "Return %": [168.40 / 157.65 - 1],
            }
        ),
        monkeypatch,
    )
    assert "₹157.65" in html
    assert "₹168.40" in html
    assert "+6.8%" in html


def test_aggregate_money_stays_whole(monkeypatch):
    html = _render(
        pd.DataFrame({"Symbol": ["X"], "Actual Value (₹)": [1234567.89]}), monkeypatch
    )
    assert "₹1,234,568" in html
