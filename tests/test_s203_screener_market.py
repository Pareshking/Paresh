"""S203: the Screener and Market sentences render their approved templates (owner, 24 Nov 2026).

The templates, by id, are in docs/archive/S203_TEMPLATES_OTHER_PAGES.md, section 2 (sc.*) and section 3 (mk.*),
with the owner's answers in section 12. One test per id, KEEP rows included, on the cases the row lists, with
fake inputs and no network. `_clean` fails a sentence with an empty slot, "None", "nan", a "–" inside it, or a
doubled word. Rows held back (the proposed text did not fit the code; see the hand-over) test today's text.
"""
from __future__ import annotations

import contextlib
import re
from pathlib import Path
from types import SimpleNamespace as N

import pandas as pd
import pytest

from src.engine import market_questions as mq
from src.engine.extra_universe import SYSTEM_750, SYSTEM_1000, SYSTEM_NANO, UNIVERSE_SHORT
from src.engine.track_record import TRACK_RECORD_CONFIG as CFG
from src.ui import components
from src.ui import screener_table as stt
from src.ui.views import market_questions_view as mqv
from src.ui.views import ranking_view as rv

ROOT = Path(__file__).resolve().parents[1]
SYSTEMS = (SYSTEM_750, SYSTEM_1000, SYSTEM_NANO)
BUY, KEEP = int(CFG["top_n"]), int(CFG["buffer_n"])
GAP = round((1 - float(CFG["high_pct"])) * 100)
PX = pd.DataFrame({"A": 1.0}, index=pd.bdate_range("2026-08-03", "2026-11-20"))   # 1M rank read on 20 Oct


def _text(html: str) -> str:
    return re.sub(r"<[^>]+>", "", html)


def _clean(html: str) -> str:
    t = _text(html)
    assert t, "an empty sentence"
    assert not re.search(r"\b(None(?! of)|nan|NaN|NaT)\b", t), t
    for bad in ("{", "}", " – ", "  ", "..", "the the ", "up −", "down −", "rose −", "fell −"):
        assert bad not in t, (bad, t)
    return t


