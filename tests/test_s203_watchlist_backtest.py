"""S203: the Watchlist and Backtest sentences render their approved templates (owner, 24 Nov 2026).

The templates, by id, are in docs/archive/S203_TEMPLATES_OTHER_PAGES.md, section 6 (wl.*) and section 7 (bt.*);
the owner's answers in section 12. One test per id, KEEP rows included, on the cases the row lists, with fake
inputs and no network. `_clean` fails a sentence with an empty slot, "None", "nan", a "–" inside it, or a doubled
word, as in tests/test_s203_templates.py.
"""
from __future__ import annotations

import html as html_lib
import re

import pandas as pd
import pytest

from src.engine import backtest_page as bp
from src.engine.track_record import TRACK_RECORD_CONFIG as CFG
from src.ui import formats
from src.ui import watchlist_lines as wl
from src.ui.views import backtest_view as bv
from src.ui.views import watchlist_view as wv
from src.ui.views.dashboard_home_view import html_of

CHECK = pd.Timestamp("2026-11-30")
FILL = pd.Timestamp("2026-12-01")
AS_OF = pd.Timestamp("2026-11-20")
LN = wl.Lines(buy=20, keep=40, high_gap=20)


def _text(html: str) -> str:
    return re.sub(r"\s+", " ", html_lib.unescape(re.sub(r"<[^>]+>", "", html))).strip()


def _clean(html: str) -> str:
    t = _text(html)
    assert t, "an empty sentence"
    # "None" begins a sentence ("None of your stocks is a buy."); inside one it is a leaked slot.
    assert not re.search(r"(?<!^)(?<![.;:] )\bNone\b|\b(nan|NaN|NaT)\b", t), t
    for bad in ("{", "}", " – ", "  ", "..", "the the ", "up −", "down −", "made −", "lost −", "12-month", "one year"):
        assert bad not in t.replace(". – in a month:", ". in a month:"), (bad, t)    # the column footnote's own dash
    return t


def _tag(html: str, tag: str) -> list[str]:
    return [_clean(x) for x in re.findall(rf"<{tag}[^>]*>(.*?)</{tag}>", html, flags=re.S)]


def _notes(html: str) -> list[str]:
    return [_clean(x) for x in re.findall(r'<p class="dh-note[^"]*">(.*?)</p>', html, flags=re.S)]


def _subs(html: str) -> list[str]:
    return [_text(x) for x in re.findall(r'<span class="dh-k-sub">(.*?)</span>', html, flags=re.S)]


# ═══ 6. Watchlist ═══════════════════════════════════════════════════════════

def _table(ranks: dict) -> pd.DataFrame:
    return pd.DataFrame({"Symbol": list(ranks), "Qualified Rank": list(ranks.values())})


def _plan(book=(), sells=(), buys=(), nxt=()):
    return wl.BookPlan(AS_OF, CHECK, FILL, sells=list(sells), buys=list(buys), holds=[], next_in_line=list(nxt),
                       book=list(book))


@pytest.mark.parametrize("ranks, n, plan, want", [
    ({"A": 3}, 1, None, "Your 1 stock is in the top 20 qualified."),
    ({"A": 55}, 1, None, "Your 1 stock is not in the top 20 qualified."),
    ({"A": 25, "B": None}, 2, None, "Both of your stocks are outside the top 20 qualified."),
    ({"A": 1, "B": 2}, 2, None, "Both of your stocks are in the top 20 qualified."),
    ({"A": 25, "B": 30, "C": None}, 3, None, "All 3 of your stocks are outside the top 20 qualified."),
    ({"A": 1, "B": 2, "C": 3}, 3, None, "All 3 of your stocks are in the top 20 qualified."),
    ({"A": 3, "B": 30, "C": 60}, 3, None, "1 of your 3 stocks is in the top 20 qualified."),
    ({"A": 3, "B": 4, "C": 60}, 3, None, "2 of your 3 stocks are in the top 20 qualified."),
    # h = 0: the head only
    ({"A": 3, "B": 30, "C": 60}, 3, _plan(book=["Z"]), "1 of your 3 stocks is in the top 20 qualified."),
    ({"A": 3}, 1, _plan(book=["A"]),
     "Your 1 stock is in the top 20 qualified. The book holds it, and would keep it at the 30 Nov check."),
    ({"A": 50}, 1, _plan(book=["A"], sells=["A"]),
     "Your 1 stock is not in the top 20 qualified. The book holds it, and would sell it at the 30 Nov check."),
    ({"A": 3, "B": 30, "C": 60}, 3, _plan(book=["A"]),
     "1 of your 3 stocks is in the top 20 qualified. The book holds one of them, A, and would keep it at the 30 Nov check."),
    ({"A": 3, "B": 30, "C": 60}, 3, _plan(book=["A", "B"]),
     "1 of your 3 stocks is in the top 20 qualified. The book holds 2 of them; none would be sold at the 30 Nov check."),
    ({"A": 3, "B": 30, "C": 60}, 3, _plan(book=["A", "B"], sells=["B"]),
     "1 of your 3 stocks is in the top 20 qualified. The book holds 2 of them; 1 would be sold at the 30 Nov check."),
    ({"A": 3, "B": 30, "C": 60}, 3, _plan(book=["A", "B", "C"], sells=["B", "C"]),
     "1 of your 3 stocks is in the top 20 qualified. The book holds 3 of them; 2 would be sold at the 30 Nov check."),
])
def test_wl_head_1(ranks, n, plan, want):
    assert _clean(wl.title(_table(ranks), n, plan, LN)) == want


@pytest.mark.parametrize("plan, want", [
    (_plan(buys=["A"]), "If today's prices hold, the model book would buy A at the 30 Nov check."),
    (_plan(sells=["B"]), "If today's prices hold, the model book would sell B at the 30 Nov check."),
    (_plan(buys=["A", "C"], sells=["B"]),
     "If today's prices hold, the model book would buy A and C and sell B at the 30 Nov check."),
    (_plan(), "If today's prices hold, the model book would not trade any of your stocks at the 30 Nov check."),
    (_plan(buys=["A"], nxt=["C"]),
     "If today's prices hold, the model book would buy A at the 30 Nov check. C is next in line."),
    (_plan(nxt=["B", "C"]),
     "If today's prices hold, the model book would not trade any of your stocks at the 30 Nov check. "
     "B and C are next in line."),
    (None, "The model book's plan for the next rebalance is not available just now."),
])
def test_wl_head_2(plan, want):
    assert _clean(wl.plan_sentence(_table({"A": 1, "B": 2, "C": 21}), plan)) == want


