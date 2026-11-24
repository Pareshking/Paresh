"""S203: the Actions and shared sentences render their approved templates (owner, 24 Nov 2026).

The templates, by id, are in docs/archive/S203_TEMPLATES_OTHER_PAGES.md (§0 "Shared", cm.*, and §1 "Actions",
ac.*). One test per id, KEEP rows included, on the cases the row lists, with fake inputs and no network. `_clean`
fails a sentence with an empty slot, "None", "nan", a "–" inside it, or a doubled word.
"""
from __future__ import annotations

import html
import re

import numpy as np
import pandas as pd
import pytest

from src.engine import exit_watch as xw
from src.engine.exit_watch import Rules, assess, qualified_ranks
from src.engine.swap_evidence import SwapEvidence
from src.ui import formats
from src.ui.views import actions_page as ap
from src.ui.views import actions_view as av
from src.ui.views import qualified_view as qv

NOV = pd.Timestamp("2026-11-20")
CHECK = pd.Timestamp("2026-11-30")
FILL = pd.Timestamp("2026-12-01")
CFG = {"buy_size": 0.05, "hold_cap_from": "2026-11-30"}


def _text(s: str, sep: str = "") -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", sep, s))).strip()


def _page(parts) -> str:
    """A section's text, tables included (a blank cell is "–", so `_clean` is run on its sentences only)."""
    return _text("".join(parts), " ")


def _notes(parts) -> list[str]:
    """Each sentence block of a section (its notes, list items and evidence box), each through `_clean`."""
    blocks = re.findall(r'<(?:p|li|div) class="(?:dh-note|ac-ev|ac-none)"[^>]*>(.*?)</(?:p|div)>|<li>(.*?)</li>',
                        "".join(parts), flags=re.S)
    return [_clean(a or b) for a, b in blocks]


def _sec(parts) -> str:
    parts = list(parts)
    _notes(parts)
    return _page(parts)


def _clean(s: str) -> str:
    t = _text(s)
    assert t, "an empty sentence"
    assert not re.search(r"\b(None|nan|NaN|NaT)\b", t), t
    for bad in ("{", "}", " – ", "..", "the the ", "is is ", "ahead by −", "behind by −"):
        assert bad not in t, (bad, t)
    return t


def _row(sym, rank, ema=5.0, high=-2.0, above=True, near=True, cmp=100.0, ind="Banks", short="No", gap=""):
    return {"Symbol": sym, "Rank": rank, "% 50 EMA": ema, "% High": high, "Above 50 EMA": above,
            "Near 52W High": near, "CMP": cmp, "Industry": ind, "Short History": short, "Data Gap": gap}


EMA_28 = 100 * (1 / (1 - 0.028) - 1)          # 2.8% above its 50D EMA: a 2.8% fall reaches it
HIGH_24 = 100 * (0.8 / (1 - 0.024) - 1)       # a 2.4% fall reaches the −20% line


def _why(rows, sym, rules=Rules(), sessions=None):
    a = assess(pd.DataFrame(rows), [sym], rules, sessions).set_index("Symbol")
    return a.loc[sym, "why"]


def _plan(**kw) -> ap.Plan:
    rank_df = kw.pop("rank_df", pd.DataFrame([_row("H1", 1), _row("H2", 2), _row("B1", 3), _row("B2", 4),
                                              _row("S5", 50, ema=-3.0, above=False, cmp=341.0)]))
    holds = kw.pop("holds", ["H1", "H2"])
    sells = kw.pop("sells", ["S5"])
    rules = kw.pop("rules", Rules())
    base = dict(source="Model book", as_of=NOV, check=CHECK, fill=FILL, sessions=6, holiday_note="", sells=sells,
                buys=["B1", "B2"], holds=holds, next_in_line=["N1"], weights=pd.Series({"B1": 0.25, "B2": 0.25}),
                assess=assess(rank_df, holds + sells, rules), trails={}, qrank=qualified_ranks(rank_df),
                rank_df=rank_df, value=2.44e7, shares={"S5": 10_000}, rules=rules,
                events_note=ap.events_note(None, None, FILL))
    base.update(kw)
    return ap.Plan(**base)


