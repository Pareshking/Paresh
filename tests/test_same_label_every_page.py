"""The same label gives the same value on every page (S154 (b), 24 Nov 2026).

`tests/test_same_label_same_value.py` holds Dashboard, Portfolio and Actions. This file
covers the labels those pages share with Market, Sectors, Indices, the stock page, the
Screener, the Watchlist, the Guide and Backtest. Each test calls the functions every page
uses for one label on one fixed input (fakes, no network) and asserts the same value and the
same rounding. Where two pages differ by a decided rule, the test asserts that difference and
cites the decision. A strict xfail is a difference no decision covers yet: it is reported for
routing (docs/FIGURE_INVENTORY.md, "Undocumented differences"), and the test starts to fail
the day the pages agree, so the marker is removed then.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.engine import dashboard_insights as di
from src.engine import indices_page as ip
from src.engine import market_questions as mq
from src.engine import portfolio_report as pr
from src.engine import sectors_page as sp
from src.engine.exit_watch import qualified_ranks
from src.ui import formats as _fmt
from src.ui import stock_lines as sl

ROOT = Path(__file__).resolve().parents[1]
AS_OF = pd.Timestamp("2026-11-20")
# Not sessions in the fixture: 20 Oct 2026 (a holiday on NSE's 2026 list, the day S193 A9 turned on)
# and one more a month earlier, so "a month back" lands on a holiday at least once.
HOLIDAYS = pd.DatetimeIndex(["2026-10-20", "2026-09-17", "2026-08-27", "2026-05-01", "2025-10-21"])


def _sessions(start="2023-06-01", end=AS_OF) -> pd.DatetimeIndex:
    return pd.bdate_range(start, end).difference(HOLIDAYS)


def _walk(idx, seed, drift=0.0004, vol=0.011, start=100.0) -> pd.Series:
    rng = np.random.default_rng(seed)
    return pd.Series(start * np.exp(np.cumsum(rng.normal(drift, vol, len(idx)))), index=idx)


def _total_market() -> pd.Series:
    return _walk(_sessions(), 7, start=10_000.0).rename("nifty_total_market")


def _prices(n=30, seed=11) -> pd.DataFrame:
    idx = _sessions()
    return pd.DataFrame({f"S{i:02d}": _walk(idx, seed + i, drift=0.0002 * (i % 5 - 2), vol=0.018)
                         for i in range(n)})


def _groups(px: pd.DataFrame) -> pd.Series:
    names = ("Auto", "Healthcare", "Metals")
    return pd.Series([names[i % 3] for i in range(px.shape[1])], index=px.columns)


def _one(values) -> None:
    """Every page's value is one number, and the shared formatter shows it the same way."""
    vals = [v for v in values]
    assert all(v is not None for v in vals), vals
    assert max(vals) - min(vals) < 1e-9, vals
    assert len({_fmt.signed(v, 1) for v in vals}) == 1, vals


# ── Nifty Total Market over 1, 3, 6 and 12 months ───────────────────────────
# Indices (every-index table), Dashboard ("three ways", size table), Portfolio ("By period"),
# Sectors (the lede: "Nifty Total Market rose 8.8%"), stock page (Returns, the lede's 12M).

def test_total_market_window_returns_agree_on_indices_dashboard_portfolio_and_sectors():
    tm, px = _total_market(), _prices()
    typical = di.typical_stock(px, tm, AS_OF)                     # Dashboard "three ways"
    periods = {label: m for label, _b, m, _o in pr.periods(tm, tm, tm, AS_OF)}   # Portfolio "By period"
    ld = sp.leads(px, _groups(px), tm)                            # Sectors
    for i, m in enumerate((1, 3, 6, 12)):
        indices = ip.ret(tm, m, AS_OF)
        dashboard = typical["market"][i]
        size_table = di.window_return(tm, AS_OF - pd.DateOffset(months=m), AS_OF)
        portfolio = periods[{1: "1 month", 3: "3 months", 6: "6 months", 12: "1 year"}[m]]
        sectors = ld.market_ret[m] - ld.gap[str(m)]               # sector_view.head: m1 - tm1
        _one([indices, dashboard, size_table, portfolio, sectors])