class _Ctx:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _FakeSt:
    """Streamlit's widgets as no-ops: the view's own sentences are what the tests read."""

    def __init__(self):
        self.session_state = {}

    def __getattr__(self, name):
        return lambda *a, **k: _Ctx()


def _render(monkeypatch, symbols, rank_df, plan=None, system_name="Nifty 750"):
    out = []
    monkeypatch.setattr(wv, "st", _FakeSt())
    monkeypatch.setattr(wv.watchlist_store, "symbols", lambda: list(symbols))
    monkeypatch.setattr(wv, "_emit", lambda parts: out.extend(p for p in parts if p))
    monkeypatch.setattr(wv, "render_screener_table", lambda *a, **k: None)
    monkeypatch.setattr(wv, "render_data_quality_footer", lambda **k: None)
    monkeypatch.setattr(wv, "_nse_lists", lambda: (pd.DataFrame({"old": [], "new": [], "date": []}), set()))
    monkeypatch.setattr(wv, "_fill_section", lambda *a, **k: None)
    monkeypatch.setattr(wl, "book_plan", lambda *a, **k: plan)
    monkeypatch.setattr(wv.formats, "session_of", lambda *_: AS_OF)
    prices = pd.DataFrame({"S1": [1.0, 1.0]}, index=pd.to_datetime(["2026-11-19", "2026-11-20"]))
    wv.render_watchlist_view(rank_df, prices, system_name=system_name)
    return "".join(out)


def _ranking(n: int = 9, fail=(3, 7)) -> pd.DataFrame:
    return pd.DataFrame({
        "Rank": range(1, n + 1), "Symbol": [f"S{i}" for i in range(1, n + 1)],
        "Above 50 EMA": [i not in fail for i in range(1, n + 1)], "Near 52W High": True,
        "Industry": [f"I{i}" for i in range(1, n + 1)], "Company Name": [f"Company {i} Limited" for i in range(1, n + 1)],
    })


def test_wl_head_2_first_sentence(monkeypatch):
    """The lede's first sentence (KEEP): the list and the session it was ranked on."""
    doc = _render(monkeypatch, ["S1"], _ranking(), plan=None)
    lede = _tag(doc, "p")[1]
    assert lede == ("Ranked in the Nifty 750 at the 20 Nov close. "
                    "The model book's plan for the next rebalance is not available just now.")


def test_wl_head_3(monkeypatch):
    doc = _render(monkeypatch, [], _ranking())
    assert _tag(doc, "h1") == ["Your watchlist is empty."]
    assert _tag(doc, "p")[1] == ("Search a stock by name, type symbols and save, or press “Add to watchlist” on any "
                                 "stock's page. The list is kept in this browser only.")


def test_wl_kept_1(monkeypatch):
    doc = _render(monkeypatch, ["S1"], _ranking())
    assert ("Kept in this browser only. Search a stock by name, or press “Add to watchlist” on its page, to add it; "
            "clear the box and save to empty the list.") in [_clean(x) for x in re.findall(
                r'<p class="wl-kept">(.*?)</p>', doc)]


@pytest.mark.parametrize("system_name, want", [
    ("Nifty 750", "None of your symbols is ranked in the Nifty 750."),
    ("> ₹2,000 Cr", "None of your symbols is ranked in > ₹2,000 Cr."),
])
def test_wl_lines_1(system_name, want):
    assert _tag("".join(wv._sec_lines_empty(system_name)), "h2") == [want]


@pytest.mark.parametrize("ranks, plan, want", [
    ({"A": 3, "B": 25}, _plan(buys=[]), "None of your stocks is a buy. B is the nearest below the buy line, "
                                        "5 places short of the top 20."),
    ({"A": 3, "B": 21}, _plan(buys=["A"]), "A is the one buy. B is the nearest below the buy line, "
                                           "1 place short of the top 20."),
    ({"A": 3, "C": 4, "B": 60}, _plan(buys=["A", "C"]), "A and C are the buys. B is the nearest below the buy line, "
                                                        "40 places short of the top 20."),
    ({"A": 3}, _plan(buys=["A"]), "A is the one buy."),
    ({"A": 3, "B": 45}, None, "B is the nearest below the buy line, 25 places short of the top 20."),
    ({"A": None, "B": None}, None, "None of your stocks is qualified: each fails a filter."),
])
def test_wl_lines_2(ranks, plan, want):
    assert _clean(wl.lines_heading(_table(ranks), plan, LN)) == want


def _lines_doc(monkeypatch, plan):
    out = []
    monkeypatch.setattr(wv, "_emit", lambda parts: out.extend(p for p in parts if p))
    monkeypatch.setattr(wv, "render_screener_table", lambda *a, **k: None)
    from src.ui.views import ranking_view
    monkeypatch.setattr(ranking_view, "_month_ago", lambda prices, m: pd.Timestamp({3: "2026-08-19", 1: "2026-10-19"}[m]))
    table = _table({"A": 3, "B": 25})
    table["Rank"] = [4, 30]
    wv._lines_section(table, None, plan, LN, 750)
    return "".join(out)


def test_wl_lines_3(monkeypatch):
    doc = _lines_doc(monkeypatch, None)
    assert ("Your stocks in rank order, grouped by where they sit against the book's lines: it buys the top 20 "
            "qualified and keeps a holding while it is in the top 40.") in _notes(doc)


@pytest.mark.parametrize("has_plan", [True, False])
def test_wl_lines_4(monkeypatch, has_plan):
    doc = _lines_doc(monkeypatch, _plan(buys=["A"]) if has_plan else None)
    keys = [_clean(x) for x in re.findall(r'<div class="wl-keys">(.*?)</div>', doc, flags=re.S)[0].split("</p>") if _text(x)]
    assert keys[0] == ("Qualified: above the 50D EMA and within 20% of the 52-week high. The qualified place is the "
                       "stock's place among them, the number Actions and the Dashboard use; “Out” means it failed a "
                       "filter that day.")
    assert keys[1] == ("Rank before: the rank among the 750 ranked stocks on 19 Aug and 19 Oct, the dates the "
                       "Dashboard's rank trail uses. Past figures are grey.")
    assert keys[2] == ("30 Nov: what the model book would do at the next rebalance if today's prices hold, from the plan "
                       "Actions shows; “–” where it neither holds nor buys the stock. Held: in the model book."
                       if has_plan else
                       "Plan: “–” on every row: the model book's plan could not be read just now. Held: in the model book.")
    assert keys[3] == "A click on a heading sorts every stock and drops the groups; Rank brings them back."