def _ev(**kw) -> SwapEvidence:
    base = dict(buys=12, sold=9, buy_1m=3.1, sold_1m=0.24, buy_3m=5.25, sold_3m=-1.0, rebought=2,
                first=pd.Timestamp("2026-02-01"), last=pd.Timestamp("2026-11-01"))
    base.update(kw)
    return SwapEvidence(**base)


# ── §0 Shared (cm.) ─────────────────────────────────────────────────────────

def test_cm_foot_1():
    rd = pd.DataFrame([_row("A", 1, gap="🔴"), _row("B", 2, short="Yes"), _row("C", 3, gap="🔴", short="Yes")])
    assert _clean(formats.foot_line(rd, NOV)) == ("Data to 20 Nov 2026 · NSE. 3 stocks ranked; 2 with a price gap, "
                                                  "2 with a short history.")
    one = rd.iloc[[0, 1]]
    assert formats.foot_line(one, NOV) == "Data to 20 Nov 2026 · NSE. 2 stocks ranked; 1 with a price gap, 1 with a short history."
    assert formats.foot_line(rd.iloc[[1]], None) == ("Data from NSE. 1 stock ranked; none with a price gap, "
                                                     "1 with a short history.")                     # date missing; g = 0
    assert formats.foot_line(rd.iloc[[0]], NOV).endswith("1 with a price gap, none with a short history.")   # s = 0
    # The Actions page draws it from that one function.
    assert _sec(ap.footer(_plan(rank_df=rd, holds=["A"], sells=[]))) == formats.foot_line(rd, NOV)


def test_cm_rule_1():
    rows = [_row("A", 1, ema=-0.25, above=False)]
    assert _why(rows, "A") == "0.3% below its 50D EMA"           # half up (glossary 12): :.1f gave 0.2
    rows = [_row("A", 1, ema=np.nan, above=False)]
    assert _why(rows, "A") == "below its 50D EMA"                # no reading


def test_cm_rule_2():
    assert _why([_row("A", 1, high=-25.0, near=False)], "A") == "more than 20% below its 52-week high"
    young = [_row("A", 1, high=np.nan, near=False, short="Yes")]
    assert _why(young, "A", sessions={"A": 70}) == "too new to have a 52-week high: 70 of 126 sessions"
    assert _why(young, "A") == "too new to have a 52-week high"   # sessions unknown


def test_cm_rule_3():
    rows = [_row("A", 1), _row("B", 2), _row("C", 3, high=0.0)]
    a = assess(pd.DataFrame(rows), ["C"], Rules(buffer_n=2)).set_index("Symbol")
    assert a.loc["C", "status"] == xw.SELL
    # The phrase reads after "it is" (stock page st.rule.1: "it is 3rd among …", never "it is ranks #3").
    assert a.loc["C", "why"] == "3rd among the qualified, past the top 2"


@pytest.mark.parametrize("buffer_n, want", [
    (12, "is 3rd among the qualified, 9 places inside the top 12"),
    (4, "is 3rd among the qualified, 1 place inside the top 4"),
    (3, "is 3rd among the qualified, the last place kept"),
])
def test_cm_rule_4(buffer_n, want):
    rows = [_row("A", 1), _row("B", 2), _row("C", 3, ema=20.0, high=0.0)]
    assert _why(rows, "C", Rules(buffer_n=buffer_n)) == want


def test_cm_rule_5():
    assert _why([_row("A", 1, ema=EMA_28, high=0.0)], "A") == "can fall 2.8% before it reaches its 50D EMA"
    assert _why([_row("A", 1, ema=20.0, high=HIGH_24)], "A") == (
        "can fall 2.4% before it reaches the −20% line from its 52-week high")
    assert _why([_row("A", 1, ema=EMA_28, high=HIGH_24)], "A") == (
        "can fall 2.8% before it reaches its 50D EMA; can fall 2.4% before it reaches the −20% line from its 52-week high")


