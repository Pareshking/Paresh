"""The Backtest page (S174, mock-up v1 approved 21 Nov 2026; docs/BACKTEST_REQUIREMENTS.md)."""
from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.engine import backtest_page as bp
from src.engine.metrics import max_drawdown

ROOT = Path(__file__).resolve().parents[1]
VIEW = ROOT / "src" / "ui" / "views" / "backtest_view.py"


def _curve(values, start="2020-01-01", freq="B"):
    idx = pd.date_range(start, periods=len(values), freq=freq)
    return pd.Series(values, index=idx, dtype=float)


# ── "A year" is calendar time (decision D) ────────────────────────────────────

def test_a_year_compounds_over_calendar_days():
    idx = pd.DatetimeIndex(["2020-01-01", "2022-01-01"])
    c = pd.Series([100.0, 121.0], index=idx)
    assert bp.a_year(c) == pytest.approx(1.21 ** (365.25 / 731) - 1)
    assert bp.a_year(c.iloc[:1]) is None
    assert bp.a_year(pd.Series([100.0, 110.0], index=pd.DatetimeIndex(["2020-01-01", "2020-07-01"]))) is None


def test_the_engine_annualises_over_calendar_time_too():
    from src.engine.backtester import run_backtest

    rng = np.random.default_rng(3)
    idx = pd.bdate_range("2018-01-01", periods=900)
    px = pd.DataFrame(100 * np.exp(np.cumsum(rng.normal(0.0004, 0.015, (900, 30)), axis=0)), index=idx,
                      columns=[f"S{i}" for i in range(30)])
    bench = px.mean(axis=1)
    res = run_backtest("calendar_year_test", px, top_n=10, _benchmark_close=bench, backtest_months=24,
                       stateful_history=True)
    eq, st = res["equity_curve"], res["stats"]
    years = (eq.index[-1] - eq.index[0]).days / 365.25
    assert st["window_years"] == pytest.approx(years)
    assert st["ann_return"] == pytest.approx((1 + st["total_return"]) ** (1 / years) - 1)
    assert st["ann_return"] == pytest.approx(bp.a_year(eq))


# ── Falls go through metrics.drawdown ─────────────────────────────────────────

def test_falls_are_separate_and_dated():
    c = _curve([100, 110, 99, 105, 111, 120, 90, 96, 100])
    f = bp.falls(c, 3)
    assert f[0].depth == pytest.approx(90 / 120 - 1) and f[0].recovered is None
    assert f[0].peak == c.index[5] and f[0].low == c.index[6]
    assert f[1].depth == pytest.approx(99 / 110 - 1) and f[1].recovered == c.index[4]
    assert f[0].depth == pytest.approx(max_drawdown(c))
    assert bp.below_peak_now(c) == pytest.approx(100 / 120 - 1)


def test_no_drawdown_formula_is_written_out_on_the_page():
    for path in (VIEW, ROOT / "src" / "engine" / "backtest_page.py"):
        assert "cummax" not in path.read_text(encoding="utf-8")


# ── The year table and the windows ────────────────────────────────────────────

def test_years_start_at_the_first_fill_and_an_index_at_its_first_whole_year():
    idx = pd.bdate_range("2020-03-02", "2022-06-30")
    c = pd.Series(np.linspace(100, 150, len(idx)), index=idx)
    late = pd.Series(np.linspace(50, 60, len(idx)), index=idx)
    yt = bp.years_table(c, {"late": late}, {"late": 2021})
    first = yt.iloc[0]
    assert first["year"] == 2020 and first["first_month"] == 3 and first["months"] == 10
    assert np.isnan(first["late"]) and np.isfinite(yt.iloc[1]["late"])
    assert yt.iloc[-1]["last_month"] == 6
    assert (1 + yt["rule"]).prod() == pytest.approx(150 / 100)


def test_summary_counts_calendar_months_against_the_benchmark():
    idx = pd.bdate_range("2020-01-01", "2021-12-31")
    c = pd.Series(np.linspace(100, 130, len(idx)), index=idx)
    b = pd.Series(np.linspace(100, 110, len(idx)), index=idx)
    s = bp.summary(c, b)
    assert s.months == 24 and s.ahead == 24 and s.up == 24
    assert s.lead == pytest.approx(s.a_year - s.bench_a_year)


def test_trade_stats_weight_each_trade_by_its_size():
    ct = pd.DataFrame({"Status": ["Closed", "Closed", "Open"], "Return %": [0.10, -0.05, 0.2],
                       "Entry Weight %": [5.0, 10.0, 5.0], "Holding (Days)": [30, 60, 10]})
    t = bp.trade_stats(ct)
    assert t["closed"] == 2 and t["open"] == 1 and t["won"] == 0.5
    assert t["profit_factor"] == pytest.approx(0.5 / 0.5)
    assert bp.trade_stats(ct.iloc[:1])["profit_factor"] is None      # no loss: no ratio, not thousands


def test_short_books_are_counted_as_too_few_stocks_not_caps():
    m = pd.DataFrame({"Period Start": pd.to_datetime(["2020-03-02", "2020-04-01"]), "Holdings": [20, 10]})
    assert bp.short_books(m, 20) == [(pd.Timestamp("2020-04-01"), 10)]


# ── The page ──────────────────────────────────────────────────────────────────

