"""The Watchlist built from mock-up v1, approved by the owner on 22 Nov 2026 (S182).

docs/WATCHLIST_REQUIREMENTS.md rows 22-26: the reader's stocks grouped by the book's
lines, the next rebalance's word from the one plan Actions shows, why a symbol is not
ranked, and the shared table drawing all of it without changing the Screener's.
"""
from __future__ import annotations

import pandas as pd

from src.engine.actions import plan_rebalance
from src.engine.track_record import TRACK_RECORD_CONFIG
from src.ui import screener_table
from src.ui import watchlist_lines as wl
from src.ui.views.ranking_view import with_book_columns

LN = wl.Lines(buy=2, keep=4, high_gap=20)


def _ranking(n: int = 9, fail=(3, 7)) -> pd.DataFrame:
    """Ranks 1..n; the ranks in `fail` fail the 50D EMA filter."""
    return pd.DataFrame({
        "Rank": range(1, n + 1), "Symbol": [f"S{i}" for i in range(1, n + 1)],
        "Above 50 EMA": [i not in fail for i in range(1, n + 1)], "Near 52W High": True,
        "Industry": [f"I{i}" for i in range(1, n + 1)], "Company Name": [f"Company {i} Limited" for i in range(1, n + 1)],
    })


# ── Row 22: grouped by the book's lines ─────────────────────────────────────

def test_rows_are_grouped_by_the_books_lines_in_rank_order():
    rank_df = _ranking()
    # Qualified places: S1 1, S2 2, S4 3, S5 4, S6 5, S8 6, S9 7; S3 and S7 fail.
    view = with_book_columns(rank_df, ["S2", "S6"])
    mine = view[view["Symbol"].isin(["S9", "S7", "S5", "S1", "S3", "S6", "S2"])].sort_values("Rank")
    table, heads = wl.grouped(mine, None, LN)
    assert list(table["Symbol"]) == ["S1", "S2", "S5", "S6", "S9", "S3", "S7"]
    assert [(h[0], h[1], h[2]) for h in heads] == [
        ("S1", "Top 2 qualified", 2), ("S5", "3rd to 4th qualified", 1),
        ("S6", "Qualified, past the 4th", 2), ("S3", "Fails a filter", 2)]
    notes = dict(zip(table["Symbol"], table["Place Note"]))
    assert notes["S1"] == "1 place inside the top 2; not held"
    assert notes["S2"] == "the 2nd, the last place the book buys"      # held: no "not held"
    assert notes["S5"] == "the 4th, the last place a holding is kept"
    assert notes["S6"] == "1 place past the 4th"
    assert notes["S9"] == "3 places past the 4th"
    assert notes["S3"] == "fails the 50D EMA filter"


def test_the_lines_are_the_records_own():
    ln = wl.lines()
    assert (ln.buy, ln.keep) == (TRACK_RECORD_CONFIG["top_n"], TRACK_RECORD_CONFIG["buffer_n"])
    assert ln.high_gap == round((1 - TRACK_RECORD_CONFIG["high_pct"]) * 100)
    assert wl.group_heading(wl.KEEP, ln)[0] == f"{ln.buy + 1}st to {ln.keep}th qualified"


# ── Row 23: "30 Nov" is the plan Actions shows ──────────────────────────────

def _fake_plan(calls):
    def model_plan(book, record, rank_df, adj_close, benchmark_close, system, check):
        calls.append((tuple(book["Symbol"]), system, pd.Timestamp(check), id(rank_df), id(adj_close)))
        return plan_rebalance(rank_df, book["Symbol"].tolist(), top_n=2, buffer_n=4)
    return model_plan