def test_the_stock_page_starts_its_market_window_on_or_after_the_date_as_decided():
    """STOCK_REQUIREMENTS row 29 (approved 23 Nov 2026, mock-up v2) and S193 A9: the stock page's
    Nifty Total Market covers the stock's own sessions, from the first session on or after the date
    back (`calendar_start_positions`); every other page reads the close on or before it. The two
    agree when the date back is a session and differ when it is a holiday (20 Oct 2026)."""
    tm = _total_market()
    idx = tm.index
    assert pd.Timestamp("2026-10-20") not in idx                    # 1M back from 20 Nov: a holiday
    row = pd.Series({f"{m}M Return": 0.05 for m in sl.PERIODS})
    rank_df = pd.DataFrame([row])
    ws = {w.months: w for w in sl.windows(row, rank_df, idx, tm)}
    assert ws[1].start == pd.Timestamp("2026-10-21")                # on or after
    others = ip.ret(tm, 1, AS_OF)                                    # from 19 Oct, on or before
    assert ws[1].market * 100 != pytest.approx(others, abs=1e-6)
    assert ws[1].market * 100 == pytest.approx(di.window_return(tm, pd.Timestamp("2026-10-21"), AS_OF))
    for m in (3, 6, 12):                                             # 20 Aug, 20 May, 20 Nov: sessions
        assert AS_OF - pd.DateOffset(months=m) in idx
        _one([ws[m].market * 100, ip.ret(tm, m, AS_OF), di.window_return(tm, AS_OF - pd.DateOffset(months=m), AS_OF)])


def test_total_market_month_so_far_and_this_year_agree_on_dashboard_and_portfolio():
    tm = _total_market()
    bm = di.book_month({}, 1.0, tm, {}, AS_OF)
    p = AS_OF.to_period("M")
    periods = {label: m for label, _b, m, _o in pr.periods(tm, tm, tm, AS_OF)}
    _one([bm.market_mtd, pr.month_returns(tm, [p], AS_OF)[p], periods["Month so far"]])
    _one([bm.market_ytd, periods["This year"]])


# Fixed 24 Nov 2026 (S154 finding 3): the lede rounds with formats.signed.
def test_sectors_lede_rounds_the_total_market_figure_as_the_other_pages_do():
    from src.ui.views import sector_view as sv
    when = AS_OF
    lead = sp.Lead("Auto", 6, 1.0, 1.0, 1.0, 1.0, 1.0, "ahead on both")
    ld = sp.Leads(when, when, when, [lead], {}, pd.Series(dtype=float), {"Auto": 6},
                  {1: 5.0}, {"1": 2.75}, {})                       # Total Market: 5.0 - 2.75 = 2.25
    gap = type("Gap", (), {"gap1": -1.0})()
    lede = sv.head(ld, lambda n: n, "sector", {"gaps": [gap]})[0]
    from src.ui.views.dashboard_home_view import sg
    assert f"rose {sg(2.25).lstrip('+')}%" in lede                  # "+2.3" on the Dashboard


# ── Share of the ranked stocks above their 200D EMA ────────────────────────
# Market (Breadth), Dashboard (At a glance), Sectors ("Inside each sector": all ranked stocks).

def _market_share(px, past=None):
    from src.engine import pit_breadth
    return pit_breadth.splice(mq._share_above_ema(px, 200), past, "above_200")