def test_wl_lines_5(monkeypatch):
    doc = _lines_doc(monkeypatch, None)
    assert ("On a wider screen: rank among the 750 ranked stocks, the trail 3M and 1M ago, returns, filters and the "
            "60-day line.") in _notes(doc)


@pytest.mark.parametrize("q, held, ema, high, want", [
    (None, False, False, False, "fails both filters"),
    (None, False, False, True, "fails the 50D EMA filter"),
    (None, False, True, False, "fails the 52W-high filter"),
    (20, True, True, True, "the 20th, the last place the book buys"),
    (19, False, True, True, "1 place inside the top 20; not held"),
    (5, True, True, True, "15 places inside the top 20"),
    (40, True, True, True, "the 40th, the last place a holding is kept"),
    (21, True, True, True, "1 place short of the top 20"),
    (41, True, True, True, "1 place past the 40th"),
    (45, True, True, True, "5 places past the 40th"),
])
def test_wl_place_1(q, held, ema, high, want):
    assert wl.place_note(q, held, ema, high, LN) == want


def test_wl_grp_1():
    assert [wl.group_heading(k, LN) for k in wl.ORDER] == [
        ("Top 20 qualified", "the book buys from these"), ("21st to 40th qualified", "kept if held, not bought"),
        ("Qualified, past the 40th", "a holding here is sold"), ("Fails a filter", "not bought; a holding is sold")]


def _nr_ranking():
    return pd.DataFrame({"Rank": [1, 2, 3], "Symbol": ["S1", "NEWNAME", "S3"], "Above 50 EMA": [True, True, False],
                         "Near 52W High": [True, True, False], "Company Name": ["One Ltd", "New Name Limited", "Three"]})


def test_wl_nr_1():
    changes = pd.DataFrame({"old": ["OLDNAME", "GONE"], "new": ["NEWNAME", "ELSE"],
                            "date": pd.to_datetime(["2025-10-24", "2020-01-01"])})
    others = {"Nifty 750": pd.DataFrame({"Symbol": ["BIG"] + [f"X{i}" for i in range(749)], "Rank": range(12, 762)})}
    rows = wl.not_ranked(["OLDNAME", "GONE", "BIG", "NEWCO", "LISTEDCO", "ZZZ"], _nr_ranking(), universe="> ₹2,000 Cr",
                         members=["NEWCO"], changes=changes, listed={"LISTEDCO"}, others=others, ln=LN)
    by = {r.symbol: (r.why, r.where) for r in rows}
    assert by["OLDNAME"] == ("NSE changed the symbol to NEWNAME (New Name) on 24 Oct 2025.",
                             "NEWNAME ranks 2nd of the 3 and is 2nd among the qualified.")
    assert by["GONE"] == ("NSE changed the symbol to ELSE on 1 Jan 2020.", "ELSE is not ranked in > ₹2,000 Cr either.")
    assert by["BIG"] == ("Not a member of the > ₹2,000 Cr. It leaves out the Nifty 750’s stocks.",
                         "Ranks 12th of 750 in the Nifty 750.")
    assert by["NEWCO"] == ("In > ₹2,000 Cr, but too new to rank.", "It needs about three months of prices.")
    assert by["LISTEDCO"] == ("Listed on NSE, but in none of the systems' lists.", "–")
    assert by["ZZZ"] == ("Not a symbol NSE lists today.", "–")
    for why, _where in by.values():
        _clean(why)


def test_wl_nr_1_the_1000_reads_as_the_screener():
    """The 1000's unranked members: "its history is being collected", the Screener's reason (sc.sys.1)."""
    rows = wl.not_ranked(["NEWCO"], _nr_ranking(), universe="Nifty 1000", members=["NEWCO"], ln=LN)
    assert (rows[0].why, rows[0].where) == ("In the Nifty 1000, but not ranked yet: its history is being collected.",
                                            "It needs about three months of prices.")
    rows = wl.not_ranked(["NEWCO"], _nr_ranking(), universe="Nifty 750", members=["NEWCO"], ln=LN)
    assert rows[0].why == "In the Nifty 750, but too new to rank."


def test_wl_nr_1_months_from_the_engine(monkeypatch):
    from src.engine import momentum
    monkeypatch.setattr(momentum, "MIN_OBSERVATIONS", 126)
    assert wl.too_new_words("Nifty 750")[1] == "It needs about six months of prices."


@pytest.mark.parametrize("sym, want", [
    ("S1", "S1 ranks 1st of the 3 and is 1st among the qualified."),
    ("S3", "S3 ranks 3rd of the 3 and fails both filters."),
])
def test_wl_nr_2(sym, want):
    assert wl._ranked_words(sym, _nr_ranking(), "Nifty 750", LN) == want


def test_wl_nr_3():
    U = wl.Unranked
    one = [U("A", wl.RENAMED, "", "")]
    assert wl.not_ranked_heading(one, "Nifty 750") == "1 of your symbols is not in the Nifty 750: 1 was renamed."
    rows = [U("A", wl.RENAMED, "", ""), U("B", wl.RENAMED, "", ""), U("C", wl.TOO_NEW, "", ""),
            U("D", wl.LISTED, "", ""), U("E", wl.UNKNOWN, "", ""), U("F", wl.ELSEWHERE, "", "", system="> ₹2,000 Cr"),
            U("G", wl.ELSEWHERE, "", "", system="> ₹2,000 Cr"), U("H", wl.ELSEWHERE, "", "", system="> ₹2,000 Cr")]
    assert _clean(wl.not_ranked_heading(rows, "Nifty 750")) == (
        "8 of your symbols are not in the Nifty 750: 2 were renamed, 1 is too new to rank, 1 is in no system's list, "
        "1 is not a known symbol, 3 are in > ₹2,000 Cr.")


@pytest.mark.parametrize("events, want", [
    ([], "No board meeting or ex-date is announced for your stocks before the 1 Dec fill."),
    ([(AS_OF, "A", "held", "board meeting")], "1 board meeting or ex-date is announced before the 1 Dec fill, for A."),
    ([(AS_OF, "A", "held", "board meeting"), (AS_OF, "B", "to buy", "ex-date"), (AS_OF, "A", "held", "ex-date")],
     "3 board meetings or ex-dates are announced before the 1 Dec fill, for A and B."),
])
def test_wl_fill_1(events, want):
    assert _clean(wl.fill_heading(events, FILL)) == want


def _rep(*pairs):
    return pd.DataFrame({"symbol": [p[0] for p in pairs], "date": pd.to_datetime([p[1] for p in pairs])})


