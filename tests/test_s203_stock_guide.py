"""S203: the stock page's and the Guide's sentences render their approved templates (owner, 24 Nov 2026).

The templates, by id, are in docs/archive/S203_TEMPLATES_OTHER_PAGES.md §8 (st.*) and §9 (gd.*), with the owner's
answers in §12. One test per id, KEEP rows included, on the cases the row lists, with fake inputs and no network.
`_clean` fails a sentence with an empty slot, "None", "nan", a "–" inside it, or a doubled word. The sell-rule
reasons (`why`) are cm.* rows written in `exit_watch.py`; the tests here pass them in as data.
"""
from __future__ import annotations

import html as _html
import inspect
import re

import pandas as pd
import pytest

from src.engine.exit_watch import CLEAR, SELL, UNKNOWN, WATCH
from src.engine.track_record import TRACK_RECORD_CONFIG
from src.ui import stock_lines as sl
from src.ui import watchlist_lines as wl
from src.ui.views import guide_view as gv
from src.ui.views import stock_view as sv

DAY = pd.Timestamp("2026-11-20")
CHECK = pd.Timestamp("2026-11-30")
LN = wl.Lines(buy=20, keep=40, high_gap=20)
UNIS = {"750": sl.Universe("750", 750), "1000": sl.Universe("1000", 1000),
        "nano": sl.Universe("> ₹2,000 Cr list", 1912)}


def _text(html: str) -> str:
    return re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", "", html))).strip()


def _clean(html: str, signs: bool = True) -> str:
    """signs=False for the Guide, whose pts answer works an example in signed figures ("+20.0% against +5.0%")."""
    t = _text(html)
    assert t, "an empty sentence"
    assert not re.search(r"\b(None|nan|NaN|NaT)\b", t), t
    for bad in ("{", "}", " – ", "  ", "..", "the the ", "up −", "down −", "+−") + (("against +", "against −") if signs else ()):
        assert bad not in t, (bad, t)
    for banned in ("12-month", "one year", "1-year"):     # glossary 6
        assert banned not in t.lower(), (banned, t)
    return t


def _row(**kw) -> pd.Series:
    base = {"Symbol": "SANSERA", "Company Name": "Sansera Engineering Ltd.",
            "Industry": "Automobile and Auto Components", "Indices": "SMALL250", "Rank": 12,
            "Rank (-3M)": 16.0, "Rank (-1M)": 13.0, "Score": 1.973009, "CMP": 4798.4,
            "Above 50 EMA": True, "% 50 EMA": 11.959154, "52W High": 4798.4, "52W High Date": "2026-11-20",
            "% High": 0.0, "Near 52W High": True, "ATH": 4798.4, "ATH Source": "snapshot",
            "ATH Date": "2026-11-20", "1M Return": 0.216294, "12M Return": 2.009156,
            "Market Cap (Cr)": 29943.728069, "Horizons Scored": 5, "FFill %": 0.0,
            "Short History": "No", "Data Gap": ""}
    base.update(kw)
    return pd.Series(base)


# ══ §8 The stock page ════════════════════════════════════════════════════════

@pytest.mark.parametrize("ema, high, state", [
    (True, True, "passes both filters"),
    (False, False, "fails both filters"),
    (True, False, "passes only the 50D EMA filter"),
    (False, True, "passes only the 52-week-high filter"),
])
@pytest.mark.parametrize("held", [True, False])
def test_st_head_1(ema, high, state, held):
    book = "is in the model book" if held else "is not in the model book"
    row = _row(**{"Above 50 EMA": ema, "Near 52W High": high})
    assert _clean(sl.title(row, UNIS["750"], held)) == f"Sansera Engineering is 12th of 750, {state} and {book}."
    assert _clean(sl.title(row, UNIS["1000"], held)) == f"Sansera Engineering is 12th of 1000, {state} and {book}."
    assert _clean(sl.title(row, UNIS["nano"], held)) == (
        f"Sansera Engineering is 12th of the 1,912 in the > ₹2,000 Cr list, {state} and {book}.")


