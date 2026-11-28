"""S203: the Dashboard and Portfolio sentences render their approved templates (owner, 24 Nov 2026).

The templates, by id, are in docs/archive/S203_TEMPLATES_DASHBOARD_PORTFOLIO.md (sections 1 and 2; the owner's
answers in section 6). Each test names the ids it renders, on the cases the archive lists, with fake inputs and
no network. `_clean` fails a sentence with an empty slot, "None", "nan", a "–" inside it, or a doubled word.
"""
from __future__ import annotations

import dataclasses
import re

import pandas as pd
import pytest

from src.engine import dashboard_insights as di
from src.ui import missing_words as mw
from src.ui.views import dashboard_home_view as dv
from src.ui.views import portfolio_page as pp

SYSTEMS = ("750", "1000", "nano")
NOV = pd.Timestamp("2026-11-20")
CHECK = pd.Timestamp("2026-11-30")


def _text(html: str) -> str:
    return re.sub(r"<[^>]+>", "", html)


def _clean(html: str) -> str:
    t = _text(html)
    assert t, "an empty sentence"
    assert not re.search(r"\b(None|nan|NaN|NaT)\b", t), t
    for bad in ("{", "}", " – ", "  ", "..", "the the ", "up −", "down −", "bought −", "sold −"):
        assert bad not in t, (bad, t)
    return t


def _bm(book, market, mom=None):
    mom = {"nifty200_mom30": 4.3, "nifty500_mom50": 5.7} if mom is None else mom
    return di.BookMonth(book_mtd=book, market_mtd=market, book_ytd=None, market_ytd=None, months_ahead=3, months=10,
                        behind_months=["Mar"], momentum_mtd=mom, momentum_ytd={}, ahead_of_momentum=0,
                        level_with_momentum=0)


# ── 1a. Today in brief ──────────────────────────────────────────────────────

@pytest.mark.parametrize("book, market, mom, want", [
    (5.7, 7.0, None, "So far in November, the book is behind Nifty Total Market but level with the best momentum index."),
    (6.5, 7.0, None, "So far in November, the book is behind Nifty Total Market but ahead of every momentum index."),
    (8.0, 7.0, None, "So far in November, the book is ahead of Nifty Total Market."),
    (7.02, 7.0, None, "So far in November, the book is level with Nifty Total Market."),
    (5.0, 7.0, None, "So far in November, the book is behind Nifty Total Market and within the range of NSE’s momentum indices."),
    (1.0, 7.0, None, "So far in November, the book is behind Nifty Total Market and behind all of NSE’s momentum indices."),
])
def test_dash_brief_1(book, market, mom, want):
    assert dv.brief_book(_bm(book, market, mom), "November") == want


def test_dash_brief_1_first_month_and_missing():
    # The 1000's first month runs from its fill; a missing figure leaves the sentence out.
    assert dv.brief_book(_bm(8.0, 7.0), "November", pd.Timestamp("2026-11-02")).startswith("Since the 2 Nov fill, the book")
    assert dv.brief_book(_bm(None, 7.0), "November") == ""
    assert dv.brief_book(_bm(5.0, None), "November") == ""


def _sig(key, like, passed=True, like_me=None):
    return {"key": key, "like": like, "like_me": like_me, "test": {"passed": passed}}


@pytest.mark.parametrize("system", SYSTEMS)
def test_dash_brief_2_3_4(system):
    uni = dv.UNIVERSE_SHORT[system]
    sigs = [_sig("fpi", 1.0), _sig("trend_fast", 0.9), _sig("breadth_thin", -1.0), _sig("rebound", None, passed=False)]
    flows = type("F", (), {"month_rank": 1})()
    html = dv._brief(_bm(8.0, 7.0), 1, CHECK, sigs, 0.5, {"beat_share": [31.0]}, flows, "November", uni)
    t = _clean(html.split('<nav')[0])
    assert "1 holding would be sold at the 30 Nov check." in t                                     # brief.2
    assert ("3 of our tested signals pass. On today’s readings, 2 point to a stronger month for momentum and 1 to a "
            "weaker one. Record foreign buying is one of them.") in t                               # brief.3
    assert f"The rally is narrow: only 31% of the {uni} beat Nifty Total Market over the past month." in t   # brief.4
    two = _text(dv._brief(_bm(8.0, 7.0), 2, CHECK, [_sig("fpi", 1.0)], 0.5, None, type("F", (), {"month_rank": 4})()))
    assert "2 holdings would be sold" in two and "1 of our tested signals passes" in two
    assert "1 points to a stronger month for momentum and none to a weaker one. Heavy foreign buying is one of them." in two
    assert "would be sold" not in _text(dv._brief(_bm(8.0, 7.0), 0, CHECK, [], None, {"beat_share": [55.0]}))
    assert "narrow" not in _text(dv._brief(_bm(8.0, 7.0), 0, CHECK, [], None, {"beat_share": [55.0]}))