@pytest.mark.parametrize("reported, n, want", [
    (_rep(("A", "2026-11-05")), 1, "A held its last results meeting on 5 Nov."),
    (_rep(("A", "2026-11-05"), ("B", "2026-10-20")), 2,
     "Every ranked stock on your list held its last results meeting between 20 Oct (B) and 5 Nov (A)."),
    (_rep(("A", "2026-11-05")), 3, "1 of the 3 ranked stocks on your list held its last results meeting on 5 Nov (A)."),
    (_rep(("A", "2026-11-05"), ("B", "2026-10-20")), 3,
     "2 of the 3 ranked stocks on your list held their last results meetings between 20 Oct (B) and 5 Nov (A)."),
    (None, 3, ""),
])
def test_wl_fill_2(reported, n, want):
    got = wl.reported_sentence(reported, n)
    assert got == want and (not want or _clean(got) == want)


def test_wl_fill_3(monkeypatch):
    out = []
    from src.engine import results_calendar as rc
    from src.ui.views import actions_page
    monkeypatch.setattr(wv, "_emit", lambda parts: out.extend(p for p in parts if p))
    monkeypatch.setattr(actions_page, "_events", lambda *a: ([(pd.Timestamp("2026-11-26"), "A", "to buy", "board meeting")],
                                                             "Board meetings from NSE's calendar."))
    monkeypatch.setattr(rc, "load", lambda: None)
    wv._fill_section(pd.DataFrame({"Symbol": ["A"]}), _plan(buys=["A"]))
    items = re.findall(r"<li>(.*?)</li>", "".join(out))
    assert [_clean(x) for x in items] == ["A (to buy) board meeting, 26 Nov"]


@pytest.mark.parametrize("syms, matched, want", [
    ([], [], "Data to 20 Nov 2026 · NSE."),
    (["S1", "ZZZ"], [], "Data to 20 Nov 2026 · NSE. 0 of your 2 symbols are ranked among the 9."),
    (["S1", "ZZZ"], ["S1"], "Data to 20 Nov 2026 · NSE. 1 of your 2 symbols is ranked among the 9; each scored on all "
                            "five horizons, none with a price gap."),
    (["S1", "S2", "ZZZ"], ["S1", "S2"], "Data to 20 Nov 2026 · NSE. 2 of your 3 symbols are ranked among the 9; 1 of "
                                        "the 2 scored on all five horizons, none with a price gap."),
])
def test_wl_foot_1(syms, matched, want):
    r = _ranking()
    r["Horizons Scored"] = [5, 4, 5, 5, 5, 5, 5, 5, 5]
    assert _clean(wv._foot(AS_OF, syms, r[r["Symbol"].isin(matched)], r)) == want


# ═══ 7. Backtest ════════════════════════════════════════════════════════════

def _sm(**kw) -> bp.Summary:
    base = dict(first=pd.Timestamp("2010-02-01"), last=pd.Timestamp("2026-10-30"), years=16.7, a_year=0.182,
                bench_a_year=0.121, lead=0.061, total=15.0, bench_total=5.0, months=201, ahead=120, up=130,
                lead_first_half=0.0012, lead_second_half=-0.0005, split=pd.Timestamp("2018-06-29"), median_lead=0.0008)
    base.update(kw)
    return bp.Summary(**base)


S = {"top_n": 20, "rebal_freq": 21, "weight_method": "Equal Weight", "buffer_n": 40, "cost_bps": 30.0,
     "ema_period": 50, "high_pct": 0.8, "ath_pct": None, "exit_ema_period": None, "exit_high_pct": None,
     "exit_ath_pct": None, "ath_min_years": 3.0, "score_method": "sharpe", "weights": tuple(CFG["config_weights"]),
     "rule": "live"}


def _f(**kw) -> dict:
    sm = kw.pop("summary", None) or _sm()
    f = {"s": dict(S), "h": {"key": "nifty_500", "name": "Nifty 500", "start": pd.Period("2010-02", "M"),
                             "end": pd.Period("2026-10", "M"), "floor": 0.0, "moved": None, "priced": 1429,
                             "unlabelled": 0},
         "default": True, "summary": sm, "stats": {"pit_periods": 200, "current_universe_periods": 0},
         "chart": {"dates": ["2010-02-05", "2026-10-30"], "series": {"rule": [100, 1600], "n500": [100, 600]},
                   "dd": {"rule": [0, -5], "n500": [0, -8]}},
         "div_yield": 1.3, "div_yield_from": pd.Timestamp("2012-02-21"), "uidx_name": None, "uidx_short": None,
         "tm_from": pd.Timestamp("2021-10-14"), "tm_window_from": pd.Timestamp("2021-11-01"),
         "falls": [bp.Fall(-0.35, pd.Timestamp("2024-09-27"), pd.Timestamp("2025-03-03"), None, 400)],
         "bench_falls": [bp.Fall(-0.40, pd.Timestamp("2020-01-17"), pd.Timestamp("2020-03-23"), pd.Timestamp("2020-11-09"), 297)],
         "below_now": -0.12, "bench_below_now": -0.08, "current_peak": pd.Timestamp("2024-09-27"), "current_days": 400,
         "years": None, "monthly": pd.DataFrame(), "mtd": None, "alternatives": [], "windows_from": [],
         "reference": None, "long_last": pd.Timestamp("2026-11-16"), "stale": [], "short": [], "trades": {},
         "indices_as_of": pd.Timestamp("2026-11-20")}
    f.update(kw)
    return f


def test_bt_tested_1():
    h = _f()["h"]
    assert _clean(bv.tested_line(S, h)) == (
        "What was tested Nifty 500 · Feb 2010 to Oct 2026 · 20 holdings · keep to rank 40 · rebalanced monthly, at the "
        "month’s last close · skip 0 days · Sharpe score · buy above its 50D EMA · within 20% of its 52-week high · "
        "six-monthly reset, winners run to 15% · 30 bps a round trip")


