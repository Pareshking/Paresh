"""
Strategy Backtesting View Controller with Friction & Turnover Attribution.
"""

import html
import math
from pathlib import Path

import pandas as pd
import streamlit as st

from src.core.config import DEFAULT_TRANSACTION_COST_BPS
from src.core.market_time import ist_now
from src.engine.backtester import DEFAULT_BACKTEST_MONTHS, run_backtest
from src.engine.corporate_actions import load_events
from src.engine.membership import load_history_or_none
from src.engine.parameter_sweep import (
    OBJECTIVES,
    count_combinations,
    run_parameter_sweep,
)
from src.engine.pipeline import price_fingerprint
from src.loaders.price_loader import fetch_benchmark_history
from src.loaders import former_members, nse_prices
from src.loaders.ranking_store import actions_digest
from src.ui import page_kit as kit
from src.ui.canonical_book import current_book
from src.engine.extra_universe import SYSTEM_750
from src.engine.systems import inception, ledger_path
from src.engine.track_record import build_combined_grid, ledger_from_curves, load_ledger, summary_stats
from src.ui.components import gap_count, render_data_quality_footer
from src.ui.theme import render_saas_table
from src.ui.views.track_record_view import grid_display


def _canonical_account_stats(ledger: dict, live_meta: dict | None) -> dict:
    """Summarise the canonical account using Track Record's frozen months and live mark."""
    meta = live_meta or {}
    period = meta.get("mtd_period")
    mtd = None
    if period:
        mtd = {
            "period": pd.Period(period, freq="M"),
            "strategy": meta.get("strategy_mtd"),
            "benchmark": meta.get("benchmark_mtd"),
            "as_of": meta.get("as_of"),
        }
    return summary_stats(ledger, mtd=mtd)


def _pct_or_dash(value) -> str:
    return "—" if value is None or pd.isna(value) else f"{float(value):+.1%}"


@st.fragment
def _tone(v) -> str:
    if v is None or pd.isna(v):
        return ""
    return "up" if v > 0 else "down" if v < 0 else ""


MODE_LIVE = "Live system"
MODE_HISTORY = "History from 2010"


@st.cache_data(show_spinner=False, ttl=3600)
def _long_file():
    """Closes and report only: traded value is fetched when a floor is set."""
    from src.loaders import nse_long

    return nse_long.load(with_value=False)


@st.cache_data(show_spinner=False, ttl=3600)
def _long_value():
    from src.loaders import nse_long

    return nse_long.load_value()


HISTORICAL_INDUSTRIES = Path(__file__).resolve().parents[3] / "data" / "reference" / "historical_industries.csv"


@st.cache_data(show_spinner=False)
def _historical_industries() -> dict[str, str]:
    """NSE sector (the 22-name level the app ranks on) for stocks no current list labels."""
    try:
        frame = pd.read_csv(HISTORICAL_INDUSTRIES)
    except (OSError, ValueError):
        return {}
    return dict(zip(frame["NSE_SYMBOL"], frame["SECTOR"]))


def _history_inputs(rank_df: pd.DataFrame, liquidity_floor_cr: float) -> dict | None:
    """The long backtest's controls and inputs, or None when it cannot run.

    Owner, 2026-10-03: any index from Jan 2010, a start and end month, and a
    traded-value floor; size from the index tier, no market-cap cutoff. Prices
    are NSE's own (src/loaders/nse_long.py), membership each index's own point-in-
    time timeline (src/engine/index_universe.py).
    """
    from src.engine import index_universe as iu
    from src.loaders import nse_long

    loaded = _long_file()
    if loaded is None:
        kit.note("The long price file is not available yet.",
                 "It is built weekly from NSE's bhavcopy by the 'NSE long price file' workflow "
                 "and published to the data-latest release.")
        return None
    close, _value, report = loaded

    c1, c2 = st.columns([1, 2])
    key = c1.selectbox("Index", list(iu.INDICES), format_func=iu.INDICES.get,
                       index=list(iu.INDICES).index(iu.DEFAULT_INDEX), key="bt_hist_index")
    membership = iu.index_history(key)
    if membership is None:
        kit.note(f"No membership history for {iu.INDICES[key]}.")
        return None
    # A year of prices before the first month, for the 12-month lookback and the EMA.
    first = max(iu.first_month(membership), pd.Period(close.index[0], freq="M") + 13)
    last = pd.Period(close.index[-1], freq="M") - 1
    if first > last:
        kit.note(f"{iu.INDICES[key]} has no completed month to test yet.")
        return None
    months_all = list(pd.period_range(first, last, freq="M"))
    start, end = c2.select_slider(
        "Months", months_all, value=(months_all[0], months_all[-1]),
        format_func=lambda p: p.strftime("%b %Y"), key=f"bt_hist_months_{key}",
        help=f"{iu.INDICES[key]}'s point-in-time list begins {first.strftime('%b %Y')}.",
    )
    floor = st.number_input(
        "Minimum traded value (₹ Cr, 20-day average; 0 = off)", min_value=0.0, max_value=500.0,
        value=float(liquidity_floor_cr or 0.0), step=1.0, key="bt_hist_floor",
    )

    # The frame ends at the first session after the end month: the engine reports
    # the completed months before its last session's month.
    after = close.index[close.index >= (end + 1).start_time]
    cut = after[0] if len(after) else close.index[-1]
    cols = sorted(iu.ever_members(membership) & set(close.columns))
    frame = close.loc[:cut, cols]

    # Industry for the cap: the current lists, then TradingView mapped to NSE's
    # names, then data/reference/historical_industries.csv (NSE's sector for the
    # names that left before today's lists, looked up 3 Oct 2026). A stock
    # nothing places is its own group, not one shared "Other" the cap would squeeze.
    sec = rank_df.set_index("Symbol")["Industry"].to_dict() if "Industry" in rank_df.columns else {}
    sec.update(former_members.industry_for([c for c in cols if c not in sec]))
    past = _historical_industries()
    sec.update({c: past[c] for c in cols if sec.get(c, "Other") == "Other" and c in past})
    unlabelled = [c for c in cols if sec.get(c, "Other") == "Other"]
    sec.update({c: f"Unlabelled · {c}" for c in unlabelled})

    traded = None
    if floor:
        value = _long_value()
        if value is None:
            kit.note("Traded value is not available right now, so the floor is off for this run.",
                     "The long file's traded-value part could not be fetched.")
            floor = 0.0
        else:
            traded = nse_long.average_value(value.reindex(columns=cols).loc[:cut])

    return {
        "close": frame, "membership": membership, "start": start, "end": end,
        "months": (end - start).n + 1, "floor": floor,
        # The Nifty 50 against its own index; the others against the Nifty 500,
        # the broadest index on file (data/benchmarks.csv holds the two).
        "benchmark": ("^NSEI", "Nifty 50") if key == "nifty_50" else ("^CRSLDX", "Nifty 500"),
        "traded_value": traded,
        "sector_map": sec, "unlabelled": len(unlabelled), "name": iu.INDICES[key],
        "built": report.get("built"), "last_session": report.get("last_session"),
    }


