"""S193 A4 (owner, 23 Nov 2026: "all pages should have same rank ... rank must come from same
engine for all"). Portfolio ranked its trail on the ranking's own frame, whose gaps are filled only
for the last 400 days, while Dashboard, Actions, Screener and Watchlist used the deep closes: the
3M-ago rank differed by 1 to 5 places for 21 holdings. Every page now passes the same frame."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text()


def _body(name: str) -> str:
    m = re.search(rf"def {name}\(\) -> None:\n(.*?)\n\n\n", APP, re.S)
    assert m, name
    return m.group(1)


def test_every_page_with_a_rank_trail_reads_the_deep_closes():
    assert "render_portfolio_view(prices=deep_adj_close" in _body("_page_portfolio")
    assert "deep_adj_close" in _body("_page_actions")
    assert "history_prices=deep_adj_close" in _body("_page_screener")
    assert "history_prices=deep_adj_close" in _body("_page_watchlist")


def test_no_page_ranks_on_the_rankings_short_frame():
    for page in ("_page_portfolio", "_page_actions", "_page_screener", "_page_watchlist"):
        assert "get_ranked_prices()" not in _body(page), page


def test_portfolio_prints_the_sessions_the_ranks_are_read_on():
    src = (ROOT / "src" / "ui" / "views" / "portfolio_page.py").read_text()
    assert "di.on_or_before(px, d) or d for d in di.trail_dates(p.as_of).values()" in src