@pytest.mark.parametrize("sm, want", [
    (_sm(), "Since February 2010, this rule made 18.2% a year, against a gain of 12.1% for the Nifty 500, before tax."),
    (_sm(a_year=0.09, bench_a_year=0.121),
     "Since February 2010, this rule made 9.0% a year, against a gain of 12.1% for the Nifty 500, before tax."),
    (_sm(a_year=0.121, bench_a_year=0.121),
     "Since February 2010, this rule made 12.1% a year, against a gain of 12.1% for the Nifty 500, before tax."),
    (_sm(a_year=-0.03, bench_a_year=-0.05),
     "Since February 2010, this rule lost 3.0% a year, against a loss of 5.0% for the Nifty 500, before tax."),
    (_sm(a_year=None, bench_a_year=None, lead=None, months=8, total=0.05, bench_total=0.03),
     "Over 8 months, this rule returned 5.0%, against a gain of 3.0% for the Nifty 500."),
    (_sm(a_year=None, bench_a_year=None, lead=None, months=8, total=-0.04, bench_total=-0.06),
     "Over 8 months, this rule lost 4.0%, against a loss of 6.0% for the Nifty 500."),
    (_sm(bench_a_year=None, lead=None), "Since February 2010, this rule made 18.2% a year, before tax."),
])
def test_bt_head_1(sm, want):
    assert _tag(html_of(bv.head(_f(summary=sm))), "h1") == [want]


@pytest.mark.parametrize("default, who", [(True, "The record’s rules"), (False, "These rules")])
def test_bt_head_2(default, who):
    doc = html_of(bv.head(_f(default=default)))
    assert _tag(doc, "p")[1] == (f"{who} replayed on the Nifty 500 as it stood each month, 1 Feb 2010 to 30 Oct 2026, on "
                                 "NSE’s closes, after 30 bps a round trip. Price returns on both sides. A replay of the "
                                 "past, not a forecast.")


def test_bt_head_3(monkeypatch):
    from src.engine import index_universe as iu
    monkeypatch.setattr(iu, "index_history", lambda key: {"x": 1})
    monkeypatch.setattr(iu, "first_month", lambda m: pd.Period("2015-04", "M"))
    monkeypatch.setattr(iu, "ever_members", lambda m: ["A"])
    monkeypatch.setitem(iu.INDICES, "nifty_midcap_150", "Nifty Midcap 150")
    monkeypatch.setattr(bv, "_run_frame", lambda *a: (pd.DataFrame({"A": [1.0]}, index=[pd.Timestamp("2026-10-30")]), "fp"))
    monkeypatch.setattr(bv.bp, "industry_map", lambda cols, ind: ({}, 0))
    monkeypatch.setattr(bv.bp, "index_file_industries", lambda: {})
    months = list(pd.period_range("2010-02", "2026-10", freq="M"))
    bounds = {"close": None, "report": {}, "months": months}
    choice = {"index": "nifty_midcap_150", "start": pd.Period("2012-01", "M"), "end": months[-1], "floor": 0}
    h = bv._history_inputs(pd.DataFrame(), choice, bounds)
    assert h["moved"] == "Nifty Midcap 150's point-in-time list begins Apr 2015, so the test starts there."
    choice["start"] = months[0]            # the default start: not said
    assert bv._history_inputs(pd.DataFrame(), choice, bounds)["moved"] is None


@pytest.mark.parametrize("default", [True, False])
def test_bt_head_4(default):
    doc = html_of(bv.head(_f(default=default)))
    warn = [_clean(x) for x in re.findall(r'<p class="bt-warn">(.*?)</p>', doc, flags=re.S)]
    assert warn == ([] if default else [
        "Warning: These settings differ from the record’s. A setting chosen after seeing its result on this same "
        "history flatters the result; only months after a rule was fixed test it."])


@pytest.mark.parametrize("system, want", [
    ("750", []),
    ("1000", ["The Nifty 1000 system does not change these runs: each run picks its own index in the settings below."]),
    ("nano", ["The > ₹2,000 Cr system does not change these runs: each run picks its own index in the settings below."]),
])
def test_bt_head_5(monkeypatch, system, want):
    from src.engine.extra_universe import SYSTEM_1000, SYSTEM_750, SYSTEM_NANO
    from src.ui import system_param
    got = []
    monkeypatch.setattr(system_param, "current", lambda: {"750": SYSTEM_750, "1000": SYSTEM_1000, "nano": SYSTEM_NANO}[system])
    monkeypatch.setattr(bv.kit, "note", lambda text, *a, **k: got.append(text))
    bv._system_note()
    assert got == want


@pytest.mark.parametrize("sm, want", [
    (_sm(), "The rule is ahead of the Nifty 500 by 6.1 points a year; it was ahead in 120 of 201 months."),
    (_sm(lead=-0.023), "The rule is behind the Nifty 500 by 2.3 points a year; it was ahead in 120 of 201 months."),
    (_sm(lead=0.0004), "The rule is level with the Nifty 500 over the run."),
    (_sm(a_year=None, bench_a_year=None, lead=None, months=8, total=0.05, bench_total=-0.02),
     "Under 12 months, so no yearly figure: the rule is up 5.0%, the Nifty 500 down 2.0%."),
    (_sm(ahead=201), "The rule is ahead of the Nifty 500 by 6.1 points a year; it was ahead in 201 of 201 months."),
])
def test_bt_lead_1(sm, want):
    assert _tag(html_of(bv.section_lead(_f(summary=sm))), "h2") == [want]


@pytest.mark.parametrize("sm, want", [
    (_sm(), ["Nifty 500 12.1%", "a year", "Nifty 500 ₹600", "60% · up in 130 months"]),
    (_sm(a_year=None, bench_a_year=None, lead=None, months=8, ahead=5, up=1, total=0.05, bench_total=0.03),
     ["needs 12 months", "over the run", "Nifty 500 ₹103", "62% · up in 1 month"]),
])
def test_bt_lead_2(sm, want):
    assert _subs(html_of(bv.section_lead(_f(summary=sm)))) == want


PRICE_NOTE = ("Price returns, both sides. The rule’s figure includes a dividend only where it was 10% of the price or "
              "more (the long file takes those out as an adjustment); the Nifty 500 figure is NSE’s price index, which "
              "takes out only special dividends, 2% of the price or more (NSE’s index methodology, Nov 2022), not "
              "ordinary ones")


@pytest.mark.parametrize("dy, want", [
    (1.3, PRICE_NOTE + ". NSE’s file puts the Nifty 500’s dividend yield at 1.3% a year on average since Feb 2012; in a "
               "test of 11 Nov 2026 the book’s was about 0.5%, measured 2020–25 only. Against the index with every "
               "dividend, the lead is about 0.8 points a year smaller than shown."),
    (None, PRICE_NOTE + "."),
])
def test_bt_lead_3(dy, want):
    assert _notes(html_of(bv.section_lead(_f(div_yield=dy))))[0] == want


def test_bt_lead_4():
    assert _notes(html_of(bv.section_lead(_f())))[1] == (
        f"A year, compounded is measured over calendar time, 16.7 years from the first fill. pts: {formats.PTS_NOTE}")