def _backtest_body(
    rank_df: pd.DataFrame,
    adj_close: pd.DataFrame,
    stock_cap: float,
    sector_cap: float,
    weights: tuple[float, ...],
    liquidity_floor_cr: float = 0.0,
    traded_value: pd.DataFrame | None = None,
    months: int = DEFAULT_BACKTEST_MONTHS,
    membership: dict | None = None,
    history_start: pd.Timestamp | None = None,
) -> None:
    """Fragment: reruns only when backtest-tab widgets change, not on every global rerun.

    Two tabs (owner, 2026-10-03): the live system's recent months, and the
    history from 2010. Lazy: only the open tab runs its backtest.
    """
    history_mode = st.session_state.get("bt_mode", MODE_LIVE) == MODE_HISTORY
    actions = kit.page_head(
        "Backtest",
        "Any index, any months from 2010, on NSE's own prices" if history_mode else
        f"Last {months} completed month{'s' if months != 1 else ''}",
        actions=True,
    )
    live_tab, history_tab = st.tabs([MODE_LIVE, MODE_HISTORY], key="bt_mode", on_change="rerun")
    history_mode = bool(history_tab.open)
    with history_tab if history_mode else live_tab:
        _backtest_tab(rank_df, adj_close, stock_cap, sector_cap, weights, liquidity_floor_cr,
                      traded_value, months, membership, history_start,
                      history_mode=history_mode, actions=actions)


