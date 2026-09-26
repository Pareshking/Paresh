"""
Strategy Backtesting View Controller with Friction & Turnover Attribution.
"""

import html
import math

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
from src.loaders.ranking_store import actions_digest
from src.ui import page_kit as kit
from src.ui.components import gap_count, render_data_quality_footer
from src.ui.theme import render_saas_table


@st.fragment
def _tone(v) -> str:
    if v is None or pd.isna(v):
        return ""
    return "up" if v > 0 else "down" if v < 0 else ""


def _backtest_body(
    rank_df: pd.DataFrame,
    adj_close: pd.DataFrame,
    stock_cap: float,
    sector_cap: float,
    weights: tuple[float, ...],
) -> None:
    """Fragment: reruns only when backtest-tab widgets change, not on every global rerun."""
    actions = kit.page_head(
        "Backtest",
        f"The strategy replayed on the last {DEFAULT_BACKTEST_MONTHS} completed months, "
        "with the settings below",
        actions=True,
    )
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
    _events = load_events()
    ph = f"{price_fingerprint(adj_close)}_{actions_digest(_events)}"
    benchmark_close = fetch_benchmark_history(period="2y")
    if benchmark_close.empty:
        st.error("Nifty 500 benchmark (^CRSLDX) data is unavailable. Backtest stopped to prevent an invalid benchmark comparison.")
        return
    sec_map = (
        rank_df.set_index("Symbol")["Industry"].to_dict()
        if "Industry" in rank_df.columns
        else {}
    )

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
            _membership=load_history_or_none(),
            _actions=_events,
        )

    if bt_res is None:
        st.warning(
            f"Insufficient price history to backtest the last "
            f"{DEFAULT_BACKTEST_MONTHS} completed months. The strategy needs a "
            "full 12-month formation window BEFORE the reported period, so "
            "roughly 18 months of continuous daily data is required."
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
        if _ranked_on and _ranked_on != "yahoo":
            st.caption(
                f"Backtested on the long price history. The live screener ranks "
                f"on {_display(_ranked_on)}, which does not yet reach far enough "
                f"back for a {DEFAULT_BACKTEST_MONTHS}-month study."
            )
    except Exception:
        pass

    stats = bt_res["stats"]

    # Say which window these numbers describe. The backtest reports the last
    # completed calendar months only -- the month in progress is excluded, so a
    # part-month return is never shown beside whole ones.
    _eq_idx = bt_res["equity_curve"].index
    bt_window_label = (
        f"{_eq_idx[0]:%d %b} to {_eq_idx[-1]:%d %b %Y}"
        if len(_eq_idx)
        else f"last {DEFAULT_BACKTEST_MONTHS} completed months"
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
                    f"scaled up from {_yrs:.2f} years, not a CAGR · Nifty 500 {stats['ann_bench']:+.1%}",
                    _tone(stats["ann_return"])),
        kit.Reading("Ahead of Nifty 500", f"{stats['alpha'] * 100:+.1f} pts",
                    f"Nifty 500 {stats['bench_return']:+.1%} over the same months", _tone(stats["alpha"])),
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
    with kit.card("Growth of ₹100", "bt_growth", "indigo = strategy · grey = Nifty 500 · daily"):
        kit.growth_chart([f"{d:%d %b}" for d in eq.index], eq.tolist(),
                         None if bm is None else bm.tolist(), key="bt")

    view = st.segmented_control(
        "Backtest detail",
        ["Current book", "This month's changes", "Month by month", "Every trade",
         "Rebalance log", "Method"],
        default="Current book",
        key="bt_view",
        label_visibility="collapsed",
    ) or "Current book"

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
    live_book = bt_res.get("live_book", pd.DataFrame())
    changes = bt_res.get("month_changes", pd.DataFrame())
    lmeta = bt_res.get("live_meta", {}) or {}

    if view in ("Current book", "This month's changes"):
        _as_of = lmeta.get("as_of")
        _sig = lmeta.get("signal_date")
        _fill = lmeta.get("fill_date")
        with kit.card(view, "bt_live"):
            kit.caption(
                "The portfolio as it stands"
                + (f" on {_as_of:%d %b %Y}" if _as_of is not None else "")
                + (
                    f", after the rebalance signalled at the {_sig:%d %b %Y} close "
                    f"and filled on {_fill:%d %b %Y}"
                    if _fill is not None
                    else ""
                )
                + ". Marked at the latest close — these figures sit outside the "
                "completed-month window the performance tables below report on."
            )

            if lmeta.get("rebalanced"):
                n_b = lmeta.get("n_bought", 0)
                n_s = lmeta.get("n_sold", 0)
                n_h = lmeta.get("n_held", 0)
                if n_b == 0 and n_s == 0:
                    kit.caption(
                        f"No change this month. The rebalance ran on {_fill:%d %b %Y} "
                        f"and every one of the {n_h} holdings stayed inside the buffer."
                    )
                else:
                    kit.caption(
                        f"Rebalanced {_fill:%d %b %Y}: {n_s} sold · {n_b} bought · "
                        f"{n_h} held. This month's changes gives the reason for each."
                    )
            else:
                kit.caption(
                    "No rebalance has run since the last reported month. The next "
                    "signal is struck at the close of this month's final session."
                )

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
                    n_up = int((live_book["Return %"] > 0).sum())
                    n_dn = int((live_book["Return %"] < 0).sum())
                    avg_r = float(live_book["Return %"].mean(skipna=True) * 100)
                    n_new = 0
                    if _fill is not None and "Entry Date" in live_book.columns:
                        n_new = int(
                            (pd.to_datetime(live_book["Entry Date"], errors="coerce")
                             == _fill).sum()
                        )
                    kit.readings([
                        kit.Reading("Holdings", f"{len(live_book)}", f"{n_new} added this month"),
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
                        ["All", "Winners", "Losers", "Still open"],
                        default="All",
                        key="bt_ct_outcome_filter",
                    )

                    if sel_m != "All months":
                        ct_df = ct_df[ct_df["Month"] == sel_m]

                    if tr_filter == "Winners":
                        ct_df = ct_df[ct_df["Return %"] > 0]
                    elif tr_filter == "Losers":
                        ct_df = ct_df[ct_df["Return %"] < 0]
                    elif tr_filter == "Still open":
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

        badge = {
            "high": ("#B42318", "HIGH — the winner is inside the noise"),
            "moderate": ("#B54708", "MODERATE"),
            "low": ("#067647", "LOW"),
            "none": ("#5E6878", "PARAMETERS HAD NO EFFECT"),
            "unknown": ("#5E6878", "UNKNOWN"),
        }.get(result.overfitting_risk, ("#5E6878", result.overfitting_risk.upper()))

        st.markdown(
            f"<div style=\"border-left: 3px solid {badge[0]}; background: {badge[0]}0D; "
            f"padding: 10px 14px; border-radius: 6px; margin: 10px 0; "
            f"font-family: 'Geist Mono', monospace; font-size: 0.78rem;\">"
            f"<strong style=\"color:{badge[0]};\">Overfitting risk: {badge[1]}</strong>"
            f"<div style=\"color:#3C4657; margin-top:4px;\">{result.risk_detail}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
        for w in result.warnings:
            st.caption(f"⚠️ {w}")

        if result.holdout_detail:
            rho = result.holdout_rho
            ho_clr = (
                "#5E6878" if rho is None
                else "#B42318" if rho < 0.2
                else "#B54708" if rho < 0.5
                else "#067647"
            )
            st.markdown(
                f"<div style=\"border-left: 3px solid {ho_clr}; background: {ho_clr}0D; "
                f"padding: 10px 14px; border-radius: 6px; margin: 10px 0; "
                f"font-family: 'Geist Mono', monospace; font-size: 0.78rem;\">"
                f"<strong style=\"color:{ho_clr};\">Holdout check</strong>"
                f"<div style=\"color:#3C4657; margin-top:4px;\">{result.holdout_detail}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )

        st.dataframe(
            _sweep_display_frame(result.table),
            width="stretch",
            hide_index=True,
            column_config=_sweep_column_config(),
        )

        if result.holdout is not None and not result.holdout.empty:
            with st.expander(
                "🎯 Holdout detail — how each combination ranked in each half",
                expanded=False,
            ):
                st.caption(
                    "A combination near the top of both columns is reproducible. "
                    "One that tops the in-sample half and sinks in the other was "
                    "fitted to the first half of the window."
                )
                st.dataframe(
                    _sweep_display_frame(result.holdout),
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
) -> None:
    """Renders the Walk-Forward Historical Strategy Backtesting Interface."""
    _backtest_body(rank_df, adj_close, stock_cap, sector_cap, weights)