def _src(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


# ── 2. Screener ─────────────────────────────────────────────────────────────

def _ranks(n_top: int, n_pass: int, prev=None) -> pd.DataFrame:
    df = pd.DataFrame({"Symbol": [f"S{i}" for i in range(n_top)], "Rank": range(1, n_top + 1),
                       "Above 50 EMA": [i < n_pass for i in range(n_top)], "Near 52W High": True})
    if prev is not None:
        df["Rank (-1M)"] = prev
    return df


@pytest.mark.parametrize("n_top, n_pass, prev, want", [
    (50, 49, [70] * 23 + list(range(1, 28)), "49 of the top 50 pass both filters. 23 of them were not in the top 50 on 20 Oct."),
    (50, 0, [70] + list(range(1, 50)), "None of the top 50 passes both filters. 1 of them was not in the top 50 on 20 Oct."),
    (50, 50, list(range(1, 51)), "All of the top 50 pass both filters. All of them were in the top 50 on 20 Oct."),
    (50, 1, None, "1 of the top 50 passes both filters."),
    (50, 49, [None] * 50, "49 of the top 50 pass both filters."),                  # 1M rank missing: second dropped
])
def test_sc_head_1(n_top, n_pass, prev, want):
    assert _clean(rv.screener_title(_ranks(n_top, n_pass, prev), PX)) == want


def test_sc_head_1_no_ranking_and_no_date():
    assert rv.screener_title(pd.DataFrame()) == "No stock is ranked yet."
    assert rv.screener_title(None) == "No stock is ranked yet."
    assert rv.screener_title(_ranks(3, 2, [70, 2, 3])) == "2 of the top 3 pass both filters. 1 of them was not in the top 3 a month ago."


@pytest.mark.parametrize("system", SYSTEMS)
def test_sc_head_2(system):
    uni = UNIVERSE_SHORT[system]
    df = _ranks(750, 300)
    want = (f"The 750 ranked stocks of the {uni}, by momentum at the 20 Nov close. "
            f"The book buys the top {BUY} qualified and keeps a holding while it is in the top {KEEP}.")
    assert _clean(rv.screener_lede(df, PX, uni)) == want
    assert rv.screener_lede(df, None, uni).startswith(f"The 750 ranked stocks of the {uni}, by momentum. ")   # no date


def test_sc_head_2_follows_the_config(monkeypatch):
    monkeypatch.setitem(CFG, "top_n", 25)
    monkeypatch.setitem(CFG, "buffer_n", 45)
    assert rv.screener_lede(_ranks(3, 3), None).endswith("buys the top 25 qualified and keeps a holding while it is in the top 45.")


def _chip(n_pass: int) -> list[str]:
    df = pd.DataFrame({"Symbol": [f"S{i}" for i in range(60)], "Rank": range(1, 61),
                       "Above 50 EMA": [i < n_pass for i in range(60)], "Near 52W High": True})
    return [s.text for s in components.compute_signals(df) if "pass both filters" in s.text]


def test_sc_chip_1():
    # Shown under the book's buy count (S203 Q3: it tested 15 and said 20), not at it.
    assert _chip(BUY - 1) == [f"Fewer than {BUY} pass both filters: the book cannot fill its {BUY} places."]
    assert _chip(BUY) == []


def test_sc_key_1():
    from src.engine.momentum import VOLUME_SPIKE, VOLUME_WINDOW
    key = _clean(rv._KEY_HTML.split("</style>")[1].format(when="on 20 Aug and 20 Oct", **rv._key_numbers(PX)))
    assert f"Qualified: above the 50D EMA and within {GAP}% of the 52-week high." in key
    assert "Rank before: the rank among the ranked stocks on 20 Aug and 20 Oct, the dates the Dashboard's rank trail uses." in key
    assert f"The book buys the top {BUY} qualified and keeps a holding while it is in the top {KEEP};" in key
    assert (f"Big movers: rank moved {rv.BIG_MOVE_PLACES} places or more since 20 Oct. Volume spike: today's volume "
            f"{VOLUME_SPIKE:g} times its {VOLUME_WINDOW}-day average or more.") in key
    assert "places or more in a month." in rv._KEY_HTML.format(when="x", **rv._key_numbers())   # no prices


def _row(**kw) -> dict:
    base = {"Symbol": "AAA", "Rank": 1, "CMP": 100.0, "Score": 2.0, "Qualified Rank": 1, "Held": False,
            "Above 50 EMA": True, "Near 52W High": True, "% 50 EMA": 4.0, "% High": -3.0, "Volume": "Normal"}
    return {**base, **kw}


def test_sc_cut_1():
    html = stt.table_html(pd.DataFrame([_row(Symbol="B", **{"Qualified Rank": BUY}),
                                        _row(Symbol="K", Rank=2, **{"Qualified Rank": KEEP})]), None, "Full Quant (35)")
    assert f"The book buys to here: the {BUY}th qualified" in html
    assert f"A holding is kept to here: the {KEEP}th qualified" in html


def test_sc_cell_1():
    assert stt.cell_title_ema(-3.25) == "3.3% below its 50D EMA"                   # half up, not 3.2
    assert stt.cell_title_high(-28.45) == f"28.5% below its 52-week high; the filter is within {GAP}%"
    html = stt.table_html(pd.DataFrame([_row(**{"Qualified Rank": None, "Above 50 EMA": False, "Near 52W High": False,
                                               "% 50 EMA": -3.24, "% High": -28.4})]), None, "Full Quant (35)")
    assert "3.2% below its 50D EMA" in html and f"28.4% below its 52-week high; the filter is within {GAP}%" in html


def test_sc_mv_1():
    assert rv._movers_heading(PX) == "What moved since 20 Oct"
    assert rv._movers_heading(None) == "What moved in the last month"


def _movers(monkeypatch, df, px=PX) -> str:
    out = []
    monkeypatch.setattr(rv.st, "html", out.append)
    rv.render_top50_changes(df, px)
    return out[0]


def _mv_df() -> pd.DataFrame:
    return pd.DataFrame({"Symbol": ["A", "B", "C", "D"], "Rank": [1, 2, 60, 70], "Rank (-1M)": [170, 2, 3, 80],
                         "Industry": "Banks", "1M Return": 0.05})


def test_sc_mv_2(monkeypatch):
    # Owner, 24 Nov 2026: "…furthest into it" (the biggest climb INTO the top 50, S189 item 2).
    h2 = _clean(re.search(r'<h2 class="mv-h">(.*?)</h2>', _movers(monkeypatch, _mv_df())).group(1))
    assert h2 == "1 stock entered the top 50 since 20 Oct and as many left. A climbed furthest into it, 169 places, from 170th to 1st."
    tie = _mv_df().assign(**{"Rank (-1M)": [170, 2, 3, 80]})
    tie.loc[1, ["Rank", "Rank (-1M)"]] = [2, 171]
    h2 = _clean(re.search(r'<h2 class="mv-h">(.*?)</h2>', _movers(monkeypatch, tie)).group(1))
    assert "A and B climbed furthest into it, 169 places each." in h2


def test_sc_mv_3(monkeypatch):
    note = _clean(re.search(r'<p class="mv-note">(.*?)</p>', _movers(monkeypatch, _mv_df())).group(1))
    assert note == ("Ranks among the ranked stocks on 20 Oct, the last session on or before the same date a month back, "
                    "against today. Every row shown.")
    assert re.search(r'<p class="mv-note">(.*?)</p>', _movers(monkeypatch, _mv_df(), None)).group(1) == "Every row shown."


@pytest.mark.parametrize("k, want", [
    (10, "The 10 that climbed most places anywhere in the ranking, 1 to 5."),
    (7, "The 7 that climbed most places anywhere in the ranking, 1 to 5."),
    (5, "The 5 that climbed most places anywhere in the ranking."),
    (0, "No stock climbed since the date a month back."),
])
def test_sc_mv_4(k, want):
    assert rv.jumps_caption(k) == want


def test_sc_mv_4_on_the_page(monkeypatch):
    html = _movers(monkeypatch, _mv_df())
    assert "The 2 that climbed most places anywhere in the ranking." in html and "The ten" not in html
    assert "In the top 50 now, not on 20 Oct." in html and "In the top 50 on 20 Oct, not now." in html


def test_sc_data_1(monkeypatch):
    monkeypatch.setattr(rv, "data_freshness", lambda: [
        {"label": "Market caps", "as_of": "18 Nov", "stale": True},
        {"label": "All-time highs", "as_of": "2y window", "stale": True},
        {"label": "Sector tags", "as_of": "", "stale": True}])
    df = pd.DataFrame({"Symbol": ["A", "B"], "Short History": ["No", "Yes"], "Data Gap": ["🟢", "🟢"]})
    line = _text(rv.data_line(df, PX)).replace("&#x27;", "'")
    assert line.startswith("Data to 20 Nov 2026 · NSE. 2 stocks ranked; 0 with a price gap, 1 with a short history.")
    assert line.endswith("Late: Market caps are to 18 Nov; All-time highs are not in, so the highs shown are the last "
                         "two years’; Sector tags carry no date, so they may be old.")


@pytest.mark.parametrize("name, nano, ranked, members, head, body", [
    ("Nifty 1000", False, ["A", "B"], ["A", "B", "C"], "2 of the Nifty 1000's 3 stocks are ranked, as one list.",
     "1 is not ranked yet: under 3 months of prices with us; their history is being collected. C."),
    ("> ₹2,000 Cr", True, ["A"], ["A", "B", "C"], "1 of the 3 stocks in the > ₹2,000 Cr list is ranked, among themselves.",
     "2 are not ranked yet: under 3 months of prices. B, C."),
    ("Combined", False, ["A"], ["A"], "1 of the 1 stock in the combined universe is ranked, as one list.", ""),
])
def test_sc_sys_1(name, nano, ranked, members, head, body):
    system = SYSTEM_1000 if name == "Nifty 1000" else SYSTEM_NANO
    h, b = rv.system_note(name, ranked, members, nano=nano, reason=rv.not_ranked_reason(system))
    assert (h, b) == (head, body)


def test_sc_sys_1_every_name():
    many = [f"S{i:02d}" for i in range(14)]
    body = rv.system_note("Combined", [], many, nano=False)[1]
    assert body.startswith("14 are not ranked yet: under 3 months of prices. S00, ") and body.endswith("S12, S13.")
    assert "and more" not in body                      # every name listed (PAGE_DESIGN §2; S189 item 6)


def test_sc_sys_2():
    assert '"The Nifty 1000\'s list is not available, so the Nifty 750 is ranked."' in _src("app.py")


def test_sc_tool_1():
    src = _src("src/ui/views/ranking_view.py")
    assert 'st.caption("Click a column header to sort the table.")' in src
    assert "rank-change' if movers else 'rank'} order: a column header you" in src


# ── 3. Market ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("b, t, want", [
    ("Very narrow", "Strong downtrend", "Participation is very narrow; Nifty Total Market is in a strong downtrend."),
    ("Narrow", "Downtrend", "Participation is narrow; Nifty Total Market is in a downtrend."),
    ("About usual", "No clear trend", "Participation is about usual; Nifty Total Market has no clear trend."),
    ("Broad", "Uptrend", "Participation is broad; Nifty Total Market is in an uptrend."),
    ("Very broad", "Strong uptrend", "Participation is very broad; Nifty Total Market is in a strong uptrend."),
    ("Not enough data", "Uptrend", "Participation cannot be read today; Nifty Total Market is in an uptrend."),
    ("Broad", "Not enough data", "Participation is broad; Nifty Total Market's trend cannot be read today."),
    ("Not enough data", "Not enough data", "The ranked stocks' prices are not in yet."),
])
def test_mk_head_1(b, t, want):
    assert _clean(mqv.market_title(N(verdict=b), N(verdict=t))) == want