@pytest.mark.parametrize("kw, want", [
    ({}, "Why the Nifty 500 and not Nifty Total Market. Nifty Total Market starts on 14 Oct 2021 and this history in "
         "2010 (owner, 21 Nov 2026). Nifty Total Market is beside it from 2022 in section 3 and from Nov 2021 in section 4."),
    ({"uidx_name": "Nifty Midcap 150"},
     "Why the Nifty 500 and not Nifty Total Market. Nifty Total Market starts on 14 Oct 2021 and this history in "
     "2010 (owner, 21 Nov 2026). Nifty Total Market is beside it from 2022 in section 3 and from Nov 2021 in section 4. "
     "For this universe its own index, the Nifty Midcap 150, is shown beside both."),
    ({"tm_from": None, "tm_window_from": None},
     "Why the Nifty 500 and not Nifty Total Market. This history starts in 2010, before Nifty Total Market "
     "(owner, 21 Nov 2026). Nifty Total Market is beside it from 2022 in section 3."),
])
def test_bt_lead_5(kw, want):
    assert _notes(html_of(bv.section_lead(_f(**kw))))[2] == want


@pytest.mark.parametrize("a, b, m, want", [
    (0.0012, -0.0005, 0.0008, "The two halves. To May 2018, the rule was ahead by 0.12 points a month on average; after "
                              "it, behind by 0.05. The median month’s lead was +0.08 points."),
    (-0.0012, 0.0021, -0.0003, "The two halves. To May 2018, the rule was behind by 0.12 points a month on average; "
                               "after it, ahead by 0.21. The median month’s lead was −0.03 points."),
    (0.0012, 0.00001, None, "The two halves. To May 2018, the rule was ahead by 0.12 points a month on average; after "
                            "it, level."),
])
def test_bt_lead_6(a, b, m, want):
    notes = _notes(html_of(bv.section_lead(_f(summary=_sm(lead_first_half=a, lead_second_half=b, median_lead=m)))))
    assert notes[3] == want


def test_bt_lead_7():
    doc = html_of(bv.section_lead(_f()))
    assert ("₹100 put in at the first fill and left to the rule, against ₹100 in the Nifty 500, weekly closes on a log "
            "scale (equal heights are equal percentage moves).") in _text(doc)


OPEN = bp.Fall(-0.35, pd.Timestamp("2024-09-27"), pd.Timestamp("2025-03-03"), None, 400)
SHUT = bp.Fall(-0.35, pd.Timestamp("2020-01-17"), pd.Timestamp("2020-03-23"), pd.Timestamp("2021-03-05"), 413)


@pytest.mark.parametrize("now, falls, want", [
    (-0.12, [OPEN], "The rule is 12.0% below its September 2024 peak. Its max drawdown since 2010, 35.0%, is not yet "
                    "made back."),
    (-0.12, [SHUT], "The rule is 12.0% below its September 2024 peak. Its max drawdown, 35.0%, was made back by "
                    "5 Mar 2021."),
    (0.0, [SHUT], "The rule is at its peak. Its max drawdown was 35.0%, made back by 5 Mar 2021."),
    (0.0, [], "The rule is at its peak."),
])
def test_bt_fall_1(now, falls, want):
    assert _tag(html_of(bv.section_falls(_f(below_now=now, falls=falls))), "h2") == [want]


@pytest.mark.parametrize("now, want", [
    (-0.12, ["Nifty 500 −8.0%", "Nifty 500 −40.0%", "since 27 Sep 2024", "needs +13.6%"]),
    (0.0, ["Nifty 500 −8.0%", "Nifty 500 −40.0%", "at its peak", ""]),
])
def test_bt_fall_2(now, want):
    assert _subs(html_of(bv.section_falls(_f(below_now=now)))) == want


def test_bt_fall_3():
    assert _notes(html_of(bv.section_falls(_f()))) == [
        "A fall runs from the highest close before it to the day that close is regained; days are calendar days. "
        "Daily closes, as on Portfolio (metrics.drawdown)."]


def _years(rows):
    """(year, first month, last month, rule, Nifty 500)."""
    return pd.DataFrame([{"year": y, "first_month": a, "last_month": b, "months": b - a + 1, "rule": r, "n500": n}
                         for y, a, b, r, n in rows])


def _monthly(start="2010-02", end="2014-10"):
    idx = pd.period_range(start, end, freq="M").to_timestamp(how="end").normalize()
    return pd.DataFrame({"rule": 0.01, "bench": 0.005}, index=idx)


YEARS = [(2010, 2, 12, 0.20, 0.10), (2011, 1, 12, 0.15, 0.10), (2012, 1, 12, 0.02, 0.103), (2013, 1, 12, 0.12, 0.10),
         (2014, 1, 10, 0.05, 0.08)]


@pytest.mark.parametrize("rows, want", [
    (YEARS, "The rule was ahead of the Nifty 500 in 2 of 3 whole years. 2012 was the worst, 8.3 points behind. "
            "2010, from Feb, was ahead. 2014, to Oct, was behind."),
    ([YEARS[0], YEARS[1], YEARS[3]], "The rule was ahead of the Nifty 500 in 2 of 2 whole years. 2010, from Feb, was ahead."),
    (YEARS[1:4], "The rule was ahead of the Nifty 500 in 2 of 3 whole years. 2012 was the worst, 8.3 points behind."),
    ([(2026, 3, 10, 0.05, 0.02)], "2026, from Mar to Oct, was ahead."),
])
def test_bt_yr_1(rows, want):
    doc = html_of(bv.section_years(_f(years=_years(rows), monthly=_monthly())))
    assert _tag(doc, "h2") == [want]


@pytest.mark.parametrize("mtd, tail", [
    (None, ""),
    ({"label": "November", "as_of": pd.Timestamp("2026-11-20"), "rule": 0.012, "bench": -0.004},
     " November so far, to 20 Nov 2026, is not in the table: this rule is up 1.2%, the Nifty 500 down 0.4%."),
    ({"label": "November", "as_of": pd.Timestamp("2026-11-20"), "rule": -0.012, "bench": None},
     " November so far, to 20 Nov 2026, is not in the table: this rule is down 1.2%."),
])
def test_bt_yr_2(mtd, tail):
    doc = html_of(bv.section_years(_f(years=_years(YEARS), monthly=_monthly(), mtd=mtd)))
    assert _notes(doc)[0] == ("A dark zero line; a lead left of it is a year behind. The first year starts at the first "
                              "fill, 1 Feb 2010. Nifty Total Market is NSE’s index, live from 14 Oct 2021, so it starts "
                              "in 2022." + tail)


