"""
Market Breadth View Controller.
"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.engine.breadth import (
    compute_hl_timeseries,
    compute_ma_breadth,
    get_recent_hl_events,
)
from src.ui.charts import render_breadth_chart, render_hl_timeseries_chart
from src.ui.components import render_data_quality_footer
from src.ui.theme import render_saas_table


def render_breadth_view(rank_df: pd.DataFrame, adj_close: pd.DataFrame) -> None:
    """Renders the Market Breadth analytics view."""
    # ── Section 1: MA Breadth ────────────────────────────────────────────────
    bc1, bc2, bc3, bc4 = st.columns([1, 2, 1.2, 1.2], vertical_alignment="center")
    ma_type = bc1.segmented_control(
        "MA Type",
        ["SMA", "EMA"],
        default="EMA",
        key="br_ma_type",
        label_visibility="collapsed",
    )
    if not ma_type:
        ma_type = "EMA"
    sel_mas = bc2.multiselect(
        "MA Periods",
        ["10D", "20D", "50D", "100D", "200D"],
        default=["50D", "200D"],
        key="br_sel_mas",
        placeholder="Select MA Periods…",
        label_visibility="collapsed",
    )
    history_days = bc3.selectbox(
        "Lookback",
        [63, 126, 252],
        index=1,
        format_func=lambda x: {63: "3 Months", 126: "6 Months", 252: "1 Year"}[x],
        key="br_lb_days",
        label_visibility="collapsed",
    )
    bview = bc4.segmented_control(
        "Breakdown",
        ["Universe", "By Index"],
        default="Universe",
        key="br_bview",
        label_visibility="collapsed",
    )
    if not bview:
        bview = "Universe"

    if not sel_mas:
        st.info("Select at least one moving average period above.")
        return

    ph = f"{adj_close.index[-1]}_{adj_close.shape[0]}x{adj_close.shape[1]}"
    breadth_df = compute_ma_breadth(
        ph, adj_close, tuple(sel_mas), lookback=history_days, ma_type=ma_type
    )

    if not breadth_df.empty:
        # KPI Cards for latest breadth readings
        kpi_items = []
        for ma_lbl in sel_mas:
            if ma_lbl in breadth_df.columns:
                val = breadth_df[ma_lbl].iloc[-1]
                clr = (
                    "#059669" if val >= 60 else ("#e11d48" if val <= 40 else "#d97706")
                )
                sig = (
                    "Strong Bullish"
                    if val >= 60
                    else (
                        "Weak / Deteriorating" if val <= 40 else "Neutral Participation"
                    )
                )
                n_stocks = int(val / 100 * len(adj_close.columns))
                kpi_items.append(f"""
                    <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 10px 14px; box-shadow: 0 1px 2px rgba(0,0,0,0.02);">
                        <div style="font-family: 'Plus Jakarta Sans', sans-serif; font-size: 0.70rem; font-weight: 700; color: #64748b; text-transform: uppercase;">Above {ma_lbl} {ma_type}</div>
                        <div style="font-family: 'Outfit', sans-serif; font-size: 1.5rem; font-weight: 800; color: {clr}; margin-top: 1px;">{val:.0f}%</div>
                        <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.69rem; color: {clr}; font-weight: 600;">{n_stocks} stocks · {sig}</div>
                    </div>
                    """)
        st.html(
            f'<div style="display: grid; grid-template-columns: repeat({len(kpi_items)}, 1fr); gap: 10px; margin-bottom: 12px;">{"".join(kpi_items)}</div>'
        )

        st.markdown(" ")
        if bview == "Universe":
            render_breadth_chart(breadth_df, ma_type=ma_type)
        else:
            # Per Index Breakdown
            st.markdown("##### Breadth by Index (Above 50D " + ma_type + ")")
            idx_order = [
                "NIFTY 50",
                "NIFTY NEXT 50",
                "NIFTY MIDCAP 150",
                "NIFTY SMALLCAP 250",
                "NIFTY MICROCAP 250",
            ]
            for idx_name in idx_order:
                syms = rank_df[
                    rank_df["Indices"].str.contains(
                        idx_name.replace("NIFTY ", ""), na=False
                    )
                ]["Symbol"].tolist()
                valid_syms = [s for s in syms if s in adj_close.columns]
                if not valid_syms:
                    continue
                ma_s = (
                    adj_close[valid_syms].ewm(span=50).mean()
                    if ma_type == "EMA"
                    else adj_close[valid_syms].rolling(50).mean()
                )
                pct = float(
                    (
                        (adj_close[valid_syms].iloc[-1] > ma_s.iloc[-1]).sum()
                        / len(valid_syms)
                    )
                    * 100
                )
                clr = (
                    "#059669" if pct >= 60 else ("#e11d48" if pct <= 40 else "#d97706")
                )

                st.html(f"""
                    <div style="display: flex; align-items: center; gap: 12px; padding: 6px 0; border-bottom: 1px solid #f1f5f9;">
                        <div style="font-family: 'Outfit', sans-serif; font-size: 0.82rem; font-weight: 700; color: #334155; min-width: 160px;">
                            {idx_name}
                        </div>
                        <div style="flex: 1; height: 6px; background-color: #f1f5f9; border-radius: 3px; overflow: hidden;">
                            <div style="width: {pct:.0f}%; height: 100%; background-color: {clr}; border-radius: 3px;"></div>
                        </div>
                        <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; font-weight: 700; color: {clr}; min-width: 45px;">
                            {pct:.0f}%
                        </div>
                        <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.75rem; color: #64748b; min-width: 70px;">
                            {len(valid_syms)} stocks
                        </div>
                    </div>
                    """)

    st.divider()

    # ── Section 2: 52W Highs & Lows ──────────────────────────────────────────
    st.markdown("#### 2. Daily New Highs & New Lows Time Series")
    st.caption(
        "Measures daily expansion of new highs vs new lows. Divergences frequently precede broad index turning points."
    )

    h1, h2, h3 = st.columns(3)
    hl_window = h1.selectbox(
        "High/Low Window",
        [52, 126, 252],
        index=2,
        format_func=lambda x: {
            52: "52 Days (Quarter)",
            126: "126 Days (6 Months)",
            252: "252 Days (52 Weeks)",
        }[x],
        key="hl_win_sel",
    )
    hl_history = h2.selectbox(
        "History Period",
        [63, 126, 252],
        index=1,
        format_func=lambda x: {63: "3 Months", 126: "6 Months", 252: "1 Year"}[x],
        key="hl_hist_sel",
    )
    hl_disp = h3.segmented_control(
        "Display Format",
        ["% of Universe", "Stock Count"],
        default="% of Universe",
        key="hl_fmt_radio",
    )
    if not hl_disp:
        hl_disp = "% of Universe"

    hl_df = compute_hl_timeseries(ph, adj_close, window=hl_window, lookback=hl_history)
    if not hl_df.empty:
        today_h = int(hl_df["New Highs"].iloc[-1])
        today_l = int(hl_df["New Lows"].iloc[-1])
        hl_ratio = today_h / max(today_l, 1)
        ratio_clr = (
            "#059669" if hl_ratio > 2 else ("#dc2626" if hl_ratio < 0.5 else "#d97706")
        )
        ratio_sig = (
            "Bullish Expansion"
            if hl_ratio > 2
            else ("Bearish Contraction" if hl_ratio < 0.5 else "Neutral")
        )

        st.html(f"""
            <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-bottom: 12px;">
                <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 10px 14px; box-shadow: 0 1px 2px rgba(0,0,0,0.02);">
                    <div style="font-family: 'Plus Jakarta Sans', sans-serif; font-size: 0.70rem; font-weight: 700; color: #64748b; text-transform: uppercase;">New {hl_window}D Highs Today</div>
                    <div style="font-family: 'Outfit', sans-serif; font-size: 1.5rem; font-weight: 800; color: #059669; margin-top: 1px;">{today_h}</div>
                    <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.69rem; color: #059669; font-weight: 600;">Expanding Highs</div>
                </div>
                <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 10px 14px; box-shadow: 0 1px 2px rgba(0,0,0,0.02);">
                    <div style="font-family: 'Plus Jakarta Sans', sans-serif; font-size: 0.70rem; font-weight: 700; color: #64748b; text-transform: uppercase;">New {hl_window}D Lows Today</div>
                    <div style="font-family: 'Outfit', sans-serif; font-size: 1.5rem; font-weight: 800; color: #dc2626; margin-top: 1px;">{today_l}</div>
                    <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.69rem; color: #dc2626; font-weight: 600;">Expanding Lows</div>
                </div>
                <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 10px 14px; box-shadow: 0 1px 2px rgba(0,0,0,0.02);">
                    <div style="font-family: 'Plus Jakarta Sans', sans-serif; font-size: 0.70rem; font-weight: 700; color: #64748b; text-transform: uppercase;">High / Low Ratio</div>
                    <div style="font-family: 'Outfit', sans-serif; font-size: 1.5rem; font-weight: 800; color: {ratio_clr}; margin-top: 1px;">{hl_ratio:.1f}×</div>
                    <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.69rem; color: {ratio_clr}; font-weight: 600;">{ratio_sig}</div>
                </div>
            </div>
            """)

        st.markdown(" ")
        is_pct = hl_disp == "% of Universe"
        render_hl_timeseries_chart(hl_df, window_label=f"{hl_window}D", is_pct=is_pct)

        # Net New Highs Chart & Historical Breakdown
        with st.expander(
            "📊 Net New Highs (Highs − Lows) & Breakout Stocks by Date", expanded=True
        ):
            net = hl_df["Net New Highs"]
            colors = ["#059669" if v >= 0 else "#e11d48" for v in net.values]
            fig_net = go.Figure(
                go.Bar(
                    x=net.index,
                    y=net.values,
                    marker_color=colors,
                    marker_line_width=0,
                    name="Net New Highs",
                )
            )
            fig_net.add_hline(y=0, line_color="#94a3b8", line_width=1)
            fig_net.update_layout(
                template="plotly_white",
                paper_bgcolor="#ffffff",
                plot_bgcolor="#ffffff",
                font={
                    "family": "Plus Jakarta Sans, sans-serif",
                    "size": 10,
                    "color": "#334155",
                },
                title={
                    "text": "<b>Daily Net New Highs (Highs − Lows)</b>",
                    "font": {"size": 13, "color": "#0f172a"},
                },
                yaxis={"gridcolor": "#f1f5f9"},
                xaxis={"gridcolor": "#f1f5f9"},
                margin={"l": 10, "r": 10, "t": 40, "b": 10},
                height=280,
                showlegend=False,
            )
            st.plotly_chart(fig_net, width="stretch", key="net_hl_chart")

            st.markdown("##### 📋 Stocks Hitting New Highs & Lows (Recent Breakdown)")
            hl_events_df = get_recent_hl_events(
                adj_close, rank_df, window=hl_window, lookback=20
            )
            if not hl_events_df.empty:
                ef1, _ef2 = st.columns([1.5, 2.5], vertical_alignment="center")
                ev_sel = ef1.segmented_control(
                    "Filter Events",
                    ["All Events", "🟢 52W Highs", "🔴 52W Lows"],
                    default="All Events",
                    key="hl_ev_filter",
                    label_visibility="collapsed",
                )
                if ev_sel == "🟢 52W Highs":
                    disp_events = hl_events_df[
                        hl_events_df["Event"].str.contains("High")
                    ]
                elif ev_sel == "🔴 52W Lows":
                    disp_events = hl_events_df[
                        hl_events_df["Event"].str.contains("Low")
                    ]
                else:
                    disp_events = hl_events_df

                render_saas_table(
                    disp_events, key="hl_breakout_records_table", max_height=400
                )
            else:
                st.caption("No new high/low breakouts recorded in the lookback window.")

    render_data_quality_footer(
        total_stocks=len(rank_df),
        gap_count=int((rank_df.get("Data Gap", pd.Series()) == "🔴").sum()),
        short_count=int((rank_df.get("Short History", pd.Series()) == "Yes").sum()),
    )