@pytest.mark.parametrize("kw, market, late, want", [
    ({}, 0.0080, False, "₹4,798 at the 20 Nov 2026 close, a new 52-week closing high. Up 200.9% over 12 months, "
                        "against up 0.8% for Nifty Total Market. Market cap ₹29,944 Cr."),           # new high
    ({"12M Return": -0.239, "52W High Date": "2026-08-19"}, -0.031, False,
     "₹4,798 at the 20 Nov 2026 close. Down 23.9% over 12 months, against down 3.1% for Nifty Total Market. "
     "Market cap ₹29,944 Cr."),
    ({"12M Return": 0.0004, "52W High Date": "2026-08-19"}, 0.05, False,
     "₹4,798 at the 20 Nov 2026 close. Unchanged over 12 months, against up 5.0% for Nifty Total Market. "
     "Market cap ₹29,944 Cr."),                                                                       # level
    ({"Market Cap (Cr)": 122000.0}, None, False,
     "₹4,798 at the 20 Nov 2026 close, a new 52-week closing high. Up 200.9% over 12 months. "
     "Market cap ₹1.22 lakh Cr."),                                                                    # market missing
    ({}, None, True, "₹4,798 at the 20 Nov 2026 close, a new 52-week closing high. Up 200.9% over 12 months; "
                     "Nifty Total Market’s 20 Nov close is not in yet. Market cap ₹29,944 Cr."),       # late
    ({"Market Cap (Cr)": None}, 0.008, False,
     "₹4,798 at the 20 Nov 2026 close, a new 52-week closing high. Up 200.9% over 12 months, "
     "against up 0.8% for Nifty Total Market."),                                                      # cap missing
])
def test_st_head_2(kw, market, late, want):
    assert _clean(sl.lede(_row(**kw), DAY, market, late)) == want


def test_st_head_3():
    def lede(hits):
        html = " ".join(sv.head_html(_row(), UNIS["750"], False, DAY, None, 12, 290, LN, None, hits))
        return [_text(p) for p in re.findall(r'<p class="dh-lede">(.*?)</p>', html)]
    one = lede([("Nifty 1000", 17, 1000)])
    assert _clean(one[1]) == "It also ranks 17th of 1,000 in the Nifty 1000. See it in the Nifty 1000 →"
    two = lede([("Nifty 750", 12, 750), ("Nifty 1000", 17, 1000)])
    assert _clean(two[1]).startswith("It also ranks 12th of 750 in the Nifty 750 and 17th of 1,000 in the Nifty 1000.")
    assert len(lede([])) == 1


def test_st_head_4():
    h = sl.Holding(165, 5.4, pd.Timestamp("2026-03-02"), 2230.0, 115.2)
    ts = sl.tiles(_row(), UNIS["750"], 12, 290, DAY, LN, h)
    assert [t.sub for t in ts] == ["+21.6% over 1M", "16 three months ago", "the book buys the top 20",
                                   "since 2 Mar 2026, 5.4% of the book"]
    out = sl.tiles(_row(**{"Rank (-3M)": None, "Above 50 EMA": False}), UNIS["750"], None, 290, DAY, LN,
                   sl.Holding(None, None, None, None, 3.0))
    assert [t.sub for t in out] == ["+21.6% over 1M", "not ranked three months ago", "fails the 50D EMA filter",
                                    "since its first buy"]


@pytest.mark.parametrize("q, where", [(12, "inside the book’s buy line"), (33, "between the book’s buy and keep lines"),
                                      (41, "past the book’s keep line")])
def test_st_rank_1_qualified(q, where):
    assert _clean("".join(sl.rank_heading(_row(), UNIS["750"], q, 290, LN))) == \
        f"{wl.fmt_ordinal(q)} of the 290 that pass both filters, {where}."


@pytest.mark.parametrize("kw, fails", [
    ({"Above 50 EMA": False, "Near 52W High": False}, "both filters"),
    ({"Above 50 EMA": False}, "the 50D EMA filter"),
    ({"Near 52W High": False, "% High": -30.0}, "the 52-week-high filter"),
    ({"Near 52W High": False, "% High": None, "Short History": "Yes"},
     "the 52-week-high filter, too new to have a 52-week high (none before 126 sessions)"),          # young
])
@pytest.mark.parametrize("system", ["750", "nano"])
def test_st_rank_1_fails(kw, fails, system):
    uni = UNIS[system]
    a, b, c = sl.rank_heading(_row(Rank=591, **kw), uni, None, 290, LN)
    assert b == f"it fails {fails}"
    assert _clean(a + b + c) == f"591st {uni.of}, but it fails {fails}, so it is not among the 290 the book picks from."