@pytest.mark.parametrize("start, end, note, blanks", [
    ("2026-08", "2026-10", "Lead in pts. A year compounds its months; the first year from the first fill. – in a month: "
                           "before Aug 2026, the replay's first month.", 2),
    ("2025-01", "2025-12", "Lead in pts. A year compounds its months; the first year from the first fill.", 0),
])
def test_bt_yr_3(start, end, note, blanks):
    grid = bv.months_grid(_monthly(start, end))
    assert _notes(grid) == [note]
    # After the last month tested: a blank cell, not "– not published yet" (owner's answer 8).
    assert grid.count('<td class="dh-num"></td>') == blanks * 3
    assert "not published" not in grid


def _ref(**rows):
    base = {"as_tested": 0.182, "nifty_500": 0.121, "cost_60": 0.17, "cost_100": 0.16, "monthly_reset": 0.175}
    base.update(rows)
    return {"rows": {k: v for k, v in base.items() if v is not None}, "after_tax": {"rule": 0.15, "nifty_500": 0.11,
                                                                                     "rates": "STCG 20%, LTCG 12.5%"},
            "built": "2026-11-16", "long_last_session": "2026-11-16"}


@pytest.mark.parametrize("ref, want", [
    (_ref(), "Tax costs the lead 2.1 points a year. Costs matter more than the rebalance rule."),
    (_ref(monthly_reset=0.16), "Tax costs the lead 2.1 points a year. The rebalance rule matters more than costs."),
    (_ref(cost_60=0.172, monthly_reset=0.172), "Tax costs the lead 2.1 points a year. Costs and the rebalance rule "
                                               "matter about as much."),
    ({**_ref(cost_60=None, monthly_reset=None), "after_tax": {}}, "The stored tests for the default run are not in yet."),
])
def test_bt_dep_1(ref, want):
    assert _tag(html_of(bv.section_depends(_f(reference=ref))), "h2") == [want]


@pytest.mark.parametrize("last, stale", [
    ("2026-11-16", ""),
    ("2026-11-09", " These tests were run on the long file to 9 Nov 2026; this page reads the file to 16 Nov 2026, so "
                   "they can differ slightly until the next weekly run."),
])
def test_bt_dep_2(last, stale):
    ref = {**_ref(), "long_last_session": last}
    assert _notes(html_of(bv.section_depends(_f(reference=ref))))[0] == (
        "The rows other than “As tested” and “Nifty 500” are re-run once a week on the default settings only (run of "
        "16 Nov 2026). After tax: STCG 20%, LTCG 12.5%, for an investor with no other gains; the index position is "
        "taxed once, long term, when sold." + stale)


def test_bt_dep_3():
    doc = html_of(bv.section_depends(_f(reference=None)))
    assert _tag(doc, "h2") == ["Costs, the rebalance rule and tax are tested for the default run only."]
    assert _notes(doc) == ["These settings are not the default, so the stored tests (60 and 100 bps, the monthly reset, "
                           "after tax) do not apply to them. Change the cost or the rule above to see either here."]


ALTS = [("Since Nifty200 Momentum 30 went live", "1 Apr 2020 – 30 Oct 2026", [("Nifty 500", 0.15, -0.2)])]


@pytest.mark.parametrize("starts, tail", [
    ([pd.Timestamp("2020-04-01"), pd.Timestamp("2021-11-01")], " These windows are short and include this rule’s max drawdown."),
    ([pd.Timestamp("2025-01-01")], " These windows are short."),
])
def test_bt_dep_4(starts, tail):
    notes = _notes(html_of(bv.section_depends(_f(alternatives=ALTS, windows_from=starts))))
    assert notes[-1] == "NSE’s Nifty200 Momentum 30 is the nearest index a fund tracks; it is a price index too." + tail


def _rows(doc: str) -> dict:
    return {_text(a): _clean(b) for a, b in re.findall(r'<tr><th scope="row">(.*?)</th><td>(.*?)</td>', doc, flags=re.S)}


@pytest.mark.parametrize("stale, want", [
    ([], "Valued at their last price. No sale used a price five or more sessions old."),
    ([{"symbol": "A", "exit": pd.Timestamp("2014-05-02"), "sessions": 7}],
     "Valued at their last price. 1 sale used a price 7 sessions old (A), in 2014: stocks taken over or delisted, sold "
     "at their last price."),
    ([{"symbol": "B", "exit": pd.Timestamp("2019-05-02"), "sessions": 9},
      {"symbol": "A", "exit": pd.Timestamp("2014-05-02"), "sessions": 6}],
     "Valued at their last price. 2 sales used a price 6 to 9 sessions old (A, B), 2014–2019: stocks taken over or "
     "delisted, sold at their last price."),
])
def test_bt_tr_1(stale, want):
    assert _rows(html_of(bv.section_trust(_f(stale=stale))))["Stocks that stopped trading"] == want


def _months(n):
    return [(pd.Timestamp(f"2020-{4 + i:02d}-01"), 10 + i) for i in range(n)]


@pytest.mark.parametrize("short, want", [
    ([], "Every rebalance found enough stocks that passed the rules."),
    (_months(1), "At April 2020’s rebalance only 10 stocks passed the rules. The rest of the book sat in cash at 0% "
                 "until the next rebalance."),
    ([(pd.Timestamp("2020-04-01"), 1)], "At April 2020’s rebalance only 1 stock passed the rules. The rest of the book "
                                        "sat in cash at 0% until the next rebalance."),
    (_months(3), "At April 2020’s rebalance only 10 stocks passed the rules; at May 2020’s, only 11; at June 2020’s, "
                 "only 12. The rest of the book sat in cash at 0% until the next rebalance."),
    (_months(4), "At April 2020’s rebalance only 10 stocks passed the rules; at May 2020’s, only 11; at June 2020’s, "
                 "only 12; 1 more rebalance was short too. The rest of the book sat in cash at 0% until the next rebalance."),
    (_months(5), "At April 2020’s rebalance only 10 stocks passed the rules; at May 2020’s, only 11; at June 2020’s, "
                 "only 12; 2 more rebalances were short too. The rest of the book sat in cash at 0% until the next "
                 "rebalance."),
])
def test_bt_tr_2(short, want):
    assert _rows(html_of(bv.section_trust(_f(short=short))))["Cash"] == want