# ── 1b. Section 1, the book this month ──────────────────────────────────────

def _book_html(bm, fill=None, late=""):
    return dv.html_of(dv.section_book(bm, 12.0, 8.0, NOV, fill=fill, late=late))


@pytest.mark.parametrize("book, market, mom, h1, lede", [
    (5.7, 7.0, None, "The book trails Nifty Total Market in November because momentum does, not its stock picks.",
     "Nifty Total Market is up 7.0% so far in November. NSE’s 2 momentum indices are up 4.3% to 5.7%. "
     "The book is up 5.7%, level with the best of them."),
    (8.25, 7.0, None, "The book is 1.3 points ahead of Nifty Total Market so far in November.",
     "The book is up 8.3%, ahead of all of them."),
    (5.0, 7.0, None, "The book is 2.0 points behind Nifty Total Market so far in November.", "within their range."),
    (7.0, 7.0, None, "The book is level with Nifty Total Market so far in November.", "Nifty Total Market is up 7.0%"),
    (-3.0, -1.0, {"nifty200_mom30": -2.1, "nifty500_mom50": -0.5}, "2.0 points behind",
     "Nifty Total Market is down 1.0% so far in November. NSE’s 2 momentum indices are down 0.5% to 2.1%. "
     "The book is down 3.0%, behind all of them."),
    (1.0, 0.0, {"nifty200_mom30": -1.2, "nifty500_mom50": 3.4}, "1.0 points ahead",
     "Nifty Total Market is unchanged so far in November. NSE’s 2 momentum indices range from −1.2% to +3.4%."),
    (1.0, 0.5, {"nifty200_mom30": 0.8}, "0.5 points ahead", "Of NSE’s momentum indices, only Nifty200 Momentum 30 has a close: +0.8%."),
])
def test_dash_book_1_to_4(book, market, mom, h1, lede):
    html = _book_html(_bm(book, market, mom))
    title = _clean(re.search(r'<h1[^>]*>(.*?)</h1>', html).group(1))
    assert h1 in title
    assert lede in _clean(re.search(r'<p class="dh-lede">(.*?)</p>', html).group(1))
    assert "What lagged is the style" not in html                                                    # book.5 dropped


def test_dash_book_1_missing_and_first_month():
    assert "Nifty Total Market has no November figure yet" in _book_html(_bm(0.4, None, {}))       # #660, kept
    first = _text(_book_html(_bm(8.0, 7.0), fill=pd.Timestamp("2026-11-02")))                      # the 1000's first month
    assert "1.0 points ahead of Nifty Total Market since the 2 Nov fill." in first
    assert "Nifty Total Market is up 7.0% since the 2 Nov fill." in first


def test_dash_book_6_tile_subs():
    assert "Up 4.3 to 5.7%" in _book_html(_bm(5.0, 7.0))
    assert "Down 0.5 to 2.1%" in _book_html(_bm(-3.0, -1.0, {"nifty200_mom30": -2.1, "nifty500_mom50": -0.5}))
    assert "From −1.2 to +3.4%" in _book_html(_bm(1.0, 0.0, {"nifty200_mom30": -1.2, "nifty500_mom50": 3.4}))
    assert "Level with Nifty Total Market" in _book_html(_bm(7.0, 7.0))
    assert "pts behind Nifty Total Market" in _book_html(_bm(5.0, 7.0))


def test_dash_book_7_and_pf_ret_3_share_one_template():
    d = dv.index_late_note(pd.Timestamp("2026-11-19"), NOV)
    assert d == ("Nifty Total Market to 19 Nov: NSE’s closes for 20 Nov are not in yet, so the index figures end a "
                 "session early; the book’s are to 20 Nov.")
    p = dv.index_late_note(pd.Timestamp("2026-11-19"), NOV, "Nifty Total Market and Momentum 50")
    assert p.startswith(mw.not_in_yet("Nifty Total Market and Momentum 50", "2026-11-19", NOV))
    assert dv.index_late_note(NOV, NOV) == ""


