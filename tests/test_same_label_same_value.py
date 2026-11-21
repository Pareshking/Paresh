"""The same label gives the same value on Dashboard, Portfolio and Actions (S154 (b), 20 Nov 2026).

Checked on 20 Nov's data before the Actions redesign: for all 20 holdings the qualified
rank, the distance from the 50D EMA and from the 52W high, and the return since entry
agreed on all three pages, and the price-history rank matched the published ranking on
all 284 qualified stocks. These tests keep the sources single.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.engine import dashboard_insights as di
from src.engine.exit_watch import Rules, assess, qualified_ranks

ROOT = Path(__file__).resolve().parents[1]


def _rank_df():
    return pd.DataFrame({"Symbol": ["A", "B", "C", "D"], "Rank": [1, 2, 3, 4], "Industry": ["X"] * 4,
                         "Above 50 EMA": [True, False, True, True], "Near 52W High": [True, True, True, True],
                         "% 50 EMA": [4.2, -1.5, 2.0, 7.7], "% High": [-3.1, -9.0, -0.4, -12.5]})


def test_the_trail_now_is_the_plans_rank_among_the_qualified():
    px = pd.DataFrame(np.linspace(100, 120, 300)[:, None].repeat(4, 1), columns=list("ABCD"),
                      index=pd.bdate_range("2025-09-01", periods=300))
    snap = pd.DataFrame({"date": [px.index[-1]] * 4, "symbol": list("ABCD"), "rank": [3, 1, 2, np.nan]})
    q = qualified_ranks(_rank_df())          # B fails the EMA filter: A=1, C=2, D=3
    _, trails = di.rank_trails(px, list("ABCD"), snap, now=q)
    assert [trails[s][-1] for s in "ABCD"] == [1, None, 2, 3]


def test_actions_reads_the_ema_and_high_distances_portfolio_shows():
    a = assess(_rank_df(), list("ACD"), Rules()).set_index("Symbol")
    r = _rank_df().set_index("Symbol")
    for s in "ACD":       # Portfolio shows rank_df's "% 50 EMA" and "% High" (portfolio_page.holdings_spec)
        assert a.loc[s, "vs 50 EMA %"] == r.loc[s, "% 50 EMA"]
        assert a.loc[s, "vs 52W high %"] == r.loc[s, "% High"]
    assert int(a.loc["D", "Qualified rank"]) == 3


def test_every_page_passes_the_plans_rank_to_the_trail():
    for page in ("src/ui/views/dashboard_home_view.py", "src/ui/views/portfolio_page.py"):
        text = (ROOT / page).read_text(encoding="utf-8")
        assert "rank_trails(" in text and "now=q" in text, page
    portfolio = (ROOT / "src/ui/views/portfolio_page.py").read_text(encoding="utf-8")
    assert 'r["% 50 EMA"]' in portfolio and 'r["% High"]' in portfolio


def test_volatility_and_beta_are_portfolios_figures_on_the_dashboard():
    # 21 Nov 2026: the Dashboard showed 16.7% and 0.77 under the labels Portfolio used for 22.7% and 1.0.
    home = (ROOT / "src/ui/views/dashboard_home_view.py").read_text(encoding="utf-8")
    assert "pr.risk(eq, market)" in home
    assert "risk.beta" not in home and "risk.vol" not in home


def test_an_index_without_the_pages_session_reads_as_missing_not_yesterday():
    # S148 / S154 (c), 21 Nov 2026: "Indices, 19 Nov" showed Nifty 50's 18 Nov move.
    idx = pd.bdate_range("2026-11-02", "2026-11-19")
    behind = pd.Series(range(len(idx)), index=idx, dtype=float).iloc[:-1]
    assert di.as_of(behind, idx[-1]).empty
    assert di.window_return(di.as_of(behind, idx[-1]), idx[0], idx[-1]) is None
    level = pd.Series(range(1, len(idx) + 1), index=idx, dtype=float)
    assert len(di.as_of(level, idx[-1])) == len(idx)
    home = (ROOT / "src/ui/views/dashboard_home_view.py").read_text(encoding="utf-8")
    page = (ROOT / "src/ui/views/portfolio_page.py").read_text(encoding="utf-8")
    assert "di.as_of(v, idx_end)" in home and "di.as_of(v, end)" in page
