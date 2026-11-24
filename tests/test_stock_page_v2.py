"""The stock page built from mock-up v2, approved by the owner on 23 Nov 2026 (S182 f).

docs/STOCK_REQUIREMENTS.md rows 22-52: the sections built from the app's own figures
(src/ui/stock_lines.py, pure functions), the market's window on the stock's own sessions
(S182 d), the chart kept and restyled with a one-line readout, and no stop loss or
chandelier exit anywhere on the page (row 50).
"""
from __future__ import annotations

import inspect
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from src.engine.exit_watch import CLEAR, SELL, assess, qualified_ranks
from src.ui import lw_chart, stock_chart
from src.ui import stock_lines as sl
from src.ui import watchlist_lines as wl
from src.ui.views import stock_view

LN = wl.Lines(buy=20, keep=40, high_gap=20)
DAY = pd.Timestamp("2026-11-20")
PROBE = str(Path(__file__).parent / "_stock_page_probe_app.py")


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


# ── Head (rows 22, 23) ───────────────────────────────────────────────────────

def test_each_system_names_its_own_universe():
    assert sl.universe("750", 750).rank_label == "Rank of 750"
    assert sl.universe("1000", 980).rank_label == "Rank of 1000"
    nano = sl.universe("nano", 1234)
    assert nano.rank_label == "Rank in the > ₹2,000 Cr list"
    assert nano.of == "of the 1,234 in the > ₹2,000 Cr list"
    assert sl.universe("combined", 2000).the == "the combined universe"


def test_the_title_answers_rank_filters_and_held():
    uni = sl.Universe("750", 750)
    assert sl.title(_row(), uni, True) == ("Sansera Engineering is 12th of 750, passes both filters "
                                           "and is in the model book.")
    assert "fails both filters and is not in the model book." in sl.title(
        _row(**{"Above 50 EMA": False, "Near 52W High": False}), uni, False)
    assert "passes one filter" in sl.title(_row(**{"Near 52W High": False}), uni, False)


def test_the_lede_gives_the_close_the_date_and_the_year_against_nifty_total_market():
    text = sl.lede(_row(), DAY, 0.0080)
    assert text == ("₹4,798 at the close on 20 Nov 2026, a new 52-week closing high. Up 200.9% in 12 months, "
                    "against +0.8% for Nifty Total Market. Market cap ₹29,944 Cr.")
    assert "Down 23.9%" in sl.lede(_row(**{"12M Return": -0.239, "52W High Date": "2026-08-19"}), DAY, 0.008)
    assert sl.market_cap(122000.0) == "₹1.22 lakh Cr"


def test_four_tiles_when_held_three_when_not():
    uni = sl.Universe("750", 750)
    h = sl.Holding(165, 5.4, pd.Timestamp("2026-03-02"), 2230.0, 115.2)
    ts = sl.tiles(_row(), uni, 12, 290, DAY, LN, h)
    assert [(t.label, t.value) for t in ts] == [("Close, 20 Nov", "₹4,798"), ("Rank of 750", "12"),
                                                ("Place among the qualified", "12th of 290"),
                                                ("In the model book", "+115.2%")]
    assert ts[3].sub == "since 2 Mar 2026, 5.4% of the book"
    assert ts[1].sub == "16 three months ago"
    out = sl.tiles(_row(**{"Above 50 EMA": False}), uni, None, 290, DAY, LN, None)
    assert len(out) == 3 and out[2].value == "Out" and out[2].sub == "fails the 50D EMA filter"


# ── 1 · Rank (row 25) ────────────────────────────────────────────────────────

def test_the_trail_reads_the_rankings_past_ranks_and_the_dashboards_qualified_places():
    days = [pd.Timestamp("2026-08-20"), pd.Timestamp("2026-10-19"), DAY]
    tr = sl.trail(_row(), days, [16.0, 11.0], 12)
    assert tr.ranks == [16, 13, 12] and tr.places == [16, 11, 12]
    html = "".join(stock_view.rank_html(_row(), sl.Universe("750", 750), 12, 290, LN, tr))
    for text in ("3M ago", "1M ago", "Now", "20 Aug", "19 Oct", "16th", "11th", "Rank of 750",
                 "Score 1.973, with all five horizons scored."):
        assert text in html, text
    assert "data:image/svg+xml" in html            # the trail is drawn (st.html drops inline SVG)