def test_st_rank_2():
    note = ("A past rank is how today’s rule ranks the stock on that day, read on the last session on or before the "
            "date. The qualified are the stocks that pass both filters; the book buys the top 20 of them and keeps a "
            "holding while it is in the top 40.")
    assert _clean(sl.rank_note(_row(), UNIS["750"], LN)) == note + " Its score is 1.973, with all five horizons scored."
    assert _clean(sl.rank_note(_row(**{"Horizons Scored": 3}), UNIS["750"], LN)) == \
        note + " Its score is 1.973, with 3 of the five horizons scored."
    assert _clean(sl.rank_note(_row(**{"Horizons Scored": None}), UNIS["750"], LN)) == note + " Its score is 1.973."
    assert _clean(sl.rank_note(_row(Score=None), UNIS["750"], LN)) == note


@pytest.mark.parametrize("a, held, want", [
    ({"status": SELL, "why": "5.0% below its 50D EMA"}, True,
     "It would be sold at the 30 Nov check if today's price holds: it is 5.0% below its 50D EMA."),
    ({"status": SELL, "why": "5.0% below its 50D EMA"}, False,
     "It would be sold if held at the 30 Nov check if today's price holds: it is 5.0% below its 50D EMA."),
    ({"status": WATCH, "why": "is 38th among the qualified, 2 places inside the top 40"}, True,
     "It is close to a sell rule: it is 38th among the qualified, 2 places inside the top 40."),       # by rank
    ({"status": WATCH, "why": "can fall 2.0% to its 50D EMA"}, True,
     "It is close to a sell rule: it can fall 2.0% to its 50D EMA."),                                  # EMA
    ({"status": WATCH, "why": "can fall 3.0% to the −20% line"}, True,
     "It is close to a sell rule: it can fall 3.0% to the −20% line."),                                # high
    ({"status": WATCH, "why": "is 40th among the qualified, the last place kept; can fall 2.0% to its 50D EMA"}, False,
     "It is close to a sell rule: it is 40th among the qualified, the last place kept; can fall 2.0% to its 50D EMA."),
    ({"status": CLEAR, "why": "", "EMA cushion": 0.107, "High cushion": 0.2}, True,
     "Clear of all three sell rules; a 10.7% fall would reach the nearest, its 50D EMA."),
    ({"status": CLEAR, "why": "", "EMA cushion": 0.30, "High cushion": 0.05}, True,
     "Clear of all three sell rules; a 5.0% fall would reach the nearest, the −20% line."),
    ({"status": CLEAR, "why": ""}, True, "Clear of all three sell rules."),                            # no cushion
    ({"status": UNKNOWN, "why": "not in the ranked universe"}, False,
     "No sell rule can be checked: the stock is not ranked today."),
    (None, False, "No sell rule can be checked: the stock is not ranked today."),
])
def test_st_rule_1(a, held, want):
    assert _clean("".join(sl.rules_heading(a, CHECK, 0.8, held))) == want
    html = "".join(sv._h2("", *sl.rules_heading(a, CHECK, 0.8, held)))
    assert _clean(html) == want


def test_st_rule_1_without_a_check_day():
    assert sl.rules_heading({"status": SELL, "why": "below its 50D EMA"}, None, 0.8)[1] == \
        " at the next check if today's price holds: it is below its 50D EMA."


def test_st_rule_2():
    rank_df = pd.DataFrame({"Symbol": ["A", "B"], "Rank": [1, 2], "CMP": [112.0, 90.0], "% 50 EMA": [12.0, -5.0],
                            "% High": [0.0, -30.0], "52W High": [112.0, 128.6],
                            "Above 50 EMA": [True, False], "Near 52W High": [True, False]})
    a = {"EMA cushion": 0.107, "High cushion": 0.2, "Rank room": 39}
    rows = sl.rules(rank_df.iloc[0], a, 1, LN, 0.8)
    assert [(r.name, r.line, r.fall, r.today) for r in rows] == [
        ("Above its 50D EMA", "₹100", "10.7%", "+12.0% above"), ("Within 20% of its 52W high", "₹90", "20.0%", "At the high"),
        ("In the top 40 of the qualified", "40th", "39 places", "1st")]
    low = sl.rules(rank_df.iloc[1], {}, None, LN, 0.8)
    assert [(r.fall, r.today) for r in low] == [("Below it", "−5.0% below"), ("Below it", "−30.0% from it"), ("Out", "Out")]
    young = sl.rules(_row(**{"% High": None, "Near 52W High": False, "Short History": "Yes"}), {}, None, LN, 0.8)
    assert (young[1].fall, young[1].today) == ("No 52W high yet", "None before 126 sessions")