def _backtest_tab(
    rank_df: pd.DataFrame,
    adj_close: pd.DataFrame,
    stock_cap: float,
    sector_cap: float,
    weights: tuple[float, ...],
    liquidity_floor_cr: float,
    traded_value: pd.DataFrame | None,
    months: int,
    membership: dict | None,
    history_start: pd.Timestamp | None,
    *,
    history_mode: bool,
    actions,
) -> None:
    """One tab's controls, backtest and views."""
    history = _history_inputs(rank_df, liquidity_floor_cr) if history_mode else None
    if history_mode and history is None:
        return
    with actions, st.popover("Change settings", icon=":material/tune:"):
        c1, c2 = st.columns(2)
        bt_n = c1.selectbox("Holdings", [10, 15, 20, 30, 50], index=2, key="bt_holdings_n")
        bt_rebal = c2.selectbox(
            "Rebalance",
            [5, 10, 21, 42, 63],
            index=2,
            format_func=lambda x: {
                5: "Weekly (5 trading days)",
                10: "Every 2 weeks (10 trading days)",
                21: "Monthly (first trading day)",
                42: "Every 2 months (42 trading days)",
                63: "Quarterly (63 trading days)",
            }[x],
            key="bt_rebal_freq",
        )
        c4, c5 = st.columns(2)
        bt_weight = c4.selectbox(
            "Weighting", ["Equal Weight", "Inverse Volatility"], index=0, key="bt_weight_scheme",
        )
        buffer_mult = c5.selectbox(
            "Keep a holding while it ranks within",
            [1.0, 1.5, 2.0],
            index=2,
            format_func=lambda x: f"Top {int(bt_n * x)} ({x:.1f}× holdings)",
            help="Retain existing positions while their rank stays inside this zone; cuts turnover by more than half.",
            key="bt_buffer_sel",
        )
        cost_drag_bps = st.slider(
            "Trading cost (bps per unit of turnover)",
            0.0,
            100.0,
            float(DEFAULT_TRANSACTION_COST_BPS),
            5.0,
            help="Round-trip cost (STT + stamp duty + brokerage + slippage). Standard NSE equity is about 25–35 bps.",
            key="bt_cost_bps",
        )
        # Lookback weights for the composite -- the only scoring model there is.
        st.markdown("**Lookback weights** · how much each window counts in the score")
        bw = st.columns(5)
        w1 = bw[0].slider("1M", 0.0, 1.0, float(weights[0]), 0.05, key="btw_1")
        w2 = bw[1].slider("3M", 0.0, 1.0, float(weights[1]), 0.05, key="btw_2")
        w3 = bw[2].slider("6M", 0.0, 1.0, float(weights[2]), 0.05, key="btw_3")
        w4 = bw[3].slider("9M", 0.0, 1.0, float(weights[3]), 0.05, key="btw_4")
        w5 = bw[4].slider("12M", 0.0, 1.0, float(weights[4]), 0.05, key="btw_5")
        active_weights = (w1, w2, w3, w4, w5)

    # Keyed on the WHOLE price history and the applied corporate actions. The
    # old key (last date + shape) missed an intraday refresh, a vendor
    # restatement and a newly logged split alike, and served the cached answer
    # for up to an hour.
    # Score on the index as it stood: the stocks it once held and has since
    # dropped need prices too, or the pool is only the survivors.
    # Preserve the original app price frame for the canonical live-book adapter.
    # The exploratory backtest may replace adj_close with an alternate price basis below.
    canonical_adj_close = adj_close
    membership = membership if membership is not None else load_history_or_none()
    # Prices as NSE published them (loaders/nse_prices.py): a past month ranks
    # on what was known then, not on a vendor's later restatement. Where the
    # file does not reach back far enough, the long Personal (Screener) history stands.
    _nse, _nse_info = (None, {}) if history else nse_prices.basis_frame(adj_close, membership, months=months)
    if history:
        adj_close, _events = history["close"], []
        membership, months = history["membership"], history["months"]
        history_start = history["start"].start_time
        liquidity_floor_cr, traded_value = history["floor"], history["traded_value"]
        kit.caption(
            f"{history['name']}, point in time · Prices: NSE closes, adjusted for splits, bonuses "
            "and demergers, and for rights issues of index stocks; no dividends · file built "
            f"{history.get('built') or '—'}, last session {history.get('last_session') or '—'}."
        )
    elif _nse is not None:
        adj_close, _events = _nse, []
        # NSE's file runs to the latest session, often a day ahead of the long Screener history
        # (on the 1st its first session of the month is already in). Months are counted back
        # from the frame's end, so a month that has just closed needs one more in the window.
        if history_start is not None:
            months = max(months, int((pd.Period(adj_close.index[-1], freq="M")
                                      - pd.Period(history_start, freq="M")).n))
        kit.caption(
            "Prices: Personal closes, NSE only where Personal data is unavailable; no dividends."
            if _nse_info.get("basis") == "screener_primary" else
            "Prices: NSE closes, adjusted for splits, bonuses and demergers; no dividends."
        )
    else:
        adj_close = former_members.with_former_members(adj_close, membership)
        _events = load_events()
        kit.caption("Prices: Personal closes, adjusted for splits and bonuses; no dividends.")
    ph = f"{price_fingerprint(adj_close)}_{actions_digest(_events)}"
    if liquidity_floor_cr:
        kit.caption(f"Liquidity floor on: a stock is bought only while its 20-day average "
                    f"traded value is ₹{liquidity_floor_cr:g} Cr or more"
                    + ("." if history else " (Configuration)."))
        if traded_value is not None:
            ph += f"_{price_fingerprint(traded_value)}"
    bench_symbol, bench_name = history["benchmark"] if history else ("^CRSLDX", "Nifty 500")
    benchmark_close = fetch_benchmark_history(period="max" if history else "2y", symbol=bench_symbol)
    if benchmark_close.empty:
        st.error(f"{bench_name} benchmark ({bench_symbol}) data is unavailable. Backtest stopped to "
                 "prevent an invalid benchmark comparison.")
        return
    sec_map = history["sector_map"] if history else (
        rank_df.set_index("Symbol")["Industry"].to_dict()
        if "Industry" in rank_df.columns
        else {}
    )
    if history and history["unlabelled"]:
        kit.caption(f"{history['unlabelled']} of these stocks have no industry on record (mostly ones "
                    "that left before today's lists); each counts as its own group for the industry cap.")
    if sec_map and not history:
        # The sector cap needs an industry for every name it can hold, and the
        # index files only label the current members.
        sec_map.update(former_members.industry_for([c for c in adj_close.columns if c not in sec_map]))

    with st.spinner("Running walk-forward backtest with friction & turnover modeling…"):
        bt_res = run_backtest(
            ph,
            adj_close,
            _benchmark_close=benchmark_close,
            top_n=bt_n,
            rebal_freq=bt_rebal,
            weight_method=bt_weight,
            config_weights=active_weights,
            stock_cap=stock_cap,
            sector_cap=sector_cap,
            sector_map=sec_map,
            cost_bps=cost_drag_bps,
            buffer_n=int(bt_n * buffer_mult),
            _membership=membership,
            backtest_months=months,
            stateful_history=True,
            history_start=history_start,
            _actions=_events,
            liquidity_floor_cr=liquidity_floor_cr,
            _traded_value=traded_value,
        )

    if bt_res is None:
        st.warning(
            f"Insufficient price history to backtest the last "
            f"{months} completed month{'s' if months != 1 else ''}. The strategy needs a "
            "full 12-month formation window BEFORE the reported period, so "
            "roughly 18 months of continuous daily data is required."
        )
        return

    if not bt_res.get("stats", {}).get("total_return") and bt_res["equity_curve"].empty:
        # The first month of a system: its first book exists (Actions, Portfolio)
        # but no month has completed, so there is no return to report yet.
        st.info(
            "No completed month yet. The first book is on Actions and Portfolio; "
            "returns appear here when the month closes."
        )
        return

    # The backtest runs on the DEEPEST history available, which is not always
    # the history the live screener ranks on -- a ranking wants the freshest
    # complete session, a backtest wants years. When the two differ, say so:
    # they do not share a corporate-action adjustment basis, so a name with a
    # demerger can sit at a different level in each, and a reader comparing a
    # backtest holding against today's table deserves to know why.
    try:
        from src.core import startup_metrics as _m
        from src.loaders.price_source import display_name as _display

        _ranked_on = str(_m.snapshot().get("facts", {}).get("price_source") or "")
        # In history mode the long NSE file is the history: nothing to explain.
        if _ranked_on and _ranked_on != "yahoo" and not history:
            st.caption(
                f"Long price history used: {_display(_ranked_on)} does not yet "
                f"reach far enough back for {months} months."
            )
    except Exception:
        pass

    stats = bt_res["stats"]

    # Say which window these numbers describe. The backtest reports the last
    # completed calendar months only -- the month in progress is excluded, so a
    # part-month return is never shown beside whole ones.
    _eq_idx = bt_res["equity_curve"].index
    bt_window_label = (
        f"{_eq_idx[0]:{'%d %b' if _eq_idx[0].year == _eq_idx[-1].year else '%d %b %Y'}} "
        f"to {_eq_idx[-1]:%d %b %Y}"
        if len(_eq_idx)
        else f"last {months} completed month{'s' if months != 1 else ''}"
    )

    # What was tested, in one line: the reader's first question of any result.
    _rebal_txt = "monthly, first trading day" if bt_rebal == 21 else f"every {bt_rebal} trading days"
    st.html(
        '<div class="bt-sum"><b>Tested</b>'
        f"<span>{html.escape(bt_window_label)}</span>"
        f"<span>Holdings <b>{bt_n}</b></span><span>Rebalance <b>{_rebal_txt}</b></span>"
        f"<span>Weighting <b>{html.escape(bt_weight.lower())}</b></span>"
        f"<span>Costs <b>{cost_drag_bps:.0f} bps</b></span>"
        f"<span>Keep while in top <b>{int(bt_n * buffer_mult)}</b></span></div>"
    )

    # The Weighting Scheme control is inert whenever the stock cap admits only
    # one fully-invested book. The backtester reports it; nothing displayed it,
    # so the selector stayed lit while making no difference to the simulation.
    _cash = float(stats.get("cap_cash_max", 0.0) or 0.0)
    if _cash > 1e-6:
        kit.note(
            f"The caps left up to {_cash:.1%} of the book in cash.",
            "Stock and industry caps are hard limits and are never raised: weight "
            "these settings cannot place in a qualifying name is held as cash at 0%. "
            "Hold more names, or loosen the stock cap in Configuration → Portfolio risk.",
        )

    if stats.get("scheme_neutralised"):
        kit.note(
            f"The {bt_weight.lower()} weighting made no difference to this run.",
            f"A {stock_cap:.0%} stock cap across {bt_n} holdings allows only one "
            f"fully-invested book, {1 / max(bt_n, 1):.1%} in every name. Raise the "
            "stock cap in Configuration → Portfolio risk, or hold fewer names.",
        )

    # ── Survivorship coverage ────────────────────────────────────────────────
    # run_backtest counts how many rebalances were scored against the index as
    # it ACTUALLY stood versus how many fell back to today's constituent list,
    # and its own comment says a caller reporting the return without reporting
    # this overstates the result. No caller reported it. Index additions skew
    # toward recent winners and this screen preferentially buys exactly those,
    # so a month scored on today's list can hold names it could not have known
    # to hold. The direction of that bias is known; the size is not, which is
    # the reason to state it rather than to estimate it.
    _pit = int(stats.get("pit_periods", 0) or 0)
    _cur = int(stats.get("current_universe_periods", 0) or 0)
    if _cur:
        _from = stats.get("pit_from")
        kit.note(
            f"Read with care: {_cur} of {_pit + _cur} rebalances used today's index lists.",
            "The membership history does not reach back that far. Index additions "
            "skew toward recent strong performers, so those periods flatter the "
            "strategy by an amount this run cannot measure. "
            + (
                f"Point-in-time membership begins {_from}; every rebalance from "
                "there on is survivorship-free."
                if _from
                else "No rebalance in this window had point-in-time membership."
            )
        )

    # ── Executive KPI Cards Grid ─────────────────────────────────────────────

    # The +/- is the standard error of the SHARPE, so it belongs beside the
    # Sharpe value. It used to render at the end of the "Sortino: x / +/-y s.e."
    # subline, where it read as the Sortino's own error, and the one tooltip
    # covering both described the Sharpe denominator ("annualised volatility")
    # for a ratio that divides by downside deviation.
    _rf = stats.get("risk_free_rate", 0.065)
    _se = float(stats.get("sharpe_stderr_iid", float("nan")))
    _sortino = float(stats.get("sortino", float("nan")))
    # Both can legitimately be absent: the standard error needs a non-empty
    # sample, and the Sortino is withheld when too few sessions fell below the
    # MAR to estimate a downside deviation. Printing a bare "nan" beside a
    # formatted ratio reads like a bug, so say nothing and n/a respectively.
    sharpe_se_txt = f" \u00b1{_se:.2f} s.e." if math.isfinite(_se) else ""
    sortino_txt = f"{_sortino:.2f}" if math.isfinite(_sortino) else "n/a"

    _yrs = stats.get("window_years", 0) or 0
    kit.readings([
        kit.Reading("Strategy return", f"{stats['total_return']:+.1%}",
                    f"after {cost_drag_bps:.0f} bps costs · {stats['gross_return']:+.1%} before",
                    _tone(stats["total_return"])),
        kit.Reading("Annualised", f"{stats['ann_return']:+.1%}",
                    f"scaled up from {_yrs:.2f} years, not a CAGR · {bench_name} {stats['ann_bench']:+.1%}",
                    _tone(stats["ann_return"])),
        kit.Reading(f"Ahead of {bench_name}", f"{stats['alpha'] * 100:+.1f} pts",
                    f"{bench_name} {stats['bench_return']:+.1%} over the same months", _tone(stats["alpha"])),
    ], "Backtest returns")
    kit.readings([
        kit.Reading("Sharpe", f"{stats['sharpe']:.2f}",
                    (f"{sharpe_se_txt.strip()} · " if sharpe_se_txt else "")
                    + f"Sortino {sortino_txt} · risk-free {_rf:.1%}"),
        kit.Reading("Worst fall", f"{stats['max_drawdown']:.1%}",
                    f"peak to trough · Calmar {stats['calmar']:.2f} (reads high over {_yrs:.2f} years)",
                    "down" if stats["max_drawdown"] < 0 else ""),
        kit.Reading("Months that beat the index", f"{stats.get('beat_rate', 0):.0%}",
                    f"{stats['win_rate']:.0%} of months were profitable · turnover "
                    f"{stats['avg_turnover']:.1f}% per rebalance",
                    "up" if stats.get("beat_rate", 0) >= 0.5 else "down"),
    ], "Backtest risk")

    eq = bt_res["equity_curve"]
    bm = bt_res["benchmark"].reindex(eq.index).ffill() if bt_res.get("benchmark") is not None else None
    with kit.card("Growth of ₹100", "bt_growth", "daily"):
        kit.growth_chart(eq.index, eq.tolist(),
                         None if bm is None else bm.tolist(), key="bt")

    # Year by month, as on the Portfolio page (owner, 3 Oct 2026): a 16-year run
    # is read by its years, and one growth line hides which ones were good.
    with kit.card("Calendar returns", "bt_calendar",
                  f"Strategy, {bench_name} and Alpha, per year"):
        _grid = build_combined_grid(ledger_from_curves(eq, bm), alpha_as_difference=True)
        if _grid.empty:
            st.info("No full month in this window yet.")
        else:
            _grid["SERIES"] = _grid["SERIES"].replace({"Nifty 500": bench_name})
            render_saas_table(grid_display(_grid))
            st.caption(
                "Calendar months, after costs. The first month starts at the first "
                "fill of the run and the last is the last completed month. CY is the "
                "calendar year compounded, FY the Indian financial year (April to "
                "March), Q1 to Q4 the calendar quarters; Alpha is the strategy's "
                "return minus the index's, for each month, year and quarter."
            )

    # The live book and the canonical account belong to the live system, not to
    # a study of another index or another decade.
    _views = (["Month by month", "Every trade", "Rebalance log", "Method"] if history else
              ["Current book", "This month's changes", "Month by month", "Every trade",
               "Rebalance log", "Method"])
    view = st.segmented_control(
        "Backtest detail",
        _views,
        default=_views[0],
        key="bt_hist_view" if history else "bt_view",
        label_visibility="collapsed",
    ) or _views[0]

    # ── Current Book & This Month's Changes ──────────────────────────────────
    # The tables below stop at the last completed month, which is right for
    # PERFORMANCE and wrong for a person holding the portfolio. They need
    # today's book and this month's trades, so that is what this section is,
    # and it is deliberately first on the page.
    #
    # "Today's book" means AFTER this month's rebalance. That rebalance is
    # signalled on the last session of last month and fills on the first of
    # this one, so by the time anyone reads this it has already executed --
    # showing the pre-rebalance book here would be showing last month's
    # portfolio under the heading "current".
    # Current holdings and the current rebalance are not an exploratory
    # backtest result. They must be the exact pinned Track Record replay that
    # Actions and Portfolio consume, regardless of the controls selected above.
    # Keep the configurable run for historical performance/trades only.
    canonical_result: dict = {}
    live_book = pd.DataFrame()
    # History mode studies another index or decade: no live book or account.
    if not history:
        try:
            live_book, canonical_result = current_book(
                canonical_adj_close, benchmark_close, SYSTEM_750
            )
        except (ValueError, KeyError) as exc:
            st.error(f"Canonical model book is unavailable: {exc}")
            live_book = pd.DataFrame()
    changes = canonical_result.get("month_changes", pd.DataFrame())
    lmeta = canonical_result.get("live_meta", {}) or {}

    if not history:
        # Account performance is not the configurable research simulation above.
        # Use the exact same frozen ledger and current live mark as Track Record.
        try:
            account_ledger = load_ledger(ledger_path(SYSTEM_750), inception(SYSTEM_750))
            account_stats = _canonical_account_stats(account_ledger, lmeta)
            with kit.card(
                "Canonical account performance",
                "bt_canonical_account",
                "Same January 2026-onward recorded account as Track Record and Portfolio; "
                "closed months are frozen and the latest month is a live mark.",
            ):
                kit.readings([
                    kit.Reading(
                        "Since-inception strategy",
                        _pct_or_dash(account_stats.get("total_return")),
                        "canonical account return, not a configurable backtest",
                        "up" if account_stats.get("total_return", 0) >= 0 else "down",
                    ),
                    kit.Reading(
                        "Nifty 500",
                        _pct_or_dash(account_stats.get("bench_return")),
                        "same dates and compounding basis",
                        "up" if account_stats.get("bench_return", 0) >= 0 else "down",
                    ),
                    kit.Reading(
                        "Alpha",
                        _pct_or_dash(account_stats.get("alpha")),
                        "strategy return minus benchmark return",
                        "up" if account_stats.get("alpha", 0) >= 0 else "down",
                    ),
                ], "Canonical account")
        except (ValueError, KeyError, TypeError) as exc:
            st.error(f"Canonical account performance is unavailable: {exc}")

    if view in ("Current book", "This month's changes"):
        _as_of = lmeta.get("as_of")
        _sig = lmeta.get("signal_date")
        _fill = lmeta.get("fill_date")
        with kit.card(view, "bt_live"):
            kit.caption(
                "The canonical book, shared with Actions and Portfolio"
                + (f", marked {_as_of:%d %b %Y}" if _as_of is not None else "")
                + ". Historical performance, trade history and parameter sweeps below use "
                "the Backtest settings and may describe a different strategy."
            )

            if lmeta.get("rebalanced"):
                n_b = lmeta.get("n_bought", 0)
                n_s = lmeta.get("n_sold", 0)
                n_h = lmeta.get("n_held", 0)
                kit.caption(
                    f"{_fill:%d %b} rebalance: {n_s} sold · {n_b} bought · {n_h} held"
                    + (" · nothing changed" if n_b == 0 and n_s == 0 else "")
                )
            else:
                kit.caption("No rebalance yet this month; the next signal is at the month's last close.")

            live_sub = "holdings" if view == "Current book" else "changes"

            def _fmt_dates(frame: pd.DataFrame) -> pd.DataFrame:
                out = frame.copy()
                if "Entry Date" in out.columns:
                    out["Entry Date"] = pd.to_datetime(
                        out["Entry Date"], errors="coerce"
                    ).dt.strftime("%d %b %Y").fillna("—")
                return out

            if live_sub == "holdings":
                if live_book.empty:
                    st.info("No open positions.")
                else:
                    lb = _fmt_dates(live_book)
                    _order = ["Symbol", "Price Now", "Return %", "MTD %", "Weight %", "Entry Date",
                              "Entry Price", "Holding (Days)", "Rank at Entry",
                              "Rank at Rebalance", "Industry"]
                    lb = lb[[c for c in _order if c in lb.columns]
                            + [c for c in lb.columns if c not in _order]]
                    n_up = int((live_book["Return %"] > 0).sum())
                    n_dn = int((live_book["Return %"] < 0).sum())
                    avg_r = float(live_book["Return %"].mean(skipna=True) * 100)
                    n_new = 0
                    if _fill is not None and "Entry Date" in live_book.columns:
                        n_new = int(
                            (pd.to_datetime(live_book["Entry Date"], errors="coerce")
                             == _fill).sum()
                        )
                    # The book's month so far: each name's MTD at its rebalance
                    # weight (weights drift with prices; close enough to read).
                    _mtd = live_book.get("MTD %", pd.Series(dtype=float))
                    _w = live_book.get("Weight %", pd.Series(dtype=float))
                    _ok = _mtd.notna() & _w.notna()
                    book_mtd = (float((_mtd[_ok] * _w[_ok]).sum() / _w[_ok].sum() * 100)
                                if _ok.any() and _w[_ok].sum() > 0 else float("nan"))
                    kit.readings([
                        kit.Reading("Holdings", f"{len(live_book)}", f"{n_new} added this month"),
                        kit.Reading(
                            "Book this month",
                            "—" if book_mtd != book_mtd else f"{book_mtd:+.1f}%",
                            "month to date, by weight",
                            "" if book_mtd != book_mtd else ("up" if book_mtd >= 0 else "down"),
                        ),
                        kit.Reading("In profit", f"{n_up}", "marked at the latest close", "up" if n_up else ""),
                        kit.Reading("In loss", f"{n_dn}", "", "down" if n_dn else ""),
                        kit.Reading("Average unrealised", f"{avg_r:+.1f}%", "", "up" if avg_r >= 0 else "down"),
                    ], "Current book")
                    render_saas_table(lb)
                    st.download_button(
                        "Export holdings CSV",
                        lb.to_csv(index=False).encode(),
                        f"current_book_{ist_now():%Y%m%d}.csv",
                        "text/csv",
                        key="dl_bt_live_book_csv",
                    )

            else:
                if changes.empty:
                    st.info(
                        "No changes to show. The list appears once the month's "
                        "rebalance has run."
                    )
                else:
                    ch = _fmt_dates(changes)
                    act_filter = st.pills(
                        "Filter Action",
                        ["All", "🟢 BOUGHT", "🔴 SOLD", "⚪ HELD"],
                        default="All",
                        key="bt_changes_action_filter",
                    )
                    if act_filter and act_filter != "All":
                        ch = ch[ch["Action"] == act_filter]
                    st.caption(
                        "What the "
                        + (f"{_fill:%d %b %Y} " if _fill is not None else "")
                        + "rebalance did. **Return %** on a SOLD row is the "
                        "realised round trip; on a BOUGHT or HELD row it is "
                        "unrealised, marked at the latest close."
                    )
                    _not_in = (changes[changes["Reason"].astype(str).str.startswith("Not in the index")]
                               if "Reason" in changes.columns else changes.iloc[0:0])
                    if not _not_in.empty:
                        _mem = membership if membership is not None else load_history_or_none()
                        _since = ((_mem or {}).get("baseline") or {}).get("date")
                        _entered = pd.to_datetime(_not_in["Entry Date"], errors="coerce")
                        _early = (_not_in[_entered < pd.Timestamp(_since)]
                                  if _since else _not_in.iloc[0:0])
                        kit.note(
                            f"{len(_not_in)} sold "
                            f"{'name was' if len(_not_in) == 1 else 'names were'} not in the "
                            f"index on the {_sig:%d %b %Y} signal date: "
                            f"{', '.join(_not_in['Symbol'].astype(str))}.",
                            (f"{', '.join(_early['Symbol'].astype(str))} entered the book before "
                             f"the index record begins ({_since}), when the backtest scored on "
                             "today's constituent list, so they were picked with hindsight. "
                             "This is the first rebalance scored on the index as it stood, and "
                             "it sells them."
                             if not _early.empty else
                             "They have left the index list, so the rules sell them."),
                        )
                    render_saas_table(ch)
                    st.download_button(
                        "Export changes CSV",
                        _fmt_dates(changes).to_csv(index=False).encode(),
                        f"month_changes_{ist_now():%Y%m%d}.csv",
                        "text/csv",
                        key="dl_bt_changes_csv",
                    )


    # ── Monthly Performance Breakdown & Rebalance Tradebook ──────────────────
    if view in ("Month by month", "Every trade", "Rebalance log"):
        with kit.card(view, "bt_perf"):
            c_dl = st.container()
            sub_view = view

            monthly = bt_res.get("monthly", pd.DataFrame())
            tradebook = bt_res.get("tradebook", pd.DataFrame())
            closed_trades = bt_res.get("closed_trades", pd.DataFrame())

            if sub_view == "Month by month":
                if not monthly.empty:
                    m_df = monthly.copy()
                    if "Period Start" in m_df.columns:
                        m_df["Period Start"] = pd.to_datetime(
                            m_df["Period Start"]
                        ).dt.strftime("%d %b %Y")
                    if "Period End" in m_df.columns:
                        m_df["Period End"] = pd.to_datetime(m_df["Period End"]).dt.strftime(
                            "%d %b %Y"
                        )

                    disp_cols = [
                        "Period Start",
                        "Period End",
                        "Strategy Net",
                        "Benchmark",
                        "Alpha vs Benchmark",
                        "Turnover %",
                        "Cost Drag %",
                        "Buys",
                        "Sells",
                        "Holdings",
                    ]
                    active_cols = [c for c in disp_cols if c in m_df.columns]

                    render_saas_table(m_df[active_cols])
                    c_dl.download_button(
                        "Export months CSV",
                        m_df[active_cols].to_csv(index=False).encode(),
                        f"monthly_performance_{ist_now():%Y%m%d}.csv",
                        "text/csv",
                        key="dl_bt_monthly_csv",
                    )
                else:
                    st.info("No monthly period records available.")

            elif sub_view == "Every trade":
                if not closed_trades.empty:
                    ct_df = closed_trades.copy()

                    # Trade KPI summary metrics
                    closed_only = (
                        ct_df[ct_df["Status"] == "Closed"]
                        if "Status" in ct_df.columns
                        else ct_df
                    )
                    # A trade whose fill price is missing has a NaN return, not a
                    # zero one. Leaving it in the base counts it as a loss in the
                    # win rate while contributing nothing to either P&L total.
                    closed_only = closed_only[closed_only["Return %"].notna()]
                    if not closed_only.empty and "Return %" in closed_only.columns:
                        n_closed = len(closed_only)
                        wins = closed_only[closed_only["Return %"] > 0]
                        losses = closed_only[closed_only["Return %"] < 0]
                        win_rate_pct = (len(wins) / n_closed * 100) if n_closed > 0 else 0.0
                        avg_win = (wins["Return %"].mean() * 100) if not wins.empty else 0.0
                        avg_loss = (
                            (losses["Return %"].mean() * 100) if not losses.empty else 0.0
                        )
                        tot_gain = wins["Return %"].sum() if not wins.empty else 0.0
                        tot_loss = (
                            abs(losses["Return %"].sum()) if not losses.empty else 0.001
                        )
                        profit_factor = (tot_gain / tot_loss) if tot_loss > 0 else 0.0
                        best_tr = (
                            (closed_only["Return %"].max() * 100)
                            if not closed_only.empty
                            else 0.0
                        )
                        worst_tr = (
                            (closed_only["Return %"].min() * 100)
                            if not closed_only.empty
                            else 0.0
                        )

                        kit.readings([
                            kit.Reading("Closed trades", f"{n_closed}", f"{win_rate_pct:.1f}% of them won"),
                            kit.Reading("Profit factor", f"{profit_factor:.2f}×", "total gains ÷ total losses"),
                            kit.Reading("Average win / loss", f"+{avg_win:.1f}% / {avg_loss:.1f}%", ""),
                            kit.Reading("Best / worst", f"+{best_tr:.1f}% / {worst_tr:.1f}%", ""),
                        ], "Closed trades")

                    tf1, tf2 = st.columns([1.5, 1], vertical_alignment="center")
                    all_months = ["All months"] + [
                        m for m in ct_df["Month"].unique() if m
                    ]
                    sel_m = tf1.selectbox(
                        "Filter Month", all_months, index=0, key="bt_ct_month_filter"
                    )

                    tr_filter = tf2.pills(
                        "Filter Outcome",
                        ["All", "Winners", "Losers", "Open"],
                        default="All",
                        key="bt_ct_outcome_filter",
                    )

                    if sel_m != "All months":
                        ct_df = ct_df[ct_df["Month"] == sel_m]

                    if tr_filter == "Winners":
                        ct_df = ct_df[ct_df["Return %"] > 0]
                    elif tr_filter == "Losers":
                        ct_df = ct_df[ct_df["Return %"] < 0]
                    elif tr_filter == "Open":
                        ct_df = ct_df[ct_df["Status"] == "Open"]

                    disp_trade_cols = [
                        "Month",
                        "Symbol",
                        "Entry Date",
                        "Entry Price",
                        "Exit Date",
                        "Exit Price",
                        "Return %",
                        "Holding (Days)",
                        "Reason for Exit",
                    ]
                    active_ct_cols = [c for c in disp_trade_cols if c in ct_df.columns]

                    render_saas_table(ct_df[active_ct_cols])
                    c_dl.download_button(
                        "Export trades CSV",
                        closed_trades[active_ct_cols].to_csv(index=False).encode(),
                        f"realized_trades_{ist_now():%Y%m%d}.csv",
                        "text/csv",
                        key="dl_bt_realized_trades_csv",
                    )
                else:
                    st.info("No realized trades logged for this backtest window.")

            else:
                # ── Rebalance Log View ───────────────────────────────────────────
                if not tradebook.empty:
                    t1, t2 = st.columns([1.5, 1], vertical_alignment="center")
                    all_periods = ["All rebalances"] + [
                        p for p in tradebook["Period"].unique() if p
                    ]
                    selected_period = t1.selectbox(
                        "Filter Rebalance Period",
                        all_periods,
                        index=0,
                        key="bt_tb_period_filter",
                    )

                    action_filter = t2.pills(
                        "Filter Action",
                        ["All", "Buy", "Sell", "Hold"],
                        default="All",
                        key="bt_tb_action_filter",
                    )

                    tb_view = tradebook.copy()
                    if selected_period != "All rebalances":
                        tb_view = tb_view[tb_view["Period"] == selected_period]

                    if action_filter == "Buy":
                        tb_view = tb_view[tb_view["Action"].str.contains("BUY")]
                    elif action_filter == "Sell":
                        tb_view = tb_view[tb_view["Action"].str.contains("SELL")]
                    elif action_filter == "Hold":
                        tb_view = tb_view[tb_view["Action"].str.contains("HOLD")]

                    tb_disp_cols = [
                        "Period",
                        "Action",
                        "Symbol",
                        "Price",
                        "Return %",
                        "Weight %",
                        "Reason / Signal",
                    ]
                    active_tb_cols = [c for c in tb_disp_cols if c in tb_view.columns]

                    render_saas_table(tb_view[active_tb_cols])

                    c_dl.download_button(
                        "Export rebalance log CSV",
                        tradebook[active_tb_cols].to_csv(index=False).encode(),
                        f"rebalance_log_{ist_now():%Y%m%d}.csv",
                        "text/csv",
                        key="dl_bt_tradebook_csv",
                    )
                else:
                    st.info(
                        "No tradebook records available for this backtest configuration."
                    )

    if view == "Method":
      with kit.card("Method", "bt_method", "how every figure on this page is made"):
        st.markdown(
            "**Zero Look-Ahead Execution**: At each rebalance date $T$, stocks are ranked using closing prices strictly up to $T$. "
            "Positions are filled at the $T+1$ close, so the first session they earn anything in is $T+2$ — the $T \\rightarrow T+1$ move "
            "happens before the book exists and is not credited to it.\n\n"
            "**Fill-to-fill accounting**: every period runs from one fill to the next, which is why a period's end date is the following "
            "period's start date. Each stock's realized return is exactly its exit fill divided by its entry fill, and the per-period "
            "strategy return is those same fills weighted — the tradebook and the equity curve are one calculation, not two.\n\n"
            f"**Transaction Cost Drag**: Deducts **{cost_drag_bps:.0f} bps** per unit of turnover (reflecting STT, Exchange fees, GST, Stamp duty, and slippage).\n\n"
            f"**Rank Persistence Buffer**: Top **{int(bt_n * buffer_mult)}** buffer zone prevents unnecessary trading when stocks oscillate around the rank threshold."
        )

    # ── Parameter Sweep ──────────────────────────────────────────────────────
    _render_parameter_sweep(
        adj_close=adj_close,
        benchmark_close=benchmark_close,
        sector_map=sec_map,
        base={
            "weight_method": bt_weight,
            "config_weights": active_weights,
            "stock_cap": stock_cap,
            "sector_cap": sector_cap,
            "rebal_freq": bt_rebal,
            "top_n": bt_n,
            "ema_period": 50,
            "high_pct": 0.80,
            "cost_bps": cost_drag_bps,
        },
    )

    render_data_quality_footer(
        total_stocks=len(rank_df),
        gap_count=gap_count(rank_df),
        short_count=int((rank_df.get("Short History", pd.Series()) == "Yes").sum()),
    )


