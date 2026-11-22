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


def test_the_stock_pages_peers_read_the_screeners_place():
    from src.ui import stock_lines as sl
    rank_df = _ranking()
    full = with_book_columns(rank_df, book_symbols=["G"])
    row = full.set_index("Symbol").loc["G"].copy()
    row["Symbol"] = "G"
    shown, in_ind = sl.peers(full, row)
    html = "".join(stock_view.industry_html(row, shown, in_ind, pd.Timestamp("2026-11-20")))
    peers = shown.set_index("Symbol")
    assert peers.loc["G", "Qualified Rank"] == 5
    assert bool(peers.loc["G", "Held"])
    assert "5th" in html and "this stock" in html


def test_the_stock_page_hands_its_peers_the_book_columns():
    # The page must build the peers from with_book_columns, not the bare ranking.
    import inspect
    src = inspect.getsource(stock_view.render_stock_view)
    assert "with_book_columns(" in src


# ── The stock page's corporate actions: NSE's own list (S184, STOCK_REQUIREMENTS row 38) ──

def test_the_log_of_large_moves_is_not_read_any_more():
    """MBAPL's +900.7% and −90.0% days of Nov 2020 (Yahoo, in corporate_actions_log.json) are not in
    NSE's closes (₹70.00, ₹70.05, ₹70.05); the page reads NSE's action list only."""
    import inspect
    src = inspect.getsource(stock_view)
    assert "load_events" not in src and "corporate_actions_log" not in src