# ── 1c. Section 2, the next rebalance ───────────────────────────────────────

@pytest.mark.parametrize("s, b, w, n, want", [
    (2, 3, 1, 6, "2 sells and 3 buys at the 30 Nov check, 6 sessions away. 1 more holding is on the edge."),
    (0, 2, 0, 6, "No sells and 2 buys at the 30 Nov check, 6 sessions away."),
    (1, 0, 3, 1, "1 sell and no buys at the 30 Nov check, 1 session away. 3 more holdings are on the edge."),
    (0, 0, 0, 4, "No change at the 30 Nov check, 4 sessions away."),
])
def test_dash_next_1(s, b, w, n, want):
    assert _clean(dv.rebalance_head(s, b, w, CHECK, n)) == want


def test_dash_next_2_3():
    assert _text(dv.worst_line("ABC", 12, 30, 40)) == "ABC fell from #12 to #30 in a month, 10 places from the cut-off."
    assert _text(dv.worst_line("ABC", 12, 39, 40)).endswith(", 1 place from the cut-off.")
    assert _text(dv.worst_line("ABC", 12, 40, 40)).endswith("in a month, and sits at the cut-off.")
    assert _text(dv.sector_go_line(2, "Capital Goods")) == ("Both Capital Goods holdings go; the sector is behind all "
                                                          "ranked stocks over 6M and 1M.")
    assert _text(dv.sector_go_line(3, "Chemicals")).startswith("All 3 Chemicals holdings go;")


def test_dash_next_5_6():
    reb = [("2026-02", 6), ("2026-03", 3), ("2026-11", 6)]
    assert dv.churn_line(5, 20, reb) == "5 of 20 holdings would change, against 5 in an average month since February."
    assert dv.churn_line(2, 20, reb) == "A light month. 2 of 20 holdings would change, against 5 in an average month since February."
    assert dv.churn_line(4, 20, [("2026-11", 10)]) == "4 of 20 holdings would change, against 10 at the November rebalance."
    assert dv.churn_line(4, 20, []) == "4 of 20 holdings would change."
    assert dv.churn_line(0, 20, []) == "No holding would change."
    assert dv.results_due_line([], CHECK) == "No holding or buy has results announced before the 30 Nov check."
    assert dv.results_due_line(["ABC", "XYZ"], CHECK) == "Results are due before the 30 Nov check from ABC and XYZ."


def test_dash_next_7_8():
    ind = pd.Series({"A": "Chemicals", "B": "Chemicals", "C": "Capital Goods", "D": "Capital Goods", "E": "Chemicals",
                     "F": "Chemicals", "G": "Textiles"})
    t = di.Turnover(top=40, new=4, climbers=[("A", None, 50, 10), ("B", 60, 45, 12), ("C", None, None, 20), ("D", 70, 50, 30)],
                    fallers=[("E", 10, None), ("F", 12, 55), ("G", 20, 60)])
    html = dv._turnover_html(t, ind)
    assert "4 of today’s top 40 were not there a month ago" in html
    say = _clean(re.search(r'<p class="dh-lede-s">(.*?)</p>', html).group(1))
    assert say == ("Chemicals and Capital Goods lead those climbing in, 2 each of the 4. "
                   "2 of the 3 falling out are Chemicals.")
    one = dv._turnover_html(di.Turnover(top=40, new=0, climbers=[("A", 1, 1, 1), ("B", 1, 1, 1), ("C", 1, 1, 1)], fallers=[]), ind)
    assert "all of today’s top 40 were there a month ago" in one
    assert "2 of the 3 stocks climbing in are Chemicals." in one and "falling out" not in _text(one).split("Now")[-1]


# ── 1d. Section 3, is momentum still working ────────────────────────────────

@pytest.mark.parametrize("year, streak, so_far, want", [
    (3.0, 0, None, "Momentum is ahead over 12 months."),
    (3.0, 2, "November", "Momentum is ahead over 12 months, but has trailed in October and so far in November."),
    (3.0, 4, "November", "Momentum is ahead over 12 months, but has trailed for 3 months and so far in November."),
    (-2.0, 3, None, "Momentum is behind over 12 months, and has trailed for 3 months in a row."),
    (-2.0, 1, "November", "Momentum is behind over 12 months."),
    (None, 2, "November", "This system’s record is under 12 months old; momentum has trailed in October and so far in November."),
    (None, 0, None, "This system’s record is under 12 months old."),
])
def test_dash_mom_1(year, streak, so_far, want):
    assert _clean(dv.momentum_head(year, streak, so_far, "October")) == want