def test_mk_head_1_missing_answers_and_the_earlier_index():
    assert mqv.market_title(None, None) == "The ranked stocks' prices are not in yet."
    assert mqv.market_title(N(verdict="Broad"), None) == "Participation is broad; Nifty Total Market's trend cannot be read today."
    assert mqv.market_title(N(verdict="Broad"), N(verdict="Uptrend"), mq.EARLIER) == \
        "Participation is broad; the Nifty 500 is in an uptrend."


def test_mk_head_2():
    assert mqv.market_sub() == ("Two questions, answered from the ranked stocks and NSE’s index closes: are most stocks "
                                "taking part, and is Nifty Total Market in an uptrend? Then today’s charts.")
    assert "and is the Nifty 500 in an uptrend?" in mqv.market_sub(mq.EARLIER)


def _m(name, now, month=None, year=None, up=60, down=40, unit="pct", primary=False, rule="r", history=None, first=None):
    return mq.Measure(name, unit, now, month, year, mq._vote(now, up, down), rule, up, down, primary, history, first)


@pytest.mark.parametrize("a200, beat, want", [
    (42.5, 45.0, "43% of the ranked stocks are above their 200D EMA, and 45% beat Nifty Total Market over 12 months."),
    (None, 45.0, "45% beat Nifty Total Market over 12 months."),
    (42.5, None, "43% of the ranked stocks are above their 200D EMA."),
    (None, None, ""),
])
def test_mk_q_1(a200, beat, want):
    assert mq._breadth_sentence("x", [_m("a", a200), _m("b", beat)], mq.MARKET) == want