# The sweep table carries raw stats: fractions for returns and drawdowns
# (0.1234 == +12.34%), an already-scaled percentage for turnover. Rendered with
# no column config they printed as bare decimals, so a 12% return and a 0.12
# ratio were indistinguishable on screen. Scale the fractions for DISPLAY only
# -- the CSV keeps the raw numbers, which is what you want to compute on.
_SWEEP_FRACTION_COLS = ("Total Return", "Alpha", "Max DD", "Win Rate")


def _sweep_display_frame(table: pd.DataFrame) -> pd.DataFrame:
    disp = table.copy()
    for col in _SWEEP_FRACTION_COLS + ("52W high floor",):
        if col in disp.columns:
            disp[col] = pd.to_numeric(disp[col], errors="coerce") * 100
    return disp


def _sweep_column_config() -> dict:
    n = st.column_config.NumberColumn
    return {
        "Rank": n("Rank", format="%.0f"),
        "Holdings": n("Holdings", format="%.0f"),
        "Rebalance": n("Rebalance", help="Trading days between rebalances", format="%.0f"),
        "EMA filter": n("EMA filter", format="%.0f"),
        "52W high floor": n("52W high floor", format="%.0f%%"),
        "Cost (bps)": n("Cost (bps)", format="%.0f"),
        "Buffer": n("Buffer", format="%.0f"),
        "Score": n("Score", help="The objective being maximised", format="%.3f"),
        "Sharpe": n("Sharpe", format="%.2f"),
        "Total Return": n("Total Return", format="%.1f%%"),
        "Alpha": n("Alpha", help="vs the Nifty 500 benchmark", format="%.1f%%"),
        "Max DD": n("Max DD", format="%.1f%%"),
        "Calmar": n("Calmar", format="%.2f"),
        "Win Rate": n("Win Rate", format="%.0f%%"),
        "Turnover": n("Turnover", help="Average per rebalance", format="%.1f%%"),
        "Periods": n("Periods", format="%.0f"),
        "In-sample Score": n("In-sample Score", format="%.3f"),
        "Out-of-sample Score": n("Out-of-sample Score", format="%.3f"),
        "In-sample Rank": n("In-sample Rank", format="%.0f"),
        "Out-of-sample Rank": n("Out-of-sample Rank", format="%.0f"),
    }


