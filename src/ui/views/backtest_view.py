"""Backtest (S174): has this rule beaten the market over a long, honest history, and what does it depend on?

Built from mock-up v1, approved by the owner on 21 Nov 2026 with his seven decisions
(docs/BACKTEST_REQUIREMENTS.md): one page of research runs on NSE's long price file
(the tab that replayed the live system's recent months is gone: Portfolio owns the record); the Nifty 500 the headline
benchmark, with each universe's own NSE index "for this universe" and Nifty Total
Market from 2022; "a year" over calendar time; price returns on both sides with the
dividend gap stated; the cost, rule and tax tests stored weekly for the default run
only (data/backtest_reference.json, scripts/build_backtest_reference.py).

Figures: src/engine/backtest_page.py, from one run of `run_backtest`. Every fall from
a peak is `metrics.drawdown`. Type and charts: the Dashboard's (dashboard_home_view,
src/ui/dash_charts.py).
"""
from __future__ import annotations

import hashlib
from time import perf_counter as _perf
import html
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

from src.ui import formats as _fmt
from src.ui import missing_words as mw

from src.core.config import BENCHMARK_SYMBOL, BENCHMARK_SYMBOL_N50, DEFAULT_TRANSACTION_COST_BPS, RISK_FREE_RATE
from src.core.market_time import ist_now
from src.engine import backtest_page as bp
from src.engine import compute_gate
from src.engine import portfolio_report as pr
from src.engine.backtest_export import RunSpec, export_zip, rules_table, trades_table
from src.engine.backtester import DEFAULT_BACKTEST_MONTHS, run_backtest  # noqa: F401  (kept for the 18-month rule's test)
from src.engine.pipeline import price_fingerprint
from src.engine.track_record import SHADOWS, TRACK_RECORD_CONFIG
from src.loaders.price_loader import fetch_benchmark_history
from src.ui import page_kit as kit
from src.ui.system_param import page_href
from src.ui.views.dashboard_home_view import END, HOME_CSS, Chart, emit, how, sg
from src.ui.views.portfolio_page import history_spec

e = html.escape
ROOT = Path(__file__).resolve().parents[3]
REFERENCE = ROOT / "data" / "backtest_reference.json"
HISTORICAL_INDUSTRIES = bp.HISTORICAL_INDUSTRIES
BOOK_YIELD = 0.5                    # % a year, the book's dividend yield in the test of 11 Nov 2026 (2020-25 only, S125)
BOOK_YIELD_TEST = "11 Nov 2026"
MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# How a held stock's weight is set at each rebalance (owner, 11 Nov 2026; decision G of
# 21 Nov 2026: the six-monthly reset is the default, applied from the first month).
REBALANCE_RULES = {
    "live": "Six-monthly reset: winners run to 15%, new buys 5% (the live rule)",
    "monthly": "Reset every holding to its target weight at every rebalance",
}
RULE_WORDS = {"live": "Six-monthly reset, winners run to 15%", "monthly": "Monthly reset to 5%"}


def rebalance_rule_kwargs(rule: str, hold_cap: float | None = None) -> dict:
    """run_backtest keywords for a rebalance rule, the live one from the record's config. `hold_cap`
    (a fraction) replaces the record's 15% cap under the live rule (S219-6); the monthly reset has none."""
    if rule != "live":
        return {}
    cfg = TRACK_RECORD_CONFIG
    return {"hold_cap": cfg["hold_cap"] if hold_cap is None else float(hold_cap), "hold_cap_from": None,
            "buy_size": cfg["buy_size"], "weight_reset_months": tuple(cfg["weight_reset_months"])}


def engine_kwargs(s: dict) -> dict:
    """The settings' own run_backtest keywords (everything but the window's inputs and the caps)."""
    return dict(top_n=s["top_n"], rebal_freq=s["rebal_freq"], weight_method=s["weight_method"],
                config_weights=s["weights"], cost_bps=s["cost_bps"], buffer_n=s["buffer_n"],
                ema_period=s["ema_period"], high_pct=s["high_pct"], score_method=s["score_method"],
                ath_pct=s["ath_pct"], ath_min_years=s["ath_min_years"], exit_ema_period=s["exit_ema_period"],
                exit_high_pct=s["exit_high_pct"], exit_ath_pct=s["exit_ath_pct"],
                score_skip=int(s.get("score_skip") or 0),
                **rebalance_rule_kwargs(s["rule"], s.get("hold_cap")))


SCORE_LABELS = {
    "sharpe": "Sharpe of each lookback window (the live system)",
    "return": "Plain return of each lookback window",
}

BT_CSS = """
.bt-tested{display:flex;flex-wrap:wrap;gap:4px 18px;font-size:var(--fs-13);color:var(--c-text_2);border-top:1px solid var(--c-ink);border-bottom:1px solid var(--c-rule_soft);padding:10px 0;margin:0}
.bt-tested b{color:var(--c-ink);font-weight:600}
.bt-warn{margin:0;font-size:var(--fs-13);color:var(--c-caution);max-width:80ch}
.dh-tab.bt-t{min-width:0;width:auto}.bt-t th,.bt-t td{padding-right:22px}.bt-t tbody th{white-space:nowrap}
.dh-tab.bt-checks{min-width:0}.bt-checks td{white-space:normal}.bt-checks td.bt-st{white-space:nowrap;font-weight:600;font-size:var(--fs-12)}
.dh-tab.bt-months{min-width:860px;font-size:var(--fs-12)}.bt-months th,.bt-months td{padding:4px 8px 4px 0}
.bt-months tr.bt-y th{padding-top:12px;border-bottom:1px solid var(--c-rule)}
.dh-note .bt-l{color:var(--c-up)}
@media (max-width:640px){.bt-checks tr{display:grid;grid-template-columns:minmax(0,1fr) auto;border-bottom:1px solid var(--c-rule_soft)}
.bt-checks th,.bt-checks td{border-bottom:0!important}.bt-checks td:nth-child(2){grid-column:1/-1;grid-row:2;padding-top:0}.bt-checks thead{display:none}
.bt-t th,.bt-t td{padding-right:12px}}
"""


# ── Small formats ─────────────────────────────────────────────────────────────


def _d(t) -> str:
    t = pd.Timestamp(t)
    return f"{t.day} {MON[t.month - 1]} {t.year}"


def _pc(v, digits: int = 1) -> str:
    return "–" if v is None or (isinstance(v, float) and not np.isfinite(v)) else sg(v * 100, digits, "%").lstrip("+")


def _pcs(v, digits: int = 1) -> str:
    return "–" if v is None or (isinstance(v, float) and not np.isfinite(v)) else sg(v * 100, digits, "%")


def _pts(v, digits: int = 1) -> str:
    return "–" if v is None or (isinstance(v, float) and not np.isfinite(v)) else sg(v * 100, digits, " pts")


def _t(v) -> str:
    return "" if v is None or not np.isfinite(v) else ("dh-up" if v > 0 else "dh-down" if v < 0 else "")


def _kt(v) -> str:
    return "" if v is None or not np.isfinite(v) else ("up" if v > 0 else "down" if v < 0 else "")


def _num(v: float, digits: int = 1) -> str:
    """An unsigned figure, half away from zero (glossary 12): 0.125 -> "0.13"."""
    return _fmt.signed(abs(float(v)), digits).lstrip("+")


def _ahead_by(v: float, digits: int = 2) -> str:
    """"ahead by 0.12" / "behind by 0.05" / "level": the word carries the sign (S203 bt.lead.6)."""
    if _fmt.reads_zero(v * 100, digits):
        return "level"
    return f"{'ahead' if v > 0 else 'behind'} by {_num(v * 100, digits)}"


def _count(n: int, word: str) -> str:
    return f"{int(n):,} {word if int(n) == 1 else word + 's'}"


def _rupees(v) -> str:
    return f"₹{v:,.0f}"


def _kpis(cells) -> str:
    """(label, value, value tone, sub)."""
    return ('<div class="dh-kpis">' + "".join(
        f'<div class="dh-kpi"><span class="dh-k-l">{e(a)}</span><span class="dh-k-v {t}">{e(v)}</span>'
        f'<span class="dh-k-sub">{e(s)}</span></div>' for a, v, t, s in cells) + "</div>")


def _kick(n: str, text: str) -> str:
    return f'<p class="dh-kick">{e(n)} · {e(text)}</p>'


def _step(lo: float, hi: float) -> float:
    """A line-bar step that puts 40 to 60 lines on the row (PAGE_DESIGN 4.2)."""
    for s in (0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 20.0):
        if (hi - lo) / s <= 60:
            return s
    return 25.0


# ── Inputs ────────────────────────────────────────────────────────────────────


# st.cache_resource, not st.cache_data (S208): cache_data unpickled a fresh copy of the
# long file (~2,500 symbols x 16 years) on every rerun of every session. The callers
# only read it (frame_for reindexes and converts into a new frame);
# tests/test_backtest_long_cache.py holds them to that. app.py drops this cache with
# st.cache_resource.clear() on a new revision and under the memory guard.
@st.cache_resource(show_spinner=False, ttl=3600, max_entries=1)
def _long_file():
    """Closes and report only: traded value is fetched when a floor is set."""
    from src.loaders import nse_long

    return nse_long.load(with_value=False)


@st.cache_resource(show_spinner=False, ttl=3600, max_entries=1)
def _long_value():
    from src.loaders import nse_long

    return nse_long.load_value()