@pytest.mark.parametrize("nows, want", [
    ([70, 70, 30, 50], "2 of 4 measures say up, 1 says down."),
    ([70, 30, 30, 50], "1 of 4 measures says up, 2 say down."),
    ([50, 30, 50, 50], "None of the 4 measures says up, 1 says down."),
    ([70, 70, 70, 50], "3 of 4 measures say up, none say down."),
])
def test_mk_q_2(nows, want):
    assert mq._trend_sentence("x", [_m(str(i), v) for i, v in enumerate(nows)]) == want


def _closes() -> pd.Series:
    idx = pd.bdate_range("2023-01-02", "2026-11-20")
    return pd.Series([1000.0 + i for i in range(len(idx))], index=idx)


def test_mk_q_3():
    s = _closes()
    assert mq._ten_month_rule_text(s, s.index[-1]) == (
        "today's close against the last ten monthly closes; above is up, below is down. "
        f"At the 30 Oct month-end it read {mq._signed1(mq.ten_month_gap(s, s.index[-1]))}.")
    assert mq._ten_month_rule_text(s.iloc[:5], s.index[4]) == \
        "today's close against the last ten monthly closes; above is up, below is down"   # month-end missing
    rules = [m.rule for m in mq.trend_answer(s, None, None, mq.MARKET).measures]
    assert rules[1:] == ["above is up, below is down", "within 5% is up, 15% or more below is down"]
    src = _src("src/engine/market_questions.py")
    for rule in ("60% or more is broad, 40% or less is narrow", "55% or more is broad, 45% or less is narrow",
                 "+5 or more is broad, −5 or less is narrow", "+3 points or more is broad, −3 or less is narrow"):
        assert f'"{rule}"' in src