def test_the_rank_heading_places_the_stock_against_the_books_lines():
    uni = sl.Universe("750", 750)
    assert sl.rank_heading(_row(), uni, 12, 290, LN) == (
        "Twelfth of the 290 that pass both filters, ", "inside the book’s buy line")
    assert sl.rank_heading(_row(), uni, 33, 290, LN)[1] == "between the book’s buy and keep lines"
    assert sl.rank_heading(_row(), uni, 41, 290, LN)[1] == "past the book’s keep line"
    a, b = sl.rank_heading(_row(Rank=591, **{"Above 50 EMA": False, "Near 52W High": False}), uni, None, 290, LN)
    assert a.startswith("591st of 750") and b == "it fails both filters"


def test_the_trail_drawing_puts_the_lines_where_it_says():
    assert sl.trail_points([20, 40, None], 40) == [52.0, 110.0, 150.0]


# ── 2 · Filters and sell rules (rows 26-28, 42) ──────────────────────────────

def _ranking() -> pd.DataFrame:
    return pd.DataFrame({"Symbol": ["A", "B", "C"], "Rank": [1, 2, 3], "CMP": [112.0, 90.0, 100.0],
                         "% 50 EMA": [12.0, -5.0, 2.0], "% High": [0.0, -30.0, -5.0],
                         "52W High": [112.0, 128.6, 105.3],
                         "Above 50 EMA": [True, False, True], "Near 52W High": [True, False, True]})


def test_each_rule_shows_its_line_the_fall_that_reaches_it_and_today():
    rank_df = _ranking()
    a = assess(rank_df, ["A"]).iloc[0].to_dict()
    q = int(qualified_ranks(rank_df)["A"])
    rows = sl.rules(rank_df.iloc[0], a, q, LN, 0.8)
    assert [(r.line, r.fall, r.today) for r in rows] == [
        ("₹100", "10.7%", "+12.0% above"), ("₹90", "20.0%", "At the high"), ("40th", "39 places", "1st")]
    head = sl.rules_heading(a, pd.Timestamp("2026-11-30"), 0.8)
    assert a["status"] == CLEAR and head == ("Clear of all three sell rules",
                                             "; a 10.7% fall would reach the nearest, its 50D EMA.")


def test_a_broken_rule_says_a_holding_would_be_sold_at_the_check():
    rank_df = _ranking()
    a = assess(rank_df, ["B"]).iloc[0].to_dict()
    assert a["status"] == SELL
    lead, rest = sl.rules_heading(a, pd.Timestamp("2026-11-30"), 0.8)
    assert lead == "It would be sold" and rest.startswith(" at the 30 Nov check if today's price holds: it is 5.0% below")
    # S203 st.rule.1: a stock the book does not hold is not called a holding.
    assert sl.rules_heading(a, pd.Timestamp("2026-11-30"), 0.8, held=False)[0] == "It would fail a sell rule"
    rows = sl.rules(rank_df.iloc[1], a, None, LN, 0.8)
    assert rows[0].fall == "Below it" and rows[2].today == "Out"


def test_the_rank_rule_reads_as_a_sentence():
    """S203 cm.rule.3-4: "it #38 · 2 places from the buffer" had no verb; "it is ranks #45" read wrong."""
    from src.engine import exit_watch as ew
    assert ew._ord(38) == "38th" and ew._ord(41) == "41st" and ew._ord(12) == "12th"


def test_the_holding_is_portfolios_own_row():
    table = pd.DataFrame({"Symbol": ["SANSERA", "X"], "Shares": [165, 3], "Weight %": [5.43, 4.0],
                          "Entry Date": ["2026-03-02", "2026-11-02"], "Entry Price": [2230.4, 10.0],
                          "Return since Entry %": [115.18, 1.0]})
    h = sl.holding_from_table(table, "SANSERA")
    lead, rest = sl.holding_sentence(True, h)
    assert lead == "The model book holds it:"
    assert rest == " 165 shares, 5.4% of the book, first bought on 2 Mar 2026 at ₹2,230, +115.2% since."
    assert sl.holding_sentence(False, None) == ("The model book does not hold it.", "")
    assert sl.holding_from_table(table, "NOPE") is None


def test_the_calendar_before_the_check():
    check = pd.Timestamp("2026-11-30")
    assert sl.calendar_sentence(check, [], pd.Timestamp("2026-11-05")) == (
        "The rules are checked at the month-end close, next on 30 Nov 2026; no board meeting is announced "
        "before then (its last results meeting was on 5 Nov).")
    ev = [(pd.Timestamp("2026-11-25"), "X", "held", "Results, dividend")]
    assert "board meetings and ex-dates announced before then: Results, dividend on 25 Nov." in \
        sl.calendar_sentence(check, ev, None)


