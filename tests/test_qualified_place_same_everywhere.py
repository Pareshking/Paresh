"""The Watchlist, the stock page's peers and the Screener give one stock the same
qualified place and the same "Held" mark (S184).

Found 22 Nov 2026 on the live site: the Screener read CUPID as 4th among the
qualified and Held, while the Watchlist read "Out" with no Held mark for every
row, and so did the stock page's peers table. Both drew the Screener's table from
the bare ranking, which has no "Qualified Rank" or "Held" column. A requirements
check could not catch it: the "Qualified #" heading was still on the page.
"""
from __future__ import annotations

import pandas as pd

from src.engine.exit_watch import qualified_ranks
from src.ui.views import stock_view, watchlist_view
from src.ui.views.ranking_view import with_book_columns


def _ranking() -> pd.DataFrame:
    # Ranks 1-8; ranks 2 and 5 fail a filter, so the qualified places are
    # A=1, C=2, D=3, F=4, G=5, H=6 and B, E are out.
    rows = []
    for rank, sym, ema, near in [
        (1, "A", True, True), (2, "B", False, True), (3, "C", True, True),
        (4, "D", True, True), (5, "E", True, False), (6, "F", True, True),
        (7, "G", True, True), (8, "H", True, True),
    ]:
        rows.append({"Rank": rank, "Symbol": sym, "Above 50 EMA": ema,
                     "Near 52W High": near, "Industry": "Auto" if rank % 2 else "IT"})
    return pd.DataFrame(rows)


def test_a_cut_list_keeps_the_place_among_all_the_qualified():
    rank_df = _ranking()
    full = with_book_columns(rank_df, book_symbols=["D", "H"]).set_index("Symbol")
    expected = qualified_ranks(rank_df)
    assert full.loc["D", "Qualified Rank"] == expected["D"] == 3
    assert full.loc["H", "Qualified Rank"] == expected["H"] == 6
    assert pd.isna(full.loc["E", "Qualified Rank"])  # fails a filter: "Out"
    assert bool(full.loc["D", "Held"]) and bool(full.loc["H", "Held"])
    assert not bool(full.loc["A", "Held"])


def _capture(monkeypatch, module) -> list[pd.DataFrame]:
    seen: list[pd.DataFrame] = []
    monkeypatch.setattr(module, "render_screener_table",
                        lambda frame, *a, **k: seen.append(frame.copy()))
    return seen


def test_the_watchlist_reads_the_screeners_place_and_held_mark(monkeypatch):
    rank_df = _ranking()
    seen = _capture(monkeypatch, watchlist_view)
    monkeypatch.setattr(watchlist_view.watchlist_store, "symbols", lambda: ["H", "E", "D"])
    watchlist_view.render_watchlist_view(rank_df, None, book_symbols=["D"])
    assert seen, "the Watchlist drew no table"
    table = seen[-1].set_index("Symbol")
    screener = with_book_columns(rank_df, book_symbols=["D"]).set_index("Symbol")
    for sym in ("H", "E", "D"):
        a, b = table.loc[sym, "Qualified Rank"], screener.loc[sym, "Qualified Rank"]
        assert (pd.isna(a) and pd.isna(b)) or a == b, sym
        assert bool(table.loc[sym, "Held"]) == bool(screener.loc[sym, "Held"]), sym
    assert table.loc["H", "Qualified Rank"] == 6  # not its place within the list


def test_the_stock_pages_peers_read_the_screeners_place(monkeypatch):
    rank_df = _ranking()
    seen = _capture(monkeypatch, stock_view)
    full = with_book_columns(rank_df, book_symbols=["G"])
    row = full.set_index("Symbol").loc["G"].copy()
    row["Symbol"] = "G"
    stock_view._render_peers(row, full)
    assert seen, "the peers table was not drawn"
    peers = seen[-1].set_index("Symbol")
    assert peers.loc["G", "Qualified Rank"] == 5
    assert bool(peers.loc["G", "Held"])


def test_the_stock_page_hands_its_peers_the_book_columns():
    # The page must build the peers from with_book_columns, not the bare ranking.
    import inspect
    src = inspect.getsource(stock_view.render_stock_view)
    assert "with_book_columns(" in src


# ── The stock page's corporate-action note (S184) ────────────────────────────

_MBAPL_LOG = [
    {"date": "2020-11-14", "symbol": "MBAPL", "move": 9.007144, "ratio": 10.007144,
     "looks_like": "10:1 reverse split", "kind": "split/bonus", "source": "yahoo"},
    {"date": "2020-11-17", "symbol": "MBAPL", "move": -0.9, "ratio": 0.1,
     "looks_like": "1:10 split", "kind": "split/bonus", "source": "yahoo"},
]


def _closes(values: list[float]) -> pd.DataFrame:
    days = pd.to_datetime(["2020-11-12", "2020-11-13", "2020-11-16", "2020-11-17", "2020-11-18"])
    return pd.DataFrame({"MBAPL": values}, index=days)


def test_a_logged_step_the_prices_do_not_have_is_not_shown(monkeypatch):
    # NSE's closes for MBAPL: ₹70.00, ₹70.05, ₹70.05 -- no step either day.
    monkeypatch.setattr(stock_view, "load_events", lambda: list(_MBAPL_LOG))
    assert stock_view._applied_events("MBAPL", _closes([70.0, 70.0, 70.05, 70.05, 70.1])) == []


def test_a_step_still_in_the_prices_is_shown(monkeypatch):
    monkeypatch.setattr(stock_view, "load_events", lambda: [_MBAPL_LOG[1]])
    shown = stock_view._applied_events("MBAPL", _closes([70.0, 70.0, 70.05, 7.005, 7.01]))
    assert [e["date"] for e in shown] == ["2020-11-17"]


def test_no_prices_means_no_note(monkeypatch):
    monkeypatch.setattr(stock_view, "load_events", lambda: list(_MBAPL_LOG))
    assert stock_view._applied_events("MBAPL", None) == []