def test_share_above_the_200d_ema_now_and_a_month_ago_agree_without_the_members_history():
    px = _prices(n=120)
    groups = _groups(px)
    ld = sp.leads(px, groups, _total_market())
    allr = next(s for s in sp.ema_shares(px, groups, ld) if s.name == "All ranked stocks")
    share = _market_share(px)
    dash = di.trail_of(share, AS_OF)                                 # Dashboard: 3M, 1M, now
    d = mq.anchor_dates(px.index)                                    # Market: month ago, now
    market_now, market_1m = share.loc[d["now"]], share.loc[d["month_ago"]]
    for a, b, c in ((allr.now, dash[2], market_now), (allr.b1, dash[1], market_1m)):
        assert a == pytest.approx(b) == pytest.approx(c)
        assert f"{a:.0f}" == f"{b:.0f}" == f"{c:.0f}"               # both pages print ":.0f"


def test_with_the_members_history_sectors_counts_todays_members_as_decided():
    """S193 A10 (owner, 23 Nov 2026): the Dashboard and Market splice the members-of-the-day
    history (`pit_breadth.splice`) for the past; Sectors counts today's members throughout and
    its headline says so. Today's figure is the same; a month ago differs."""
    px = _prices(n=120)
    groups = _groups(px)
    ld = sp.leads(px, groups, _total_market())
    allr = next(s for s in sp.ema_shares(px, groups, ld) if s.name == "All ranked stocks")
    d1 = ld.d1
    past = pd.DataFrame({"above_200": [allr.b1 + 3.0]}, index=pd.DatetimeIndex([d1]))   # the members of 19 Oct
    share = _market_share(px, past)
    dash = di.trail_of(share, AS_OF)
    assert dash[2] == pytest.approx(allr.now)
    assert dash[1] == pytest.approx(allr.b1 + 3.0) and dash[1] != pytest.approx(allr.b1)
    text = (ROOT / "src/ui/views/sector_view.py").read_text(encoding="utf-8")
    assert "today’s members" in text or "today's members" in text


# Fixed 24 Nov 2026 (S154 finding 4): ema_shares counts every ranked stock.
def test_a_ranked_stock_without_an_industry_counts_on_every_page():
    px = _prices(n=120)
    groups = _groups(px)
    groups.iloc[:6] = ""                                             # six ranked stocks with no industry
    ld = sp.leads(px, groups, _total_market())
    allr = next(s for s in sp.ema_shares(px, groups, ld) if s.name == "All ranked stocks")
    assert allr.now == pytest.approx(_market_share(px).iloc[-1])


# ── Nifty 500: against its 200D EMA, its 10-month average, its 52W high ─────
# Header strip, Market (trend question, size table), Dashboard (signal rows), Indices (from 12M high).

def _nifty500() -> pd.Series:
    return _walk(pd.bdate_range("2014-01-01", AS_OF), 3, drift=0.0003, start=8_000.0)


def test_nifty500_against_its_200d_ema_agrees_on_header_market_and_dashboard(monkeypatch):
    from src.loaders import price_loader
    full = _nifty500()
    five = full[full.index > AS_OF - pd.DateOffset(years=5)]          # Market and Dashboard read period="5y"
    monkeypatch.setattr(price_loader, "fetch_benchmark_history", lambda period="2y", symbol=None: full)
    fn = getattr(price_loader.get_market_regime, "__wrapped__", price_loader.get_market_regime)
    header = fn(end=f"{AS_OF:%Y-%m-%d}").distance_pct                # the header reads the whole history
    market = mq.ema_gap(five, AS_OF)
    trend = mq.trend_answer(five, None, None)
    in_trend = next(m for m in trend.measures if m.name == "Nifty 500 against its 200D EMA")
    dash = di.trail_of(mq._ema_gap_series(five), AS_OF)
    assert abs(header - market) < 1e-4                                 # the EMA has converged in five years
    _one([market, in_trend.now, dash[2]])
    assert in_trend.month_ago == pytest.approx(dash[1])                # a month ago, the same session


def test_nifty500_against_its_10_month_average_agrees_on_market_and_dashboard():
    n500 = _nifty500()
    trend = mq.trend_answer(n500, None, None)
    m = next(x for x in trend.measures if x.name == "Nifty 500 against its 10-month average")
    dash = [mq.ten_month_today(n500, d) for d in di.trail_dates(AS_OF).values()]
    _one([m.now, dash[2]])
    assert m.month_ago == pytest.approx(dash[1])