@st.cache_data(show_spinner=False, ttl=3600, max_entries=16)
def _fingerprint_once(kind: str, stamp: str, inputs: str, _frame: pd.DataFrame) -> str:
    """A run frame's whole-history fingerprint, once per input (S208).

    Only the string is kept, not the frame: holding the run frame and the traded-value
    frame in st.cache_resource cost ~45 MB resident on the page bench, for less than the
    hash it saved. `stamp` names the stored file (its build, last session, object and
    shape) and `inputs` everything the frame is cut by, so a new file or window is a new
    key. The fingerprint still covers every row (owner decision 3B).
    """
    return price_fingerprint(_frame)


def _file_stamp(frame: pd.DataFrame, report: dict | None = None) -> str:
    report = report or {}
    last = frame.index[-1] if len(frame.index) else "-"
    return f"{report.get('built')}|{report.get('last_session')}|{id(frame)}|{frame.shape}|{last}"


def _run_frame(close: pd.DataFrame, report: dict, key: str, columns, end: pd.Period,
               to_latest: bool) -> tuple[pd.DataFrame, str]:
    """The run's price frame, built per rerun as before, and its fingerprint, hashed once."""
    frame = bp.frame_for(close, columns, end, to_latest)
    cols = hashlib.md5(",".join(map(str, sorted(map(str, columns)))).encode()).hexdigest()
    fingerprint = _fingerprint_once("run", _file_stamp(close, report), f"{key}|{end}|{bool(to_latest)}|{cols}", frame)
    return frame, fingerprint


def _traded(value: pd.DataFrame, cols: list, last) -> tuple[pd.DataFrame, str]:
    """The run's average traded value, per rerun as before, and its fingerprint, hashed once."""
    from src.loaders import nse_long

    traded = nse_long.average_value(value.reindex(columns=cols).loc[:last])
    cols_key = hashlib.md5(",".join(map(str, cols)).encode()).hexdigest()
    fingerprint = _fingerprint_once("traded", _file_stamp(value), f"{cols_key}|{pd.Timestamp(last)}", traded)
    return traded, fingerprint