def test_highs_are_closing_prices_and_the_all_time_high_is_named_when_it_differs():
    assert "closing prices" in sl.highs_note(_row())
    assert sl.highs_note(_row()).endswith("The all-time high is the same close, ₹4,798.")
    assert sl.highs_note(_row(ATH=1300.55, **{"ATH Date": "2024-09-20"})).endswith(
        "The all-time closing high is ₹1,301, on 20 Sep 2024.")


def test_the_ladder_low_is_the_calendar_year_of_closes():
    # Owner, 24 Nov 2026: "365-day calendar window everywhere instead of 252": the 50s are over a year old.
    year = pd.bdate_range("2025-06-30", "2026-06-30")
    s = pd.Series(np.r_[np.full(10, 50.0), np.linspace(100, 200, len(year))],
                  index=pd.bdate_range("2024-06-03", periods=10).append(year))
    lad = sl.ladder(_row(CMP=200.0, **{"52W High": 200.0, "% 50 EMA": 25.0}), s, 0.8)
    assert lad.low == 100.0 and lad.line == 160.0 and lad.ema == 160.0
    assert lad.x(lad.low) == 0.0 and lad.x(lad.high) == 100.0


# ── 3 · Returns and falls (rows 29-32; S182 d) ───────────────────────────────

def test_the_market_window_starts_on_the_stocks_first_session():
    """20 Oct 2026 was Dussehra: the stock's 1M window opens on 21 Oct, and so must the market's
    (the live page started the market on 19 Oct)."""
    idx = pd.DatetimeIndex(["2026-10-16", "2026-10-19", "2026-10-21", "2026-10-22", "2026-11-20"])
    assert sl.window_start(idx, 1) == pd.Timestamp("2026-10-21")
    market = pd.Series([90.0, 100.0, 110.0, 111.0, 121.0], index=idx)
    assert sl.market_return(market, pd.Timestamp("2026-10-21"), DAY) == pytest.approx(0.1)
    # An index day missing: the last close on or before the stock's first session.
    assert sl.market_return(market.drop(pd.Timestamp("2026-10-21")), pd.Timestamp("2026-10-21"), DAY) == \
        pytest.approx(0.21)


def test_windows_carry_the_typical_stock_and_the_rank_by_return():
    idx = pd.bdate_range("2025-11-01", "2026-11-20")
    rank_df = pd.DataFrame({"Symbol": list("ABCD"), **{f"{m}M Return": [0.3, 0.1, -0.1, 0.2] for m in sl.PERIODS},
                            **{f"Max DD {m}M": [-5.0, -10.0, -20.0, -8.0] for m in sl.PERIODS},
                            **{f"{m}M Sharpe": [1.5, 0.5, -0.5, 1.0] for m in sl.PERIODS}})
    market = pd.Series(np.linspace(100, 110, len(idx)), index=idx)
    ws = sl.windows(rank_df.iloc[3], rank_df, idx, market)
    w = ws[0]
    assert w.place == 2 and w.typical == pytest.approx(0.15) and w.typical_fall == pytest.approx(-9.0)
    assert w.lead == pytest.approx(w.ret - w.market)
    assert ws[-1].start == pd.Timestamp("2025-11-20")


def test_line_bars_use_one_scale_and_fill_left_for_a_fall():
    ws = [sl.Window(1, None, 0.216, 0.099, None, None, None, None, None),
          sl.Window(12, None, 2.009, 0.008, None, None, None, None, None)]
    assert sl.line_step(ws) == 5
    b1, b12 = sl.bars(ws, 5)
    assert b1.n == b12.n and b1.zero == 0 and b1.filled == 4 and b1.part == pytest.approx(0.32)
    assert b12.filled == 40
    neg = [sl.Window(1, None, -0.137, 0.099, None, None, None, None, None)]
    step = sl.line_step(neg)
    (b,) = sl.bars(neg, step)
    assert step == 1 and b.zero == 14 and b.start == 1 and b.filled == 13 and b.part_at == 0


def test_the_returns_heading_and_note():
    ws = [sl.Window(12, None, 2.009156, 0.008, None, -16.996686, None, None, None)]
    # S203 Q5 (owner, 24 Nov 2026): the lede keeps the 12M return; the heading counts the windows ahead.
    assert "".join(sl.returns_heading(ws)) == ("Ahead of Nifty Total Market on 1 of 1 window; "
                                               "its max drawdown over 12 months was 17.0%.")   # glossary 1, 6, 8
    ws2 = ws + [sl.Window(3, None, -0.05, 0.02, None, -9.0, None, None, None),
                sl.Window(6, None, 0.10, 0.04, None, -12.0, None, None, None)]
    assert "".join(sl.returns_heading(ws2)).startswith("Ahead of Nifty Total Market on 2 of 3 windows; its max drawdown over 12")
    assert sl.returns_tone(ws2) == "up"
    assert sl.returns_heading([sl.Window(12, None, None, None, None, None, None, None, None)])[0] == \
        "No return to show for this stock yet."
    note = sl.returns_note(DAY, sl.Universe("750", 750))
    assert "not annualised" in note and "Nifty Total Market" in note and "the median of the 750" in note