def _render_parameter_sweep(
    adj_close,
    benchmark_close,
    sector_map,
    base: dict,
) -> None:
    """Grid search over buy/sell criteria, with the overfitting caveat attached.

    The caveat is rendered with the result rather than tucked into a tooltip.
    Searching many combinations on one window and keeping the winner is data
    mining; the honest output is the distribution plus how far the winner sits
    from the pack, and that is what this shows.
    """
    with st.expander("Parameter sweep · search buy and sell criteria", expanded=False):
        st.caption(
            "Backtests every combination you select over the same window and ranks "
            "them. Read the overfitting verdict before acting on a winner."
        )

        c1, c2, c3 = st.columns(3)
        holdings = c1.multiselect("Holdings Count", [5, 10, 15, 20, 30, 50],
                                  default=[10, 20, 30], key="sweep_holdings")
        rebals = c2.multiselect(
            "Rebalance Interval", [5, 10, 21, 42, 63], default=[21],
            format_func=lambda x: "Monthly" if x == 21 else f"{x}D",
            key="sweep_rebal",
        )
        emas = c3.multiselect("EMA Filter Period", [20, 50, 100, 200],
                              default=[50], key="sweep_ema")

        c4, c5, c6 = st.columns(3)
        floors = c4.multiselect(
            "52W High Floor", [0.0, 0.7, 0.8, 0.9],
            default=[0.8],
            format_func=lambda x: "Off" if x == 0.0 else f"{x:.0%} of 52W high",
            key="sweep_floor",
        )
        costs = c5.multiselect("Cost (bps)", [0.0, 15.0, 30.0, 50.0],
                               default=[30.0], key="sweep_cost")
        objective = c6.selectbox("Optimise For", list(OBJECTIVES),
                                 index=0, key="sweep_objective")

        use_holdout = st.checkbox(
            "Validate the winner on a holdout half",
            value=True,
            key="sweep_holdout",
            help=(
                "Splits the window in two, ranks the whole grid on each half, and "
                "reports where the in-sample winner landed in the half it never "
                "saw. This is the only check here that separates a real setting "
                "from a lucky one. It roughly doubles the run time."
            ),
        )

        space = {}
        if len(holdings) > 1 or (holdings and holdings != [base["top_n"]]):
            space["Holdings"] = holdings
        if rebals:
            space["Rebalance"] = rebals
        if emas:
            space["EMA filter"] = emas
        if floors:
            space["52W high floor"] = floors
        if costs:
            space["Cost (bps)"] = costs
        space = {k: v for k, v in space.items() if v}

        n_combos = count_combinations(space)
        if n_combos == 0:
            st.info("Select at least one value for a parameter to sweep.")
            return

        # Every combination is a full walk-forward backtest. Say what it costs
        # BEFORE the click, not with a spinner afterwards.
        st.markdown(
            f"**{n_combos}** combination{'s' if n_combos != 1 else ''} — "
            f"each one a full walk-forward backtest"
            + (
                ", scored three times over (full window, in-sample half, "
                "out-of-sample half)."
                if use_holdout
                else "."
            )
        )
        if n_combos > 100:
            st.warning(
                f"{n_combos} combinations is a wide search. The more you try, the "
                "better the best one looks by chance alone. Narrow the grid, or "
                "read the overfitting verdict carefully."
            )

        if not st.button("Run sweep", key="sweep_run", type="primary"):
            return

        bar = st.progress(0.0, text="Starting…")

        def _tick(frac, msg):
            bar.progress(min(max(frac, 0.0), 1.0), text=msg)

        try:
            result = run_parameter_sweep(
                adj_close, space, objective=objective, base=dict(base),
                sector_map=sector_map, _benchmark_close=benchmark_close,
                progress=_tick, holdout=use_holdout,
            )
        except ValueError as exc:
            bar.empty()
            st.error(str(exc))
            return
        bar.empty()

        if result.table.empty:
            for w in result.warnings:
                st.warning(w)
            st.info("No combination produced a backtest over this window.")
            return

        risk_tone, risk_label = {
            "high": ("down", "HIGH — the winner is inside the noise"),
            "moderate": ("warn", "MODERATE"),
            "low": ("up", "LOW"),
            "none": ("muted", "PARAMETERS HAD NO EFFECT"),
            "unknown": ("muted", "UNKNOWN"),
        }.get(result.overfitting_risk, ("muted", result.overfitting_risk.upper()))

        kit.callout(f"Overfitting risk: {risk_label}", result.risk_detail, risk_tone)
        for w in result.warnings:
            st.caption(f"⚠️ {w}")

        if result.holdout_detail:
            rho = result.holdout_rho
            kit.callout(
                "Holdout check", result.holdout_detail,
                "muted" if rho is None else "down" if rho < 0.2 else "warn" if rho < 0.5 else "up",
            )

        if result.holdout is not None and not result.holdout.empty:
            t_all, t_half = st.tabs(["All combinations", "Holdout halves"])
            with t_all:
                st.dataframe(
                    _sweep_display_frame(result.table),
                    width="stretch",
                    hide_index=True,
                    column_config=_sweep_column_config(),
                )
            with t_half:
                st.caption(
                    "How each combination ranked in each half. A combination near the "
                    "top of both columns is reproducible. One that tops the in-sample "
                    "half and sinks in the other was fitted to the first half of the "
                    "window."
                )
                st.dataframe(
                    _sweep_display_frame(result.holdout),
                    width="stretch",
                    hide_index=True,
                    column_config=_sweep_column_config(),
                )
        else:
            st.dataframe(
                _sweep_display_frame(result.table),
                width="stretch",
                hide_index=True,
                column_config=_sweep_column_config(),
            )

        st.download_button(
            f"Download sweep results ({len(result.table)} rows)",
            result.table.to_csv(index=False).encode(),
            f"paresh_parameter_sweep_{ist_now():%Y%m%d}.csv",
            "text/csv",
            key="sweep_csv",
        )

def render_backtest_view(
    rank_df: pd.DataFrame,
    adj_close: pd.DataFrame,
    stock_cap: float,
    sector_cap: float,
    weights: tuple[float, ...],
    liquidity_floor_cr: float = 0.0,
    traded_value: pd.DataFrame | None = None,
    months: int = DEFAULT_BACKTEST_MONTHS,
    membership: dict | None = None,
    history_start: pd.Timestamp | None = None,
) -> None:
    """Renders the Walk-Forward Historical Strategy Backtesting Interface."""
    _backtest_body(
        rank_df, adj_close, stock_cap, sector_cap, weights,
        liquidity_floor_cr, traded_value, months, membership, history_start
    )