def _peak_just_over_a_year_back() -> tuple[pd.Series, pd.Timestamp]:
    """About 249 sessions a year, as NSE has (249 in 2024 and 2025): the high 251 sessions back is
    more than a calendar year back, and still inside a 252-session window."""
    idx = pd.bdate_range("2023-01-02", AS_OF)
    idx = idx[np.arange(len(idx)) % 20 != 7]                           # ~12 holidays a year
    s = pd.Series(np.linspace(100.0, 110.0, len(idx)), index=idx)
    s.iloc[-251] = 125.0
    assert s.index[-251] <= AS_OF - pd.DateOffset(years=1)
    return s, s.index[-251]


def test_from_the_52w_high_agrees_on_market_indices_and_sectors():
    s, _ = _peak_just_over_a_year_back()
    market = mq.from_high(s, AS_OF)                                    # Market: trend question, size table
    sectors = sp.from_high(s, AS_OF)                                   # Sectors: NSE sector indices
    f = ip.Frames(pd.DataFrame({"nifty_500": s}), pd.DataFrame({"nifty_500": s * np.nan}),
                  pd.DataFrame(), pd.DataFrame(), {"nifty_500": "Nifty 500"}, {"nifty_500": "Broad"})
    indices = ip.every_index(f, families=("Broad",), now=AS_OF)["Broad"][0].from_high
    _one([market, sectors, indices])


# Fixed 24 Nov 2026 (owner: "Use calendar date everywhere"): both read the calendar year.
def test_the_dashboards_52w_high_is_markets():
    s, _ = _peak_just_over_a_year_back()
    dash = di.trail_of(mq._from_high_series(s), AS_OF)[2]
    assert f"{dash:.1f}" == f"{mq.from_high(s, AS_OF):.1f}"


# ── Over 12 months: the share beating Nifty Total Market, the median stock's lead ─
# Market (Breadth question), Dashboard ("three ways").

def _beat_both(px, tm):
    typical = di.typical_stock(px, tm, AS_OF)
    share_m, gap_m = mq._beat_index_12m(px, tm, AS_OF)
    return (share_m, gap_m), (typical["beat_share"][-1], typical["median"][-1] - typical["market"][-1])


def test_the_12m_beat_share_and_median_lead_agree_when_every_stock_has_both_closes():
    (share_m, gap_m), (share_d, gap_d) = _beat_both(_prices(n=40), _total_market())
    assert share_m == pytest.approx(share_d) and f"{share_m:.0f}" == f"{share_d:.0f}"
    _one([gap_m, gap_d])


def test_the_12m_figures_differ_by_the_recorded_gap_rule_when_a_close_is_missing():
    """S193 A11 (cause confirmed in the code, 23 Nov 2026; owner to decide once settled): Market's
    `_beat_index_12m` takes each stock's last close in the week to each date; the Dashboard's
    `typical_stock` takes the exact session and drops the stock. They part only when a close is missing."""
    px, tm = _prices(n=40), _total_market()
    start = di.on_or_before(px.index, AS_OF - pd.DateOffset(months=12))
    px.loc[start, px.columns[:8]] = np.nan                            # eight stocks miss the start session
    (share_m, gap_m), (share_d, gap_d) = _beat_both(px, tm)
    assert (share_m, gap_m) != pytest.approx((share_d, gap_d))
    full = _beat_both(_prices(n=40), tm)[0]
    assert share_m == pytest.approx(full[0], abs=15)                   # Market keeps the eight on a near close


# ── A stock: qualified place, qualified count, 12M return, distance from the high ─
# Screener, stock page, Watchlist, Sectors ("Stocks in a sector"), Actions.