def test_one_name_one_unit_on_the_page():
    """S173: the names the page used to mix are gone from its source; glossary 8 (owner, 23 Nov 2026): "Max drawdown", not "largest fall"."""
    src = VIEW.read_text(encoding="utf-8")
    for banned in ("Largest fall", "largest fall", "Annualised", '"Alpha', "Alpha vs", "CAGR", "Strategy Net", "Ahead of the index",
                   "Worst fall", "Calmar", "Live system", "Personal closes", "Recommendation: 30", "@st.fragment",
                   "render_data_quality_footer", "Zero Look-Ahead"):
        assert banned not in src, banned
    for name in ('"A year, compounded"', '"Lead over the Nifty 500"', '"Max drawdown"',
                 '"Below its peak now"', '"Months ahead of the Nifty 500"', '"Days below its peak"'):
        assert name in src, name


def test_rebalance_line_reasons_in_plain_words():
    from src.ui.views.backtest_view import _reason

    assert _reason("New Momentum Leader (Rank #12)") == "Rank 12, new"
    assert _reason("Buffer Zone Retention (Rank #31)") == "Rank 31, kept"
    assert _reason("Trend Breakdown") == "Trend Breakdown"


def _fake_run(n=900):
    idx = pd.bdate_range("2010-01-04", periods=n)
    rng = np.random.default_rng(5)
    eq = pd.Series(np.exp(np.cumsum(rng.normal(0.0006, 0.012, n))), index=idx)
    eq.iloc[0] = 1.0
    bench = pd.Series(np.exp(np.cumsum(rng.normal(0.0003, 0.01, n))) * 5000, index=idx)
    monthly = pd.DataFrame({"Period Start": idx[::21], "Holdings": [20] * len(idx[::21])})
    monthly.loc[3, "Holdings"] = 10
    trades = pd.DataFrame({"Status": ["Closed"] * 3, "Symbol": ["A", "B", "C"], "Return %": [0.1, -0.02, 0.05],
                           "Entry Weight %": [5.0, 5.0, 5.0], "Holding (Days)": [30, 40, 50],
                           "Exit Date": [f"{idx[100]:%d %b %Y}"] * 3})
    res = {"equity_curve": eq, "stats": {"pit_periods": 40, "current_universe_periods": 0, "cagr_gross": 0.2,
                                         "volatility": 0.19, "sharpe": 0.7, "sharpe_stderr_iid": 0.2, "sortino": 0.9,
                                         "avg_turnover": 36.0},
           "monthly": monthly, "closed_trades": trades, "live_meta": {}}
    return res, bench


def test_the_page_parts_carry_the_requirements_markers(monkeypatch):
    from src.engine.track_record import TRACK_RECORD_CONFIG as cfg
    from src.ui.views import backtest_view as bv
    from src.ui.views.dashboard_home_view import html_of

    monkeypatch.setattr(bv, "_store", lambda: None)
    res, bench = _fake_run()
    close = pd.DataFrame({"A": np.ones(900)}, index=res["equity_curve"].index)
    h = {"key": "nifty_500", "name": "Nifty 500", "close": close, "start": pd.Period("2010-01", "M"),
         "end": pd.Period("2013-04", "M"), "first": pd.Period("2010-01", "M"), "latest": pd.Period("2013-04", "M"),
         "floor": 0.0, "unlabelled": 0, "priced": 1429, "to_latest": True, "moved": None}
    s = {"top_n": 20, "rebal_freq": 21, "weight_method": "Equal Weight", "buffer_n": 40, "cost_bps": 30.0,
         "ema_period": 50, "high_pct": 0.8, "ath_pct": None, "exit_ema_period": None, "exit_high_pct": None,
         "exit_ath_pct": None, "ath_min_years": 3.0, "score_method": "sharpe", "weights": tuple(cfg["config_weights"]),
         "rule": "live"}
    assert bv.is_default(s, h, cfg["stock_cap"], cfg["sector_cap"])
    f = bv.gather(res, s, h, bench, True)
    # Inline spans (the headline's verdict colour, S219 2) join their text; other tags break it.
    text = re.sub(r"<[^>]+>", " ", re.sub(r"</?span[^>]*>", "", html_of(bv.page_parts(f))))
    for marker in ("Backtest", "a year to the Nifty 500", "Price returns on both sides", "What was tested",
                   "A year, compounded", "Lead over the Nifty 500", "points a year", "calendar time",
                   "Why the Nifty 500 and not Nifty Total Market", "The two halves", "Show the table",
                   "Below its peak now", "Max drawdown", "Days below its peak", "Back at the peak",
                   "Month by month", "Survivorship", "Look-ahead", "Not checked", "Rules chosen after looking",
                   "found only 10 stocks", "Trades closed", "Median trade", "Portfolio", "Data to", "prices to"):
        assert marker.lower() in text.lower(), marker
    kinds = [p.kind for p in bv.page_parts(f) if hasattr(p, "kind")]
    assert kinds[:2] == ["btgrowth", "trows"]


def test_the_stored_reference_is_for_the_default_run():
    ref = json.loads((ROOT / "data" / "backtest_reference.json").read_text(encoding="utf-8"))
    assert set(ref["rows"]) >= {"as_tested", "monthly_reset", "cost_60", "cost_100", "nifty_500"}
    assert ref["after_tax"]["replay_gap_pts"] <= 0.5
    assert ref["rows"]["cost_100"] < ref["rows"]["cost_60"] < ref["rows"]["as_tested"]
    assert ref["after_tax"]["rule"] < ref["rows"]["as_tested"]
