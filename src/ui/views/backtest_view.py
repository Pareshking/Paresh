"""
Strategy Backtesting View Controller with Friction & Turnover Attribution.
"""

from datetime import datetime

import pandas as pd
import streamlit as st

from src.core.market_time import ist_now
from src.engine.backtester import DEFAULT_BACKTEST_MONTHS, run_backtest
from src.engine.parameter_sweep import (
    OBJECTIVES,
    count_combinations,
    run_parameter_sweep,
)
from src.loaders.price_loader import fetch_benchmark_history
from src.ui.charts import render_backtest_equity_chart
from src.ui.components import render_data_quality_footer
from src.ui.theme import render_saas_table


def render_backtest_view(
    rank_df: pd.DataFrame,
    adj_close: pd.DataFrame,
    stock_cap: float,
    sector_cap: float,
    weights: tuple[float, ...],
) -> None:
    """Renders the Walk-Forward Historical Strategy Backtesting Interface."""
    # ── Aligned Controls Grid ────────────────────────────────────────────────
    c1, c2, c3 = st.columns(3, vertical_alignment="center")
    bt_n = c1.selectbox(
        "Holdings Count", [10, 15, 20, 30, 50], index=2, key="bt_holdings_n"
    )
    bt_rebal = c2.selectbox(
        "Rebalancing Interval",
        [5, 10, 21, 42, 63],
        index=2,
        format_func=lambda x: {
            5: "Weekly (5 Trading Days)",
            10: "Bi-Weekly (10 Trading Days)",
            21: "Monthly (First Trading Day)",
            42: "Bi-Monthly (42 Trading Days)",
            63: "Quarterly (63 Trading Days)",
        }[x],
        key="bt_rebal_freq",
    )
    c4, c5, c6 = st.columns(3, vertical_alignment="center")
    bt_weight = c4.selectbox(
        "Weighting Scheme",
        ["Equal Weight", "Inverse Volatility"],
        index=0,
        key="bt_weight_scheme",
    )
    cost_drag_bps = c5.slider(
        "Transaction Cost Drag (bps)",
        0.0,
        100.0,
        30.0,
        5.0,
        help="Round-trip cost (STT + Stamp Duty + Brokerage + Slippage). Standard NSE equity is ~25-35 bps.",
        key="bt_cost_bps",
    )
    buffer_mult = c6.selectbox(
        "Persistence Buffer",
        [1.0, 1.5, 2.0],
        index=2,
        format_func=lambda x: f"{x:.1f}× Portfolio Size (Top {int(bt_n * x)})",
        help="Retain existing positions if their rank remains within the buffer zone, cutting turnover by >50%.",
        key="bt_buffer_sel",
    )

    # Lookback weights for the composite -- the only scoring model there is.
    with st.expander("🎛️ Customize Lookback Weights for Backtest", expanded=False):
        st.caption(
            "Adjust the relative weighting across 5 windows to test factor sensitivities."
        )
        bw = st.columns(5)
        w1 = bw[0].slider("1M (21D)", 0.0, 1.0, float(weights[0]), 0.05, key="btw_1")
        w2 = bw[1].slider("3M (63D)", 0.0, 1.0, float(weights[1]), 0.05, key="btw_2")
        w3 = bw[2].slider("6M (126D)", 0.0, 1.0, float(weights[2]), 0.05, key="btw_3")
        w4 = bw[3].slider("9M (189D)", 0.0, 1.0, float(weights[3]), 0.05, key="btw_4")
        w5 = bw[4].slider("12M (252D)", 0.0, 1.0, float(weights[4]), 0.05, key="btw_5")
        active_weights = (w1, w2, w3, w4, w5)

    ph = f"{adj_close.index[-1]}_{adj_close.shape[0]}x{adj_close.shape[1]}"
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
        )

    if bt_res is None:
        st.warning(
            f"Insufficient price history to backtest the last "
            f"{DEFAULT_BACKTEST_MONTHS} completed months. The strategy needs a "
            "full 12-month formation window BEFORE the reported period, so "
            "roughly 18 months of continuous daily data is required."
        )
        return

    stats = bt_res["stats"]

    # Say which window these numbers describe. The backtest reports the last
    # completed calendar months only -- the month in progress is excluded, so a
    # part-month return is never shown beside whole ones.
    _eq_idx = bt_res["equity_curve"].index
    bt_window_label = (
        f"Last {DEFAULT_BACKTEST_MONTHS} Completed Months "
        f"({_eq_idx[0]:%d %b %Y} → {_eq_idx[-1]:%d %b %Y})"
        if len(_eq_idx)
        else f"Last {DEFAULT_BACKTEST_MONTHS} Completed Months"
    )

    # ── Active Configuration Attribution Strip ──────────────────────────────
    st.markdown(
        f"""
        <div style='background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 7px 14px; margin-bottom: 12px; font-family: IBM Plex Mono; font-size: 0.76rem; color: #475569; display: flex; flex-wrap: wrap; gap: 14px; align-items: center;'>
            <span>📅 <strong>Period:</strong> <span style='color: #0f172a; font-weight: 600;'>{bt_window_label}</span></span>
            <span>🎯 <strong>Engine:</strong> <span style='color: #0f172a; font-weight: 600;'>Composite Sharpe</span></span>
            <span>⏱️ <strong>Interval:</strong> <span style='color: #0f172a; font-weight: 600;'>{'Monthly · First Trading Day' if bt_rebal == 21 else f'{bt_rebal} Trading Days'}</span></span>
            <span>📦 <strong>Portfolio:</strong> <span style='color: #0f172a; font-weight: 600;'>Top {bt_n} Stocks (Buffer: Top {int(bt_n * buffer_mult)})</span></span>
            <span>⚖️ <strong>Weighting:</strong> <span style='color: #0f172a; font-weight: 600;'>{bt_weight}</span></span>
            <span>💸 <strong>Cost Drag:</strong> <span style='color: #0f172a; font-weight: 600;'>{cost_drag_bps:.0f} bps</span></span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Executive KPI Cards Grid ─────────────────────────────────────────────
    alpha_status = "Outperforming" if stats["alpha"] >= 0 else "Underperforming"
    alpha_clr = "#059669" if stats["alpha"] >= 0 else "#dc2626"
    ret_clr = "#059669" if stats["total_return"] >= 0 else "#dc2626"

    kpi_bt_html = f"""
    <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-bottom: 10px;">
        <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 10px 14px; box-shadow: 0 1px 2px rgba(0,0,0,0.02);">
            <div style="font-family: 'Plus Jakarta Sans', sans-serif; font-size: 0.70rem; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em;">Strategy Return (Net)</div>
            <div style="font-family: 'Outfit', sans-serif; font-size: 1.45rem; font-weight: 800; color: {ret_clr}; margin-top: 1px;">{stats['total_return']:+.1%}</div>
            <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.69rem; color: #64748b;">Gross: {stats['gross_return']:+.1%}</div>
        </div>
        <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 10px 14px; box-shadow: 0 1px 2px rgba(0,0,0,0.02);">
            <div style="font-family: 'Plus Jakarta Sans', sans-serif; font-size: 0.70rem; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em;">CAGR (Annualized)</div>
            <div style="font-family: 'Outfit', sans-serif; font-size: 1.45rem; font-weight: 800; color: #0f172a; margin-top: 1px;">{stats['ann_return']:+.1%}</div>
            <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.69rem; color: #64748b;">Nifty: {stats['ann_bench']:+.1%}</div>
        </div>
        <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 10px 14px; box-shadow: 0 1px 2px rgba(0,0,0,0.02);">
            <div style="font-family: 'Plus Jakarta Sans', sans-serif; font-size: 0.70rem; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em;">Net Alpha vs Benchmark</div>
            <div style="font-family: 'Outfit', sans-serif; font-size: 1.45rem; font-weight: 800; color: {alpha_clr}; margin-top: 1px;">{stats['alpha']:+.1%}</div>
            <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.69rem; color: {alpha_clr}; font-weight: 600;">{alpha_status}</div>
        </div>
        <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 10px 14px; box-shadow: 0 1px 2px rgba(0,0,0,0.02);">
            <div style="font-family: 'Plus Jakarta Sans', sans-serif; font-size: 0.70rem; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em;">Net Sharpe Ratio</div>
            <div style="font-family: 'Outfit', sans-serif; font-size: 1.45rem; font-weight: 800; color: #0f172a; margin-top: 1px;">{stats['sharpe']:.2f}</div>
            <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.69rem; color: #64748b;">Sortino: {stats.get('sortino', 0):.2f}</div>
        </div>
    </div>
    <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-bottom: 12px;">
        <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 10px 14px; box-shadow: 0 1px 2px rgba(0,0,0,0.02);">
            <div style="font-family: 'Plus Jakarta Sans', sans-serif; font-size: 0.70rem; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em;">Max Drawdown</div>
            <div style="font-family: 'Outfit', sans-serif; font-size: 1.45rem; font-weight: 800; color: #dc2626; margin-top: 1px;">{stats['max_drawdown']:.1%}</div>
            <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.69rem; color: #dc2626;">Peak to Trough</div>
        </div>
        <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 10px 14px; box-shadow: 0 1px 2px rgba(0,0,0,0.02);">
            <div style="font-family: 'Plus Jakarta Sans', sans-serif; font-size: 0.70rem; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em;">Calmar Ratio</div>
            <div style="font-family: 'Outfit', sans-serif; font-size: 1.45rem; font-weight: 800; color: #0f172a; margin-top: 1px;">{stats['calmar']:.2f}</div>
            <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.69rem; color: #64748b;">CAGR / Max DD</div>
        </div>
        <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 10px 14px; box-shadow: 0 1px 2px rgba(0,0,0,0.02);">
            <div style="font-family: 'Plus Jakarta Sans', sans-serif; font-size: 0.70rem; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em;">Win Rate</div>
            <div style="font-family: 'Outfit', sans-serif; font-size: 1.45rem; font-weight: 800; color: #059669; margin-top: 1px;">{stats['win_rate']:.0%}</div>
            <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.69rem; color: #64748b;">Profitable Periods</div>
        </div>
        <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 10px 14px; box-shadow: 0 1px 2px rgba(0,0,0,0.02);">
            <div style="font-family: 'Plus Jakarta Sans', sans-serif; font-size: 0.70rem; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em;">Avg Period Turnover</div>
            <div style="font-family: 'Outfit', sans-serif; font-size: 1.45rem; font-weight: 800; color: #0f172a; margin-top: 1px;">{stats['avg_turnover']:.1f}%</div>
            <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.69rem; color: #64748b;">Per Rebalance</div>
        </div>
    </div>
    """
    st.markdown(kpi_bt_html, unsafe_allow_html=True)

    st.markdown(" ")
    render_backtest_equity_chart(bt_res["equity_curve"], bt_res["benchmark"])

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

    if not live_book.empty or not changes.empty:
        _as_of = lmeta.get("as_of")
        _sig = lmeta.get("signal_date")
        _fill = lmeta.get("fill_date")
        with st.expander(
            "📌 Current Book & This Month's Changes", expanded=True
        ):
            st.caption(
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
                    st.info(
                        f"**No change this month.** The rebalance ran on "
                        f"{_fill:%d %b %Y} and every one of the {n_h} holdings "
                        "stayed inside the buffer, so nothing was bought or sold."
                    )
                else:
                    st.success(
                        f"**Rebalanced {_fill:%d %b %Y}** — "
                        f"**{n_s} sold · {n_b} bought · {n_h} held**. "
                        "See This Month's Changes for the reason behind each."
                    )
            else:
                st.info(
                    "No rebalance has run since the last reported month. The next "
                    "signal is struck at the close of this month's final session."
                )

            live_sub = st.segmented_control(
                "Live Book Detail",
                ["📦 Current Holdings", "🔀 This Month's Changes"],
                default="📦 Current Holdings",
                key="bt_live_sub_view",
                label_visibility="collapsed",
            )
            if not live_sub:
                live_sub = "📦 Current Holdings"

            def _fmt_dates(frame: pd.DataFrame) -> pd.DataFrame:
                out = frame.copy()
                if "Entry Date" in out.columns:
                    out["Entry Date"] = pd.to_datetime(
                        out["Entry Date"], errors="coerce"
                    ).dt.strftime("%d %b %Y").fillna("—")
                return out

            if live_sub == "📦 Current Holdings":
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
                    st.html(
                        f"""
                        <div style="display: grid; grid-template-columns: repeat(5, 1fr); gap: 10px; margin-bottom: 12px;">
                            <div style="background:#ffffff;border:1px solid #e2e8f0;border-radius:8px;padding:8px 12px;">
                                <div style="font-family:'Plus Jakarta Sans',sans-serif;font-size:0.68rem;font-weight:700;color:#64748b;text-transform:uppercase;">Holdings</div>
                                <div style="font-family:'Outfit',sans-serif;font-size:1.3rem;font-weight:800;color:#0f172a;margin-top:1px;">{len(live_book)}</div>
                            </div>
                            <div style="background:#ffffff;border:1px solid #e2e8f0;border-radius:8px;padding:8px 12px;">
                                <div style="font-family:'Plus Jakarta Sans',sans-serif;font-size:0.68rem;font-weight:700;color:#64748b;text-transform:uppercase;">Added This Month</div>
                                <div style="font-family:'Outfit',sans-serif;font-size:1.3rem;font-weight:800;color:#0f172a;margin-top:1px;">{n_new}</div>
                            </div>
                            <div style="background:#ffffff;border:1px solid #e2e8f0;border-radius:8px;padding:8px 12px;">
                                <div style="font-family:'Plus Jakarta Sans',sans-serif;font-size:0.68rem;font-weight:700;color:#64748b;text-transform:uppercase;">In Profit</div>
                                <div style="font-family:'Outfit',sans-serif;font-size:1.3rem;font-weight:800;color:#059669;margin-top:1px;">{n_up}</div>
                            </div>
                            <div style="background:#ffffff;border:1px solid #e2e8f0;border-radius:8px;padding:8px 12px;">
                                <div style="font-family:'Plus Jakarta Sans',sans-serif;font-size:0.68rem;font-weight:700;color:#64748b;text-transform:uppercase;">In Loss</div>
                                <div style="font-family:'Outfit',sans-serif;font-size:1.3rem;font-weight:800;color:#dc2626;margin-top:1px;">{n_dn}</div>
                            </div>
                            <div style="background:#ffffff;border:1px solid #e2e8f0;border-radius:8px;padding:8px 12px;">
                                <div style="font-family:'Plus Jakarta Sans',sans-serif;font-size:0.68rem;font-weight:700;color:#64748b;text-transform:uppercase;">Avg Unrealised</div>
                                <div style="font-family:'Outfit',sans-serif;font-size:1.3rem;font-weight:800;color:{'#059669' if avg_r >= 0 else '#dc2626'};margin-top:1px;">{avg_r:+.1f}%</div>
                            </div>
                        </div>
                        """
                    )
                    render_saas_table(lb, key="bt_live_book_table")
                    st.download_button(
                        "⬇️ Export Current Holdings (CSV)",
                        lb.to_csv(index=False).encode(),
                        f"current_book_{datetime.now():%Y%m%d}.csv",
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
                    render_saas_table(ch, key="bt_month_changes_table")
                    st.download_button(
                        "⬇️ Export This Month's Changes (CSV)",
                        _fmt_dates(changes).to_csv(index=False).encode(),
                        f"month_changes_{datetime.now():%Y%m%d}.csv",
                        "text/csv",
                        key="dl_bt_changes_csv",
                    )


    # ── Monthly Performance Breakdown & Rebalance Tradebook ──────────────────
    with st.expander("📋 Per-Period Performance & Rebalance Tradebook", expanded=True):
        c_sub, c_dl = st.columns([2, 1], vertical_alignment="center")
        sub_view = c_sub.segmented_control(
            "Backtest Detail View",
            [
                "📊 Monthly Performance & Alpha",
                "📋 Realized Trades & Returns",
                "🔄 Rebalance Log",
            ],
            default="📋 Realized Trades & Returns",
            key="bt_detail_sub_view",
            label_visibility="collapsed",
        )
        if not sub_view:
            sub_view = "📋 Realized Trades & Returns"

        monthly = bt_res.get("monthly", pd.DataFrame())
        tradebook = bt_res.get("tradebook", pd.DataFrame())
        closed_trades = bt_res.get("closed_trades", pd.DataFrame())

        if sub_view == "📊 Monthly Performance & Alpha":
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

                render_saas_table(m_df[active_cols], key="bt_monthly_table")
                c_dl.download_button(
                    "⬇️ Export Monthly Performance (CSV)",
                    m_df[active_cols].to_csv(index=False).encode(),
                    f"monthly_performance_{datetime.now():%Y%m%d}.csv",
                    "text/csv",
                    key="dl_bt_monthly_csv",
                )
            else:
                st.info("No monthly period records available.")

        elif sub_view == "📋 Realized Trades & Returns":
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

                    trade_kpi_html = f"""
                    <div style="display: grid; grid-template-columns: repeat(5, 1fr); gap: 10px; margin-bottom: 12px;">
                        <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 8px 12px; box-shadow: 0 1px 2px rgba(0,0,0,0.02);">
                            <div style="font-family: 'Plus Jakarta Sans', sans-serif; font-size: 0.68rem; font-weight: 700; color: #64748b; text-transform: uppercase;">Closed Trades</div>
                            <div style="font-family: 'Outfit', sans-serif; font-size: 1.3rem; font-weight: 800; color: #0f172a; margin-top: 1px;">{n_closed}</div>
                        </div>
                        <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 8px 12px; box-shadow: 0 1px 2px rgba(0,0,0,0.02);">
                            <div style="font-family: 'Plus Jakarta Sans', sans-serif; font-size: 0.68rem; font-weight: 700; color: #64748b; text-transform: uppercase;">Win Rate</div>
                            <div style="font-family: 'Outfit', sans-serif; font-size: 1.3rem; font-weight: 800; color: #059669; margin-top: 1px;">{win_rate_pct:.1f}%</div>
                        </div>
                        <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 8px 12px; box-shadow: 0 1px 2px rgba(0,0,0,0.02);">
                            <div style="font-family: 'Plus Jakarta Sans', sans-serif; font-size: 0.68rem; font-weight: 700; color: #64748b; text-transform: uppercase;">Profit Factor</div>
                            <div style="font-family: 'Outfit', sans-serif; font-size: 1.3rem; font-weight: 800; color: #0f172a; margin-top: 1px;">{profit_factor:.2f}×</div>
                        </div>
                        <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 8px 12px; box-shadow: 0 1px 2px rgba(0,0,0,0.02);">
                            <div style="font-family: 'Plus Jakarta Sans', sans-serif; font-size: 0.68rem; font-weight: 700; color: #64748b; text-transform: uppercase;">Avg Win / Loss</div>
                            <div style="font-family: 'Outfit', sans-serif; font-size: 1.15rem; font-weight: 800; color: #0f172a; margin-top: 1px;">+{avg_win:.1f}% / {avg_loss:.1f}%</div>
                        </div>
                        <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 8px 12px; box-shadow: 0 1px 2px rgba(0,0,0,0.02);">
                            <div style="font-family: 'Plus Jakarta Sans', sans-serif; font-size: 0.68rem; font-weight: 700; color: #64748b; text-transform: uppercase;">Best / Worst</div>
                            <div style="font-family: 'Outfit', sans-serif; font-size: 1.15rem; font-weight: 800; color: #0f172a; margin-top: 1px;">+{best_tr:.1f}% / {worst_tr:.1f}%</div>
                        </div>
                    </div>
                    """
                    st.html(trade_kpi_html)

                tf1, tf2 = st.columns([1.5, 1], vertical_alignment="center")
                all_months = ["🌟 All Months"] + [
                    m for m in ct_df["Month"].unique() if m
                ]
                sel_m = tf1.selectbox(
                    "Filter Month", all_months, index=0, key="bt_ct_month_filter"
                )

                tr_filter = tf2.pills(
                    "Filter Outcome",
                    ["All", "🟢 Winners (>0%)", "🔴 Losers (<0%)", "🌟 Active Open"],
                    default="All",
                    key="bt_ct_outcome_filter",
                )

                if sel_m != "🌟 All Months":
                    ct_df = ct_df[ct_df["Month"] == sel_m]

                if tr_filter == "🟢 Winners (>0%)":
                    ct_df = ct_df[ct_df["Return %"] > 0]
                elif tr_filter == "🔴 Losers (<0%)":
                    ct_df = ct_df[ct_df["Return %"] < 0]
                elif tr_filter == "🌟 Active Open":
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

                render_saas_table(ct_df[active_ct_cols], key="bt_closed_trades_table")
                c_dl.download_button(
                    "⬇️ Export Realized Trades (CSV)",
                    closed_trades[active_ct_cols].to_csv(index=False).encode(),
                    f"realized_trades_{datetime.now():%Y%m%d}.csv",
                    "text/csv",
                    key="dl_bt_realized_trades_csv",
                )
            else:
                st.info("No realized trades logged for this backtest window.")

        else:
            # ── Rebalance Log View ───────────────────────────────────────────
            if not tradebook.empty:
                t1, t2 = st.columns([1.5, 1], vertical_alignment="center")
                all_periods = ["🌟 All Rebalance Periods"] + [
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
                    ["All", "🟢 BUY", "🔴 SELL", "⚪ HOLD"],
                    default="All",
                    key="bt_tb_action_filter",
                )

                tb_view = tradebook.copy()
                if selected_period != "🌟 All Rebalance Periods":
                    tb_view = tb_view[tb_view["Period"] == selected_period]

                if action_filter == "🟢 BUY":
                    tb_view = tb_view[tb_view["Action"].str.contains("BUY")]
                elif action_filter == "🔴 SELL":
                    tb_view = tb_view[tb_view["Action"].str.contains("SELL")]
                elif action_filter == "⚪ HOLD":
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

                render_saas_table(tb_view[active_tb_cols], key="bt_tradebook_table")

                c_dl.download_button(
                    "⬇️ Export Full Rebalance Log (CSV)",
                    tradebook[active_tb_cols].to_csv(index=False).encode(),
                    f"rebalance_log_{datetime.now():%Y%m%d}.csv",
                    "text/csv",
                    key="dl_bt_tradebook_csv",
                )
            else:
                st.info(
                    "No tradebook records available for this backtest configuration."
                )

    with st.expander("ℹ️ Backtest Methodology & Mathematical Assumptions"):
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
    st.divider()
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
        gap_count=int((rank_df.get("Data Gap", pd.Series()) == "🔴").sum()),
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
    with st.expander("🔬 Parameter Sweep — search buy/sell criteria", expanded=False):
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
            "high": ("#dc2626", "HIGH — the winner is inside the noise"),
            "moderate": ("#d97706", "MODERATE"),
            "low": ("#059669", "LOW"),
            "none": ("#64748b", "PARAMETERS HAD NO EFFECT"),
            "unknown": ("#64748b", "UNKNOWN"),
        }.get(result.overfitting_risk, ("#64748b", result.overfitting_risk.upper()))

        st.markdown(
            f"<div style=\"border-left: 3px solid {badge[0]}; background: {badge[0]}0D; "
            f"padding: 10px 14px; border-radius: 6px; margin: 10px 0; "
            f"font-family: 'IBM Plex Mono', monospace; font-size: 0.78rem;\">"
            f"<strong style=\"color:{badge[0]};\">Overfitting risk: {badge[1]}</strong>"
            f"<div style=\"color:#475569; margin-top:4px;\">{result.risk_detail}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
        for w in result.warnings:
            st.caption(f"⚠️ {w}")

        if result.holdout_detail:
            rho = result.holdout_rho
            ho_clr = (
                "#64748b" if rho is None
                else "#dc2626" if rho < 0.2
                else "#d97706" if rho < 0.5
                else "#059669"
            )
            st.markdown(
                f"<div style=\"border-left: 3px solid {ho_clr}; background: {ho_clr}0D; "
                f"padding: 10px 14px; border-radius: 6px; margin: 10px 0; "
                f"font-family: 'IBM Plex Mono', monospace; font-size: 0.78rem;\">"
                f"<strong style=\"color:{ho_clr};\">Holdout check</strong>"
                f"<div style=\"color:#475569; margin-top:4px;\">{result.holdout_detail}</div>"
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
