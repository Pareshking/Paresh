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
        '"Company"',
        '"Sector / Industry"',
        '"Current Price"',
        '"P&L (₹)"',
        '"P&L %"',
        '"Weight %"',
        '"Target Weight %"',
        '"Weight Drift %"',
        '"Day P&L (₹)"',
    ]
    positions = [block.index(item) for item in expected]
    assert positions == sorted(positions)
    assert 'render_saas_table(current_view, max_height=620, variant="portfolio")' in source


def test_portfolio_copy_avoids_internal_accounting_language_in_primary_sections():
    source = PORTFOLIO_VIEW.read_text(encoding="utf-8")
    primary = source[source.index('head = kit.page_head'):source.index('display_cols = [')]
    assert "current-book unrealised" not in primary
    assert "frozen Track Record" not in primary
    assert "Historical ending value" not in source
    assert "current month-to-date" in source


def test_portfolio_table_variant_is_scoped_to_portfolio():
    source = THEME.read_text(encoding="utf-8")
    assert 'variant: str = "default"' in source
    assert 'portfolio_class = "portfolio" if variant == "portfolio" else ""' in source
    assert ".saas-table-wrapper.portfolio" in source


def test_portfolio_history_is_grouped_into_performance_and_activity():
    source = PORTFOLIO_VIEW.read_text(encoding="utf-8")
    assert '["Performance", "Activity"]' in source
    assert '["Overview", "Equity", "Drawdown", "Monthly"]' in source
    assert '["Trades", "Rebalances"]' in source
    assert 'Latest portfolio activity' not in source


def test_portfolio_pnl_cells_use_explicit_sign_semantics():
    source = THEME.read_text(encoding="utf-8")
    assert 'portfolio_sign_class = "portfolio-pos" if val > 0' in source
    assert 'portfolio-neg' in source
    assert '.saas-table-wrapper.portfolio .portfolio-pos' in source
    assert '.saas-table-wrapper.portfolio .portfolio-neg' in source