def _answer(ms, score_m=None, words=("Very narrow", "Narrow", "About usual", "Broad", "Very broad")):
    now = mq._score(ms, "now")
    month = score_m if score_m is not None else mq._score(ms, "month_ago")
    return mq.Answer("Are most stocks taking part?", mq.word_for(now, words), "s.", now or 0.0, month, None, ms, words)


def test_mk_q_4():
    a = _answer([_m("Stocks above their 200D EMA", 65, 50, primary=True), _m("Stocks above their 50D EMA", 55, 35)])
    t = _clean(mqv._changes_html(a, "breadth"))
    assert t == ("The answer a month ago: narrow."
                 "Stocks above their 50D EMA: 35% a month ago, 55% now, now between."
                 "Stocks above their 200D EMA: 50% a month ago, 65% now, now broad.")
    same = _answer([_m("Stocks above their 200D EMA", 65, 62, primary=True)])
    assert _text(mqv._changes_html(same, "breadth")).endswith("Stocks above their 200D EMA: 62% a month ago, 65% now.")
    young = _answer([_m("Stocks above their 200D EMA", 65, None, primary=True, first=pd.Timestamp("2026-11-02"))])
    assert _text(mqv._changes_html(young, "breadth")) == \
        "– a month ago: not published yet (the breadth history starts 2 Nov 2026)."
    assert _text(mqv._changes_html(_answer([_m("x", 65)]), "trend")) == "A month-ago reading is not available."


def test_mk_q_5():
    a = _answer([_m("A", 55, primary=True), _m("B", 65, primary=True)])
    assert a.verdict == "Broad"
    assert _clean(mqv._would_html(a)) == ("To very broad: A reaching 60% (now 55%)."
                                          "To about usual: B falling below 60% (now 65%); or A falling to 40% (now 55%).")
    end = _answer([_m("A", 65, primary=True), _m("B", 65, primary=True), _m("C", 65, primary=True)])
    assert _text(mqv._would_html(end)) == \
        "No single measure moving one step would change the answer; it would take two or more."


def test_mk_q_6():
    a = _answer([_m("A", 65, primary=True)])
    assert "● Today · ○ A month ago · dashed ring: 12 months ago" in mqv._scale(a)


def test_mk_q_7():
    assert _text(mqv._range_html(_m("A", 65))) == "–: the measure is too new (under 12 months of history)."
    h = mqv._range_html(_m("A", 65, history=(30.0, 45.0, 60.0, 80.0, 70.0, pd.Timestamp("2023-03-01"))))
    assert 'title="Lowest 30%, highest 80%; the shaded part is the middle half"' in h


def test_mk_q_8(monkeypatch):
    note = ("Each measure votes by its cut-offs; primary measures count twice. The bar runs from the lowest reading "
            "in the price history the site holds to the highest; the shaded part is the middle half. The verdict is "
            "at an end when the weighted vote is 0.6 or more either way, leaning at 0.25.")
    assert note in _text(mqv.question_section_html(_answer([_m("A", 65, primary=True)]), "breadth", "q"))
    assert (mq.END_AT, mq.LEAN_AT) == (0.6, 0.25)
    assert mq.word_for(0.6, ("a", "b", "c", "d", "e")) == "e" and mq.word_for(0.25, ("a", "b", "c", "d", "e")) == "d"


def test_mk_q_9():
    h = (30.0, 45.0, 60.0, 80.0, 70.4, pd.Timestamp("2023-03-01"))
    t = _text(mqv.question_section_html(_answer([_m("A", 65, year=52, primary=True, history=h)]), "breadth", "q"))
    assert "70th percentile since Mar 2023" in t and "12 months ago 52%" in t
    bare = _text(mqv.question_section_html(_answer([_m("A", 65, primary=True)]), "breadth", "q"))
    assert "percentile" not in bare and "12 months ago –" in bare


