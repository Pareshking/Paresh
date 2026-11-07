"""Data findings from the 7 Nov site review (owner: fix them correctly)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.engine.exit_watch import RANK_SCALE, Rules, assess, nearest_rule

VIEWS = Path(__file__).resolve().parents[1] / "src" / "ui" / "views"


def _rank_df() -> pd.DataFrame:
    # 6 Nov: PVRINOX qualified #16 (24 places to the buffer), 13.8% EMA cushion;
    # LAURUSLABS #1 (39 places), 12.6% EMA cushion.
    rows = []
    for i in range(1, 41):
        rows.append({"Symbol": f"S{i}", "Rank": i, "Above 50 EMA": True, "Near 52W High": True,
                     "% 50 EMA": 30.0, "% High": 0.0, "Industry": "X"})
    rows[0].update(Symbol="LAURUSLABS", **{"% 50 EMA": 100 * (1 / (1 - 0.126) - 1), "% High": -2.7})
    rows[15].update(Symbol="PVRINOX", **{"% 50 EMA": 100 * (1 / (1 - 0.138) - 1), "% High": -1.0})
    return pd.DataFrame(rows)


def test_holds_are_ordered_by_least_room_on_one_scale_and_say_which_rule():
    a = assess(_rank_df(), ["LAURUSLABS", "PVRINOX"], Rules())
    assert a["Symbol"].tolist() == ["PVRINOX", "LAURUSLABS"]
    by = a.set_index("Symbol")
    assert nearest_rule(by.loc["PVRINOX"]) == "rank buffer · 24 places"
    assert nearest_rule(by.loc["LAURUSLABS"]) == "50D EMA · 12.6%"
    assert RANK_SCALE == 0.20


def test_the_actions_page_no_longer_says_clear_of_all_three():
    src = (VIEWS / "actions_view.py").read_text(encoding="utf-8")
    assert "clear of all three" not in src and "nearest_rule(" in src


def test_backtest_mtd_is_the_accounts_not_a_weighted_holdings_average():
    src = (VIEWS / "backtest_view.py").read_text(encoding="utf-8")
    assert 'lmeta.get("strategy_mtd")' in src
    assert '"by weight"' not in src


def test_portfolio_drawdown_names_its_basis():
    assert '"Max drawdown, daily"' in (VIEWS / "portfolio_view.py").read_text(encoding="utf-8")


def test_configuration_does_not_report_an_unused_price_file_as_missing():
    src = (VIEWS / "config_view.py").read_text(encoding="utf-8")
    assert '("Price History", PRICES_FILE)' not in src
    assert '"Path": path' not in src


def test_the_guide_claims_no_liquidity_filter_and_no_outcomes():
    src = (VIEWS / "guide_view.py").read_text(encoding="utf-8")
    for phrase in ("liquidity gating", "Liquidity Gating", "Maximises", "minimises maximum",
                   "$w_i", "eliminate"):
        assert phrase not in src, phrase
    assert "No liquidity filter" in src