def test_bt_tr_3():
    rows = _rows(html_of(bv.section_trust(_f())))
    assert rows["Survivorship"] == ("200 of 200 rebalances picked from the Nifty 500 as it stood that day, leavers "
                                    "included; the long file prices all 1,429 stocks the lists ever named.")
    assert rows["Costs"] == ("30 bps a round trip: about 22 statutory, the rest for the spread, which has not been "
                             "measured. The last book’s sale is not charged.")
    assert rows["Sector cap"] == "Uses today’s sector labels for every year, not the label of the day."
    # No vendor in a sentence (rule 13): an outside dataset, not "the Kaggle dataset".
    assert rows["The index before Feb 2012"] == ("Nifty 500 closes before 21 Feb 2012 come from an outside dataset, not "
                                                 "yet checked against NSE’s own file (S167).")
    assert "The index before Feb 2012" not in _rows(html_of(bv.section_trust(_f(summary=_sm(first=pd.Timestamp("2013-01-01"))))))
    assert "Kaggle" not in bv.Path(bv.__file__).read_text(encoding="utf-8").split("def section_trust")[1].split("def ")[0]


@pytest.mark.parametrize("cur, first, want", [
    (0, "2010-02-01", "Survivorship and look-ahead are handled; costs, tax and the choice of rules are the soft spots; "
                      "3 checks are not made."),
    (5, "2013-01-01", "Look-ahead is handled; survivorship, costs, tax and the choice of rules are the soft spots; "
                      "2 checks are not made."),
])
def test_bt_tr_4(cur, first, want):
    f = _f(summary=_sm(first=pd.Timestamp(first)), stats={"pit_periods": 195, "current_universe_periods": cur})
    assert _tag(html_of(bv.section_trust(f)), "h2") == [want]
    # k = 0: the last clause dropped
    assert bv.trust_headline([("Look-ahead", "", "Checked"), ("Costs", "", "Soft spot")]) == (
        'Look-ahead is handled; <span class="dh-watch">costs</span> is the soft spot.')


def test_bt_trd_1():
    assert _tag(html_of(bv.section_trades_head(_f(trades={}))), "h2") == ["No trade closed in this run."]
    assert _tag(html_of(bv.section_trades_head(_f(trades={"closed": 0, "open": 3}))), "h2") == ["No trade closed in this run."]


def _trades(won, pf):
    return {"closed": 1200, "open": 20, "won": won, "median_days": 90.0, "median_return": 0.03, "mean_return": 0.05,
            "profit_factor": pf}


@pytest.mark.parametrize("won, pf, want", [
    (0.55, 1.8, "1,200 trades closed; 55% won. The winners paid for the losers: gains were 1.80 times the losses."),
    (0.45, 1.4, "1,200 trades closed; fewer than half won (45%). The winners paid for the losers: gains were 1.40 times "
                "the losses."),
    (0.45, 0.9, "1,200 trades closed; fewer than half won (45%)."),
    (0.55, 1.0, "1,200 trades closed; 55% won."),
    (0.55, None, "1,200 trades closed; 55% won."),
])
def test_bt_trd_2(won, pf, want):
    assert _tag(html_of(bv.section_trades_head(_f(trades=_trades(won, pf)))), "h2") == [want]


def test_bt_trd_3():
    doc = html_of(bv.section_trades_head(_f(trades=_trades(0.55, 1.8))))
    # The last two, average win and loss and best and worst, came back on 28 Nov 2026 (S239 item 8).
    assert _subs(doc)[:5] == ["20 still held", "of closed trades", "entry fill to exit fill", "mean +5.0%",
                              "each trade weighted by its size at entry"]
    assert all(t in doc for t in ("Average win", "Average loss", "Best trade", "Worst trade"))
    assert _notes(doc) == ["Every trade, the rebalance log and the rebalance periods are below; the live record’s trades are on Portfolio, "
                           "which owns the record."]


@pytest.mark.parametrize("idx, want", [
    (pd.Timestamp("2026-11-20"), "Data to 30 Oct 2026 · NSE’s long price file, the last completed month · prices to "
                                 "16 Nov 2026 · indices to 20 Nov 2026."),
    (None, "Data to 30 Oct 2026 · NSE’s long price file, the last completed month · prices to 16 Nov 2026."),
])
def test_bt_foot_1(idx, want):
    assert _clean(html_of(bv.foot(_f(indices_as_of=idx)))) == want


def test_bt_err_1(monkeypatch):
    got = []
    monkeypatch.setattr(bv.kit, "page_empty", lambda title, lede, *a, **k: got.append((title, lede)))
    monkeypatch.setattr(bv, "_long_file", lambda: None)
    assert bv._history_bounds() is None
    short = pd.DataFrame({"A": [1.0, 1.0]}, index=pd.to_datetime(["2026-01-02", "2026-06-30"]))
    monkeypatch.setattr(bv, "_long_file", lambda: (short, None, {}))
    assert bv._history_bounds() is None
    assert got == [("No long price file yet.", "It is built each week from NSE's daily files; the Backtest runs once it is in."),
                   ("No completed month to test yet.", "The long price file needs a year of prices before its first month.")]
    # The note when a run has too little history: "12 months of prices", not "a 12M lookback" (glossary 6).
    src = bv.Path(bv.__file__).read_text(encoding="utf-8")
    assert '"The rules need 12 months of prices before the first "\n                 "month tested; pick a later start above."' in src
    assert "12M lookback" not in src


def test_bt_dep_from_2012_column():
    """S174 "1 a" D1 (owner, 22 Nov 2026): each stored test also from Mar 2012, NSE's own index closes only."""
    late = {"as_tested": 0.198, "monthly_reset": 0.201, "cost_60": 0.183, "cost_100": 0.162, "nifty_500": 0.118,
            "window": ["2012-03-01", "2026-10-30"]}
    parts = bv.section_depends(_f(reference={**_ref(), "from_2012": late}))
    assert "From 1 Mar 2012: each test re-run from that month, on NSE’s own Nifty 500 closes only" in html_of(parts)
    spec = next(p.spec for p in parts if getattr(p, "kind", "") == "trows")
    assert spec["head"] == ["A year", "From 1 Mar 2012, a year"]
    vals = {r["name"]: r["vals"] for r in spec["rows"]}
    assert vals["As tested"][1] == "19.8%" and vals["Nifty 500"][1] == "11.8%" and vals["After tax"][1] == "–"

def test_bt_dep_no_from_2012_column_before_the_weekly_run_stores_it():
    doc = html_of(bv.section_depends(_f(reference=_ref())))
    assert "From 1 Mar 2012" not in doc and "From Mar 2012" not in doc