def test_dash_mom_2_3():
    t_ = lambda ok: {"passed": ok, "on": 1.0, "off": -0.5, "n_on": 30, "n": 120, "halves": [1.0, 0.5]}  # noqa: E731
    row = {"name": "S", "sub": "", "cells": ["1", "2", "3"], "flip": "", "hist": ""}
    sigs = [{**row, "key": "a", "like": 1.0, "like_me": -1.0, "test": t_(True)},
            {**row, "key": "b", "like": 1.0, "like_me": 1.0, "test": t_(True)},
            {**row, "key": "c", "like": None, "like_me": None, "test": t_(False)}]
    t = _clean(dv.momentum_lede(sigs, 0.0, pd.Timestamp("2026-10-30")))
    assert t == ("We tested each signal on the Nifty 500’s record since 2010: 2 pass and 1 is not confirmed. "
                 "On today’s readings, 2 point to a stronger month and none to a weaker one. "
                 "At the 30 Oct month-end, which the tests read, it was 1 and 1.")
    same = [dict(x, like_me=x["like"]) for x in sigs[:2]]
    assert _clean(dv.momentum_lede(same, 0.0)).startswith("We tested each signal on the Nifty 500’s record since 2010: all 2 pass.")
    assert "month-end" not in dv.momentum_lede(same, 0.0)
    assert dv.momentum_lede([{"key": "x", "like": None, "test": None}], 0.0) == ""
    html = dv.html_of(dv.section_momentum([("12M", 3.0, "")], 0, sigs, 0.0, uni="1000", since="November 2026"))
    h2 = re.search(r'<h2[^>]*>(.*?)</h2>', html).group(1)
    assert "pass" not in h2 and "readings" not in h2                     # the h2 drops the count (owner's answer 2)
    assert "one of them a reading the page used" not in html             # mom.2's clause dropped


def test_dash_mom_4_and_11():
    sigs = [{"key": "qualify", "name": "Q", "sub": "", "cells": ["1", "2", "–"], "like": None, "like_me": None,
             "test": None, "flip": "", "now_note": True}]
    for since, want in (("December 2021", "This system’s record starts in December 2021."), ("", "This system’s record has not begun.")):
        t = _text(dv.html_of(dv.section_momentum([], 0, sigs, 0.0, uni="750", since=since)))
        assert "Each tile is the top fifth of the 750 by this site’s score, less all its members, equal weight, in points." in t
        assert want in t and "The month so far uses the ranks of the last month-end." in t
        assert "– in Now: not published yet (today’s share is worked out each night)." in t


def _ep(peak, low, depth, rec, m):
    return di.LagEpisode(peak=pd.Timestamp(peak), low=pd.Timestamp(low), depth=depth,
                         recovered=None if rec is None else pd.Timestamp(rec), months_to_recover=m)


def test_dash_mom_5_6_7():
    eps = [_ep("2024-06-28", "2025-03-31", -14.25, None, None), _ep("2023-12-29", "2024-04-30", -6.0, "2024-08-30", 8)]
    lag = di.MomentumLag(now=-3.25, best=pd.Timestamp("2024-06-28"), as_of=pd.Timestamp("2026-10-30"), episodes=eps)
    t = _clean(dv._lag_note(lag, "the 750", "December 2021"))
    assert "Against the 750, equal weight, the top fifth is 3.3% below its June 2024 best (month-ends to October 2026)." in t
    assert ("Its deepest fall since December 2021 was 14.3%, from Jun 2024 to Mar 2025. It is not yet made back. "
            "The one before, 6.0% from Dec 2023 to Apr 2024, took 8 months to recover.") in t
    assert "2024–24" not in t and "2024–" not in t      # the December peak no longer reads as the next year
    at_best = di.MomentumLag(now=-0.02, best=pd.Timestamp("2026-10-30"), as_of=pd.Timestamp("2026-10-30"), episodes=[])
    assert "the top fifth is at its best (month-ends to October 2026)." in dv._lag_note(at_best)
    long = di.MomentumLag(now=0, best=NOV, as_of=NOV, episodes=[
        _ep("2010-01-29", "2011-01-31", -20.0, "2012-06-29", 29), _ep("2015-01-30", "2015-06-30", -7.0, "2016-01-29", 12),
        _ep("2018-01-31", "2018-06-29", -6.0, "2018-12-31", 11)])
    line = _clean(dv._long_record_line(long)).strip()
    assert line == ("On the Nifty 500’s record since 2010, by the same rule, the deepest fall was 20.0% from Jan 2010; "
                    "it was made back by Jun 2012. The 2 other falls of 5% or more took 11 to 12 months to recover.")
    long.episodes = long.episodes[:2]
    assert dv._long_record_line(long).endswith("The other fall of 5% or more took 12 months to recover.")