def _reference() -> dict | None:
    try:
        return json.loads(REFERENCE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _history_bounds() -> dict | None:
    """The long file and the months it can test, before any choice is made."""
    loaded = _long_file()
    if loaded is None:
        kit.page_empty("No long price file yet.",
                       "It is built each week from NSE's daily files; the Backtest runs once it is in.", kicker="Backtest")
        return None
    close, _value, report = loaded
    # A year of prices before the first month, for the 12-month lookback and the EMA.
    first = pd.Period(close.index[0], freq="M") + 13
    last = pd.Period(close.index[-1], freq="M") - 1
    if first > last:
        kit.page_empty("No completed month to test yet.",
                       "The long price file needs a year of prices before its first month.", kicker="Backtest")
        return None
    return {"close": close, "report": report, "months": list(pd.period_range(first, last, freq="M"))}


def _history_inputs(rank_df: pd.DataFrame, choice: dict, bounds: dict) -> dict | None:
    """The run's inputs for the settings applied, or None when it cannot run.

    Owner, 3 Oct 2026: any index from Jan 2010, a start and end month, and a traded-value
    floor; size from the index tier. Prices are NSE's own (src/loaders/nse_long.py),
    membership each index's own point-in-time timeline (src/engine/index_universe.py).
    """
    from src.engine import index_universe as iu

    close, report = bounds["close"], bounds["report"]
    key = choice["index"]
    membership = iu.index_history(key)
    if membership is None:
        kit.note(f"No membership history for {iu.INDICES[key]}.", kind="warning")
        return None
    first = max(iu.first_month(membership), bounds["months"][0])
    start, end = choice["start"], choice["end"]
    moved = None
    if start < first:
        # The slider's first month is the file's; an index whose list begins later starts there, said
        # only when the reader moved the start (the default always starts at the list's first month).
        moved = None if start == bounds["months"][0] else f"{iu.INDICES[key]}'s point-in-time list begins {first.strftime('%b %Y')}, so the test starts there."
        start = first
    if start > end:
        kit.note(f"{iu.INDICES[key]} has no completed month in the window chosen.",
                 f"Its list begins {first.strftime('%b %Y')}; move the start or end month.", kind="warning")
        return None
    floor = float(choice["floor"] or 0.0)
    to_latest = end == bounds["months"][-1]
    frame, close_fingerprint = _run_frame(close, report, key, iu.ever_members(membership), end, to_latest)
    cols = list(frame.columns)

    # Today's list's industries, then the leavers' (bp.industry_map): the same map the weekly
    # reference uses, so the stored tests re-run exactly this page's default.
    sec, unlabelled = bp.industry_map(cols, bp.index_file_industries())

    traded = traded_fingerprint = None
    if floor:
        value = _long_value()
        if value is None:
            kit.note("Traded value is not available right now, so the floor is off for this run.", kind="warning")
            floor = 0.0
        else:
            traded, traded_fingerprint = _traded(value, cols, frame.index[-1])

    return {"key": key, "close": frame, "close_fingerprint": close_fingerprint, "membership": membership, "start": start, "end": end,
            "months": (end - start).n + 1, "floor": floor, "traded_value": traded,
            "traded_fingerprint": traded_fingerprint, "moved": moved,
            "sector_map": sec, "unlabelled": unlabelled, "name": iu.INDICES[key],
            "built": report.get("built"), "last_session": report.get("last_session"),
            "priced": report.get("symbols_priced"), "to_latest": to_latest, "first": first,
            "latest": bounds["months"][-1]}


OPEN_MIRROR = "bt_change_open__v"


def _remember_open() -> None:
    st.session_state[OPEN_MIRROR] = bool(st.session_state.get("bt_change_open"))


def _settings_form(weights: tuple[float, ...], liquidity_floor_cr: float, bounds: dict) -> dict:
    """Every setting in one form; nothing runs until Apply (owner, 9 Oct 2026)."""
    from src.engine import index_universe as iu

    # Opens in place under the settings line; open or shut, it stays so for the session (S219-6).
    with st.expander("Change the test", icon=":material/tune:", expanded=bool(st.session_state.get(OPEN_MIRROR)),
                     key="bt_change_open", on_change=_remember_open):
        with st.form("bt_settings", border=False):
            choice: dict = {}
            st.markdown("**Window**")
            h1, h2 = st.columns([1, 2])
            choice["index"] = h1.selectbox(
                "Universe", list(iu.INDICES), format_func=iu.INDICES.get,
                index=list(iu.INDICES).index(bp.DEFAULT_INDEX), key="bt_hist_index")
            months = bounds["months"]
            choice["start"], choice["end"] = h2.select_slider(
                "Start and end month", months, value=(months[0], months[-1]),
                format_func=lambda m: m.strftime("%b %Y"), key="bt_hist_months",
                help="An index whose point-in-time list begins later starts there.")
            choice["floor"] = st.number_input(
                "Minimum traded value (₹ Cr, 20-day average; 0 = off)", min_value=0.0,
                max_value=500.0, value=float(liquidity_floor_cr or 0.0), step=1.0, key="bt_hist_floor")

            st.markdown("**Portfolio**")
            c1, c2 = st.columns(2)
            top_n = c1.number_input("Holdings", min_value=1, max_value=100, value=20, step=1, key="bt_top_n")
            keep_rank = c2.number_input(
                "Keep a holding while its rank is within the top", min_value=1, max_value=750,
                value=40, step=1, key="bt_keep_rank",
                help="A stock already held is sold only when it ranks below this. Below the number of "
                     "holdings it is raised to it.")
            c3, c4 = st.columns(2)
            rebal = c3.number_input(
                "Rebalance every (trading days)", min_value=1, max_value=252, value=21, step=1,
                key="bt_rebal_days",
                help="21 = monthly: the signal is each calendar month's last close, the purchase the next "
                     "session's close (the live system). Any other number: every that many sessions.")
            weighting = c4.selectbox("Weighting", ["Equal Weight", "Inverse Volatility"],
                                     format_func={"Equal Weight": "Equal weight",
                                                  "Inverse Volatility": "Inverse volatility"}.get,
                                     index=0, key="bt_weight_scheme")
            rule = st.selectbox(
                "Rebalance rule", list(REBALANCE_RULES), format_func=REBALANCE_RULES.get, index=0,
                key="bt_rebalance_rule",
                help="The live book, from the 30 Nov 2026 signal: holdings keep their drifted weight (cut "
                     "back only above 15%), each new buy is 5% of the account at the last reset, and every "
                     "holding goes back to its target weight in March and September. Applied here from the "
                     "first month. The other rule resets every holding at every rebalance, as the record did "
                     "before.")
            hold_cap = st.number_input(
                "Cut a holding back when it grows past (% of the book)", min_value=5.0, max_value=100.0,
                value=float(TRACK_RECORD_CONFIG["hold_cap"]) * 100, step=1.0, key="bt_hold_cap",
                help="Under the six-monthly reset a holding keeps the weight its price moves gave it and is cut back "
                     "to this only when it grows past it. 15% is the live rule. The monthly reset puts every "
                     "holding back to its target each month, so this setting does not apply to it.")
            cost = st.number_input(
                "Trading cost (bps a round trip)", min_value=0.0, max_value=300.0,
                value=float(DEFAULT_TRANSACTION_COST_BPS), step=1.0, key="bt_cost",
                help="30 bps: about 22 bps of it is statutory (STT 0.1% each side, stamp duty 0.015% on the "
                     "buy, exchange and SEBI fees, GST); the rest pays the spread, which has not been "
                     "measured (S123).")

            st.markdown("**Rules** · to buy, a stock must pass every buy rule; a holding is kept while it "
                        "passes every keep rule (blank = same as buy)")
            b_col, k_col = st.columns(2)
            b_col.caption("To buy")
            k_col.caption("To keep holding")
            ema_period = b_col.number_input(
                "Close above its EMA of (sessions)", min_value=2, max_value=400, value=50,
                step=1, key="bt_ema_period", help="The live system uses 50.")
            exit_ema = k_col.number_input(
                "Close above its EMA of (sessions) ", min_value=2, max_value=400, value=None,
                step=1, key="bt_exit_ema", placeholder="same as buy",
                help="The exit average: a holding is sold when its close falls below this average. Blank = the "
                     "buy rule's average (the live system).")
            off_52w = b_col.number_input(
                "Within this % of its 52-week high", min_value=0.5, max_value=95.0, value=20.0,
                step=0.5, key="bt_52w_off", help="The live system uses 20%.")
            exit_52w = k_col.number_input(
                "Within this % of its 52-week high ", min_value=0.5, max_value=95.0, value=None,
                step=0.5, key="bt_exit_52w", placeholder="same as buy",
                help="A holding is sold when its close is further than this below its 52-week high. Blank = the "
                     "buy rule's 20% (the live system).")
            off_ath = b_col.number_input(
                "Within this % of its all-time high (blank = no rule)", min_value=0.5,
                max_value=95.0, value=None, step=0.5, key="bt_ath_off", placeholder="no rule",
                help="All-time high = the highest close on file up to each signal date, since 2008.")
            exit_ath = k_col.number_input(
                "Within this % of its all-time high ", min_value=0.5, max_value=95.0, value=None,
                step=0.5, key="bt_exit_ath", placeholder="same as buy")
            ath_years = st.number_input(
                "All-time-high rule: years of prices on file before it applies", min_value=0.0,
                max_value=30.0, value=3.0, step=0.5, key="bt_ath_years",
                help="The price history starts in Jan 2008, so a stock trading before then may have its real "
                     "peak earlier. Such a stock is held to the all-time-high rule only after this many years "
                     "of prices on file; a stock that listed later is held to it from the first day.")

            st.markdown("**Score** · how stocks are ranked")
            sc1, sc2 = st.columns([2, 1])
            score = sc1.radio("Score each lookback window by", list(SCORE_LABELS),
                              format_func=SCORE_LABELS.get, key="bt_score", horizontal=True,
                              help="Sharpe: each window's return divided by its ups and downs (the live system). "
                                   "Plain return: the window's return alone, so a jumpy stock scores as high as "
                                   "a steady one with the same gain.")
            skip = sc2.number_input(
                "Leave out the latest sessions (days)", min_value=0, max_value=63, value=0, step=1,
                key="bt_score_skip",
                help="The score is read this many sessions before each signal day, so the last few days' moves "
                     "do not count; the filters and the purchase stay on the signal day. 0 = the live system.")
            st.caption("Lookback weights · how much each window counts in the score")
            bw = st.columns(5)
            active = tuple(
                bw[i].slider(lbl, 0.0, 1.0, float(weights[i]), 0.05, key=f"btw_{i + 1}")
                for i, lbl in enumerate(["1M", "3M", "6M", "9M", "12M"])
            )
            st.caption("A setting chosen after seeing its result on this same history flatters the result: only "
                       "months after a rule was fixed test it. The 30-holding settings from the 12 Oct 2026 sweep "
                       "are recorded forward as a shadow book (Portfolio), not offered here as advice.")
            st.form_submit_button("Apply", type="primary", icon=":material/play_arrow:", use_container_width=True)

    def frac(off):
        return None if off is None else 1.0 - float(off) / 100.0

    return {
        "history": choice,
        "top_n": int(top_n), "rebal_freq": int(rebal), "weight_method": weighting,
        "buffer_n": max(int(keep_rank), int(top_n)), "cost_bps": float(cost),
        "ema_period": int(ema_period), "high_pct": frac(off_52w), "ath_pct": frac(off_ath),
        "exit_ema_period": None if exit_ema is None else int(exit_ema),
        "exit_high_pct": frac(exit_52w), "exit_ath_pct": frac(exit_ath),
        "ath_min_years": float(ath_years),
        "score_method": score, "weights": active, "rule": rule, "score_skip": int(skip),
        "hold_cap": float(hold_cap) / 100.0,
    }


def is_default(s: dict, h: dict, stock_cap: float, sector_cap: float) -> bool:
    """The run the page opens on, and the one data/backtest_reference.json tests."""
    cfg = TRACK_RECORD_CONFIG
    return (h["key"] == bp.DEFAULT_INDEX and h["start"] == h["first"] and h["end"] == h["latest"]
            and not h["floor"] and s["top_n"] == cfg["top_n"] and s["buffer_n"] == cfg["buffer_n"]
            and s["rebal_freq"] == 21 and s["weight_method"] == cfg["weight_method"] and s["rule"] == bp.DEFAULT_RULE
            and s["cost_bps"] == cfg["cost_bps"] and s["ema_period"] == cfg["ema_period"]
            and abs((s["high_pct"] or 0) - cfg["high_pct"]) < 1e-9 and s["ath_pct"] is None
            and s["exit_ema_period"] is None and s["exit_high_pct"] is None and s["exit_ath_pct"] is None
            and s["score_method"] == "sharpe" and not s.get("score_skip")
            and (s.get("hold_cap") is None or abs(s["hold_cap"] - cfg["hold_cap"]) < 1e-9)
            and np.allclose(s["weights"], cfg["config_weights"])
            and abs(stock_cap - cfg["stock_cap"]) < 1e-9 and abs(sector_cap - cfg["sector_cap"]) < 1e-9)


# ── The page's parts ───────────────────────────────────────────────────────────


def tested_items(s: dict, h: dict) -> list[str]:
    """The run's settings in short plain words, in the order of the form (S219-6)."""
    rebal = ("monthly, at the month’s last close" if s["rebal_freq"] == 21 else f"every {s['rebal_freq']} sessions")
    skip = int(s.get("score_skip") or 0)
    items = [h["name"], f"{h['start'].strftime('%b %Y')} to {h['end'].strftime('%b %Y')}",
             f"{s['top_n']} holdings", f"keep to rank {s['buffer_n']}", f"rebalanced {rebal}",
             f"skip {skip} day{'' if skip == 1 else 's'}",
             "Sharpe score" if s["score_method"] == "sharpe" else "plain-return score",
             f"buy above its {s['ema_period']}D EMA", f"within {(1 - s['high_pct']) * 100:g}% of its 52-week high"]
    if s["ath_pct"] is not None:
        items.append(f"within {(1 - s['ath_pct']) * 100:g}% of its all-time high")
    if s["ath_pct"] is not None or s["exit_ath_pct"] is not None:
        items.append(f"all-time high: the highest close since {h['close'].index[0]:%b %Y}, applied after "
                     f"{s['ath_min_years']:g} years on file")
    if s["exit_ema_period"] is not None:
        items.append(f"sell below its {s['exit_ema_period']}D EMA")
    if s["exit_high_pct"] is not None:
        items.append(f"sell beyond {(1 - s['exit_high_pct']) * 100:g}% below its 52-week high")
    if s["exit_ath_pct"] is not None:
        items.append(f"sell beyond {(1 - s['exit_ath_pct']) * 100:g}% below its all-time high")
    if s["rule"] == "live":
        cap = s.get("hold_cap")
        cap = TRACK_RECORD_CONFIG["hold_cap"] if cap is None else cap
        items.append(f"six-monthly reset, winners run to {cap * 100:g}%")
    else:
        items.append(RULE_WORDS.get(s["rule"], s["rule"]).lower())
    if s["weight_method"] != "Equal Weight":
        items.append(s["weight_method"].lower())
    if not np.allclose(s["weights"], TRACK_RECORD_CONFIG["config_weights"]):
        items.append("lookback weights " + " / ".join(f"{w:.2f}".lstrip("0") for w in s["weights"]))
    if h["floor"]:
        items.append(f"traded value ₹{h['floor']:g} Cr or more")
    items.append(f"{s['cost_bps']:g} bps a round trip")
    return items


def tested_line(s: dict, h: dict) -> str:
    """The one line first on the page: what this run tested, "Change the test" right under it."""
    return ('<div class="bt-tested" aria-label="What was tested"><span><b>What was tested</b> '
            + e(" · ".join(tested_items(s, h))) + "</span></div>")


def _against(b) -> str:
    """", against a gain of 12.1% for the Nifty 500"; nothing when the index figure is missing (S203 bt.head.1)."""
    if b is None or (isinstance(b, float) and not np.isfinite(b)):
        return ""
    return f", against a {'gain' if b >= 0 else 'loss'} of {_pc(abs(b))} for the Nifty 500"


def _updown(v) -> str:
    return "–" if v is None else f"{'up' if v >= 0 else 'down'} {_pc(abs(v))}"


def head(f: dict) -> list:
    sm, h = f["summary"], f["h"]
    # The verdict phrase in up/down colour: the rule's figure against the index's (S219 2).
    if sm.a_year is not None:
        ahead = None if sm.bench_a_year is None else sm.a_year >= sm.bench_a_year
        # The verb carries the sign, never a signed figure after "made" (S203 bt.head.1).
        title = (e(f"Since {sm.first:%B %Y}, this rule ")
                 + kit.verdict(f"{'made' if sm.a_year >= 0 else 'lost'} {_pc(abs(sm.a_year))} a year", ahead)
                 + e(_against(sm.bench_a_year) + ", before tax."))
    else:
        ahead = None if sm.total is None or sm.bench_total is None else sm.total >= sm.bench_total
        verb = "returned" if sm.total is None or sm.total >= 0 else "lost"
        title = (e(f"Over {sm.months} months, this rule ")
                 + kit.verdict(f"{verb} {_pc(None if sm.total is None else abs(sm.total))}", ahead)
                 + e(_against(sm.bench_total) + "."))
    lede = (f"{'The record’s rules' if f['default'] else 'These rules'} replayed on the {h['name']} as it stood each "
            f"month, {_d(sm.first)} to {_d(sm.last)}, on NSE’s closes, after {f['s']['cost_bps']:g} bps a round trip. "
            "Price returns on both sides. A replay of the past, not a forecast.")
    out = [f'<div class="dh-sec"><p class="dh-kick">Backtest</p><h1 id="s-top" class="dh-h1">{title}</h1>'
           f'<p class="dh-lede">{e(lede)}</p></div>']
    if h.get("moved"):
        out.append(f'<p class="dh-note">{e(h["moved"])}</p>')
    if not f["default"]:
        out.append('<p class="bt-warn"><span class="warn-word">Warning:</span> These settings differ from the record’s. A setting chosen after seeing its result '
                   'on this same history flatters the result; only months after a rule was fixed test it.</p>')
    return out


def section_lead(f: dict) -> list:
    sm, st_ = f["summary"], f["stats"]
    # The words carry the sign; the colour only repeats it (S203 bt.lead.1, S193 J).
    if sm.lead is not None and round(sm.lead * 100, 1) == 0:
        h2 = "The rule is level with the Nifty 500 over the run."
    elif sm.lead is not None:
        h2 = (f'The rule is <span class="{_t(sm.lead)}">{"ahead of" if sm.lead > 0 else "behind"} the Nifty 500 by '
              f'{abs(sm.lead) * 100:.1f} points a year</span>; it was ahead in {sm.ahead} of {sm.months} months.')
    else:
        h2 = (f'Under 12 months, so no yearly figure: the rule is <span class="{_t(sm.total)}">{e(_updown(sm.total))}</span>, '
              f'the Nifty 500 {e(_updown(sm.bench_total))}.')
    tiles = _kpis([
        # A coloured change carries its sign (S193 J: never colour alone).
        ("A year, compounded", _pcs(sm.a_year) if sm.a_year is not None else "–", _t(sm.a_year),
         f"Nifty 500 {_pc(sm.bench_a_year)}" if sm.a_year is not None else "needs 12 months"),
        ("Lead over the Nifty 500", _pts(sm.lead) if sm.lead is not None else _pts(sm.total - sm.bench_total),
         _t(sm.lead if sm.lead is not None else sm.total - sm.bench_total), "a year" if sm.lead is not None else "over the run"),
        ("₹100 became", _rupees(100 * (1 + sm.total)), "", f"Nifty 500 {_rupees(100 * (1 + sm.bench_total))}"),
        ("Months ahead of the Nifty 500", f"{sm.ahead} of {sm.months}", "",
         f"{sm.ahead / max(sm.months, 1):.0%} · up in {_count(sm.up, 'month')}"),
    ])
    ch = f["chart"]
    series = [{"name": "This rule", "short": "This rule", "color": "s-book", "values": ch["series"]["rule"], "dd": ch["dd"]["rule"]},
              {"name": "Nifty 500", "short": "Nifty 500", "color": "s-n500", "values": ch["series"]["n500"],
               "dd": ch["dd"]["n500"], "dash": True}]
    top = max(v for v in ch["series"]["rule"] + ch["series"]["n500"] if v is not None)
    ticks = [t for t in (50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000) if t <= top * 1.2]
    spec = {"dates": ch["dates"], "series": series, "ticks": ticks, "ddHead": "Below its peak"}
    dy, half = f["div_yield"], sm.split
    notes = [
        "<b>Price returns, both sides.</b> The rule’s figure includes a dividend only where it was 10% of the price or "
        "more (the long file takes those out as an adjustment); the Nifty 500 figure is NSE’s price index, which takes "
        "out only special dividends, 2% of the price or more (NSE’s index methodology, Nov 2022), not ordinary ones"
        + (f". NSE’s file puts the Nifty 500’s dividend yield at {dy:.1f}% a year on average since "
           f"{f['div_yield_from']:%b %Y}; in a test of {BOOK_YIELD_TEST} the book’s was about {BOOK_YIELD:.1f}%, measured "
           f"2020–25 only. Against the index with every dividend, the lead is about {dy - BOOK_YIELD:.1f} points a year "
           "smaller than shown."
           if dy is not None and f.get("div_yield_from") is not None else "."),
        f"<b>A year, compounded</b> is measured over calendar time, {sm.years:.1f} years from the first fill. "
        f"<b>pts</b>: {_fmt.PTS_NOTE}",
        "<b>Why the Nifty 500 and not Nifty Total Market.</b> "
        + (f"Nifty Total Market starts on {_d(f['tm_from'])} and this history in {sm.first.year}" if f.get("tm_from") is not None
           else f"This history starts in {sm.first.year}, before Nifty Total Market")
        + f" (owner, 21 Nov 2026). Nifty Total Market is beside it from {bp.TOTAL_MARKET_FROM} in section 3"
        + (f" and from {f['tm_window_from']:%b %Y} in section 4." if f.get("tm_window_from") is not None else ".")
        + (f" For this universe its own index, the {e(f['uidx_name'])}, is shown beside both." if f.get("uidx_name") else ""),
    ]
    if half is not None and sm.lead_first_half is not None:
        # The words carry the sign (S203 bt.lead.6): "led by −0.12" had no branch.
        notes.append(f"<b>The two halves.</b> To {half - pd.offsets.MonthEnd(1):%b %Y}, the rule was "
                     f"{_ahead_by(sm.lead_first_half)} points a month on average; after it, {_ahead_by(sm.lead_second_half)}."
                     + (f" The median month’s lead was {sg(sm.median_lead * 100, 2)} points." if sm.median_lead is not None else ""))
    rows = [["Total return", _pcs(sm.total, 0), _pcs(sm.bench_total, 0)],
            ["A year, compounded", _pc(sm.a_year), _pc(sm.bench_a_year)],
            # Costs and turnover do not apply to an index: a blank cell, not "–" (S193 E, rule 2).
            ["A year before costs", _pc(st_.get("cagr_gross")), mw.NOT_APPLICABLE],
            ["Volatility, a year (daily returns)", _pc(st_.get("volatility")), _pc(st_.get("bench_volatility"))],
            [f"Sharpe, over a fixed {RISK_FREE_RATE:.1%} a year, ± one standard error",
             f"{st_.get('sharpe', float('nan')):.2f} ± {st_.get('sharpe_stderr_iid', float('nan')):.2f}", _ratio(st_.get("bench_sharpe"))],
            [f"Sortino, over a fixed {RISK_FREE_RATE:.1%} a year",
             f"{st_['sortino']:.2f}" if np.isfinite(st_.get("sortino", float("nan"))) else "–", _ratio(st_.get("bench_sortino"))],
            ["Turnover, one way, a month", f"{st_.get('avg_turnover', 0):.0f}%", mw.NOT_APPLICABLE]]
    return ['<div class="dh-sec">', _kick("1", "Ahead of the Nifty 500"), f'<h2 id="s-lead" class="dh-h2">{h2}</h2>', tiles, "</div>",
            Chart("btgrowth", spec, {"label": "Growth of ₹100 on a log scale, this rule and the Nifty 500, and how far each "
                                              "sits below its peak"}),
            '<div class="dh-sec dh-sec-cont">'
            + how("₹100 put in at the first fill and left to the rule, against ₹100 in the Nifty 500, weekly closes on a "
                  "log scale (equal heights are equal percentage moves). The lower pane is how far each sits below its "
                  "own highest value so far, on daily closes.",
                  "Move the pointer, tap, or use the arrow keys; the values follow in the headings. At rest they are "
                  "the latest.", ["Measure", "This rule", "Nifty 500"], rows)
            + "".join(f'<p class="dh-note">{n}</p>' for n in notes) + "</div>", END]


def section_falls(f: dict) -> list:
    rule_falls, n500_falls, now, bnow = f["falls"], f["bench_falls"], f["below_now"], f["bench_below_now"]
    big = rule_falls[0] if rule_falls else None
    if now < -0.005:
        peak = f["current_peak"]
        # One verb for one event, "made back" (S203 bt.fall.1, dash.mom.6); the open case gives its depth too.
        h2 = f'The rule is <span class="dh-down">{e(_pc(-now))} below its {peak:%B %Y} peak</span>.'
        if big and big.recovered is None:
            h2 += f" Its max drawdown since {f['summary'].first.year}, {e(_pc(abs(big.depth)))}, is not yet made back."
        elif big:
            h2 += f" Its max drawdown, {e(_pc(abs(big.depth)))}, was made back by {e(_d(big.recovered))}."
    else:
        h2 = "The rule is at its peak."
        if big:
            h2 += (f" Its max drawdown was {e(_pc(abs(big.depth)))}, made back by {e(_d(big.recovered))}." if big.recovered is not None
                   else f" Its max drawdown was {e(_pc(abs(big.depth)))}.")
    cur_days = f["current_days"]
    needs = (1 / (1 + now) - 1) if now < 0 else 0.0
    tiles = _kpis([
        ("Below its peak now", _pcs(now), "dh-down" if now < 0 else "", f"Nifty 500 {_pcs(bnow)}"),
        ("Max drawdown", _pcs(big.depth) if big else "–", "dh-down",
         f"Nifty 500 {_pcs(n500_falls[0].depth)}" if n500_falls else ""),
        ("Days below its peak", f"{cur_days:,}" if now < 0 else "0", "dh-watch" if now < 0 else "",
         f"since {_d(f['current_peak'])}" if now < 0 else "at its peak"),
        ("Recovered", "Not yet" if now < 0 else "Yes", "dh-watch" if now < 0 else "dh-up",
         f"needs {_pcs(needs)}" if now < 0 else ""),
    ])

    def row(name, fl):
        rec = _d(fl.recovered) if fl.recovered is not None else '<span class="dh-watch">not yet</span>'
        return (f'<tr><th scope="row">{e(name)}</th><td class="dh-num dh-down">{e(_pcs(fl.depth))}</td>'
                f'<td class="dh-num">{e(_d(fl.peak))}</td><td class="dh-num">{e(_d(fl.low))}</td>'
                f'<td class="dh-num">{rec}</td><td class="dh-num">{fl.days:,}</td></tr>')
    body = "".join(row("This rule" + (" (open)" if fl.recovered is None else ""), fl) for fl in rule_falls)
    body += "".join(row("Nifty 500", fl).replace("<th scope=\"row\">", '<th scope="row" class="dh-muted">', 1) for fl in n500_falls[:2])
    table = ('<div class="dh-scroll"><table class="dh-tab bt-t"><thead><tr><th scope="col">Deepest drawdowns</th>'
             '<th scope="col" class="dh-num">Fall</th><th scope="col" class="dh-num">Peak</th><th scope="col" class="dh-num">Low</th>'
             '<th scope="col" class="dh-num">Back at the peak</th><th scope="col" class="dh-num">Days below</th></tr></thead>'
             f"<tbody>{body}</tbody></table></div>")
    return ['<div class="dh-sec">', _kick("2", "Falls from a peak"), f'<h2 id="s-falls" class="dh-h2">{h2}</h2>', tiles, table,
            '<p class="dh-note">A fall runs from the highest close before it to the day that close is regained; days are '
            'calendar days. Daily closes, as on Portfolio (<code>metrics.drawdown</code>).</p></div>', END]


def _span(r) -> str:
    n, a, b = int(r["months"]), int(r["first_month"]), int(r["last_month"])
    if n == 12:
        return ""
    return f"{MON[a - 1]}–{MON[b - 1]}" if n > 1 else MON[b - 1]


_SHORT = {"Survivorship": "survivorship", "Look-ahead": "look-ahead", "Costs": "costs", "Tax": "tax",
          "Rules chosen after looking": "the choice of rules"}


def _and(words: list[str]) -> str:
    return words[0] if len(words) == 1 else ", ".join(words[:-1]) + " and " + words[-1]


def trust_headline(checks: list) -> str:
    """Built from the table's own statuses (S203 bt.tr.4): it said "handled" over a "Soft spot" row."""
    done = [_SHORT[a] for a, _, c in checks if c == "Checked" and a in _SHORT]
    soft = [_SHORT[a] for a, _, c in checks if c == "Soft spot" and a in _SHORT]
    parts = []
    if done:
        w = _and(done)
        parts.append(f"{w[0].upper() + w[1:]} {'is' if len(done) == 1 else 'are'} handled")
    if soft:
        w = _and(soft)
        if not parts:
            w = w[0].upper() + w[1:]
        parts.append(f'<span class="dh-watch">{e(w)}</span> {"is the soft spot" if len(soft) == 1 else "are the soft spots"}')
    n = sum(1 for c in checks if c[2] == "Not checked")
    if n:
        parts.append(f"{n} check{'s are' if n != 1 else ' is'} not made")
    return "; ".join(parts) + "."


def section_years(f: dict) -> list:
    yt: pd.DataFrame = f["years"]
    cols = [("n500", "Nifty 500")]
    if f.get("uidx_name"):
        cols.append(("uidx", f["uidx_short"]))
    if "tm" in yt and f["h"]["key"] != bp.TOTAL_MARKET:
        cols.append(("tm", "Nifty Total Market"))
    lead = (yt["rule"] - yt["n500"]).tolist()
    finite = [v * 100 for v in lead if np.isfinite(v)]
    lo = min(0.0, min(finite or [0.0]))
    hi = max(0.0, max(finite or [0.0]))
    step = _step(lo, hi)
    lo, hi = np.floor(lo / step) * step, np.ceil(hi / step) * step
    if hi - lo < step * 40:
        hi = lo + step * 40 if lo < 0 else step * 40
    rows = []
    for (_, r), ld in zip(yt.iterrows(), lead):
        vals = [_pcs(r["rule"])] + [_pcs(r.get(k)) for k, _ in cols] + [_pts(ld).replace(" pts", "")]
        rows.append({"name": str(int(r["year"])), "sub": _span(r), "bar": None if not np.isfinite(ld) else round(ld * 100, 2),
                     "vals": vals, "cls": [_kt(r["rule"])] + ["muted"] * len(cols) + [_kt(ld) + " b"],
                     "read": [[_pts(ld), "lead over the Nifty 500", _kt(ld)], [_pcs(r["rule"]), "this rule"],
                              [_pcs(r["n500"]), "Nifty 500"]]})
    # Whole years only: a first or last year of a few months is shown in the table, not counted as a year
    # (S193 B: "13 of 17 years" counted Jan-Oct 2026). The worst is a whole year too; "behind" carries the sign.
    whole = [i for i, (_, r) in enumerate(yt.iterrows()) if int(r["months"]) == 12 and np.isfinite(lead[i])]
    ahead = sum(1 for i in whole if lead[i] > 0)
    known = len(whole)
    part = [(int(r["year"]), (int(r["first_month"]), int(r["last_month"])), lead[i]) for i, (_, r) in enumerate(yt.iterrows())
            if int(r["months"]) != 12 and np.isfinite(lead[i])]
    worst = min(whole, key=lambda i: lead[i]) if whole else None
    # Sentences, not a parenthesis inside the headline; "points" in a sentence (S203 bt.yr.1).
    sents = []
    if known:
        tone = "dh-up" if ahead * 2 > known else "dh-down" if ahead * 2 < known else ""
        sents.append(f'The rule was ahead of the Nifty 500 in <span class="{tone}">{ahead} of {known} whole years</span>.'
                     if tone else f"The rule was ahead of the Nifty 500 in {ahead} of {known} whole years.")
    if worst is not None and lead[worst] < 0:
        sents.append(f'{int(yt.iloc[worst]["year"])} was the worst, '
                     f'<span class="dh-down">{e(_num(lead[worst] * 100))} points behind</span>.')
    for y, (a_m, b_m), v in part:
        side = "ahead" if v > 0 else "behind" if v < 0 else "level"
        span = (f"from {MON[a_m - 1]} to {MON[b_m - 1]}" if a_m > 1 and b_m < 12 else
                f"from {MON[a_m - 1]}" if a_m > 1 else f"to {MON[b_m - 1]}")
        sents.append(f"{y}, {span}, was {side}.")
    h2 = " ".join(sents) or "No whole calendar year in this run yet."
    spec = {"label": "Year", "barHead": "Lead over the Nifty 500", "head": ["This rule"] + [c for _, c in cols] + ["Lead, pts"],
            "rows": rows, "lo": float(lo), "hi": float(hi), "step": step, "rest": f"{rows[0]['name']}, the first year" if rows else ""}
    mtd = f.get("mtd")
    live = f", live from {_d(f['tm_from'])}," if f.get("tm_from") is not None else ""
    note = (f"A dark zero line; a lead left of it is a year behind. The first year starts at "
            f"the first fill, {_d(f['summary'].first)}. Nifty Total Market is NSE’s index{live} so it starts in "
            f"{bp.TOTAL_MARKET_FROM}.")
    if mtd:
        # The sign in words (rule 2): "this rule is up 1.2%", not "this rule +1.2%".
        note += (f" {mtd['label']} so far, to {_d(mtd['as_of'])}, is not in the table: this rule is {_updown(mtd['rule'])}"
                 + (f", the Nifty 500 {_updown(mtd['bench'])}." if mtd.get("bench") is not None else "."))
    grid = months_grid(f["monthly"])
    return ['<div class="dh-sec">', _kick("3", "Year by year"), f'<h2 id="s-years" class="dh-h2">{h2}</h2>', "</div>",
            Chart("trows", spec, {"label": "Each calendar year: this rule, the Nifty 500 and the lead",
                                  "note": f"Each line is {step:g} pts"}),
            f'<div class="dh-sec dh-sec-cont"><p class="dh-note">{e(note)}</p>'
            f'<details><summary>Show the table · month by month</summary><div class="dh-scroll">{grid}</div></details></div>', END]


def _months_dash_note(m: pd.DataFrame) -> str:
    """One footnote for the grid's "–" (S193 E, rule 1): months before the first fill. Months after the last
    month tested are blank cells, not "–" (S203 bt.yr.3, owner's answer 8)."""
    first = m.index.min()
    return mw.column_note("a month", f"before {first:%b %Y}, the replay's first month") if first.month > 1 else ""


def _ratio(v) -> str:
    return "–" if v is None or (isinstance(v, float) and not np.isfinite(v)) else f"{v:.2f}"


def months_grid(m: pd.DataFrame) -> str:
    """Month by month, Portfolio's layout: this rule, the Nifty 500 and the lead in pts, a block a year."""
    if m.empty:
        return ""
    head = "".join(f'<th scope="col" class="dh-num">{x}</th>' for x in MON + ["Year"])
    body = ""
    last = m.index.max()
    for y, g in m.groupby(m.index.year):
        by = {d.month: r for d, r in g.iterrows()}

        def empty(k, y=y):
            # Before the first fill: "–", said in the note; after the last month tested: blank (owner's answer 8).
            return '<td class="dh-num"></td>' if (y, k) > (last.year, last.month) else '<td class="dh-num dh-muted">–</td>'

        yr_rule = float((1 + g["rule"]).prod() - 1)
        yr_b = float((1 + g["bench"]).prod() - 1)
        body += f'<tr class="bt-y"><th scope="rowgroup" colspan="14">{y}</th></tr>'
        for label, fn, yv in (("This rule", lambda r: _pcs(r["rule"]), _pcs(yr_rule)),
                              ("Nifty 500", lambda r: _pcs(r["bench"]), _pcs(yr_b)),
                              ("Lead", lambda r: _pts(r["rule"] - r["bench"]).replace(" pts", ""), _pts(yr_rule - yr_b).replace(" pts", ""))):
            cells = "".join(f'<td class="dh-num">{e(fn(by[k]))}</td>' if k in by else empty(k)
                            for k in range(1, 13))
            body += f'<tr><th scope="row">{label}</th>{cells}<td class="dh-num"><b>{e(yv)}</b></td></tr>'
    return (f'<table class="dh-tab bt-months"><thead><tr><th scope="col"></th>{head}</tr></thead><tbody>{body}</tbody></table>'
            f'<p class="dh-note">Lead in pts. A year compounds its months; the first year from the first fill. {e(_months_dash_note(m))}</p>')


def section_depends(f: dict) -> list:
    sm, ref, alt = f["summary"], f["reference"], f["alternatives"]
    parts = ['<div class="dh-sec">', _kick("4", "What the result depends on")]
    rows = []
    if ref:
        r = ref["rows"]
        at = ref.get("after_tax") or {}
        tax_cost = None
        if at.get("rule") is not None and at.get("nifty_500") is not None and r.get("as_tested") and r.get("nifty_500"):
            tax_cost = (r["as_tested"] - r["nifty_500"]) - (at["rule"] - at["nifty_500"])
        cost_hit = (r["as_tested"] - r["cost_60"]) if r.get("cost_60") is not None else None
        rule_hit = abs(r["as_tested"] - r["monthly_reset"]) if r.get("monthly_reset") is not None else None
        # Two sentences, and a sentence when the stored tests are missing, not a label (S203 bt.dep.1).
        bits = []
        if tax_cost is not None:
            bits.append(f'Tax costs the lead <span class="dh-down">{_num(tax_cost * 100)} points a year</span>.')
        if cost_hit is not None and rule_hit is not None:
            c, r_ = _num(cost_hit * 100), _num(rule_hit * 100)
            bits.append("Costs and the rebalance rule matter about as much." if c == r_ else
                        "Costs matter more than the rebalance rule." if cost_hit > rule_hit else
                        "The rebalance rule matters more than costs.")
        h2 = " ".join(bits) if bits else "The stored tests for the default run are not in yet."
        items = [("As tested", "six-monthly reset, 30 bps", sm.a_year, True),
                 ("Monthly reset", "the record’s rule to Oct 2026", r.get("monthly_reset"), False),
                 ("Costs 60 bps", "a round trip", r.get("cost_60"), False),
                 ("Costs 100 bps", "a round trip", r.get("cost_100"), False),
                 ("After tax", "estimate, sold at the end, no other gains", at.get("rule"), False),
                 ("Nifty 500", "price index", sm.bench_a_year, False),
                 ("Nifty 500 after tax", "bought at the start, sold at the end", at.get("nifty_500"), False)]
        items = [x for x in items if x[2] is not None]
        hi_v = max(v for *_, v, _b in items) * 100
        step = _step(0, hi_v)
        hi = float(np.ceil(hi_v / step) * step)
        for name, sub, v, base in items:
            rows.append({"name": name, "sub": sub, "bar": round(v * 100, 2), "vals": [_pc(v)], "cls": ["b" if base else ""],
                         "read": [[_pc(v), name.lower() + ", a year"]]})
        spec = {"label": f"{_d(sm.first)} – {_d(sm.last)}", "barHead": f"A year, 0 to {hi:g}%", "head": ["A year"],
                "rows": rows, "lo": 0.0, "hi": hi, "step": step, "lines": [round(sm.bench_a_year * 100, 2)] if sm.bench_a_year else [],
                "rest": "As tested"}
        stale = "" if ref.get("long_last_session") == f"{f['long_last']:%Y-%m-%d}" else (
            f" These tests were run on the long file to {_d(ref['long_last_session'])}; this page reads the file to "
            f"{_d(f['long_last'])}, so they can differ slightly until the next weekly run.")
        parts += [f'<h2 id="s-depends" class="dh-h2">{h2}</h2>', "</div>",
                  Chart("trows", spec, {"label": "The default run, re-run with other costs and rules, and after tax",
                                        "note": f"Each line is {step:g}%; the dashed line is the Nifty 500"}),
                  '<div class="dh-sec dh-sec-cont">'
                  f'<p class="dh-note">The rows other than “As tested” '
                  f'and “Nifty 500” are re-run once a week on the default settings only (run of {_d(ref["built"])}). After tax: '
                  f'{e(at.get("rates", ""))}, for an investor with no other gains; the index position is taxed once, long term, '
                  f'when sold.{e(stale)}</p>']
    else:
        parts += ['<h2 id="s-depends" class="dh-h2">Costs, the rebalance rule and tax are tested for the default run only.</h2>',
                  '<p class="dh-note">These settings are not the default, so the stored tests (60 and 100 bps, the monthly reset, '
                  'after tax) do not apply to them. Change the cost or the rule above to see either here.</p>']
    trows = ""
    for title, span, items in alt:
        trows += (f'<tr class="dh-grp-row"><th scope="rowgroup" colspan="3">{e(title)}'
                  f'<span class="dh-sub">{e(span)}</span></th></tr>')
        for name, a, dd in items:
            trows += (f'<tr><th scope="row">{e(name)}</th><td class="dh-num {_t(a)}">{e(_pcs(a))}</td>'
                      f'<td class="dh-num dh-down">{e(_pcs(dd))}</td></tr>')
    if trows:
        parts += ['<div class="dh-scroll"><table class="dh-tab bt-t"><thead><tr><th scope="col">Against what you could buy</th>'
                  '<th scope="col" class="dh-num">A year</th><th scope="col" class="dh-num">Max drawdown</th></tr></thead>'
                  f'<tbody>{trows}</tbody></table></div>',
                  '<p class="dh-note">NSE’s Nifty200 Momentum 30 is the nearest index a fund tracks; it is a price index too. '
                  + ("These windows are short and include this rule’s max drawdown." if _windows_cover_max_drawdown(f)
                     else "These windows are short.") + '</p>']
    return parts + ["</div>", END]


def _windows_cover_max_drawdown(f: dict) -> bool:
    """Whether every comparison window starts on or before the rule's max drawdown's peak (S203 bt.dep.4)."""
    falls, starts = f.get("falls") or [], f.get("windows_from") or []
    return bool(falls and starts and falls[0].peak >= max(pd.Timestamp(x) for x in starts))


def section_trust(f: dict) -> list:
    st_, h, sm = f["stats"], f["h"], f["summary"]
    pit, cur = int(st_.get("pit_periods", 0) or 0), int(st_.get("current_universe_periods", 0) or 0)
    stale, short = f["stale"], f["short"]
    stale_txt = "No sale used a price five or more sessions old."
    if stale:
        lo, hi = min(x["sessions"] for x in stale), max(x["sessions"] for x in stale)
        y0, y1 = min(x["exit"].year for x in stale), max(x["exit"].year for x in stale)
        stale_txt = (f"{len(stale)} sale{'s' if len(stale) > 1 else ''} used a price {lo if lo == hi else f'{lo} to {hi}'} "
                     f"sessions old ({', '.join(sorted({x['symbol'] for x in stale})[:6])}{'…' if len(stale) > 6 else ''}), "
                     f"{f'in {y0}' if y0 == y1 else f'{y0}–{y1}'}: stocks taken over or delisted, sold at their last price.")
    # A month does not find stocks; at its rebalance only so many passed (S203 bt.tr.2).
    short_txt = "Every rebalance found enough stocks that passed the rules."
    if short:
        first_d, first_n = short[0]
        short_txt = (f"At {first_d:%B %Y}’s rebalance only {_count(first_n, 'stock')} passed the rules"
                     + "".join(f"; at {d:%B %Y}’s, only {n:,}" for d, n in short[1:3])
                     + (f"; {_count(len(short) - 3, 'more rebalance')} {'was' if len(short) == 4 else 'were'} short too"
                        if len(short) > 3 else "")
                     + ". The rest of the book sat in cash at 0% until the next rebalance.")
    shadows = ", ".join(f"“{b.name.replace(' (shadow)', '')}” from {b.inception.strftime('%b %Y')}" for b in SHADOWS.values())
    checks = [
        ("Survivorship", f"{pit} of {pit + cur} rebalances picked from the {h['name']} as it stood that day, leavers included; "
                         f"the long file prices all {h['priced']:,} stocks the lists ever named." if h.get("priced") else
                         f"{pit} of {pit + cur} rebalances picked from the {h['name']} as it stood that day, leavers included.",
         "Checked" if not cur else "Soft spot"),
        ("Look-ahead", "Ranked on the month’s last close, bought at the next close; the first day the book earns is the day "
                       "after. Index lists are used from their effective date (NSE announces them about four weeks ahead).",
         "Checked"),
        ("Stocks that stopped trading", "Valued at their last price. " + stale_txt, "Checked"),
        ("Cash", short_txt, "Checked"),
        ("Costs", f"{f['s']['cost_bps']:g} bps a round trip: about 22 statutory, the rest for the spread, which has not been "
                  "measured. The last book’s sale is not charged.", "Soft spot"),
        ("Tax", "Not in any figure above except the two after-tax rows. A monthly book realises most gains within a year.",
         "Soft spot"),
        ("Rules chosen after looking", "The record’s rules were settled while this history was on screen, and the 30-holding "
                                       "settings came from a sweep of it (12 Oct 2026). Only months after a rule was fixed test "
                                       f"it: the shadow books {shadows} (Portfolio).", "Soft spot"),
        ("Sector cap", "Uses today’s sector labels for every year, not the label of the day"
                         + (f"; {h['unlabelled']} stocks have none and count as their own group." if h["unlabelled"] else "."),
         "Not checked"),
    ]
    if sm.first < pd.Timestamp("2012-02-21"):
        checks.append(("The index before Feb 2012", "Nifty 500 closes before 21 Feb 2012 come from an outside dataset, not yet "
                                                    "checked against NSE’s own file (S167).", "Not checked"))
    checks.append(("A second source for the result", "None: the replay is our own engine. Prices pass the long file’s audits "
                                                     "(other price histories, BSE, Screener).", "Not checked"))
    tone = {"Checked": "dh-up", "Soft spot": "dh-watch", "Not checked": "dh-watch"}
    body = "".join(f'<tr><th scope="row">{e(a)}</th><td>{e(b)}</td><td class="bt-st {tone[c]}">{e(c)}</td></tr>' for a, b, c in checks)
    return ['<div class="dh-sec">', _kick("5", "Can it be trusted"),
            f'<h2 id="s-trust" class="dh-h2">{trust_headline(checks)}</h2>',
            '<div class="dh-scroll"><table class="dh-tab bt-checks"><thead><tr><th scope="col">Check</th>'
            '<th scope="col">What this run shows</th><th scope="col">Status</th></tr></thead>'
            f'<tbody>{body}</tbody></table></div></div>', END]


def section_trades_head(f: dict) -> list:
    ts = f["trades"]
    if not ts or not ts.get("closed"):
        return ['<div class="dh-sec">', _kick("6", "Trades"), '<h2 id="s-trades" class="dh-h2">No trade closed in this run.</h2></div>']
    won = ts["won"]
    pf = ts.get("profit_factor")
    h2 = (f'{ts["closed"]:,} trades closed; ' + (f'<span class="dh-down">fewer than half won ({won:.0%})</span>.'
                                                if won < 0.5 else f'<span class="dh-up">{won:.0%} won</span>.'))
    # Only when it is true (S203 bt.trd.2): it was printed whatever the profit factor.
    if pf is not None and np.isfinite(pf) and pf > 1:
        h2 += f" The winners paid for the losers: gains were {pf:.2f} times the losses."
    tiles = _kpis([
        ("Trades closed", f"{ts['closed']:,}", "", f"{ts['open']} still held"),
        ("Won", f"{won:.0%}", "", "of closed trades"),
        ("Median holding", f"{ts['median_days']:.0f} days", "", "entry fill to exit fill"),
        ("Median trade", _pcs(ts["median_return"]), _t(ts["median_return"]), f"mean {_pcs(ts['mean_return'])}"),
        ("Gains over losses", f"{pf:.2f}×" if pf else "–", "", "each trade weighted by its size at entry"),
    ])
    return ['<div class="dh-sec">', _kick("6", "Trades"), f'<h2 id="s-trades" class="dh-h2">{h2}</h2>', tiles,
            f'<p class="dh-note">Every trade and the rebalance log are below; the live record’s trades are on '
            f'<a class="bt-l" href="{page_href("portfolio")}" target="_self">Portfolio</a>, which owns the record.</p></div>']


def foot(f: dict) -> list:
    sm = f["summary"]
    idx = f" · indices to {_d(f['indices_as_of'])}" if f.get("indices_as_of") is not None else ""
    return [f'<p class="dh-foot">{_fmt.data_to(sm.last, "NSE’s long price file")}, the last completed month · prices to {_d(f["long_last"])}{idx}.</p>']


# ── Gathering ─────────────────────────────────────────────────────────────────


def _store():
    try:
        from src.ui import indices_data
        return indices_data.frames()
    except Exception:  # noqa: BLE001  the page draws without the index store, saying less
        return None


def gather(res: dict, s: dict, h: dict, bench: pd.Series, default: bool) -> dict:
    eq = pd.Series(res["equity_curve"]).dropna()
    eq.index = pd.DatetimeIndex(eq.index)
    bench = pd.to_numeric(bench, errors="coerce").dropna()
    bench.index = pd.DatetimeIndex(bench.index)
    store = _store()
    close = store.close if store is not None else pd.DataFrame()
    others = {"n500": bench}
    uidx_name = uidx_short = None
    key = h["key"]
    if key in bp.UNIVERSE_INDEX:
        ikey, uidx_name = bp.UNIVERSE_INDEX[key]
        if key == "nifty_50":
            u = fetch_benchmark_history(period="max", symbol=BENCHMARK_SYMBOL_N50)
        else:
            u = close[ikey] if ikey in close else pd.Series(dtype=float)
        u = pd.to_numeric(u, errors="coerce").dropna()
        if len(u):
            u.index = pd.DatetimeIndex(u.index)
            others["uidx"] = u
            uidx_short = uidx_name.replace("Nifty ", "")
        else:
            uidx_name = None
    tm = close[bp.TOTAL_MARKET].dropna() if bp.TOTAL_MARKET in close else pd.Series(dtype=float)
    first_year = {"tm": bp.TOTAL_MARKET_FROM}
    if "uidx" in others:
        u = others["uidx"]
        first_year["uidx"] = u.index[0].year + (0 if (u.index[0].month, u.index[0].day) <= (1, 7) else 1)
    year_inputs = dict(others)
    if len(tm):
        year_inputs["tm"] = tm
    years = bp.years_table(eq, year_inputs, first_year)
    sm = bp.summary(eq, bench)

    falls = bp.falls(eq, 3)
    bench_cal = bp.on_calendar(bench, eq.index)
    now = bp.below_peak_now(eq)
    peak_at = eq.loc[:eq.index[-1]].idxmax() if now < 0 else eq.index[-1]
    alts, windows_from, tm_window_from = [], [], None
    mom = close[bp.MOMENTUM_INDEX].dropna() if bp.MOMENTUM_INDEX in close else pd.Series(dtype=float)
    if len(mom) and eq.index[-1] > mom.index[0]:
        start = mom.index[0] + pd.offsets.MonthEnd(0)
        w = bp.window(eq, {"mom": mom, "n500": bench}, start)
        if w:
            windows_from.append(w["from"])
            alts.append(("Since Nifty200 Momentum 30 went live", f"{_d(w['from'])} – {_d(w['to'])}",
                         [(f"This rule, {h['name']}", *w["rule"]), ("Nifty200 Momentum 30", *w["mom"]), ("Nifty 500", *w["n500"])]))
    ref = _reference() if default else None
    if len(tm) and eq.index[-1] > tm.index[0]:
        start = tm.index[0] + pd.offsets.MonthEnd(0)
        w = bp.window(eq, {"tm": tm, "n500": bench}, start)
        if w:
            windows_from.append(w["from"])
            tm_window_from = w["from"]
            items = [(f"This rule, {h['name']}", *w["rule"])]
            tu = (ref or {}).get("total_market_universe")
            if tu and key != bp.TOTAL_MARKET:
                items.append(("This rule, Nifty Total Market", tu["rule"][0], tu["rule"][1]))
            items += [("Nifty Total Market", *w["tm"]), ("Nifty 500", *w["n500"])]
            alts.append(("Since Nifty Total Market went live", f"{_d(w['from'])} – {_d(w['to'])}", items))

    meta = res.get("live_meta") or {}
    mtd = None
    if h.get("to_latest") and meta.get("strategy_mtd") is not None and meta.get("mtd_period"):
        per = pd.Period(meta["mtd_period"], "M")
        if per == pd.Period(sm.last, "M") + 1:
            mtd = {"label": per.strftime("%B"), "as_of": meta.get("as_of"), "rule": float(meta["strategy_mtd"]),
                   "bench": None if meta.get("benchmark_mtd") is None else float(meta["benchmark_mtd"])}
    dy = dy_from = None
    if store is not None and "nifty_500" in store.dy:
        v = store.dy["nifty_500"].dropna()
        dy = float(v.mean()) if len(v) else None
        dy_from = pd.Timestamp(v.index[0]) if len(v) else None
    chart = bp.weekly_chart(eq, {"n500": bench})
    return {
        "s": s, "h": h, "default": default, "stats": res.get("stats") or {}, "summary": sm,
        "falls": falls, "bench_falls": bp.falls(bench_cal, 2), "below_now": now,
        "bench_below_now": bp.below_peak_now(bench_cal), "current_peak": pd.Timestamp(peak_at),
        "current_days": int((eq.index[-1] - pd.Timestamp(peak_at)).days),
        "years": years, "monthly": bp.months(eq, bench), "alternatives": alts, "reference": ref,
        "uidx_name": uidx_name, "uidx_short": uidx_short, "mtd": mtd, "div_yield": dy, "div_yield_from": dy_from, "chart": chart,
        "tm_from": pd.Timestamp(tm.index[0]) if len(tm) else None, "windows_from": windows_from,
        "tm_window_from": tm_window_from,
        "stale": bp.stale_exits(res.get("closed_trades"), h["close"]),
        "short": bp.short_books(res.get("monthly"), s["top_n"]),
        "trades": bp.trade_stats(res.get("closed_trades")),
        "long_last": pd.Timestamp(h["close"].index[-1]),
        "indices_as_of": store.as_of if store is not None else None,
    }


def page_parts(f: dict) -> list:
    """Everything but the widgets, in order (for tests and the requirements check)."""
    return ([tested_line(f["s"], f["h"])] + head(f) + section_lead(f) + section_falls(f) + section_years(f) + section_depends(f)
            + section_trust(f) + section_trades_head(f) + foot(f))


# ── The page ──────────────────────────────────────────────────────────────────


def _derived_key(s: dict, h: dict, bench: pd.Series, stock_cap: float, sector_cap: float, default: bool) -> str:
    """Everything the page's figures are cut from, as one string: the run's own inputs and the benchmark."""
    ph = h.get("close_fingerprint") or ""
    if h["traded_value"] is not None:
        ph += f"_{h.get('traded_fingerprint') or ''}"
    last = bench.index[-1] if len(bench) else "-"
    parts = (ph, repr(sorted(s.items(), key=lambda kv: kv[0])), stock_cap, sector_cap, default, h.get("name"),
             h.get("months"), str(h.get("start")), h.get("floor"), len(bench), str(last), len(h["close"].index))
    return hashlib.md5(repr(parts).encode()).hexdigest()


# S220: on a warm session the run itself is a cache hit (0.03 s), but the figures, the trade table and the
# trade log were rebuilt from it for every reader: 4.6 of 6 s locally, ~3x that live. They are pure functions
# of the run, so they are kept once per run, like the run. cache_data (a copy per reader), not cache_resource,
# so no reader's page can change another's.
@st.cache_data(show_spinner=False, ttl=3600, max_entries=8)
def _derived(key: str, _res: dict, _s: dict, _h: dict, _bench: pd.Series, default: bool) -> tuple[dict, dict]:
    f = gather(_res, _s, _h, _bench, default)
    trades = pr.trades_table(_res.get("closed_trades"), _res.get("tradebook"), _h["close"].index, _h["sector_map"])
    spec = history_spec(trades, _res.get("tradebook"), [])
    for line in spec["lines"]:
        line[5] = _reason(line[5])
    return f, spec


def _run(s: dict, h: dict, bench: pd.Series, stock_cap: float, sector_cap: float) -> dict | None:
    # Computed once with the frame in its cached loader (S208), not on every rerun.
    ph = h.get("close_fingerprint") or price_fingerprint(h["close"])
    if h["traded_value"] is not None:
        ph += f"_{h.get('traded_fingerprint') or price_fingerprint(h['traded_value'])}"
    queued = st.empty()
    # One backtest computes at a time across the whole server (compute_gate, TODO S65).
    if compute_gate.busy():
        mine = compute_gate.holder() is not None and compute_gate.holder() == compute_gate.current_session()
        queued.warning(
            "Backtest running: request queued. Your previous settings are still computing "
            "(a backtest cannot be stopped part-way); this one starts as soon as it finishes."
            if mine else
            "Backtest running: request queued. Another reader's backtest is computing; "
            "yours starts as soon as it finishes.",
            icon=":material/hourglass_top:",
        )
    with st.spinner("Running the backtest…"):
        res = run_backtest(
            ph, h["close"], _benchmark_close=bench, stock_cap=stock_cap, sector_cap=sector_cap,
            sector_map=h["sector_map"], _membership=h["membership"], backtest_months=h["months"],
            stateful_history=True, history_start=h["start"].start_time, _actions=[],
            liquidity_floor_cr=h["floor"], _traded_value=h["traded_value"], **engine_kwargs(s))
    queued.empty()
    return res


def _download(res: dict, s: dict, h: dict, stock_cap: float, sector_cap: float, eq: pd.Series) -> None:
    """One download (owner, 8 Oct 2026): the rules this run followed and every trade it made."""
    try:
        trades = trades_table(res.get("closed_trades"))
        rules = rules_table(RunSpec(
            mode="Research run on NSE's long price file", universe=h["name"], benchmark="Nifty 500",
            first_fill=eq.index[0] if len(eq) else None, last_session=eq.index[-1] if len(eq) else None,
            top_n=s["top_n"], rebal_freq=s["rebal_freq"], buffer_n=s["buffer_n"], weight_method=s["weight_method"],
            cost_bps=s["cost_bps"], stock_cap=stock_cap, sector_cap=sector_cap, weights=tuple(s["weights"]),
            liquidity_floor_cr=float(h["floor"] or 0.0),
            price_basis=("NSE closes, adjusted for splits, bonuses, demergers and rights issues, and for dividends of "
                         "10% or more of the price"),
            has_industry_map=bool(h["sector_map"]), stats=res.get("stats") or {}, ema_period=s["ema_period"],
            high_pct=s["high_pct"], ath_pct=s["ath_pct"], ath_min_years=s["ath_min_years"], score_method=s["score_method"],
            exit_ema_period=s["exit_ema_period"], exit_high_pct=s["exit_high_pct"], exit_ath_pct=s["exit_ath_pct"],
            score_skip=int(s.get("score_skip") or 0),
            hold_cap=rebalance_rule_kwargs(s["rule"], s.get("hold_cap")).get("hold_cap"),
            generated=f"{ist_now():%Y-%m-%d %H:%M}"), trades)
        slug = "".join(c if c.isalnum() else "_" for c in h["name"]).strip("_").lower()
        span = f"{eq.index[0]:%Y%m}_{eq.index[-1]:%Y%m}" if len(eq) else "empty"
        st.download_button("Download the rules and every trade (ZIP of 2 CSV files)", export_zip(rules, trades),
                           f"backtest_{slug}_{span}.zip", "application/zip", key="dl_bt_export",
                           icon=":material/download:")
    except Exception as exc:  # the page must not fail because a download could not be built
        from src.core.logger import logger
        logger.warning("Backtest download not built: %s: %s", type(exc).__name__, exc)
        st.caption("The download is not available for this run; the figures on the page are complete. Run it again to retry.")


def _reason(text: str) -> str:
    """The engine's rebalance-line reasons in the page's words (S173): "Rank 12, new", "Rank 12, kept"."""
    m = re.search(r"Rank #(\w+)", text or "")
    rank = m.group(1) if m else "–"
    if "New Momentum Leader" in text:
        return f"Rank {rank}, new"
    if "Buffer Zone Retention" in text:
        return f"Rank {rank}, kept"
    return text


def _system_note() -> None:
    """Say so when a system other than the 750 is chosen: these runs pick their own index (S193 C)."""
    from src.engine.extra_universe import SYSTEM_750, SYSTEM_NAMES
    from src.ui import system_param

    system = system_param.current()
    if system != SYSTEM_750:
        kit.note(f"The {SYSTEM_NAMES.get(system, system)} system does not change these runs: each run picks its own "
                 "index in the settings below.", kind="info")


def render_backtest_view(rank_df: pd.DataFrame, stock_cap: float, sector_cap: float, weights: tuple[float, ...],
                         liquidity_floor_cr: float = 0.0) -> None:
    """One page of research runs on NSE's long price file (S174)."""
    from src.core import startup_metrics as _metrics

    stages: dict[str, float] = {}
    clock = [_perf()]

    def mark(name: str) -> None:   # S220: where a live Backtest's seconds go, in the hidden metrics div
        now = _perf()
        stages[name] = round(now - clock[0], 2)
        clock[0] = now
        _metrics.note("backtest_stages_s", dict(stages))

    st.html(f"<style>{HOME_CSS}{BT_CSS}</style>")
    # First on the page: the run's settings in one line, "Change the test" under it (S219-6), then the answer.
    line = st.container()
    bounds = _history_bounds()
    if bounds is None:
        return
    s = _settings_form(weights, liquidity_floor_cr, bounds)
    _system_note()
    top = st.container()
    h = _history_inputs(rank_df, s["history"], bounds)
    mark("inputs")
    if h is None:
        return
    with line:
        emit([tested_line(s, h)])
    bench = fetch_benchmark_history(period="max", symbol=BENCHMARK_SYMBOL)
    if bench.empty:
        # A failure is an amber note, not a red box (S193 E, rule 4).
        kit.note("The Nifty 500's closes are unavailable.", "Backtest stopped rather than compare against nothing.", kind="warning")
        return
    res = _run(s, h, bench, stock_cap, sector_cap)
    mark("run")
    if res is None:
        kit.note("Not enough price history for this window.", "The rules need 12 months of prices before the first "
                 "month tested; pick a later start above.", kind="warning")
        return
    eq = pd.Series(res.get("equity_curve")).dropna()
    if eq.empty or len(eq) < 2:
        kit.empty("No completed month in this window yet.")
        return
    default = is_default(s, h, stock_cap, sector_cap)
    f, spec = _derived(_derived_key(s, h, bench, stock_cap, sector_cap, default), res, s, h, bench, default)
    mark("derived")
    with top:
        emit(head(f))
    emit(section_lead(f) + section_falls(f) + section_years(f) + section_depends(f) + section_trust(f)
         + section_trades_head(f))
    _download(res, s, h, stock_cap, sector_cap, eq)
    mark("sections+download")
    with st.expander("Show the table · every trade and the rebalance log", expanded=False):
        emit([Chart("history", spec,
                    {"label": "Every trade and every rebalance line",
                     "note": "A trade is one stock from the fill that bought it to the fill that sold it. A rebalance line is "
                             "one stock’s action at one rebalance (bought, sold or kept). Signal is the close the rule read; "
                             "the fill is the next session’s close. Returns are before costs."})])
    emit([END] + foot(f))
    mark("trade_log+foot")


__all__ = ["render_backtest_view", "page_parts", "gather", "is_default", "rebalance_rule_kwargs", "engine_kwargs",
           "tested_items", "REBALANCE_RULES"]