def _ranking(flags) -> pd.DataFrame:
    rows = []
    for i, (ema, near) in enumerate(flags, start=1):
        rows.append({"Rank": i, "Symbol": f"S{i:02d}", "Above 50 EMA": ema, "Near 52W High": near,
                     "Industry": "Auto" if i % 2 else "IT", "12M Return": 0.01 * i, "% High": -1.5 * i,
                     "52W High Date": "2026-10-01"})
    return pd.DataFrame(rows)


@pytest.mark.parametrize("yes,no", [(True, False), (np.True_, np.False_), ("True", "False"), ("✅", "")])
def test_the_qualified_count_and_place_agree_on_screener_stock_page_and_sectors(yes, no):
    from src.ui.components import to_bool_mask
    from src.ui.views.ranking_view import with_book_columns
    flags = [(yes, yes), (no, yes), (yes, yes), (yes, no), (yes, yes), (yes, yes)]
    rank_df = _ranking(flags)
    if yes == "✅":
        pytest.xfail("Undocumented, not live (the engine writes booleans): exit_watch._flag reads '✓' but not "
                     "'✅'; theme.is_tick_true reads '✅' but not '✓'. The Screener's count and the qualified "
                     "place would part on a ticked table.")
    passes = to_bool_mask(rank_df["Above 50 EMA"]) & to_bool_mask(rank_df["Near 52W High"])
    screener_count = int(passes.sum())                                 # "Pass both filters" (ranking_view.py:392)
    q = qualified_ranks(rank_df)                                        # stock page n_q, Sectors, Actions
    assert screener_count == len(q) == 4
    screener = with_book_columns(rank_df, book_symbols=[]).set_index("Symbol")["Qualified Rank"]
    for sym, place in q.items():
        assert screener[sym] == place


def test_a_stocks_12m_return_and_distance_from_the_high_are_the_screeners_columns():
    rank_df = _ranking([(True, True)] * 3)
    row = rank_df.iloc[2]
    ws = {w.months: w for w in sl.windows(row, rank_df, _sessions(), _total_market())}
    assert ws[12].ret == row["12M Return"]                             # stock page Returns, the Screener's column
    assert sl.from_high(row, AS_OF) == _fmt.pct(row["% High"], fraction=False)   # Portfolio, Actions read "% High"
    assert sl.lede(row, AS_OF, None).count(_fmt.pct(abs(row["12M Return"]), signed_=False)) == 1


# ── The book's rule numbers: 20 bought, kept to 40, within 20% of the 52W high, 50D EMA ─
# Screener (lede, key), Watchlist and stock page (`watchlist_lines.lines`), Guide, Backtest defaults.

def test_the_rule_numbers_are_the_track_records_on_every_page():
    from src.engine.track_record import TRACK_RECORD_CONFIG as cfg
    from src.ui import watchlist_lines as wl
    from src.ui.views import ranking_view
    ln = wl.lines()
    assert (ln.buy, ln.keep) == (int(cfg["top_n"]), int(cfg["buffer_n"]))
    within = round((1 - float(cfg["high_pct"])) * 100)
    lede = ranking_view.screener_lede(pd.DataFrame({"Rank": [1]}), None)
    assert f"top {ln.buy} qualified" in lede and f"top {ln.keep}" in lede
    assert f"top {ln.buy} qualified" in ranking_view._KEY_HTML and f"within {within}% of the 52W high" in ranking_view._KEY_HTML
    guide = (ROOT / "src/ui/views/guide_view.py").read_text(encoding="utf-8")
    assert f"within {within}% of its 52-week high" in guide
    bt = (ROOT / "src/ui/views/backtest_view.py").read_text(encoding="utf-8")
    assert f'value={int(cfg["top_n"])}, step=1, key="bt_top_n"' in bt
    assert f"value={int(cfg['buffer_n'])}, step=1, key=\"bt_keep_rank\"" in bt
    assert f"max_value=400, value={int(cfg['ema_period'])}," in bt
    assert f"max_value=95.0, value={float(within)}," in bt
    from src.core.config import (DEFAULT_LOOKBACK_WEIGHTS, DEFAULT_SECTOR_CAP, DEFAULT_STOCK_CAP,
                                 DEFAULT_TRANSACTION_COST_BPS)
    assert float(DEFAULT_TRANSACTION_COST_BPS) == float(cfg["cost_bps"])
    # Configuration's defaults (weights, "Most in one sector", "Most in one stock") are the Guide's.
    assert [float(w) for w in DEFAULT_LOOKBACK_WEIGHTS] == [float(w) for w in cfg["config_weights"]]
    assert (DEFAULT_SECTOR_CAP, DEFAULT_STOCK_CAP) == (float(cfg["sector_cap"]), float(cfg["stock_cap"]))


