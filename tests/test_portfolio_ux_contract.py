"""Regression tests for Portfolio presentation contracts.

These tests intentionally verify presentation ordering/copy without changing
the canonical accounting calculations.
"""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PORTFOLIO_VIEW = ROOT / "src/ui/views/portfolio_view.py"
THEME = ROOT / "src/ui/theme.py"


def test_portfolio_primary_columns_are_first_and_single_table_is_preserved():
    source = PORTFOLIO_VIEW.read_text(encoding="utf-8")
    start = source.index('    display_cols = [')
    end = source.index('    ]', start) + 6
    block = source[start:end]

    expected = [
        '"Symbol"',
        '"Current Price"',
        '"P&L %"',
        '"P&L (₹)"',
        '"Weight %"',
        '"Target Weight %"',
        '"Weight Drift %"',
        '"Day P&L (₹)"',
        '"Sector / Industry"',
    ]
    # Company is not a column (the symbol is enough, and on a phone it pushed
    # price and P&L off screen); Status was always "Held"; 3M/6M/12M returns
    # belong to the screener.
    for dropped in ('"Company"', '"Status"', '"3M Return"', '"6M Return"', '"12M Return"'):
        assert dropped not in block
    positions = [block.index(item) for item in expected]
    assert positions == sorted(positions)
    assert 'render_saas_table(current_view, max_height=620, variant="portfolio")' in source


def test_portfolio_copy_avoids_internal_accounting_language_in_primary_sections():
    source = PORTFOLIO_VIEW.read_text(encoding="utf-8")
    primary = source[source.index('kit.page_head('):source.index('display_cols = [')]
    assert "current-book unrealised" not in primary
    assert "frozen Track Record" not in primary
    assert "Historical ending value" not in source


def test_portfolio_table_variant_is_scoped_to_portfolio():
    source = THEME.read_text(encoding="utf-8")
    assert 'variant: str = "default"' in source
    assert 'portfolio_class = "portfolio" if variant == "portfolio" else ""' in source
    assert ".saas-table-wrapper.portfolio" in source


def test_portfolio_is_one_flowing_page_with_no_history_tabs():
    source = PORTFOLIO_VIEW.read_text(encoding="utf-8")
    assert "history_tab" not in source and "segmented_control" not in source
    for card in ("Equity & drawdown", "Calendar returns", "Trades", "Rebalances", "Industry exposure"):
        assert f'kit.card("{card}"' in source
    # Equity and drawdown share one card, so one tab fewer.
    assert source.index("kit.equity_chart(") < source.index("kit.drawdown_chart(")
    assert 'Latest portfolio activity' not in source


def test_portfolio_pnl_cells_use_explicit_sign_semantics():
    source = THEME.read_text(encoding="utf-8")
    assert 'portfolio_sign_class = "portfolio-pos" if val > 0' in source
    assert 'portfolio-neg' in source
    assert '.saas-table-wrapper.portfolio .portfolio-pos' in source
    assert '.saas-table-wrapper.portfolio .portfolio-neg' in source

def test_portfolio_equity_chart_uses_absolute_values_without_growth_factor_scaling():
    # Guard the chart contract against accidental 100x factor formatting.
    page_kit = (ROOT / "src/ui/page_kit.py").read_text(encoding="utf-8")
    portfolio = PORTFOLIO_VIEW.read_text(encoding="utf-8")
    assert "def equity_chart(" in page_kit
    assert "v * 100" not in page_kit
    assert "kit.equity_chart(" in portfolio
    assert "kit.growth_chart(" not in portfolio
    assert '"value": float(v)' in page_kit

def test_portfolio_monthly_view_is_calendar_grid_with_live_mtd():
    source = PORTFOLIO_VIEW.read_text(encoding="utf-8")
    assert "def _calendar_grid_html(" in source
    assert '"monthly_grid": pd.DataFrame(monthly_grid_rows)' in source
    assert '"mtd_period": live_period_key' in source
    assert 'Origin": "Live MTD"' in source
    assert "Quarters are calendar (Q1 = Jan–Mar); FY runs Apr–Mar." in source
    assert "is live month-to-date." in source


def test_portfolio_equity_card_reports_the_marked_month_not_cumulative_return():
    source = PORTFOLIO_VIEW.read_text(encoding="utf-8")
    equity = source[source.index('kit.card("Equity & drawdown"'):source.index('kit.card("Calendar returns"')]
    assert 'labels["prefix"].split(" ")[0]' in equity
    assert 'f"{month} strategy"' in equity and 'f"{month} Nifty 500"' in equity
    assert 'f"{month} alpha"' in equity
    assert "MTD gap" not in source
    assert 'st.metric("Since inception", f"{historical_return:+.1%}"' not in equity