def test_st_rule_3():
    h = sl.Holding(165, 5.4, pd.Timestamp("2026-03-02"), 2230.0, 115.2)
    assert sl.holding_sentence(False, None) == ("The model book does not hold it.", "")
    assert sl.holding_sentence(True, None) == ("The model book holds it.", "")
    lead, rest = sl.holding_sentence(True, h)
    assert _clean(lead + rest) == ("The model book holds it: 165 shares, 5.4% of the book, first bought on 2 Mar 2026 "
                                   "at ₹2,230, up 115.2% since.")
    down = sl.Holding(1, None, pd.Timestamp("2026-03-02"), None, -4.25)
    assert _clean("".join(sl.holding_sentence(True, down))) == \
        "The model book holds it: 1 share, first bought on 2 Mar 2026, down 4.3% since."
    level = sl.Holding(None, 5.0, None, None, 0.02)
    assert _clean("".join(sl.holding_sentence(True, level))) == "The model book holds it: 5.0% of the book, unchanged since."
    assert sl.holding_sentence(True, sl.Holding(None, None, None, None, None)) == ("The model book holds it:", "")


def test_st_rule_4():
    """Not rebuilt: the proposed `mw.no_events("it", check)` writes "before the 30 Nov fill", and 30 Nov is the
    check, not the fill (see the S203 report). Today's sentence is pinned until the owner decides."""
    assert _clean(sl.calendar_sentence(CHECK, [], pd.Timestamp("2026-11-05"))) == (
        "The rules are checked at the month-end close, next on 30 Nov 2026; no board meeting is announced "
        "before then (its last results meeting was on 5 Nov).")
    assert _clean(sl.calendar_sentence(CHECK, [], None)) == (
        "The rules are checked at the month-end close, next on 30 Nov 2026; no board meeting is announced before then.")
    ev = [(pd.Timestamp("2026-11-25"), "X", "held", "Results, dividend"), (pd.Timestamp("2026-11-27"), "X", "held", "Bonus")]
    assert _clean(sl.calendar_sentence(CHECK, ev, None)) == (
        "The rules are checked at the month-end close, next on 30 Nov 2026; board meetings and ex-dates announced "
        "before then: Results, dividend on 25 Nov and Bonus on 27 Nov.")
    assert sl.calendar_sentence(None, [], None) == "The rules are checked at the month-end close."


def test_st_rule_5():
    lead = ("Highs and lows are closing prices over the last 12 months, as the ranking uses them, so they can differ "
            "from an intraday high quoted elsewhere.")
    assert _clean(sl.highs_note(_row())) == lead + " The all-time high is the same close, ₹4,798."
    assert _clean(sl.highs_note(_row(ATH=6100.2, **{"ATH Date": "2024-09-20"}))) == \
        lead + " The all-time closing high is ₹6,100, on 20 Sep 2024."
    assert _clean(sl.highs_note(_row(ATH=6100.2, **{"ATH Date": None}))) == lead + " The all-time closing high is ₹6,100."
    assert _clean(sl.highs_note(_row(ATH=None))) == lead


def _w(m, ret, market, fall):
    return sl.Window(m, None, ret, market, None, fall, None, None, None)


@pytest.mark.parametrize("ws, want", [
    ([_w(1, 0.2, 0.1, -5.0), _w(3, -0.05, 0.02, -9.0), _w(6, 0.1, 0.04, -12.0), _w(9, 0.3, 0.05, -14.0),
      _w(12, 2.009, 0.008, -16.996686)],
     "Ahead of Nifty Total Market on 4 of 5 windows; its max drawdown over 12 months was 17.0%."),     # 12M
    ([_w(1, 0.2, 0.1, -5.0), _w(6, 0.1, 0.2, -12.04), _w(12, None, None, None)],
     "Ahead of Nifty Total Market on 1 of 2 windows; its max drawdown over 6 months was 12.0%."),      # shorter window
    ([_w(12, 0.2, None, -16.0)], "Its max drawdown over 12 months was 16.0%."),                        # market missing / late
    ([_w(12, 0.2, 0.1, None)], "Ahead of Nifty Total Market on 1 of 1 window."),                       # drawdown missing
    ([_w(12, None, None, None)], "No return to show for this stock yet."),
])
def test_st_ret_1(ws, want):
    assert _clean("".join(sl.returns_heading(ws))) == want