# ── 4 · Price (rows 33, 34, 47-49) ───────────────────────────────────────────

def test_the_charts_ema_is_the_rankings_none_before_30_prints():
    close = pd.Series(np.linspace(100, 140, 40), index=pd.bdate_range("2026-01-01", periods=40))
    ema = stock_chart.ranking_ema(close)
    assert ema.iloc[:29].isna().all() and ema.iloc[29:].notna().all()


def test_the_chart_keeps_price_volume_and_rs_against_nifty_total_market():
    idx = pd.bdate_range("2023-01-02", "2026-11-20")
    close = pd.Series(np.linspace(100, 300, len(idx)), index=idx)
    market = pd.Series(np.linspace(100, 150, len(idx)), index=idx)
    vol = pd.Series(1e5, index=idx)
    panes, has_vol = stock_chart.price_chart_panes(close, vol, market, stock_chart.RANGES["12M"])
    assert has_vol and [p["series"][0]["name"] for p in panes] == ["Price", "Volume", stock_chart.RS_NAME]
    assert [s["name"] for s in panes[0]["series"]] == ["Price", "50D EMA"]
    assert panes[2]["series"][0]["data"][0][1] == pytest.approx(100.0)     # 100 at the start of the range
    assert list(stock_chart.RANGES) == ["6M", "12M", "3Y"]   # glossary 6
    assert stock_chart.RS_NAME == "RS against Nifty Total Market"


def test_the_readout_is_one_line_at_a_fixed_height():
    """Row 48: the readout cannot wrap, so hovering cannot move the plot (scripts/chart_hover_audit.mjs
    checks it in a browser at 412 and 1400 px)."""
    panes = [{"height": 200, "series": [{"name": "Price", "fmt": "price", "data": [("2026-11-19", 1.0), ("2026-11-20", 2.0)]}]}]
    one = lw_chart.chart_html(panes, one_line=True, label="Price")
    assert "flex-wrap:nowrap;white-space:nowrap;overflow:hidden;height:20px" in one
    assert "const ONE_LINE=true" in one and "tabindex='0'" in one and "ArrowLeft" in one
    assert "const ONE_LINE=false" in lw_chart.chart_html(panes)     # every other chart unchanged


def test_the_price_heading():
    assert sl.price_heading(57, 60, 298.6) == ("Above its 50D EMA on 57 of the last 60 sessions; ",
                                               "against Nifty Total Market it has almost tripled", " in 12 months.")
    # A ratio, not a gap in points (S193 B, glossary 4).
    assert sl.rs_words(110.0) == "its relative strength rose 10.0%" and sl.rs_words(80.0) == "its relative strength fell 20.0%"
    assert sl.price_heading(18, 60, 88.2)[1] == "against Nifty Total Market its relative strength fell 11.8%"
    above, of = sl.sessions_above(pd.Series([1.0, 3.0, 2.0]), pd.Series([np.nan, 2.0, 2.5]))
    assert (above, of) == (1, 2)


# ── 5 · Industry (rows 18, 36, 37) ───────────────────────────────────────────

def test_the_industry_heading_and_link():
    full = pd.DataFrame({"Symbol": ["A", "S", "B"], "Rank": [8, 12, 600],
                         "Industry": ["Automobile and Auto Components"] * 3, "Qualified Rank": [8, 12, np.nan],
                         "CMP": [1.0, 2.0, 3.0]})
    row = _row(Symbol="S")
    shown, in_ind = sl.peers(full, row)
    assert sl.industry_heading(row, in_ind) == "Second of 3 Auto stocks; 2 of them pass both filters."
    html = "".join(stock_view.industry_html(row, shown, in_ind, DAY))
    assert "screener?ind=Automobile%20and%20Auto%20Components" in html
    assert "All 3 Auto stocks on the Screener →" in html and "this stock" in html


# ── 6 · Data (rows 19, 38, 39) ───────────────────────────────────────────────