# ── 1e. Section 4, money flows ──────────────────────────────────────────────

def _flows(mtd, before, rank=5):
    return di.Flows(as_of=NOV, mtd=mtd, month_rank=rank, months_in_record=120, prior_record=("Sep 2024", 50000.0),
                    last20=mtd, last20_is_record=True, streak=4, before=before, before_selling_months=7,
                    monthly=[("Oct", 1.0), ("Nov", 2.0)], trail20=[1000.0, 2000.0, 3000.0],
                    since=pd.Timestamp("2016-01-01"), month_from=pd.Timestamp("2026-11-03"))


@pytest.mark.parametrize("mtd, before, rank, dii, want", [
    (21000.0, -150000.0, 1, (0, 0, -5000.0),
     "Foreign investors have bought ₹21,000 Cr so far in November, the most in a month since 2016. They sold ₹1.50 lakh Cr "
     "over the 11 months before. Domestic institutions are net sellers so far in November, selling into the foreign buying."),
    (21000.0, 30000.0, 3, None,
     "Foreign investors have bought ₹21,000 Cr so far in November. They bought ₹30,000 Cr over the 11 months before."),
    (-5000.0, 12000.0, 9, (0, 0, -800.0),
     "Foreign investors have sold ₹5,000 Cr so far in November. They bought ₹12,000 Cr over the 11 months before. "
     "Domestic institutions are net sellers so far in November."),
])
def test_dash_flow_1_2(mtd, before, rank, dii, want):
    assert _clean(dv.flows_head(_flows(mtd, before, rank), dii)) == want


def _ev(heavy, rest, c1, lmb):
    return di.FlowEvidence(months=130, threshold=14372.0, after_heavy=heavy, after_rest=rest, hit_heavy=62.5, hit_rest=48.0,
                           halves=[("2016-2020", 1.0, 0.2), ("2021-2026", 0.8, 0.1)], corr_same=0.41, corr_next=c1,
                           large_minus_broad=lmb, first="Jan 2016", last="Oct 2026", heavy_months=33, tested=129, tested_heavy=32)


def test_dash_flow_4_5_8_to_13():
    html = dv.html_of(dv.section_flows(_flows(21000.0, -150000.0), _ev(1.25, -0.3, 0.05, -1.24), None,
                                       bars={"values": [1], "full": ["Nov 2026"], "band_note": ""}))
    t = _clean(html)
    assert "Highest 20-session total since 2016" in t                                                # flow.4
    assert "November so far has bought back 14% of that selling" in t                               # flow.5
    assert ("After the quarter of months with the most foreign buying (₹14,000 Cr or more), momentum’s lead over the "
            "Nifty 500 the next month averaged +1.3 points, against −0.3 after the rest. Momentum was ahead after 63% of "
            "those months, against 48% of the rest.") in t                                           # flow.8, answer 6
    assert "Tested here · 129 months with a next month, 32 heavy, in-sample" in t                    # flow.10 (#662)
    assert "and say nothing about the next (+0.05)." in t                                           # flow.11
    assert "Not a large-cap story. In those heavy-buying months the Nifty 50 trailed the Nifty 500 by 1.2 points" in t
    assert "a heavy-buying month, ₹14,000 Cr or more" in t and "₹14,372" not in t                    # flow.13
    t2 = _text(dv.html_of(dv.section_flows(_flows(21000.0, 0.0), _ev(1.0, 0.5, -0.25, 0.02), None)))
    assert "and only loosely with the next (−0.25)." in t2
    assert "Not a large-cap story. In those months the Nifty 50 and the Nifty 500 did about the same." in t2


# ── 1f. Section 5, size ─────────────────────────────────────────────────────

def _size_rows(large, mid, small, micro=(None, None, None)):
    return [("Large", [0, 0, 0], list(large)), ("Mid", [0, 0, 0], list(mid)), ("Small", [0, 0, 0], list(small)),
            ("Micro", [0, 0, 0], list(micro))]


