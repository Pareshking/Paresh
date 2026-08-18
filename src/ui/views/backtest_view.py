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
    bt_ranking = c3.selectbox(
        "Ranking Model",
        [
            "Composite Sharpe (Config Weights)",
            "Multi-Window Pure Sharpe",
            "Residual (α) Momentum (126D Alpha)",
            "Industry-Relative Momentum",
            "Momentum Acceleration",
            "Exp Regression",
            "Sharpe (Single Window)",
            "Return (Classic Momentum)",
        ],
        index=0,
        key="bt_ranking_model",
    )

    c4, c5, c6 = st.columns(3, vertical_alignment="center")
    bt_weight = c4.selectbox(
        "Weighting Scheme",
        ["Equal Weight", "Inverse Volatility", "MVO (Mean-Variance)"],
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

    # Dynamic Lookback Controls for Backtest
    if "Composite" in bt_ranking or "Multi-Window" in bt_ranking:
        with st.expander("🎛️ Customize Lookback Weights for Backtest", expanded=False):
            st.caption(
                "Adjust the relative weighting across 5 windows to test factor sensitivities."
            )
            bw = st.columns(5)
            w1 = bw[0].slider(
                "1M (21D)", 0.0, 1.0, float(weights[0]), 0.05, key="btw_1"
            )
            w2 = bw[1].slider(
                "3M (63D)", 0.0, 1.0, float(weights[1]), 0.05, key="btw_2"
            )
            w3 = bw[2].slider(
                "6M (126D)", 0.0, 1.0, float(weights[2]), 0.05, key="btw_3"
            )
            w4 = bw[3].slider(
                "9M (189D)", 0.0, 1.0, float(weights[3]), 0.05, key="btw_4"
            )
            w5 = bw[4].slider(
                "12M (252D)", 0.0, 1.0, float(weights[4]), 0.05, key="btw_5"
            )
            active_weights = (w1, w2, w3, w4, w5)
            lb_val = 126
    elif (
        "Single Window" in bt_ranking
        or "Exp Regression" in bt_ranking
        or "Classic Momentum" in bt_ranking
    ):
        with st.expander("⏱️ Single-Window Lookback Period", expanded=False):
            lb_val = st.selectbox(
                "Lookback Window",
                [21, 63, 126, 189, 252],
                index=2,
                format_func=lambda x: {
                    21: "1M (Calendar Month)",
                    63: "3M (Calendar Month × 3)",
                    126: "6M (Calendar Month × 6)",
                    189: "9M (Calendar Month × 9)",
                    252: "12M (Calendar Month × 12)",
                }[x],
                key="bt_single_lb",
            )
            active_weights = tuple(weights)
    else:
        active_weights = tuple(weights)
        lb_val = 126

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
            lookback_ret=lb_val,
            ranking_method=bt_ranking,
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
            <span>🎯 <strong>Engine:</strong> <span style='color: #0f172a; font-weight: 600;'>{bt_ranking}</span></span>
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
            <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.69rem; color: #64748b;">Nifty: {stats['bench_return']:+.1%}</div>
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
            "Portfolio positions are established at $T+1$ (next trading day), completely eliminating look-ahead bias.\n\n"
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
            "lookback_ret": lb_val,
            "ranking_method": bt_ranking,
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
            f"each one a full walk-forward backtest."
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
                progress=_tick,
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

        st.dataframe(result.table, width="stretch", hide_index=True)
        st.download_button(
            f"Download sweep results ({len(result.table)} rows)",
            result.table.to_csv(index=False).encode(),
            f"umiya_parameter_sweep_{ist_now():%Y%m%d}.csv",
            "text/csv",
            key="sweep_csv",
        )