def test_mk_size_1():
    s = _closes()
    size = {"Nifty 50": s * 2}
    note = _text(mqv.size_trend_html(s, size, name=mq.MARKET)).split("Now")[-1]
    assert note.endswith("as a monthly chart draws it; at a month-end it is the classic month-end reading. "
                         "Figures are per cent of the index's level.")
    late = _text(mqv.size_trend_html(s, size, late=["Nifty Midcap 150"], day=s.index[-1], name=mq.MARKET))
    assert late.endswith("Figures are per cent of the index's level. NSE’s 20 Nov close for Nifty Midcap 150 is not in yet.")


def test_mk_size_2(monkeypatch):
    from src.loaders import benchmark_indices as bi
    tm = pd.Series(1.0, index=pd.bdate_range("2021-10-14", "2026-11-20"))
    monkeypatch.setattr(bi, "series", lambda key, **kw: tm)
    joined = pd.Series(1.0, index=pd.bdate_range("2012-01-02", "2026-11-20"))
    assert mqv.joined_note(joined, mq.MARKET) == (
        "Nifty Total Market from 14 Oct 2021, when NSE launched it. Before that it is the Nifty 500, scaled to meet it "
        "on that day, so the trend’s ranges reach back to 2012. NSE publishes no Nifty Total Market closes before its launch.")
    assert mqv.joined_note(tm, mq.MARKET) == ""                                               # no join needed
    assert mqv.joined_note(joined, mq.EARLIER) == ("Nifty Total Market’s closes did not load, so this reads the "
                                                   "Nifty 500, the nearest index with a long history.")


@pytest.mark.parametrize("ret, a, b, want", [
    (8.25, 61.0, 48.4, "Over 12 months, Nifty Total Market rose 8.3%, and the share of stocks above their 200D EMA went from 61% to 48%."),
    (-3.0, 40.0, 52.0, "Over 12 months, Nifty Total Market fell 3.0%, and the share of stocks above their 200D EMA went from 40% to 52%."),
    (0.04, 50.2, 49.6, "Over 12 months, Nifty Total Market was unchanged, and the share of stocks above their 200D EMA stayed at 50%."),
])
def test_mk_ch_1(ret, a, b, want):
    assert _clean(mqv.year_head(mq.MARKET, ret, a, b)) == want


def test_mk_ch_2():
    assert mqv.highs_head(5.5, -2.04) == "Net new 52-week highs this week: +5.5% of stocks, against −2.0% 12 months ago."
    assert mqv.highs_head(-1.25, None) == "Net new 52-week highs this week: −1.3% of stocks."


def _charts(monkeypatch, fn, *args):
    """Runs a chart section with Streamlit and the chart kit stubbed; returns the heads, notes and html drawn."""
    from src.ui import dash_charts as dc
    from src.ui.views import dashboard_home_view as dv
    heads, html = [], []
    monkeypatch.setattr(mqv, "_chart_head", lambda title, note: heads.append((title, note)))
    monkeypatch.setattr(mqv.st, "columns", lambda *a, **k: (contextlib.nullcontext(), contextlib.nullcontext()))
    monkeypatch.setattr(mqv.st, "html", html.append)
    monkeypatch.setattr(dc, "render", lambda *a, **k: None)
    monkeypatch.setattr(dv, "_breadth_spec", lambda *a, **k: None)
    fn(*args)
    return heads, html


def test_mk_ch_3(monkeypatch):
    s = _closes()
    weekly = pd.Series([float(i % 7 - 3) for i in range(len(s))], index=s.index)
    _, html = _charts(monkeypatch, mqv._breadth_charts, s, weekly * 10 + 50, weekly, weekly)
    q1, q3 = weekly.quantile(0.25), weekly.quantile(0.75)
    from src.ui import formats as f
    assert html == [f'<p class="qp-note">Shaded: the usual range since Jan 2023, {f.signed(q1, 1)} to '
                    f'{f.signed(q3, 1)} (the middle half of all weeks).</p>']