def test_corporate_actions_come_from_nses_list_one_per_action():
    acts = pd.DataFrame({"symbol": ["MBAPL", "MBAPL", "X"], "series": ["BE", "EQ", "EQ"],
                         "kind": ["split", "split", "bonus"],
                         "ex_date": pd.to_datetime(["2026-07-03"] * 3),
                         "purpose": ["FVSPLT FRM RS 10 TO RS 2", "Face Value Split (Sub-Division) - From Rs 10/- To Rs 2/-", "Bonus 1:1"],
                         "price_factor": [0.2, 0.2, 0.5]})
    (a,) = sl.nse_actions(acts, "MBAPL")
    assert sl.action_line(a) == ("Split, ex 3 Jul 2026: Face Value Split (Sub-Division) - From Rs 10/- To Rs 2/-; "
                                 "prices before it are scaled by 0.2")
    dc = sl.data_checks(_row(), DAY, [a], pd.Timestamp("2024-10-04"))
    assert sl.data_heading(dc).startswith("1 corporate action in NSE’s lists since October 2024, the latest a split ex 3 Jul 2026")


def test_a_clean_stock_says_nothing_to_correct():
    dc = sl.data_checks(_row(), DAY, [], pd.Timestamp("2024-10-04"))
    texts = [t for _, t in dc.items]
    assert "More than 126 sessions of prices, so the 52-week high counts" in texts
    assert "Ranked on all five horizons (1, 3, 6, 9 and 12 months)" in texts
    assert "No split, bonus, rights issue or demerger in NSE’s lists since October 2024" in texts
    assert sl.data_heading(dc).startswith("Nothing to correct")
    short = sl.data_checks(_row(**{"Short History": "Yes", "Horizons Scored": 2}), DAY, [], None)
    assert short.to_read == 2


# ── The page in the app (rows 20, 40, 50) ────────────────────────────────────

def _body(at) -> str:
    return " ".join(h.proto.body for h in at.get("html")) + " ".join(m.value for m in at.markdown)


def test_a_stock_not_in_the_ranking_says_so_with_a_way_back():
    at = AppTest.from_file(PROBE, default_timeout=180)
    at.query_params["stock"] = "NOSUCH"
    at.run()
    assert not at.exception
    assert "NOSUCH is not in the current ranking" in _body(at)
    assert any("Back to screener" in b.label for b in at.button)


def test_no_stop_loss_or_chandelier_exit_anywhere_on_the_page():
    """Row 50 (owner, 22 Nov 2026: "we don't have exit or SL so remove it"): the page shows neither,
    with a ranking that carries both columns, and no code on the page reads them."""
    at = AppTest.from_file(PROBE, default_timeout=180)
    at.query_params["stock"] = "S3"
    at.run()
    assert not at.exception
    page = (_body(at) + " ".join(str(b.label) for b in at.button)).lower()
    assert "S3" in _body(at)
    for word in ("stop loss", "chandelier", "chand exit", "factsheet", "atr"):
        assert word not in page, word
    for module in (stock_view, sl, stock_chart):
        src = inspect.getsource(module)
        for col in ('"Stop Loss"', '"Chand Exit"', "_factsheet", '"ATR"'):
            assert col not in src, (module.__name__, col)


def test_the_page_runs_for_every_system(monkeypatch):
    rank_df = pd.DataFrame({"Symbol": ["A"], "Rank": [1], "CMP": [10.0], "Industry": ["IT"]})
    for system, label in (("750", "Rank of 750"), ("1000", "Rank of 1000"), ("nano", "Rank in the > ₹2,000 Cr list"),
                          ("combined", "Rank in the combined universe")):
        uni = sl.universe(system, len(rank_df))
        assert uni.rank_label == label
        assert stock_view.e(label) in "".join(stock_view.head_html(rank_df.iloc[0], uni, False, DAY, None, None, 0, LN, None))


def test_the_screener_opens_searched_to_an_industry():
    """Row 37: the page's link "All 49 Auto stocks on the Screener" is screener?ind=<NSE industry>."""
    at = AppTest.from_file(PROBE, default_timeout=180)
    at.query_params["ind"] = "IT"
    at.run()
    assert not at.exception
    assert at.selectbox(key="rank_search_predictive").value == "[INDUSTRY] IT"


def test_a_late_market_close_is_said_not_read_a_session_early():
    """S148, S203 st.ret.3: Nifty Total Market without a close for the page's session reads "–", and the page says why."""
    row = pd.Series({"CMP": 100.0, "12M Return": 0.25})
    day = pd.Timestamp("2026-11-24")
    text = sl.lede(row, day, None, late=True)
    assert "Nifty Total Market’s 24 Nov close is not in yet" in text and "against" not in text
    assert ", against +5.0% for Nifty Total Market" in sl.lede(row, day, 0.05)