def test_dash_size_1_3_4():
    book = {"Large": 10.0, "Mid": 30.0, "Small": 34.0, "Micro": 26.0}
    t = _clean(dv.size_head(_size_rows((-3.2, -5.0, -7.75), (1.0, -2.0, 0.5), (2.0, 1.0, -1.0)), book))
    assert t == ("Large Cap momentum is failing: the Nifty200 Momentum 30 is 3.2 to 7.8 points behind the Nifty 200 on "
                 "1M, 3M and 6M. In Mid Cap and Small Cap, momentum is within 2.5 points of its index on every window. "
                 "They hold 64% of the book.")
    assert "on every window" in dv.size_head(_size_rows((-4.0, -4.0, -4.0), (5, 5, 5), (5, 5, 5)), book)
    assert _clean(dv.size_head(_size_rows((1, 1, 1.5), (3, 1, -0.5), (4, 2, 2.0)), book)) == \
        "Momentum is within 2.5 points of its index in every size over 6M."
    assert _clean(dv.size_head(_size_rows((1, 1, 1.5), (3, 1, -4.25), (4, 2, 2.0)), book)) == \
        "Mid Cap momentum is furthest from its index: 4.3 points behind over 6M."
    assert "even as" not in dv.size_head(_size_rows((-3.2, -5.0, -7.75), (9, 9, 9), (9, 9, 9)), book)   # size.2 dropped
    # dash.size.4 over 12M, the approved window, when the 12M figures can be read (the table stops at 6M).
    rows = _size_rows((1, 1, 1.5), (3, 1, -0.5), (4, 2, 2.0))
    assert _clean(dv.size_head(rows, book, {"Large": 1.0, "Mid": -6.04, "Small": 3.0})) == \
        "Mid Cap momentum is furthest from its index: 6.0 points behind over 12M."
    assert _clean(dv.size_head(rows, book, {"Large": 1.0, "Mid": -2.0})) == \
        "Momentum is within 2.5 points of its index in every size over 12M."


def test_momentum_gap_reads_twelve_months():
    import pandas as pd
    from src.engine import dashboard_insights as di
    days = pd.bdate_range("2025-10-01", "2026-11-20")
    up = pd.Series(range(100, 100 + len(days)), index=days, dtype=float)
    flat = pd.Series(100.0, index=days)
    gap = di.momentum_gap({"midcap150_mom50": up, "midcap150": flat}, days[-1], 12)
    assert set(gap) == {"Mid"} and gap["Mid"] > 0


def test_dash_size_5():
    book = {"Small": 34.0}
    rows = [["Nifty 100", 50, 70, 62], ["Nifty Midcap 150", 40, 45, 41], ["Nifty Smallcap 250", 30, 35, 22]]
    assert _clean(dv.shared_line(rows, book)) == ("Now Nifty 100 is the broadest and Nifty Smallcap 250 the narrowest of "
                                                  "NSE’s size lists. 34% of the book is in Small Cap.")
    rows[1][2] = 75
    assert "A month ago the broadest was Nifty Midcap 150." in dv.shared_line(rows, book)
    tie = [["Nifty 100", 50, 70, 62], ["Nifty Midcap 150", 40, 45, 62], ["Nifty Smallcap 250", 30, 35, 22]]
    assert "Nifty 100 and Nifty Midcap 150 are the broadest, at 62%" in _text(dv.shared_line(tie, {}))
    assert dv.shared_line([["Nifty 100", 1, 1, 50], ["Nifty Midcap 150", 1, 1, 50]], {}) == ""


@pytest.mark.parametrize("system", SYSTEMS)
def test_dash_size_7_8(system):
    uni = dv.UNIVERSE_SHORT[system]
    typ = {"market": [1, 2, 3, 10.0], "equal_weight": [1, 2, 3, 14.2], "median": [1, 2, 3, -3.4], "beat_share": [35.0, 1, 1, 1]}
    t = _clean(dv._typical_html(typ, uni))
    assert f"Only 35% of the {uni} beat Nifty Total Market over the past month." in t
    assert (f"Over 12 months the equal-weighted {uni} beat Nifty Total Market by 4.2 points, but the median stock fell 3.4%. "
            "A few large winners lift the average.") in t
    assert "the field a momentum book picks from" not in t


# ── 1g. Section 6 and At a glance ───────────────────────────────────────────

