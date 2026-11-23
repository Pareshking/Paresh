"""S193 item A #1 (23 Nov 2026): the stock page under ?sys=nano said SANSERA was
"in none of the systems' lists" while the 750 ranked it 12th. The stock page now
gets the other systems' rankings and this system's members, as the Watchlist does."""
import pandas as pd

from src.engine.extra_universe import SYSTEM_750, SYSTEM_NAMES, SYSTEM_NANO
from src.ui import stock_lines as sl
from src.ui.views import stock_view


def _render(monkeypatch, **kw):
    out = []
    monkeypatch.setattr(stock_view, "_emit", lambda parts: out.extend(parts))
    monkeypatch.setattr(stock_view, "_render_actions", lambda *a, **k: None)
    import src.ui.views.watchlist_view as wv
    monkeypatch.setattr(wv, "_nse_lists", lambda: (None, {"SANSERA", "OTHER"}))
    nano = pd.DataFrame({"Symbol": ["AAA", "BBB"], "Rank": [1, 2]})
    stock_view._render_not_ranked("SANSERA", nano, sl.universe(SYSTEM_NANO, 2), pd.Timestamp("2026-11-20"),
                                  None, **kw)
    return " ".join(out)


def test_a_stock_another_system_ranks_says_where(monkeypatch):
    r750 = pd.DataFrame({"Symbol": [f"S{i}" for i in range(11)] + ["SANSERA"], "Rank": range(1, 13)})
    text = _render(monkeypatch, other_rankings=lambda: {SYSTEM_NAMES[SYSTEM_750]: r750})
    assert "none of the systems" not in text
    assert "Ranks 12th of 12" in text
    assert "screener?stock=SANSERA" in text  # the link opens it under the 750


def test_a_member_too_new_to_rank_says_so(monkeypatch):
    text = _render(monkeypatch, members=["SANSERA"], other_rankings={})
    assert "too new to rank" in text


def test_a_failing_lookup_of_other_systems_does_not_break_the_page(monkeypatch):
    def boom():
        raise RuntimeError("R2 down")
    text = _render(monkeypatch, other_rankings=boom)
    assert "none of the systems" in text