def test_st_ret_2():
    assert _clean(sl.returns_note(DAY, UNIS["nano"])) == (
        "Price returns, without dividends. Each window runs from its first session on or after the same date back to "
        "20 Nov; Nifty Total Market over the same sessions. Lead is the stock’s return less Nifty Total Market’s, in "
        "points (pts = percentage points: 12% − 8% = 4 pts). The typical stock is the median of the > ₹2,000 Cr list. "
        "Max drawdown is the deepest fall from a peak inside the window. Sharpe is the window’s return over its "
        "volatility, as the ranking scores it, not annualised. Rank by return is its place among the > ₹2,000 Cr list "
        "on that window’s return alone.")


@pytest.mark.parametrize("late", [True, False])
def test_st_ret_3(late):
    ws = [_w(12, 0.2, None if late else 0.1, -16.0)]
    html = "".join(sv.returns_html(ws, DAY, UNIS["750"], late))
    note = _text(re.search(r'<p class="dh-note sp-cols">(.*?)</p>', html, re.S).group(1))
    assert note.endswith("NSE’s 20 Nov close for Nifty Total Market is not in yet.") is late
    cells = re.findall(r'<td class="n">(.*?)</td>', html)
    assert cells[0] == ("–" if late else "+10.0%")             # the market's column: a dash, not a session-early figure


def test_st_px_1():
    assert _clean("".join(sl.price_heading(57, 60, 298.6))) == \
        "Above its 50D EMA on 57 of the last 60 sessions; against Nifty Total Market it has almost tripled over 12 months."
    assert _clean("".join(sl.price_heading(57, 60, 210.0))) == \
        "Above its 50D EMA on 57 of the last 60 sessions; against Nifty Total Market it has more than doubled over 12 months."
    assert _clean("".join(sl.price_heading(57, 60, 520.0))) == \
        "Above its 50D EMA on 57 of the last 60 sessions; against Nifty Total Market it has grown 5.2 times over 12 months."
    assert _clean("".join(sl.price_heading(18, 60, 88.2))) == \
        "Above its 50D EMA on 18 of the last 60 sessions; against Nifty Total Market its relative strength fell 11.8% over 12 months."
    assert _clean("".join(sl.price_heading(18, 60, None))) == "Above its 50D EMA on 18 of the last 60 sessions."       # no RS
    assert _clean("".join(sl.price_heading(0, 0, None))) == "Too few sessions for a 50D EMA yet."
    # The chart's chips rewrite the window the heading names (stock_view swaps RANGE_WORDS).
    from src.ui.stock_chart import DEFAULT_RANGE, RANGE_WORDS
    assert RANGE_WORDS[DEFAULT_RANGE] in sl.price_heading(57, 60, 298.6)[2]


def test_st_px_2():
    from src.engine.backtester import EMA_MIN_PRINTS
    assert f"(none before {int(EMA_MIN_PRINTS)} sessions)" in sl.PRICE_NOTE
    assert _clean(sl.PRICE_NOTE).startswith("Three panes: price with its 50D EMA, the one the ranking reads (none before 30 sessions);")


def _sector(qualified):
    n = len(qualified)
    return pd.DataFrame({"Symbol": [f"S{i}" for i in range(n - 1)] + ["SANSERA"], "Rank": range(1, n + 1),
                         "Industry": ["Automobile and Auto Components"] * n, "Qualified Rank": qualified})


@pytest.mark.parametrize("qualified, want", [
    ([1.0, 2.0, None, None], "4th of the 4 Auto stocks; 2 of them pass both filters."),
    ([1.0, None, None], "3rd of the 3 Auto stocks; 1 of them passes both filters."),
    ([None, None], "2nd of the 2 Auto stocks; none of them passes both filters."),
])
def test_st_ind_1(qualified, want):
    in_ind = _sector(qualified)
    assert _clean(sl.industry_heading(_row(), in_ind)) == want
    others = in_ind[in_ind["Symbol"] != "SANSERA"]                       # pos missing
    assert _clean(sl.industry_heading(_row(), others)).startswith(f"{len(others)} Auto stocks; ")


def test_st_ind_2():
    in_ind = pd.DataFrame({"Symbol": [f"S{i}" for i in range(25)] + ["SANSERA"]})
    below = pd.concat([in_ind.head(7), in_ind.tail(1)])
    assert _clean(sv._peers_note(below, in_ind, "SANSERA")) == "The 7 best-ranked of the sector’s 26, and this stock (26th)"
    among = pd.DataFrame({"Symbol": ["S0", "SANSERA", "S2"]})
    assert _clean(sv._peers_note(among, among, "SANSERA")) == "The 3 best-ranked of the sector’s 3, with this stock"


