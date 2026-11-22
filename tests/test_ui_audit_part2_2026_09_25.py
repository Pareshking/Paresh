"""Regressions from the line-by-line UI audit, part 2 (2026-09-25)."""

import numpy as np
import pandas as pd

from src.engine.momentum import CARRIED_MARK
from src.ui import components, screener_table
from src.ui.views import market_view, stock_view


def _capture(monkeypatch, module):
    out = []
    monkeypatch.setattr(module.st, "markdown", lambda h, **k: out.append(str(h)))
    monkeypatch.setattr(module.st, "html", lambda h, **k: out.append(str(h)))
    return out


def test_stock_page_index_badges_are_exact_tags():
    """MID150/SMALL250/MICRO250/NN50 all contain "50"; they each wore "N50". The kicker reads exact tags."""
    from src.ui import stock_lines as sl
    row = pd.Series({"Symbol": "ABC", "Rank": 5, "Indices": "MID150", "Industry": "IT"})
    parts = sl.kicker(row, stock_view.INDEX_NAMES)
    assert "Midcap 150" in parts and "Nifty 50" not in parts


def test_rank_path_reads_oldest_to_now():
    from src.ui import stock_lines as sl
    from src.ui import watchlist_lines as wl
    row = pd.Series({"Symbol": "ABC", "Rank": 1, "Rank (-1M)": 2, "Rank (-3M)": 6})
    days = [pd.Timestamp("2026-08-20"), pd.Timestamp("2026-10-19"), pd.Timestamp("2026-11-20")]
    tr = sl.trail(row, days, [5, 2], 1)
    page = "".join(stock_view.rank_html(row, sl.Universe("750", 750), 1, 290, wl.Lines(20, 40, 20), tr))
    body = page[page.index("<tbody>"):]
    assert body.index(">6<") < body.index(">2<") < body.index(">1<")
    assert page.index("3M ago") < page.index("1M ago") < page.index("Now")


def _peers_html(rank_df, sym):
    """The industry table, as the stock page draws it."""
    from src.ui import stock_lines as sl
    from src.ui.views.ranking_view import with_book_columns
    full = with_book_columns(rank_df)
    row = full[full["Symbol"] == sym].iloc[0]
    shown, in_ind = sl.peers(full, row)
    return "".join(stock_view.industry_html(row, shown, in_ind, pd.Timestamp("2026-11-20")))


def test_peers_table_formats_float32_prices():
    rank_df = pd.DataFrame({"Symbol": ["AAA", "BBB"], "Rank": [1, 2], "Industry": ["IT", "IT"],
                            "CMP": np.array([1234.5677, 99.0], dtype="float32")})
    html = _peers_html(rank_df, "AAA")
    # Whole rupees (owner, 22 Nov 2026, S173; paise 7-22 Nov, F66).
    assert ">₹1,235<" in html and "1234.5" not in html


def test_peers_tag_this_stock_even_below_the_top_eight():
    """Eight rows, this stock's among them and marked."""
    from src.ui import stock_lines as sl
    n = 12
    rank_df = pd.DataFrame({"Symbol": [f"S{i}" for i in range(n)], "Rank": range(1, n + 1),
                            "Industry": ["IT"] * n, "CMP": [100.0] * n})
    html = _peers_html(rank_df, "S11")
    assert html.count("<tr class=") == sl.PEERS_SHOWN
    assert '<tr class="me">' in html and "this stock" in html
    assert ">S0<" in html


def test_ranking_row_float32_nan_drawdown_is_a_dash():
    row = {"Symbol": "YNG", "Rank": 9, "CMP": 100.0,
           "Max DD 12M": np.float32("nan"), "12M Return": np.nan}
    html = screener_table._row_html(row, screener_table.columns_for("Core"), {})
    assert "nan" not in html.lower()


def test_gap_count_sees_a_gap_that_also_carries_the_mark():
    df = pd.DataFrame({"Data Gap": ["🔴", "🔴" + CARRIED_MARK, "", CARRIED_MARK]})
    assert components.gap_count(df) == 2


def test_breadth_by_index_matches_exact_tags():
    df = pd.DataFrame({"Symbol": ["A", "B", "C", "D"],
                       "Indices": ["N50", "NN50", "MID150", "SMALL250,MICRO250"]})
    assert market_view.index_members(df, "NIFTY 50") == ["A"]
    assert market_view.index_members(df, "NIFTY NEXT 50") == ["B"]
    assert market_view.index_members(df, "NIFTY MIDCAP 150") == ["C"]
    assert market_view.index_members(df, "NIFTY MICROCAP 250") == ["D"]