# ── The ranked list's market value: Dashboard (flows against it), Portfolio (industries by it) ─

def test_the_ranked_lists_market_value_is_one_function_on_dashboard_and_portfolio():
    home = (ROOT / "src/ui/views/dashboard_home_view.py").read_text(encoding="utf-8")
    page = (ROOT / "src/ui/views/portfolio_page.py").read_text(encoding="utf-8")
    assert "system_market_caps(" in home and "system_market_caps(" in page
    assert '"mcap": ROOT / "data" / "nse_market_caps.csv"' in home
    assert 'ROOT / "data" / "nse_market_caps.csv"' in page


# ── The index closes behind those labels: one value in every file a page reads ─

def test_the_index_files_the_pages_read_give_one_close_per_session():
    """Dashboard, Portfolio and the stock page read data/benchmark_indices.csv; Market and Sectors
    data/nse_total_market.csv joined to it (`market_questions_view.total_market`); Indices NSE's
    index store. On common sessions the closes are the same (the collector refuses a gap over 0.05%)."""
    from src.loaders import benchmark_indices as bi
    from src.loaders import nse_indices as ni
    f = ROOT / "data" / "nse_total_market.csv"
    if not f.exists() or not bi.read().shape[0]:
        pytest.skip("index files not in this checkout")
    store = ni.read_compact()
    t = pd.read_csv(f, parse_dates=["date"])
    pairs = [(bi.series(bi.TOTAL_MARKET), pd.Series(t["close"].values, index=t["date"]), 5e-4)]
    for ours, theirs in ((bi.TOTAL_MARKET, "nifty_total_market"), ("nifty50", "nifty_50"),
                         ("midcap150", "nifty_midcap_150"), ("smallcap250", "nifty_smallcap_250"),
                         ("microcap250", "nifty_microcap_250")):
        x = store[store["key"] == theirs].set_index("date")["close"]
        x.index = pd.to_datetime(x.index)
        pairs.append((bi.series(ours), x, 1e-6))
    for a, b, tol in pairs:
        j = pd.concat([pd.to_numeric(a, errors="coerce"), pd.to_numeric(b, errors="coerce")], axis=1, join="inner").dropna()
        assert len(j), a.name
        assert float((j.iloc[:, 0] / j.iloc[:, 1] - 1).abs().max()) <= tol, a.name


def test_total_market_keeps_nse_weekend_sessions_the_archive_lacks(monkeypatch, tmp_path):
    """S154 finding 2: data/nse_total_market.csv lacks NSE's weekend sessions (Muhurat, Budget days);
    total_market() took the index file's rows only after the archive's end, so a 1M window from
    6 Nov 2026 would have started on the wrong session from 8 Dec."""
    from src.loaders import benchmark_indices as bi
    from src.ui.views import market_questions_view as mqv
    days = pd.DatetimeIndex(["2026-11-06", "2026-11-08", "2026-11-09"])
    ours = pd.Series([100.0, 101.0, 102.0], index=days)
    monkeypatch.setattr(bi, "series", lambda key, *a, **k: ours)
    tm = mqv.total_market()
    assert pd.Timestamp("2026-11-08") in tm.index
    assert tm.index.is_monotonic_increasing and not tm.index.duplicated().any()