def test_st_data_1():
    texts = lambda dc: [t for _, t in dc.items]   # noqa: E731
    clean = sl.data_checks(_row(), DAY, [], pd.Timestamp("2024-10-04"))
    assert texts(clean) == [
        "A close on every session of the last 12 months; none carried forward",
        "More than 126 sessions of prices, so the 52-week high counts",
        "Ranked on all five horizons (1, 3, 6, 9 and 12 months)",
        "The price is the 20 Nov close, the ranking’s own day",
        "No split, bonus, rights issue or demerger in NSE’s lists since October 2024",
        "All-time closing high over the full price history we hold, its weekly years filled with NSE’s daily closes"]
    from src.engine.momentum import CARRIED_MARK
    rough = sl.data_checks(_row(**{"FFill %": 12.5, "Data Gap": f"🔴 {CARRIED_MARK}", "Short History": "Yes",
                                   "Horizons Scored": 3, "ATH Source": "window"}), DAY, [], None)
    assert texts(rough) == [
        "12.5% of the last 12 months’ sessions carry the previous close",
        "A data gap in the last 12 months",
        "Fewer than 126 sessions of prices, so the 52W-high filter cannot pass yet",
        "Ranked on 3 of the five horizons; the score is spread over those it has",
        "The price is the last print, not the 20 Nov close",
        "No split, bonus, rights issue or demerger in NSE’s lists",
        "High from a two-year window, not all-time"]
    for t in texts(clean) + texts(rough):
        _clean(t)
        assert "Screener" not in t                                     # rule 13: no vendor in a sentence


def _act(kind="split", ex="2026-07-03"):
    return sl.Action(kind, "", pd.Timestamp(ex), 0.2)


@pytest.mark.parametrize("actions, bad, want", [
    ([], 0, "Nothing to correct: a full year of prices with no gaps, and no split, bonus or rights issue to adjust for."),
    ([_act()], 0, "1 corporate action in NSE’s lists since October 2024, the latest a split ex 3 Jul 2026; prices before "
                  "it are rescaled."),
    ([_act("bonus", "2025-02-01"), _act("rights")], 0,
     "2 corporate actions in NSE’s lists since October 2024, the latest a rights issue ex 3 Jul 2026; prices before it "
     "are rescaled."),
    ([], 1, "1 check to read below."),
    ([_act()], 2, "1 corporate action in NSE’s lists since October 2024, the latest a split ex 3 Jul 2026; prices before "
                  "it are rescaled. 2 checks to read below."),
])
def test_st_data_2(actions, bad, want):
    dc = sl.DataChecks([(True, "x")] + [(False, "y")] * bad, actions, " since October 2024")
    assert _clean(sl.data_heading(dc)) == want


def test_st_data_3():
    a = sl.Action("split", "Face Value Split (Sub-Division) - From Rs 10/- To Rs 2/-", pd.Timestamp("2026-07-03"), 0.2)
    assert sl.action_line(a) == ("Split, ex 3 Jul 2026: Face Value Split (Sub-Division) - From Rs 10/- To Rs 2/-; "
                                 "prices before it are scaled by 0.2")
    assert sl.action_line(sl.Action("rights", "", pd.Timestamp("2026-07-03"), None)) == "Rights issue, ex 3 Jul 2026"


def _not_ranked(monkeypatch, sym, **kw):
    out = []
    monkeypatch.setattr(sv, "_emit", lambda parts: out.extend(parts))
    monkeypatch.setattr(sv, "_render_actions", lambda *a, **k: None)
    import src.ui.views.watchlist_view as wv
    monkeypatch.setattr(wv, "_nse_lists", lambda: (None, {"SANSERA"}))
    ranked = pd.DataFrame({"Symbol": ["AAA", "BBB"], "Rank": [1, 2]})
    sv._render_not_ranked(sym, ranked, sl.universe("750", 750), DAY, None, **kw)
    html = " ".join(out)
    return (_clean(re.search(r'<h1 class="dh-h1">(.*?)</h1>', html).group(1)),
            _clean(re.search(r'<p class="dh-lede">(.*?)</p>', html).group(1)), html)


def test_st_nr_1(monkeypatch):
    h1, lede, html = _not_ranked(monkeypatch, "NOSUCH", other_rankings={})
    assert h1 == "NOSUCH is not in the current ranking of the 750."
    assert lede.endswith("Back to the Screener →") and 'href="screener"' in html     # a link, as the others are
    _h1, lede, html = _not_ranked(monkeypatch, "SANSERA", other_rankings={"Nifty 1000": pd.DataFrame(
        {"Symbol": ["SANSERA"], "Rank": [1]})})
    assert "See it in the Nifty 1000 →" in lede and "Back to the Screener" not in lede


