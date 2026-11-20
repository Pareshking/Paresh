"""Regression tests for Portfolio presentation contracts.

These tests intentionally verify presentation ordering/copy without changing
the canonical accounting calculations.
"""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PORTFOLIO_VIEW = ROOT / "src/ui/views/portfolio_view.py"
THEME = ROOT / "src/ui/theme.py"
PAGE = ROOT / "src/ui/views/portfolio_page.py"


def test_portfolio_holdings_columns_in_the_agreed_order():
    # Mock-up v3, owner approved 20 Nov 2026: a broker's columns, the entry date,
    # and how close each holding is to an exit rule; one table, sortable.
    page = PAGE.read_text(encoding="utf-8")
    block = page[page.index("    cols = [[\"s\", \"Stock\""):page.index("    text = {\"holdings\"")]
    expected = ['"Stock"', '"Industry · size"', '"Entry date"', '"Qty"', '"Entry price"', '"Price"', '"Value"', '"Weight"',
                '"Today"', 'f"P&L from {fill_s}"', '"Since entry"', '"vs 50D EMA"', '"From 52W high"', '"Rank 3M · 1M · now"']
    positions = [block.index(item) for item in expected]
    assert positions == sorted(positions)
    # S111: no column is "shares today x the first entry price", nor a P&L from it.
    assert "Invested Value" not in block and '"P&L %"' not in block
    assert 'Chart("holdings", spec' in PAGE.read_text(encoding="utf-8")


def test_portfolio_copy_avoids_internal_accounting_language_in_primary_sections():
    source = PAGE.read_text(encoding="utf-8")
    assert "current-book unrealised" not in source
    assert "frozen Track Record" not in source
    assert "Historical ending value" not in source


def test_portfolio_table_variant_is_scoped_to_portfolio():
    source = THEME.read_text(encoding="utf-8")
    assert 'variant: str = "default"' in source
    assert 'portfolio_class = "portfolio" if variant == "portfolio" else ""' in source
    assert ".saas-table-wrapper.portfolio" in source


def test_portfolio_sections_in_order_and_the_trade_history_hidden_in_one_place():
    # Owner, 20 Nov 2026: holdings first; "Rebalance and trades are two different
    # sections, why? Can't it be one and hidden?"
    source = PAGE.read_text(encoding="utf-8")
    for fn in ("def page_parts(", "def render("):
        body = source[source.index(fn):]
        calls = ["header(p)", "section_book(p)", "section_exposure(p)", "section_returns(p)", "section_equity(p)",
                 '_head("pf-cal", "Calendar returns"', "day_section(p)", "section_trades_top(p, s)", "section_systems(p)"]
        at = [body.index(c) for c in calls]
        assert at == sorted(at), fn
    assert source.count("st.expander(") == 1 and "Trade history: every trade and every rebalance line" in source


def test_portfolio_pnl_cells_use_explicit_sign_semantics():
    source = THEME.read_text(encoding="utf-8")
    assert 'portfolio_sign_class = "portfolio-pos" if val > 0' in source
    assert 'portfolio-neg' in source
    assert '.saas-table-wrapper.portfolio .portfolio-pos' in source
    assert '.saas-table-wrapper.portfolio .portfolio-neg' in source

def test_portfolio_growth_chart_is_100_at_the_start_with_both_drawdowns():
    # Approved mock-up v3: ₹100 on 1 Jan, the market's drawdown drawn with the book's
    # (owner, 20 Nov: "Showing only portfolio DD, not index benchmark ... overlay ??").
    source = PAGE.read_text(encoding="utf-8")
    spec = source[source.index("def growth_spec("):source.index("def section_equity(")]
    assert '"book": [round(float(v) / base * 100, 2)' in spec and '"ddm":' in spec and '"dd":' in spec


def test_portfolio_monthly_view_is_calendar_grid_with_live_mtd():
    source = PORTFOLIO_VIEW.read_text(encoding="utf-8")
    assert '"monthly_grid": pd.DataFrame(monthly_grid_rows)' in source
    assert '"mtd_period": live_period_key' in source
    assert 'Origin": "Live MTD"' in source
    page = PAGE.read_text(encoding="utf-8")
    cal = page[page.index("def calendar_html("):page.index("def month_bars_spec(")]
    # One row group per year; the month in progress is named as such.
    assert 'so far" if y == this.year' in cal and "pr.calendar(m)" in cal and "pr.financial_years(" in cal


def test_portfolio_header_reports_the_month_so_far_beside_the_market():
    source = PAGE.read_text(encoding="utf-8")
    head = source[source.index("def header("):source.index("NAV = (")]
    assert 'f"Month so far · {this:%b}"' in head and "behind" in head and "Nifty Total Market" in head
    assert "MTD gap" not in source