def test_dash_sec_1_2_3():
    assert _clean(dv.strong_weak_head(44.0, 21.0, 3)) == ("44% of the book is in sectors ahead of all ranked stocks over "
                                                          "6M and 1M; 21% is in 3 behind on both.")
    assert "21% is in 1 sector behind on both" in _text(dv.strong_weak_head(44.0, 21.0, 1))
    assert _text(dv.strong_weak_head(44.0, 0.0, 0)).endswith(". No sector the book holds is behind on both.")
    assert _text(dv.strong_weak_head(0.0, 10.0, 1)).startswith("None of the book is in a sector ahead")
    weights = pd.DataFrame({"Industry": ["A", "B", "C"], "Holdings": [2, 1, 1], "Weight": [40.0, 30.0, 30.0]})
    sectors = pd.DataFrame({"Industry": ["A", "B", "C"], "rel_6m": [5.0, -3.0, 2.0], "rel_1m": [2.0, -1.0, -1.0]})
    t = _text(dv.html_of(dv.section_strong_weak(weights, sectors)))
    assert "Ahead of all ranked stocks over 6 months and 1 month." in t
    assert "Behind all ranked stocks over 6 months and 1 month." in t
    assert "Ahead on one window only: C over 6 months." in t


def test_dash_gl_2_and_pf_eq_11():
    note = mw.book_too_short(63, 20)
    assert note == "the system is too young (the figure needs 63 sessions; the book has 20)"
    assert ("No risk figures yet: " + note + ".").count(":") == 1


# ── 2. Portfolio ────────────────────────────────────────────────────────────

def _page(**kw):
    blank = {f.name: None for f in dataclasses.fields(pp.Page)}
    blank.update(kw)
    return pp.Page(**blank)


@pytest.mark.parametrize("since, mkt, want", [
    (12.34, 8.0, "The book is up 12.3% since 1 Jan 2026, 4.3 points ahead of Nifty Total Market."),
    (-2.0, 1.0, "The book is down 2.0% since 1 Jan 2026, 3.0 points behind Nifty Total Market."),
    (5.0, 5.02, "The book is up 5.0% since 1 Jan 2026, level with Nifty Total Market."),
    (5.0, None, "The book is up 5.0% since 1 Jan 2026."),
    (None, None, "The model book’s record starts on 1 Jan 2026."),
])
def test_pf_head_1(since, mkt, want):
    assert _clean(pp.header_title(since, mkt, pd.Timestamp("2026-01-01"))) == want


def test_pf_head_3_4():
    led = {"months": {f"2026-{m:02d}": {"origin": "backfill", "finalized_on": "2026-11-02"} for m in range(1, 11)}}
    assert pp._provenance(_page(ledger=led, system="750")) == (" The months January to October 2026 were worked out from "
                                                              "the rules on 2 Nov 2026. Later months were recorded as they happened.")
    one = {"months": {"2026-10": {"origin": "backfill"}}}
    assert pp._provenance(_page(ledger=one, system="nano")).startswith(" October 2026 was worked out from the rules.")
    mem = {"indices": {"nifty_1000": {"baseline": {"date": "2026-10-30"}}}}
    assert pp.reconstructed_note("1000", mem) == (" November is reconstructed: its 30 Oct book uses a list NSE first "
                                                  "published on 16 Nov.")
    assert "reconstructed" in pp._provenance(_page(ledger={}, system="1000"))
    assert pp._provenance(_page(ledger={}, system="750")) == ""
    src = (pp.ROOT / "src/ui/views/portfolio_page.py").read_text(encoding="utf-8")
    assert "30 Oct book" not in src and "on 16 Nov" not in src                                    # no typed dates


def test_pf_exp_1():
    first = pd.Series({"Large": 30.0, "Mid": 25.0, "Small": 45.0})
    assert pp.size_shift("2026-01-01", first, pd.Series({"Large": 10, "Small": 60.0, "Micro": 30.0})) == (
        "At its first rebalance, Jan 2026, the book held 55% in Large Cap and Mid Cap. Now 90% is in Small Cap and Micro Cap. ")
    assert pp.size_shift("2026-10-01", pd.Series({"Nano Cap": 100.0}), pd.Series({"Nano Cap": 100.0})) == (
        "At its first rebalance, Oct 2026, the book held none in Large Cap and Mid Cap. Now 100% is in Nano Cap. ")
    assert pp.size_shift("2026-01-01", first, pd.Series({"Large": 60.0, "Mid": 20.0, "Small": 20.0})).endswith(
        "Now 80% is in Large Cap and Mid Cap. ")