def test_st_btn_1():
    src = inspect.getsource(sv._render_actions)
    for caption in ('"In watchlist" if on_list else "Add to watchlist"', '"Share"', '"Chart on TradingView"',
                    '"Remove from your watchlist" if on_list else "Save to your watchlist, kept in this browser"',
                    "Link to this stock's page. Use the copy button on the right.",
                    '"Opens this stock on TradingView in a new tab"'):
        assert caption in src, caption


# ══ §9 The Guide ═════════════════════════════════════════════════════════════

def _guide() -> str:
    # The FAQ quotes the header's pill as "... % above its 200D EMA": an ellipsis, not a doubled stop.
    return _text(gv._body()).replace('"... %', '"%')


def test_gd_head_1(monkeypatch):
    seen = {}
    monkeypatch.setattr(gv.kit, "page_head", lambda title, sub, **kw: seen.update(title=title, sub=sub, **kw))
    monkeypatch.setattr(gv.st, "html", lambda *_a, **_k: None)
    monkeypatch.setattr(gv, "render_data_quality_footer", lambda **_k: None)
    gv.render_guide_view(pd.DataFrame({"Symbol": ["A"], "Short History": ["No"]}))
    assert seen["kicker"] == "Guide"
    assert seen["title"] == "How the ranking picks the book, and how to act on it."
    assert _clean(gv.kit.sentence(seen["sub"])) == "The ranking, the filters, the book and the record, step by step."


@pytest.mark.parametrize("n, want", [(750, "Universe. The 750 stocks of Nifty Total Market as NSE published it on "
                                            "each date, so a stock counts only while it was a member."),
                                     (1012, "Universe. The 1,012 stocks of Nifty Total Market as NSE published it on "
                                            "each date, so a stock counts only while it was a member."),
                                     (None, "Universe. The stocks of Nifty Total Market as NSE published it on each "
                                            "date, so a stock counts only while it was a member.")])
def test_gd_step_1(monkeypatch, n, want):
    monkeypatch.setattr(gv, "_members_now", lambda: n)
    t = _clean(_guide(), signs=False)
    assert want in t and "the Nifty Total Market" not in t and "About 750" not in t
    assert "The Nifty 1000 and the > ₹2,000 Cr list follow the same steps on their own lists." in t


def test_gd_step_1_reads_the_membership_record():
    from src.engine.membership import describe, load_history_or_none
    h = load_history_or_none()
    assert gv._members_now() == (describe(h)["current_size"] if h else None)


@pytest.mark.parametrize("high_pct, gap", [(0.8, "20%"), (0.75, "25%")])
def test_gd_step_3(monkeypatch, high_pct, gap):
    monkeypatch.setitem(TRACK_RECORD_CONFIG, "high_pct", high_pct)
    assert f"Filters. Above its 50D EMA and within {gap} of its 52-week high." in _clean(_guide(), signs=False)


def test_gd_step_4(monkeypatch):
    t = _clean(_guide(), signs=False)
    assert ("Book. The top 20 stocks that pass both filters, at most 8 from one sector. A holding stays while it "
            "ranks within the top 40 and passes both filters. From the 30 Nov 2026 rebalance every holding goes back "
            "to 5% twice a year (March and September); in between, winners run (see Weighting).") in t
    monkeypatch.setitem(TRACK_RECORD_CONFIG, "hold_cap_from", "2027-01-29")
    monkeypatch.setitem(TRACK_RECORD_CONFIG, "buy_size", 0.04)
    monkeypatch.setitem(TRACK_RECORD_CONFIG, "weight_reset_months", [1, 7])
    assert "From the 29 Jan 2027 rebalance every holding goes back to 4% twice a year (January and July)" in _guide()


@pytest.mark.parametrize("limit", [5, 7])
def test_gd_sc_1(monkeypatch, limit):
    from src.engine import calendar_momentum
    monkeypatch.setattr(calendar_momentum, "ANCHOR_STALENESS_LIMIT", limit)
    assert (f"If a stock did not trade that day, its last close up to {limit} sessions before stands in; older than "
            "that, the window has no value for that stock.") in _clean(_guide(), signs=False)