def test_cm_rule_6():
    rows = [_row("A", 1), _row("B", 2), _row("C", 3, ema=EMA_28, high=HIGH_24)]
    assert _why(rows, "C", Rules(buffer_n=3)) == (                                          # 3 reasons
        "is 3rd among the qualified, the last place kept; can fall 2.8% before it reaches its 50D EMA; "
        "can fall 2.4% before it reaches the −20% line from its 52-week high")
    assert _why([_row("A", 1, ema=-0.25, high=-25.0, above=False, near=False)], "A") == (    # 2 reasons
        "0.3% below its 50D EMA; more than 20% below its 52-week high")
    assert _why([_row("A", 1, ema=-0.25, above=False)], "A") == "0.3% below its 50D EMA"     # 1 reason


def test_cm_late_1():
    assert formats.closes_not_in(["Nifty 50"], NOV) == "NSE’s 20 Nov close for Nifty 50 is not in yet."
    assert formats.closes_not_in(["Nifty 50", "Nifty Bank", "Nifty IT"], NOV) == (
        "NSE’s 20 Nov closes for Nifty 50, Nifty Bank and Nifty IT are not in yet.")
    assert formats.closes_not_in([f"Nifty {i}" for i in range(5)], NOV) == (
        "NSE’s 20 Nov closes for 5 of these indices are not in yet.")
    assert formats.closes_not_in([], NOV) == ""


# ── §1 Actions (ac.) ────────────────────────────────────────────────────────

def test_ac_head_1():
    p = _plan()
    sell_amt, buy_amt = 10_000 * 341.0, 2.44e7 * 0.5
    assert _clean(ap.title(p, sell_amt, buy_amt)) == ("1 sell and 2 buys at the 30 Nov check, filled on 1 Dec. "
                                                      "₹34.1 lakh out and ₹1.22 Cr in.")
    two = _plan(sells=["S5", "H2"], holds=["H1"])
    assert _clean(ap.title(two, sell_amt, buy_amt)).startswith("2 sells and 2 buys at the 30 Nov check")
    # Zero on one side: in ink, not a verdict colour.
    no_sell = ap.title(_plan(sells=[]), 0, buy_amt)
    assert _clean(no_sell) == "No sells and 2 buys at the 30 Nov check, filled on 1 Dec. ₹1.22 Cr in."
    assert no_sell.startswith("No sells and ") and '<span class="dh-up">2 buys</span>' in no_sell
    no_buy = ap.title(_plan(buys=[]), sell_amt, 0)
    assert _clean(no_buy) == "1 sell and no buys at the 30 Nov check, filled on 1 Dec. ₹34.1 lakh out."
    assert _clean(ap.title(_plan(sells=[], buys=[]))) == (
        "No trade at the 30 Nov check: every holding is clear of the sell rules.")
    # My holdings: no share counts, so no "out".
    mine = _plan(source="My holdings", shares={})
    assert _clean(ap.title(mine, 0, buy_amt)) == "1 sell and 2 buys at the 30 Nov check, filled on 1 Dec. ₹1.22 Cr in."
    assert _clean(ap.title(mine, 0, 0)) == "1 sell and 2 buys at the 30 Nov check, filled on 1 Dec."
    # The header draws it from the plan's own amounts.
    assert "1 sell and 2 buys at the 30 Nov check, filled on 1 Dec. ₹34.1 lakh out and ₹1.22 Cr in." in _clean(
        "".join(ap.header(p)))


def test_ac_head_2():
    assert ap.subtitle(_plan()) == "What the model book would trade at the next rebalance, if today's prices hold."
    assert ap.subtitle(_plan(source="My holdings")) == "Your holdings under the record's rules, if today's prices hold."