def test_the_history_builder_carries_the_live_month_for_the_calendar():
    import src.engine.pipeline  # noqa: F401  (pipeline first: see the app's import order)
    from src.ui.views.portfolio_view import build_portfolio_history

    h = build_portfolio_history({}, 2_000_000, {"months": {"2026-08": {"strategy": 0.03, "benchmark": 0.0}}},
                                {"strategy_mtd": 0.027, "benchmark_mtd": -0.054,
                                 "mtd_period": "2026-09", "as_of": "2026-09-30"})
    assert h["strategy_mtd"] == 0.027 and h["benchmark_mtd"] == -0.054
    assert h["mtd_period"] == "2026-09"


def test_a_closed_month_awaiting_freeze_is_not_called_mtd():
    # 1 Oct 2026: the latest close is 30 Sep, so September is finished but the
    # Track Record has not frozen it yet; October has no close.
    import src.engine.pipeline  # noqa: F401
    import pandas as pd

    from src.ui.views.portfolio_view import (
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
    assert _calendar_note(_month_labels("2026-09", "mtd", sep15), "2026-09", "mtd") == ""   # owner: not needed

    ledger = {"months": {"2026-08": {"strategy": 0.03, "benchmark": 0.0}}}
    meta = {"strategy_mtd": 0.027, "benchmark_mtd": -0.054, "mtd_period": "2026-09", "as_of": "2026-09-30"}
    closed = build_portfolio_history({}, 2_000_000, ledger, meta, today=oct1)
    live = build_portfolio_history({}, 2_000_000, ledger, meta, today=sep15)
    assert closed["mtd_state"] == "closed" and live["mtd_state"] == "mtd"
    assert closed["monthly_grid"]["Origin"].iat[-1] == "Closed, awaiting freeze"
    assert live["monthly_grid"]["Origin"].iat[-1] == "Live MTD"
    # Same numbers either way: only the words differ.
    assert closed["equity"].iat[-1] == live["equity"].iat[-1]


def test_actions_explains_a_fill_due_on_the_first_of_the_month():
    import pandas as pd

    from src.ui.views.actions_view import fill_due_note

    sep30, oct1, oct2 = pd.Timestamp("2026-09-30"), pd.Timestamp("2026-10-01"), pd.Timestamp("2026-10-02")
    note = fill_due_note(sep30, oct1, oct1)
    assert "Oct 2026" in note and "30 Sep" in note and "today's closing price" in note
    assert fill_due_note(sep30, oct1, sep30) == ""          # before the fill day
    assert fill_due_note(oct1, oct2, oct2) == ""            # same month: nothing odd


def test_record_caption_and_correlation_card_wording():
    # Owner, 7 Oct 2026: no annualised figure for a record under a year, the
    # drawdown named for what it is; the correlation reading kept (20 Nov).
    record = (PORTFOLIO_VIEW.parent / "track_record_view.py").read_text(encoding="utf-8")
    assert "not a CAGR)" not in record and "worst month-to-month fall" not in record
    assert "largest fall from a peak" in record and "if elapsed >= 1:" in record
    source = PAGE.read_text(encoding="utf-8")
    assert "1.00 = move exactly together" not in source
    assert '"How they move together, 90 sessions"' in source


def test_the_menu_button_is_the_only_navigation_on_every_screen():
    # Owner, 7 Nov 2026: "a hamburger menu only", in the menu's old style.
    components = (ROOT / "src/ui/components.py").read_text(encoding="utf-8")
    theme = THEME.read_text(encoding="utf-8")
    assert "app_toplinks" not in components and "app_toplinks" not in theme
    # Owner, 7 Nov 2026 (audit decision 6): four quick links beside the menu on
    # a desktop, hidden below 1024 px; the menu still lists every page.
    assert '_QUICK_PAGES = ("Dashboard", "Actions", "Screener", "Portfolio")' in components
    assert "@media (max-width: 1023px) { .st-key-app_quicklinks { display: none !important; } }" in theme
    assert 'key=f"app_nav_menu_{_page_slug}"' in components
    assert '[class*="st-key-app_nav_menu_"] { display: none !important; }' not in theme
    # Regrouped by the owner on 7 Nov (audit decision 6's second half).
    for group in ('("My book",', '("Market",', '("Method",'):
        assert group in components


def test_track_record_copy_uses_points_alpha_and_its_own_start():
    source = (ROOT / "src/ui/views/track_record_view.py").read_text(encoding="utf-8")
    # Owner, 12 Oct 2026: "since <start>", not "YTD", which is wrong for a system
    # that started mid-year and for any record longer than one calendar year.
    assert "f\"after costs · since {start.strftime('%b %Y')}\"" in source
    assert '"after costs · YTD"' not in source
    # Alpha in points (owner, 8 Nov 2026, S97 d; replaces 12 Oct's %), through
    # the formatter, never by rewriting a % string.
    assert 'kit.Reading("Ahead of the index", _fmt.pts(stats["alpha"]),' in source
    assert 'replace("%", " pts")' not in source
    assert "Each system starts on its own date" not in source
    assert "A dash means the system had not started yet" not in source


def test_one_word_for_one_thing_across_pages():
    # Owner, 12 Oct 2026: "Max drawdown"; records say Bought / Sold / Held and
    # plans Buy / Sell / Hold; "52W high" and "50D EMA" in labels; the book's
    # columns as on Portfolio; "Nifty 500", not "NIFTY 500", on the page.
    views = ROOT / "src/ui/views"
    backtest = (views / "backtest_view.py").read_text(encoding="utf-8")
    assert 'kit.Reading("Max drawdown"' in backtest and '"Worst fall"' not in backtest
    assert 'kit.Reading("Ahead of the index"' in backtest
    assert '["All", "Buy", "Sell", "Hold"]' in backtest and '"🟢 BOUGHT", "🔴 SOLD"' not in backtest
    assert "Portfolio risk" not in backtest and "Filter " not in backtest
    theme = THEME.read_text(encoding="utf-8")
    # The words are the owner's (12 Oct); the emoji went with audit F46 (7 Nov).
    assert ">Bought<" in theme and ">Sold<" in theme and ">Held<" in theme
    assert "🟢 Bought" not in theme and "🔴 Sold" not in theme
    assert "🟢 BUY</span>" not in theme
    assert 'f"NIFTY 500 ' not in PORTFOLIO_VIEW.read_text(encoding="utf-8")
    assert ">NIFTY 500<" not in (ROOT / "src/ui/components.py").read_text(encoding="utf-8")
    stock = (views / "stock_view.py").read_text(encoding="utf-8")
    assert "52W High</" not in stock and "vs 50 EMA" not in stock
    assert "Momentum Signal" not in (ROOT / "app.py").read_text(encoding="utf-8")


def test_backtest_alpha_is_in_points_like_track_record():
    # Owner, 12 Oct 2026: the Backtest headline alpha reads as Track Record's
    # does; 8 Nov 2026 (S97 d): both in points.
    source = (ROOT / "src/ui/views/backtest_view.py").read_text(encoding="utf-8")
    assert "_fmt.pts(stats['alpha'])" in source
    assert "_fmt.pct(stats['alpha'])" not in source


def test_production_qa_does_not_wait_for_the_removed_live_month_note():
    # #397 removed "is live month-to-date"; V1 Production QA still required it
    # and failed on ecf5878. A running month is evidenced by the Equity tiles.
    qa = (ROOT / "scripts/portfolio_production_qa.py").read_text(encoding="utf-8")
    assert '"is live month-to-date"' not in qa
    assert '"calendar_live_month_marked": bool(re.search(' in qa


def test_header_tiles_say_which_return_is_the_account():
    # Owner, 14 Nov 2026: the account tile is the portfolio's; owner, 20 Nov: "add
    # the uninvested line" under it, so holdings + not invested = the value.
    import pandas as pd

    from src.ui.views.portfolio_view import _month_labels, tile_labels

    nov13 = pd.Timestamp("2026-11-13")
    tiles = tile_labels("2026-11-02", _month_labels("2026-11", "mtd", nov13)["prefix"])
    assert tiles["holdings"] == "Holdings since 2 Nov"
    assert "before costs" in tiles["holdings_note"]
    source = PAGE.read_text(encoding="utf-8")
    head = source[source.index("def header("):source.index("NAV = (")]
    assert '"Portfolio value"' in head and 'not invested"' in head and '"Since inception, after costs"' in head
    assert '"Since last rebalance"' not in head and '"MTD return"' not in head


def test_production_qa_waits_for_the_month_tiles_not_only_the_headings(monkeypatch):
    # Run 44114529502 (17 Nov 2026): the desktop read came at 1,570 characters,
    # headings drawn and the Equity tiles not yet; the phone passed seconds later.
    import importlib.util
    import sys
    import types

    # The script imports Playwright and its sibling probe at load; neither is needed here.
    sync_api = types.ModuleType("playwright.sync_api")
    sync_api.sync_playwright = None
    monkeypatch.setitem(sys.modules, "playwright", types.ModuleType("playwright"))
    monkeypatch.setitem(sys.modules, "playwright.sync_api", sync_api)
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("pqa", ROOT / "scripts/portfolio_production_qa.py")
    pqa = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pqa)
    reads = iter(["Month so far · Nov  Calendar returns",
                  # Run 44116558226: the page still streaming, the footer not yet drawn.
                  "Month so far · Nov  Equity, drawdown & risk  Calendar returns",
                  "Month so far · Nov  Equity, drawdown & risk  Calendar returns  Three systems  Data to 19 Nov 2026."])

    class Loc:
        def __init__(self, sel):
            self.sel = sel

        def inner_text(self, timeout=None):
            return next(reads)

        def count(self):
            return 0

    class Frame:
        def locator(self, sel):
            return Loc(sel)

    monkeypatch.setattr(pqa, "app_frame", lambda page: Frame())
    monkeypatch.setattr(pqa.time, "sleep", lambda s: None)
    text = pqa.settle_view(object(), "calendar returns", also=pqa.MONTH_TILE)
    assert "Data to 19 Nov" in text and "Month so far · Nov" in text