@pytest.mark.parametrize("min_high, months", [(126, 6), (189, 9)])
def test_gd_fl_5(monkeypatch, min_high, months):
    from src.core import config
    monkeypatch.setattr(config, "HIGH_52W_MIN_OBSERVATIONS", min_high)
    t = _clean(_guide(), signs=False)
    assert f"A new listing waits about {months} months" in t
    assert (f"No stock is ranked before 63 sessions of prices, and the 52-week high needs {min_high} closes before "
            f"the near-the-high filter can pass. A recent listing therefore waits about {months} months of trading "
            "before it can be bought.") in t


def test_gd_bk_2(monkeypatch):
    want = ("From the 30 Nov 2026 rebalance a holding that is kept is trimmed only above 15%, not back to 5% (see "
            "Weighting)")
    assert want in _clean(_guide(), signs=False)
    monkeypatch.setitem(TRACK_RECORD_CONFIG, "hold_cap", 0.12)
    assert "is trimmed only above 12%, not back to 5%" in _guide()


def test_gd_wt_2():
    t = _clean(_guide(), signs=False)
    assert ("In between, a holding that stays is left as its price moved it unless it is above 15%, when it is cut to "
            "15%, and each new buy is 5% of the account as it stood at the last reset, paid from cash; when cash is "
            "short the new names get fewer shares, and no holding is sold to pay for them.") in t
    # The paragraph splits after "pay for them."; the test's figures stay a dated quote (rule 14).
    assert "pay for them.</p>\n<p>No sector is above 40% after a rebalance." in gv._body()
    assert ("In the test behind the decision (8 Nov 2026, with an estimate of tax) the monthly reset earned 15.4% a "
            "year after tax and the six-monthly 15.3%") in t


def test_gd_wt_3():
    from src.engine.portfolio import PortfolioOptimizer
    n = int(inspect.signature(PortfolioOptimizer.inverse_volatility).parameters["window"].default)
    assert (f"Inverse volatility can be tried in the Backtest: each holding's weight is proportional to one over its "
            f"volatility over the last {n} sessions.") in _clean(_guide(), signs=False)


def test_gd_faq_4():
    assert ("Does Nifty Total Market's trend change the model? No. The header's \"... % above its 200D EMA\" (or "
            "below) compares the index it names with its 200D EMA, for context. The model holds 20 stocks whatever "
            "the index does and keeps no cash target.") in _text(gv._body())


def test_gd_keep():
    """KEEP rows: the score formulas, Filters, the 52-week-high note, Acting on it and the Questions."""
    body = gv._body()
    t = _text(body)
    w = " + ".join(f"{float(v):.2f}·z({k})" for k, v in zip(("1M", "3M", "6M", "9M", "12M"),
                                                            TRACK_RECORD_CONFIG["config_weights"]))
    assert f"score = ({w}) / (sum of the weights of the windows the stock has)" in body
    assert "Near the high: the close at or above 80% of its 52-week high." in t
    assert "The 52-week high is read from closes" in t
    assert "After the month's last close, open Actions: it lists what to sell and what to buy." in t
    assert ("Why is a stock ranked 14th not in the book? Either it fails a filter (the rank counts every stock; the "
            "book takes only those passing both), or the book is full of holdings still inside the buffer of 40.") in t
    assert "60 bps" not in t or "at 60 and 100 bps every week (section 4)" in t
    for banned in ("12-month", "one year", "1-year"):
        assert banned not in t.lower()


def test_st_rule_4_reads_to_the_fill():
    """Owner, 24 Nov 2026: "Read to the fill". The window and the sentence are Actions' own; the check is never
    called the fill."""
    fill = pd.Timestamp("2026-12-01")
    assert sl.calendar_sentence(CHECK, [], None, fill) == (
        "The rules are checked at the month-end close, next on 30 Nov 2026. "
        "No board meeting or ex-date is announced for it before the 1 Dec fill.")
    assert sl.calendar_sentence(CHECK, [], pd.Timestamp("2026-11-05"), fill) == (
        "The rules are checked at the month-end close, next on 30 Nov 2026. No board meeting or ex-date is "
        "announced for it before the 1 Dec fill (its last results meeting was on 5 Nov).")
    ev = [(pd.Timestamp("2026-12-01"), "TCS", "held", "board meeting")]
    assert sl.calendar_sentence(CHECK, ev, None, fill) == (
        "The rules are checked at the month-end close, next on 30 Nov 2026. "
        "Announced before the 1 Dec fill: board meeting on 1 Dec.")