def test_ac_head_3():
    t = _sec(ap.header(_plan()))
    for want in ("breaks a sell rule at today's close", "₹34.1 lakh to sell", "best qualified, not held",
                 "₹1.22 Cr to buy", "all clear of the rules", "6 sessions away · fills Tue 1 Dec"):
        assert want in t, want
    t = _sec(ap.header(_plan(sells=["S5", "H2"], holds=["H1"])))
    assert "break a sell rule at today's close" in t
    t = _sec(ap.header(_plan(sells=[], buys=[], sessions=1, holiday_note="NSE holidays not yet published")))
    assert "none breaks a sell rule" in t and "1 session away · fills Tue 1 Dec" in t
    assert "NSE holidays not yet published" in t and "to sell" not in t and "to buy" not in t
    rd = pd.DataFrame([_row("H1", 1, ema=EMA_28, high=0.0), _row("B1", 2)])
    t = _sec(ap.header(_plan(rank_df=rd, holds=["H1"], sells=[])))
    assert "1 close to a rule" in t


def test_ac_chg_1():
    rd = pd.DataFrame([_row("H1", 1, ema=EMA_28, high=0.0), _row("H2", 2)])
    t = _sec(ap.section_change(_plan(rank_df=rd, sells=[], buys=[])))
    assert "H1 can fall 2.8% before it reaches its 50D EMA." in t
    t = _sec(ap.section_change(_plan(sells=[])))
    assert "No holding is close to a sell rule." in t


def test_ac_chg_2():
    t = _sec(ap.section_change(_plan()))
    assert "Holdings close to a sell rule could still change to a sale" in t
    assert "Next in line would come in if a buy drops out or another holding breaks a rule" in t
    assert "Results and corporate actions before the fill to 1 Dec" in t


def test_ac_chg_3():
    p = _plan(events=[(pd.Timestamp("2026-11-25"), "H1", "held", "Results")])
    assert "H1 (held) Results, 25 Nov" in _clean(ap._events_html(p))


def test_ac_chg_4():
    assert _clean(ap._events_html(_plan())) == (
        "No board meeting or ex-date is announced for any holding, sell or buy before the 1 Dec fill.")


def test_ac_chg_5():
    cal, ca = pd.Timestamp("2026-12-05"), pd.Timestamp("2026-12-03")
    assert ap.events_note(cal, ca, FILL) == ("Board meetings are from NSE's calendar, announced to 5 Dec. "
                                             "Ex-dates are from NSE's corporate actions, collected to 3 Dec. "
                                             "Dates are as companies announced them and can move.")
    assert ap.events_note(None, ca, FILL) == ("Ex-dates are from NSE's corporate actions, collected to 3 Dec. "
                                              "Dates are as companies announced them and can move.")     # no calendar
    assert ap.events_note(cal, None, FILL, ca_read=False) == (
        "Board meetings are from NSE's calendar, announced to 5 Dec. "
        "NSE's corporate-action file could not be read just now. Dates are as companies announced them and can move.")
    assert ap.events_note(cal, pd.Timestamp("2026-11-27"), FILL) == (
        "Board meetings are from NSE's calendar, announced to 5 Dec. "
        "Ex-dates are from NSE's corporate actions, collected to 27 Nov; later ones are not in yet. "
        "Dates are as companies announced them and can move.")                    # ex-dates end before the fill


def test_ac_after_1():
    p = _plan(now_weights=pd.Series({"H1": 0.5, "H2": 0.5}))
    t = _sec(ap.section_after(p))
    assert ("Now: each stock at its weight today, after it has moved since the last fill. After: the weights the record "
            "strikes at the rebalance. Size by NSE’s index lists today: Large Cap is the Nifty 100,") in t
    assert "(our own groups, not NSE indices). pts = percentage points: 12% − 8% = 4 pts." in t


def test_ac_sell_1():
    t = _sec(ap.section_sell(_plan(sells=[])))
    assert t == "Sell none at today's close"                         # the note that repeated the tile is dropped
    assert "Nothing breaks" not in t


def test_ac_sell_2():
    assert ("Sell in full. The basket carries these sells with the model book's share counts."
            in _sec(ap.section_sell(_plan())))
    assert ("Sell in full. Your share counts are not known, so the basket has no sells."
            in _sec(ap.section_sell(_plan(source="My holdings", shares={}))))


def test_ac_sell_3():
    assert "On a wider screen each row also shows when it was bought." in _sec(ap.section_sell(_plan()))


