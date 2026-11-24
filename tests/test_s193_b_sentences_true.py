"""S193 item B (23 Nov 2026): sentences whose number came from a code fault, fixed by rule.

Report: docs/archive/S193_ITEM_B_2026-11-23.md, section 1 (B1-B9). Each test names the page text it
read wrong on 20 Nov 2026 prices.
"""
from __future__ import annotations

import ast
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def test_b1_every_cached_function_hashes_an_argument():
    # Streamlit does not hash an argument named "_x". _chart_series(_key, _prices, ...) hashed only `pit`,
    # so the 1000 and the list shared one Market chart for an hour ("54% to 45%" on both).
    bad = []
    for path in (ROOT / "src").rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.FunctionDef):
                continue
            if not any("cache_data" in ast.unparse(d) or "cache_resource" in ast.unparse(d) for d in node.decorator_list):
                continue
            args = [a.arg for a in node.args.args + node.args.kwonlyargs]
            if args and not any(not a.startswith("_") for a in args):
                bad.append(f"{path.relative_to(ROOT)}:{node.lineno} {node.name}")
            if any(a.startswith("_") and "key" in a for a in args):
                bad.append(f"{path.relative_to(ROOT)}:{node.lineno} {node.name} (a key Streamlit ignores)")
    for path, name in [("src/ui/views/market_questions_view.py", "_chart_series"),
                       ("src/ui/views/ranking_view.py", "_new_high_counts")]:
        assert f"def {name}(key: str," in (ROOT / path).read_text(encoding="utf-8")
    assert bad == []


def test_b2_b3_the_book_against_the_momentum_indices():
    from src.ui.views.dashboard_home_view import _against_momentum as at
    assert at(5.5, 4.3, 4.56) == "ahead of all of them"        # the 1000 read "level with the best"
    assert at(-2.8, 4.3, 5.7) == "behind all of them"          # the list read "within their range"
    assert at(4.58, 4.3, 4.56) == "level with the best of them"
    assert at(4.4, 4.3, 4.56) == "within their range"


def test_b4_month_end_state_is_the_month_end_reading():
    from src.ui.views.dashboard_home_view import _last_month_end, _month_end_change
    idx = pd.to_datetime(["2026-09-30", "2026-10-30", "2026-11-03", "2026-11-20"])
    gap = pd.Series([2.0, -3.9, 1.0, 1.5], index=idx)         # today above the EMA, 30 Oct below it
    assert _last_month_end(gap, pd.Timestamp("2026-11-20")) == -3.9
    jump = pd.Series([30.0, 46.0, 40.0, 20.0], index=idx)     # +16 pts from 30 Sep to 30 Oct
    assert _month_end_change(jump, pd.Timestamp("2026-11-20"), lambda v, ch: ch >= 15) is True
    src = (ROOT / "src" / "ui" / "views" / "dashboard_home_view.py").read_text(encoding="utf-8")
    body = src[src.index("def _signals("):src.index("BREADTH_TIER =")]
    assert body.count('row("') == body.count("me_on=") - 1 == 7   # every row states its month-end reading


def test_b5_a_stock_with_no_rank_a_month_ago_entered():
    from src.ui.views.ranking_view import top50_changes
    df = pd.DataFrame({"Symbol": ["A", "B", "C", "D"], "Rank": [1, 2, 60, np.nan], "Rank (-1M)": [70, np.nan, 10, 20]})
    entered, left = top50_changes(df)
    assert list(entered["Symbol"]) == ["A", "B"]               # B: no rank a month ago (MILKYMIST, 20 Nov)
    assert list(left["Symbol"]) == ["C", "D"]                  # D: no rank now


def test_b6_b9_portfolio_labels():
    src = (ROOT / "src" / "ui" / "views" / "portfolio_page.py").read_text(encoding="utf-8")
    assert '_head("pf-exp", "Sector & size", f"now, against the {uni}' not in src   # escaped twice: "&gt;"
    assert '"this book" if sid == system' in src