def test_calendar_grid_renders_from_the_real_history_builder():
    # Rendered, not grepped: the grid read "Strategy Net" off itertuples()
    # rows, which rename spaced columns, and every Monthly view raised
    # KeyError in production (1 Oct 2026) while the source-text tests passed.
    # pipeline first: src.engine.momentum and src.engine.pipeline import each
    # other, and only this order resolves (the app's own order).
    import src.engine.pipeline  # noqa: F401
    from src.ui.views.portfolio_view import _calendar_grid_html, build_portfolio_history

    ledger = {"months": {
        "2026-01": {"strategy": 0.10, "benchmark": -0.02, "origin": "recorded"},
        "2026-02": {"strategy": -0.05, "benchmark": 0.01},
        "2026-08": {"strategy": 0.03, "benchmark": 0.00},
    }}
    meta = {"strategy_mtd": 0.027, "benchmark_mtd": -0.054, "mtd_period": "2026-09", "as_of": "2026-09-30"}
    h = build_portfolio_history({}, 2_000_000, ledger, meta)
    html = _calendar_grid_html(h["monthly_grid"], h["mtd_period"])
    assert html.count('class="pcg-mtd">MTD<') == 1          # the live September cell only
    assert "+10.0%" in html and "+2.7%" in html
    assert "Alpha +8.1%" in html and "Δ" not in html          # 2.7% − (−5.4%)
    assert h["strategy_mtd"] == 0.027 and h["benchmark_mtd"] == -0.054


def test_a_closed_month_awaiting_freeze_is_not_called_mtd():
    # 1 Oct 2026: the latest close is 30 Sep, so September is finished but the
    # Track Record has not frozen it yet; October has no close.
    import src.engine.pipeline  # noqa: F401
    import pandas as pd

    from src.ui.views.portfolio_view import (
        _calendar_grid_html,
        _calendar_note,
        _month_labels,
        build_portfolio_history,
        live_month_state,
    )

    sep30, oct1, sep15 = pd.Timestamp("2026-09-30"), pd.Timestamp("2026-10-01"), pd.Timestamp("2026-09-15")
    assert live_month_state("2026-09", oct1) == "closed"
    assert live_month_state("2026-09", sep30) == "mtd" and live_month_state("2026-09", sep15) == "mtd"
    assert live_month_state("2026-10", oct1) == "mtd"
    assert live_month_state(None, oct1) == "none"

    labels = _month_labels("2026-09", "closed", oct1)
    assert labels == {"prefix": "Sep (closed)", "badge": "CLOSED", "next": "Oct MTD"}
    assert _month_labels("2026-09", "mtd", sep15)["prefix"] == "Sep MTD"
    assert "closed, not yet frozen" in _calendar_note(labels, "2026-09", "closed")
    assert "live month-to-date" in _calendar_note(_month_labels("2026-09", "mtd", sep15), "2026-09", "mtd")

    ledger = {"months": {"2026-08": {"strategy": 0.03, "benchmark": 0.0}}}
    meta = {"strategy_mtd": 0.027, "benchmark_mtd": -0.054, "mtd_period": "2026-09", "as_of": "2026-09-30"}
    closed = build_portfolio_history({}, 2_000_000, ledger, meta, today=oct1)
    live = build_portfolio_history({}, 2_000_000, ledger, meta, today=sep15)
    assert closed["mtd_state"] == "closed" and live["mtd_state"] == "mtd"
    assert closed["monthly_grid"]["Origin"].iat[-1] == "Closed, awaiting freeze"
    assert live["monthly_grid"]["Origin"].iat[-1] == "Live MTD"
    # Same numbers either way: only the words differ.
    assert closed["equity"].iat[-1] == live["equity"].iat[-1]
    html = _calendar_grid_html(closed["monthly_grid"], "2026-09", "closed")
    assert html.count(">CLOSED<") == 1 and ">MTD<" not in html
    assert _calendar_grid_html(live["monthly_grid"], "2026-09", "mtd").count(">MTD<") == 1


def test_actions_explains_a_fill_due_on_the_first_of_the_month():
    import pandas as pd

    from src.ui.views.actions_view import fill_due_note

    sep30, oct1, oct2 = pd.Timestamp("2026-09-30"), pd.Timestamp("2026-10-01"), pd.Timestamp("2026-10-02")
    note = fill_due_note(sep30, oct1, oct1)
    assert "Oct 2026" in note and "30 Sep" in note and "today's closing price" in note
    assert fill_due_note(sep30, oct1, sep30) == ""          # before the fill day
    assert fill_due_note(oct1, oct2, oct2) == ""            # same month: nothing odd