def test_30_nov_is_the_plan_actions_shows_for_the_same_stocks(monkeypatch):
    import src.engine.track_record as tr
    import src.ui.book_series as bs
    import src.ui.canonical_book as cb
    import src.ui.model_plan as mp
    import src.ui.views.portfolio_view as pv
    from src.engine import dashboard_insights as di
    from src.ui.views import actions_page
    from src.ui.views.actions_view import next_rebalance

    rank_df = _ranking()
    prices = pd.DataFrame({s: [100.0, 101.0] for s in rank_df["Symbol"]},
                          index=pd.to_datetime(["2026-11-19", "2026-11-20"]))
    book = pd.DataFrame({"Symbol": ["S2", "S5", "S7"], "Return %": 0.0, "Entry Date": "2026-11-02", "Weight %": 33.3})
    calls: list = []
    monkeypatch.setattr(cb, "current_book", lambda *a, **k: (book, {}))
    monkeypatch.setattr(mp, "model_plan", _fake_plan(calls))
    # What Actions reads besides the plan, left out of this test.
    monkeypatch.setattr(tr, "load_ledger", lambda *a, **k: {})
    monkeypatch.setattr(bs, "book_series", lambda *a, **k: None)
    monkeypatch.setattr(pv, "build_portfolio_history", lambda *a, **k: (_ for _ in ()).throw(ValueError()))
    monkeypatch.setattr(actions_page, "_sizes", lambda *a: {})
    monkeypatch.setattr(actions_page, "_events", lambda *a: ([], ""))
    monkeypatch.setattr(di, "rank_trails", lambda *a, **k: ({}, {}))

    actions = actions_page.gather("Model book", rank_df, prices, None, "750")
    mine = wl.book_plan(rank_df, prices, None, "750")
    assert len(calls) == 2 and calls[0] == calls[1], "the Watchlist planned with other inputs than Actions"
    assert mine.check == actions.check == next_rebalance(pd.Timestamp("2026-11-20"))[0]
    assert mine.fill == actions.fill
    words = {s: mine.word(s) for s in rank_df["Symbol"]}
    for s in actions.buys:
        assert words[s] == wl.BUY
    for s in actions.sells:
        assert words[s] == wl.SELL
    for s in actions.holds:
        assert words[s] == wl.HOLD
    for s in actions.next_in_line:
        assert words[s] == wl.NEXT
    # The case is not empty: S7 fails a filter and is sold, S5 (4th) is kept to the line.
    assert actions.sells == ["S7"] and set(actions.holds) == {"S2", "S5"} and actions.next_in_line
    assert words["S9"] == wl.MISSING


def test_the_column_header_is_the_next_rebalance_day():
    plan = wl.BookPlan(pd.Timestamp("2026-11-20"), pd.Timestamp("2026-11-30"), pd.Timestamp("2026-12-01"),
                       sells=["S2"], buys=["S1"], holds=[], next_in_line=["S4"], book=["S2"])
    view = with_book_columns(_ranking(), ["S2"])
    table, heads = wl.grouped(view[view["Symbol"].isin(["S1", "S2", "S4"])], plan, LN)
    doc = screener_table.table_html(table, None, "Watchlist", groups=heads, plan_label=wl.fmt_day(plan.check))
    assert ">30 Nov<" in doc and 'class="c-plan pos" data-v="Buy"' in doc and 'class="c-plan neg" data-v="Sell"' in doc
    assert "Next in line" in doc
    assert doc.count('<tr class="gh">') == len(heads)
    assert wl.plan_sentence(table, plan) == ("If today's prices hold, on Mon 30 Nov the model book buys S1 "
                                             "and sells S2; S4 is next in line.")


# ── Row 24: why a symbol is not ranked ──────────────────────────────────────

def test_not_ranked_says_why_and_where():
    rank_df = _ranking()
    changes = pd.DataFrame({"old": ["OLDCO", "S9X"], "new": ["S4", "GONE"],
                            "date": pd.to_datetime(["2025-10-24", "2020-01-01"])})
    others = {"> ₹2,000 Cr": pd.DataFrame({"Symbol": ["NANO1", "X"], "Rank": [1, 2]})}
    rows = wl.not_ranked(["S1", "OLDCO", "NANO1", "NEWCO", "LISTEDCO", "ZZZ"], rank_df, universe="Nifty 750",
                         members=["NEWCO"], changes=changes, listed={"LISTEDCO", "S4"}, others=others, ln=LN)
    by = {r.symbol: r for r in rows}
    assert "S1" not in by                                   # ranked: not listed here
    assert by["OLDCO"].kind == wl.RENAMED and by["OLDCO"].replace_with == "S4"
    assert by["OLDCO"].why == "NSE changed the symbol to S4 (Company 4) on 24 Oct 2025."
    assert by["OLDCO"].where == "S4 ranks 4th of the 9 and is 3rd among the qualified."
    assert by["NANO1"].kind == wl.ELSEWHERE and by["NANO1"].where == "Ranks 1st of 2 in > ₹2,000 Cr."
    assert by["NANO1"].why == "Not a member of the Nifty 750."
    assert by["NEWCO"].kind == wl.TOO_NEW
    assert by["LISTEDCO"].kind == wl.LISTED
    assert by["ZZZ"].kind == wl.UNKNOWN
    assert wl.not_ranked_heading(rows, "Nifty 750") == (
        "5 of your symbols are not in the Nifty 750: one was renamed, one is too new to rank, "
        "one is in no system's list, one is not a known symbol, one is in > ₹2,000 Cr.")