def test_b7_a_system_with_no_frozen_month_has_a_daily_path_from_the_fill():
    from src.core.config import MODEL_BOOK_CAPITAL
    from src.ui.views.portfolio_view import _from_the_fill
    idx = pd.to_datetime(["2026-10-30", "2026-11-02", "2026-11-03", "2026-11-20"])
    prices = pd.DataFrame({"X": [100.0, 100.0, 110.0, 120.0]}, index=idx)
    table = pd.DataFrame({"Symbol": ["X"], "Shares": [900.0]})
    value = 900 * 120.0 + 5_000.0
    eq, bm = _from_the_fill(table, prices, pd.Timestamp("2026-11-02"), pd.Series([1.0, 2.0, 2.2, 2.4], index=idx), value)
    assert eq.index[0] == pd.Timestamp("2026-10-30") and eq.iloc[0] == float(MODEL_BOOK_CAPITAL)   # the money put in
    assert eq.index[-1] == pd.Timestamp("2026-11-20") and eq.iloc[-1] == value                     # never 30 Nov
    assert round(bm.loc["2026-11-20"] / bm.loc["2026-11-02"], 6) == 1.2                            # rebased at the fill


# ── Owner, 23 Nov 2026: "Fix, I am with your recommendation" (the Guide, wording per system, small wording) ──

def test_guide_states_what_the_code_does():
    import re
    from src.ui.views import guide_view
    body = re.sub(r"\s+", " ", guide_view._body())
    assert "waits about six months" in body and "about six weeks" not in body          # 63 sessions to rank, 126 for the high
    assert "buy orders only" not in body and "its sells at the model book's share counts" in body
    assert "never above" not in body and "as it stood at the last reset" in body
    assert "except the after-tax rows in the Backtest's section 4" in body
    assert "none is quoted here" not in body and "side by side" not in body
    assert "rights issues and demergers" in body


def test_frozen_months_are_named_only_where_a_system_has_them():
    from src.ui.views.dashboard_home_view import _frozen_span
    assert _frozen_span({"months": {f"2026-{m:02d}": {} for m in range(1, 11)}}) == "January to October"
    assert _frozen_span({"months": {"2026-10": {}}}) == "October"
    assert _frozen_span({}) == ""                                    # the Nifty 1000, Nov 2026


def test_backtest_heading_counts_the_checks_not_made():
    from src.ui.views.backtest_view import trust_headline
    assert trust_headline([("Look-ahead", "", "Checked"), ("b", "", "Not checked"), ("c", "", "Not checked")]) == \
        "Look-ahead is handled; 2 checks are not made (below)."
    assert trust_headline([("Look-ahead", "", "Checked")]) == "Look-ahead is handled."


def test_backtest_trust_headline_follows_the_statuses():
    """S203 bt.tr.4: survivorship marked a soft spot is not called handled."""
    import re

    from src.ui.views.backtest_view import trust_headline
    rows = [("Survivorship", "", "Soft spot"), ("Look-ahead", "", "Checked"), ("Costs", "", "Soft spot"),
            ("Tax", "", "Soft spot"), ("Rules chosen after looking", "", "Soft spot"), ("Sector cap", "", "Not checked")]
    assert re.sub(r"<[^>]+>", "", trust_headline(rows)) == (
        "Look-ahead is handled; survivorship, costs, tax and the choice of rules are the soft spots; "
        "1 check is not made (below).")
    rows[0] = ("Survivorship", "", "Checked")
    assert re.sub(r"<[^>]+>", "", trust_headline(rows)).startswith(
        "Survivorship and look-ahead are handled; costs, tax and the choice of rules are the soft spots")


def test_the_list_groups_by_tradingview_sector():
    from src.ui.views import sector_view as sv
    assert sv.tv_sectors("nano") and sv.tv_sectors("combined") and not sv.tv_sectors("750") and not sv.tv_sectors("1000")
    assert list(sv.GROUPINGS_TV) == ["TradingView sector", "TradingView industry"]
    assert sv.TV_ONLY in "".join(sv.section_only_nse(False))