def test_ac_buy_1():
    # Every place is taken: qualified stocks sit outside the book, but no sell frees a place.
    p = _plan(sells=[], buys=[])
    assert ap.no_buy_line(p) == "No stock that passes both filters is free to buy: every place is taken."
    assert "No stock that passes both filters is free to buy: every place is taken." in _sec(ap.section_buy(p))
    # The qualified list is all held.
    rd = pd.DataFrame([_row("H1", 1), _row("H2", 2), _row("S5", 3, above=False)])
    p = _plan(rank_df=rd, buys=[])
    assert ap.no_buy_line(p) == "No stock that passes both filters is outside the book."


def test_ac_buy_2():
    assert ap.amounts_line(_plan(value=1.0234567e7)) == (
        "Amounts are the record's target weight of the model book's value today, ₹1.02 Cr.")
    assert ap.amounts_line(_plan(source="My holdings", value=2.5e6)) == (
        "Amounts are each buy's target weight of ₹25.0 lakh, the capital in the Kite basket box.")


def test_ac_buy_3():
    assert ap.buy_limit_line(0.0425, 4, CFG) == (
        "Each buy gets 4.3%, less than the 5% buy size. The record does not trim a kept stock to make room, "
        "so the buys share the 17.0% the sells free up. This is the six-monthly rule, in force from the "
        "30 Nov 2026 rebalance.")                                         # 4.25 half up; the date read from the config
    assert ap.buy_limit_line(0.05, 4, CFG) == ""                         # at the buy size: no sentence
    assert ap.buy_limit_line(0.04, 2, {"buy_size": 0.05}).endswith("the buys share the 8.0% the sells free up.")


def test_ac_buy_4():
    s = ap.swaps_sentences(_ev())
    assert s == ["In their first month, the record's 12 buys were ahead by 3.1 points on Nifty Total Market on average.",
                 "The 9 stocks it sold were ahead by 0.2 points in the month after the sale.",
                 "Over 3 months: +5.3 against −1.0 points.",
                 "2 of the 9 sold were bought back within 2 months."]
    s = ap.swaps_sentences(_ev(buy_1m=-0.5, sold_1m=-1.25, buy_3m=None, rebought=0))
    assert s == ["In their first month, the record's 12 buys were behind by 0.5 points on Nifty Total Market on average.",
                 "The 9 stocks it sold were behind by 1.3 points in the month after the sale.",
                 "None of the 9 sold was bought back within 2 months."]   # no 3M figures: the third is dropped
    s = ap.swaps_sentences(_ev(buy_1m=0.04, sold_1m=-0.01, rebought=1, unpriced=("JBCHEPHARM",)))
    assert s[:2] == ["In their first month, the record's 12 buys were level with Nifty Total Market on average.",
                     "The 9 stocks it sold were level with Nifty Total Market in the month after the sale."]
    assert s[3:] == ["1 of the 9 sold was bought back within 2 months.", "JBCHEPHARM has no price here and is left out."]
    s = ap.swaps_sentences(_ev(unpriced=("A", "B")))
    assert s[-1] == "A, B have no price here and are left out."
    t = _clean(ap.swaps_html(_ev()))
    assert t.startswith("What swaps have added so far. In their first month")
    assert t.endswith("Feb 2026 to Nov 2026: a short record, measured on the record itself, before costs, with "
                      "overlapping windows; evidence, not proof.")
    assert ap.swaps_html(None) == ""


def test_ac_buy_5():
    assert ("On a wider screen each row also shows the weight, the 3- and 6-month returns and the distance from the "
            "52-week high.") in _sec(ap.section_buy(_plan()))


def test_ac_hold_1():
    rd = pd.DataFrame([_row("H1", 1), _row("H2", 2), _row("H3", 3, high=0.0), _row("H4", 9, above=False)])
    p = _plan(rank_df=rd, holds=["H1", "H2"], sells=["H3", "H4"], rules=Rules(buffer_n=2))
    t = _sec(ap.section_hold(p))
    assert "1 to go" in t and "0 to go" in t
    p = _plan(rank_df=rd, holds=["H3", "H4"], sells=[], rules=Rules(buffer_n=2))
    t = _sec(ap.section_hold(p))
    assert "past 2" in t and "off the list" in t