def test_a_symbol_listed_today_is_never_called_renamed():
    rank_df = _ranking()
    changes = pd.DataFrame({"old": ["REUSED"], "new": ["S4"], "date": pd.to_datetime(["2010-01-01"])})
    rows = wl.not_ranked(["REUSED"], rank_df, universe="Nifty 750", changes=changes, listed={"REUSED"}, ln=LN)
    assert rows[0].kind == wl.LISTED


def test_a_rename_to_a_symbol_not_ranked_here_offers_no_replacement():
    rows = wl.not_ranked(["OLD"], _ranking(), universe="Combined",
                         changes=pd.DataFrame({"old": ["OLD"], "new": ["ELSE"], "date": [pd.NaT]}), ln=LN)
    assert rows[0].kind == wl.RENAMED and rows[0].replace_with == ""
    assert rows[0].where == "ELSE is not ranked in Combined either."


# ── The shared table: the Screener's views are unchanged ────────────────────

def test_the_screeners_views_draw_no_watchlist_parts():
    view = with_book_columns(_ranking(), ["S2"])
    for density in ("Executive", "Core", "Full Quant"):
        keys = [c[0] for c in screener_table.columns_for(density, view.columns)]
        assert "plan" not in keys
        doc = screener_table.table_html(view, None, density)
        table = doc.split("</style>")[1]          # the markup, not the shared stylesheet
        assert 'class="gh"' not in table and "c-plan" not in table and "pnote" not in table
        assert "grouped" not in table.split("<tbody>")[0]
        assert "tr:not(.gh)" not in doc           # the phone's column rule is the Screener's own
    # The 20th and 40th still carry the Screener's line names in rank order.
    big = with_book_columns(_ranking(45, fail=()), [])
    doc = screener_table.table_html(big, None, "Core")
    assert "The book buys to here: the 20th qualified" in doc
    assert "A holding is kept to here: the 40th qualified" in doc


def test_the_systems_own_index_tags_are_named():
    view = with_book_columns(_ranking(2, fail=()), [])
    view["Indices"] = ["NANO", "NANO250"]
    table, heads = wl.grouped(view, None, LN)
    doc = screener_table.table_html(table, None, "Watchlist", groups=heads)
    assert ">NANO<" not in doc and ">NANO250<" not in doc
    assert "&gt; ₹2,000 Cr" in doc and ">Nifty 1000<" in doc


def test_formatting_goes_through_one_set_of_helpers():
    assert wl.fmt_date("2026-11-20") == "20 Nov 2026"
    assert wl.fmt_weekday("2026-11-30") == "Mon 30 Nov"
    assert [wl.fmt_ordinal(n) for n in (1, 2, 3, 11, 12, 13, 21, 697)] == [
        "1st", "2nd", "3rd", "11th", "12th", "13th", "21st", "697th"]
    assert wl.fmt_system("Nifty 750") == "the Nifty 750" and wl.fmt_system("> ₹2,000 Cr") == "> ₹2,000 Cr"
    assert wl.MISSING == "–"


def test_dates_and_dash_are_the_shared_formatters():
    """S173: the page writes dates and missing values through src/ui/formats.py, not its own copy."""
    from src.ui import formats
    for d in ("2026-11-20", "2026-01-05"):
        assert wl.fmt_date(d) == formats.date(pd.Timestamp(d))
        assert wl.fmt_day(d) == formats.date(pd.Timestamp(d), short=True)
    assert wl.MISSING is formats.DASH and wl.MINUS is formats.MINUS


def test_the_foot_names_the_data_date_once():
    """Row 28 / S173 rule 7: one "Data to <date> · NSE" line. The page writes its own foot line, so it must
    not also hand the date to the shared footer (both printed it on 22 Nov, one line apart)."""
    from src.ui import formats
    from src.ui.views import watchlist_view as wv

    ranking = _ranking()
    foot = wv._foot(pd.Timestamp("2026-11-20"), ["S1", "S2", "ZZZ"], ranking[ranking["Symbol"].isin(["S1", "S2"])], ranking)
    assert foot.startswith(formats.data_to(pd.Timestamp("2026-11-20")) + ".")
    assert foot.count("Data to") == 1 and "2 of your 3 symbols ranked among the 9" in foot
    # That the view does not also hand the date to the shared footer: test_launch_slot_10_leftovers.
