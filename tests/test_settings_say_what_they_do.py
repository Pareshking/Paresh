"""Each setting says where it acts, and acts there (owner, 12 Oct 2026).

The Kite basket read a Portfolio capital input removed on 30 Sep and sized every
basket on Rs 10 lakh against Portfolio's Rs 20 lakh. Configuration said its caps,
volatility target and liquidity floor changed the Portfolio page, which has been
the track record's pinned model book since 30 Sep and reads none of them; the
volatility target was read by nothing at all.
"""

from __future__ import annotations

import inspect
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_the_kite_basket_starts_at_portfolios_capital(monkeypatch):
    from src.core.config import MODEL_BOOK_CAPITAL
    from src.ui import widget_state
    from src.ui.views import actions_view, portfolio_view

    assert portfolio_view.PORTFOLIO_STARTING_CAPITAL == MODEL_BOOK_CAPITAL == 2_000_000
    monkeypatch.setattr(widget_state.st, "session_state", {})
    assert actions_view.kite_capital() == MODEL_BOOK_CAPITAL
    monkeypatch.setattr(widget_state.st, "session_state", {"ac_kite_capital__v": 500_000})
    assert actions_view.kite_capital() == 500_000, "the reader's own capital is kept"
    monkeypatch.setattr(widget_state.st, "session_state", {"ac_kite_capital": 5})
    assert actions_view.kite_capital() == MODEL_BOOK_CAPITAL, "an implausible value falls back"

    source = (ROOT / "src/ui/views/actions_view.py").read_text(encoding="utf-8")
    assert "port_total_capital_input" not in source
    assert "the capital on the Portfolio page" not in source


def test_portfolio_takes_no_configuration_limits():
    from src.ui.views.portfolio_view import render_portfolio_view

    assert list(inspect.signature(render_portfolio_view).parameters) == ["calc", "rank_df"]
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "vol_target" not in app and "cfg_vt" not in app


def test_configuration_says_its_limits_act_on_the_backtest_only():
    from src.ui.views import config_view

    limits = next(s for s in config_view._SECTIONS if s[0] == "cfg-limits")
    assert limits[3] == "the Backtest only"
    assert "track record's own limits" in limits[2]
    source = (ROOT / "src/ui/views/config_view.py").read_text(encoding="utf-8")
    assert "Volatility targeting" not in source.replace("# Volatility targeting was removed", "")
    assert "the Portfolio page holds cash" not in source
    assert "on the Portfolio page today" not in source
    assert '"bt_top_n"' in source and '"port_top_n"' not in source