def test_ac_hold_2():
    rd = pd.DataFrame([_row("H1", 1)])
    p = _plan(rank_df=rd, holds=["H1", "GONE"], sells=[])
    assert "GONE Not ranked No sell rule can be checked: the stock is not ranked today." in _sec(ap.section_hold(p))


def test_ac_hold_3():
    assert ap.hold_note(Rules()) == (
        "Ordered by the least room on any sell rule; a full rank buffer counts as a 20% fall. “To 50D EMA” and "
        "“To −20% from 52W high” are how far the price can fall from today before it crosses that line. "
        "Rank 3M · 1M · now: the place among the stocks that pass both filters, 3 months ago, a month ago and now; "
        "\"Out\" means it does not pass them.")
    assert "“To −25% from 52W high”" in ap.hold_note(Rules(high_pct=0.75))      # read from the rules, not typed
    assert "To −20% from 52W high" in _sec(ap.section_hold(_plan()))  # the table's own heading


def test_ac_kite_1():
    assert ap.kite_caption(_plan(source="My holdings")) == (
        "Buy orders only, each at its target weight of the capital above; your share counts are not known.")
    assert ap.kite_caption(_plan(value=1.0234567e7)) == (
        "The model book's sell orders, with its share counts, and its buy orders, each at the record's target weight "
        "of the book's value today, ₹1.02 Cr.")


def test_ac_empty_1():
    assert ap.MY_EMPTY == ("Add your holdings above,", "or upload the holdings CSV from Kite, to see what to do with them.")


@pytest.mark.parametrize("name, month, want", [
    ("Nano Cap", "2026-10", "The Nano Cap model book forms at the 30 Sep 2026 close; its record starts in October 2026."),
    # 31 Oct 2026 is a Saturday: the last session is the Friday, from NSE's calendar.
    ("Nifty 1000", "2026-11", "The Nifty 1000 model book forms at the 30 Oct 2026 close; its record starts in "
                              "November 2026."),
])
def test_ac_empty_2(name, month, want):
    assert ap.record_start_line(name, month) == want


def test_ac_qual_1():
    assert qv.LEDE == "Best-ranked stocks passing both filters."


def test_ac_qual_2():
    assert qv.no_pass_lines(0.8) == ("No stock passes both filters today.",
                                     "They are a close above the 50D EMA and within 20% of the 52-week high.")
    assert qv.no_pass_lines(0.75)[1].endswith("within 25% of the 52-week high.")
    assert qv.no_pass_lines() == qv.no_pass_lines(0.8)                   # the record's own rule


def test_ac_qual_3():
    df = pd.DataFrame({"Industry": ["Banks"] * 5 + ["Capital Goods"] * 4 + ["IT", "Power", "Auto", "Metals",
                                                                             "Oil", "FMCG", "Chemicals",
                                                                             "Realty", "Media", "Telecom",
                                                                             "Textiles"]})
    assert qv.concentration_line(df) == "Banks and Capital Goods hold 45% of the list."
    tie = pd.DataFrame({"Industry": ["Banks"] * 4 + ["IT"] * 2 + ["Power"] * 2 + ["Auto", "Oil"]})
    assert qv.concentration_line(tie) == "Banks, IT and Power hold 80% of the list."
    spread = pd.DataFrame({"Industry": list("ABCDEFGHIJ")})
    assert qv.concentration_line(spread) == ""                            # under 40%: no sentence
    assert qv.concentration_line(pd.DataFrame({"Industry": ["Banks"] * 3})) == ""


def test_ac_view_1():
    # Dropped: nothing on a page called them (S203 ac.view.1).
    for name in ("fill_due_note", "rows_html", "sells_html", "buys_html"):
        assert not hasattr(av, name), name
    assert not hasattr(qv, "correlation_note")