def test_pf_ret_4():
    ex = lambda w: pd.DataFrame({"kind": "size", "date": pd.Timestamp("2026-11-02"), "name": list(w), "weight": list(w.values())})  # noqa: E731
    assert pp.yardstick_line(_page(exposure=ex({"Small": 40, "Micro": 30, "Mid": 30}))).startswith(
        "Most of the book is in Small Cap and Micro Cap, so")
    assert pp.yardstick_line(_page(exposure=ex({"Small": 25, "Micro": 23, "Mid": 22, "Large": 20, "Nano Cap": 10}))).startswith(
        "The book’s largest size groups are Small Cap and Micro Cap, so")
    assert pp.yardstick_line(_page(exposure=pd.DataFrame())) == ""


def test_pf_eq_3_5_6_9():
    assert pp.capture_word(80.0, "Falls", "bad") == "Falls less on bad days"
    assert pp.capture_word(100.2, "Rises", "good") == "Rises as much on good days"
    assert pp.capture_word(130.0, "Rises", "good") == "Rises more on good days"
    t = pp.tracking_line(15.8)
    assert t == ("A tracking error of 15.8% means the book’s return over 12 months usually lands within about 15.8 points "
                 "of Nifty Total Market’s, two years in three. On a typical day the two differ by about 1.0 points "
                 "(tracking error ÷ √250).")
    src = (pp.ROOT / "src/ui/views/portfolio_page.py").read_text(encoding="utf-8")
    assert "points on a typical day" in src and " pt on a typical day" not in src                 # eq.5
    assert "Swings about as much as the index" in src                                             # eq.3 at 1.0
    assert "where its lead comes from" not in src and "20-stock" not in src                       # eq.10 dropped


def test_pf_tr_2_4_and_sys_1_2():
    reb = [(pd.Timestamp("2026-01-01"), 20, 0, 0), (pd.Timestamp("2026-02-02"), 6, 6, 14),
           (pd.Timestamp("2026-03-02"), 3, 3, 17), (pd.Timestamp("2026-11-02"), 6, 6, 14)]
    assert pp.changed_tile(reb, 20) == ("Changed at a rebalance", "5 of 20", "", "On average since February", "",
                                        "Latest November 6 · fewest March 3")
    assert pp.changed_tile(reb[:1], 20)[1] == "–" and pp.changed_tile(reb[:1], 20)[5] == "The system is too young"
    assert pp._rebalances(1) == "1 rebalance" and pp._rebalances(3) == "3 rebalances"
    assert pp.window_line("1 Oct", ["750"]).startswith("“Since 1 Oct” is the window the 750 has traded since it began, so")
    assert "the window that the 750 and the 1000 have both traded" in pp.window_line("1 Oct", ["750", "1000"])
    assert "the window that the 750, the 1000 and the list have all traded" in pp.window_line("1 Oct", ["750", "1000", "list"])
    assert pp.window_line("1 Oct", []) == "" and pp._and([]) == ""
    assert "once its first full month is frozen" in pp.window_line("1 Oct", ["750"])


def test_pf_book_2_day_3_cal_2_err_2():
    src = (pp.ROOT / "src/ui/views/portfolio_page.py").read_text(encoding="utf-8")
    assert "The record keeps returns and weights, not costs, so rupee figures are a" in src     # book.2
    assert "more than {hc}% below the 52-week high" in src
    assert "One day says little; a run of bars on one side says more." in src                     # day.3
    assert "The book beat Nifty Total Market on {beat} of" not in src
    assert "mw.NOT_PUBLISHED" not in src.split("def calendar_html")[1].split("def month_bars_spec")[0]   # cal.2
    assert "could not be sized" not in src                                                        # err.2


def test_combined_names_the_record_its_tiles_read():
    # S236 (site audit, 28 Nov 2026): Combined's tiles read the 750's record, the note said "This system's".
    sigs = [{"key": "qualify", "name": "Q", "sub": "", "cells": ["1", "2", "–"], "like": None, "like_me": None,
             "test": None, "flip": "", "now_note": True}]
    t = _text(dv.html_of(dv.section_momentum([("12M", 3.0, "the Nifty 750's record (Combined keeps none)")], 0, sigs,
                                             0.0, uni="combined universe", since="December 2021", borrowed=True)))
    assert "The Nifty 750’s record, which Combined reads, starts in December 2021." in t
    assert "This system’s record" not in t