@pytest.mark.parametrize("today, me, me_at, want", [
    (2.34, 1.1, "2026-10-30", "Nifty Total Market is 2.3% above its 10-month average on 20 Nov. At the 30 Oct month-end it was 1.1% above."),
    (-4.0, -2.0, "2026-10-30", "Nifty Total Market is 4.0% below its 10-month average on 20 Nov. At the 30 Oct month-end it was 2.0% below."),
    (0.02, 0.0, "2026-10-30", "Nifty Total Market is at its 10-month average on 20 Nov. At the 30 Oct month-end it was at its 10-month average."),
    (2.34, 2.34, "2026-11-20", "Nifty Total Market is 2.3% above its 10-month average on 20 Nov."),   # month-end today
    (2.34, None, None, "Nifty Total Market is 2.3% above its 10-month average on 20 Nov."),
])
def test_mk_ch_4(today, me, me_at, want):
    assert _clean(mqv.ten_month_head(mq.MARKET, today, pd.Timestamp("2026-11-20"), me,
                                     None if me_at is None else pd.Timestamp(me_at))) == want


def test_mk_ch_4_note(monkeypatch):
    heads, _ = _charts(monkeypatch, mqv._trend_charts, _closes(), {})
    assert heads[0][1] == ("Monthly closes against the average of the last ten, November at today's close. Above the "
                           "average the 10-month rule reads up; the classic rule reads only month-ends. Three years; price only.")


def test_mk_ch_5(monkeypatch):
    # Owner, 24 Nov 2026: "% against the line" (a ratio less 100, as Indices, S173 IX-2), not points.
    s = _closes()
    heads, _ = _charts(monkeypatch, mqv._trend_charts, s, {"Nifty 50": s * 1.0, "Nifty Smallcap 250": s.pow(1.01)})
    title, note = heads[1]
    assert title.startswith("Over 12 months, Nifty Smallcap 250 did best against Nifty Total Market, ")
    assert "% above its line; Nifty 50 did worst, on it" in title
    assert note.startswith("Each size index divided by Nifty Total Market, set to 100 at the start 12 months ago")
    assert "pts" not in title + note and "points" not in note
    assert mqv.size_line_head({"A": 18.24, "B": -6.1}, "Nifty Total Market") == (
        "Over 12 months, A did best against Nifty Total Market, 18.2% above its line; B did worst, 6.1% below it")
    assert mqv.size_line_head({"A": -1.0, "B": -6.1}, "Nifty Total Market").endswith(
        "A did best against Nifty Total Market, 1.0% below its line; B did worst, 6.1% below it")
    assert mqv.size_line_head({"A": 3.0}, "Nifty Total Market") == (
        "Over 12 months, A is the only size index with a year of closes: 3.0% above its line")


def test_mk_ch_6():
    assert mqv.TEN_MONTH_RANGE["note"] == ("Monthly closes against a 10-month average: twelve points would show almost "
                                           "no history of the line crossing the average, so it opens on three years")


def test_mk_pit_1():
    src = _src("src/ui/views/market_questions_view.py")
    assert ("In a test of 20 Nov 2026, counting today’s members back in "
            "'\n            'time made the past look about 5 points broader than it was.") in src   # a dated quote (rule 14)
    assert "a members-of-the-day history is kept for the Nifty 750 only, so the past may read a few" in src


def test_mk_today_1():
    src = _src("src/ui/views/market_view.py")
    assert 'kit.empty("Pick at least one EMA or SMA", "under Chart settings.")' in src
    assert 'kit.caption("No index tags on the ranked stocks.")' in src
    assert "No stock made a new high or low in the last 20 sessions." in src


def test_mk_dead_1():
    assert not hasattr(mqv, "run_example")
    assert "run_example" not in _src("src/ui/views/market_questions_view.py")


def test_sc_sys_1_a_list_takes_no_possessive():
    from src.ui.views.ranking_view import system_note
    head, _ = system_note("> ₹2,000 Cr", ["A", "B"], ["A", "B", "C"], nano=True)
    assert head == "2 of the 3 stocks in the > ₹2,000 Cr list are ranked, among themselves."
    head, _ = system_note("Combined", ["A"], ["A", "B"], nano=False)
    assert head == "1 of the 2 stocks in the combined universe is ranked, as one list."


def test_the_qualified_now_column_has_one_width_on_every_system():
    """Owner, 24 Nov 2026: the Nifty 1000's table showed a ~300 px gap. One "Out" row's reasons, on one nowrap
    line, set the column's width; each reason is now its own line in a column of one fixed width."""
    from src.ui import screener_table as stt
    assert "td.qn{width:7.5rem;min-width:7.5rem}" in stt._CSS
    assert "white-space:nowrap" not in stt._CSS.split("td .why{", 1)[1].split("}", 1)[0]
