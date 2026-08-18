"""
Qualified Momentum Picks View Controller.
Contains Top 30 Qualified Composite Momentum and Top 30 Qualified Residual Momentum sections.
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.ui.components import render_data_quality_footer, to_bool_mask
from src.ui.theme import render_master_screener_table


def _render_qualified_section(
    title: str,
    subtitle: str,
    df_subset: pd.DataFrame,
    adj_close: pd.DataFrame,
    key_prefix: str,
    theme_color: str = "#4f46e5",
) -> None:
    """Renders a complete qualified momentum section with KPIs, screener table, industry concentration, and correlation matrix."""
    st.markdown(
        f"""
        <div style="display: flex; justify-content: space-between; align-items: baseline; margin-top: 10px; margin-bottom: 6px;">
            <div style="font-family: 'Outfit', sans-serif; font-size: 1.15rem; font-weight: 800; color: #0f172a;">
                {title}
            </div>
            <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.75rem; color: {theme_color}; font-weight: 700; background: #f8fafc; border: 1px solid #e2e8f0; padding: 3px 8px; border-radius: 6px;">
                {subtitle}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if df_subset.empty:
        st.info(
            "No stocks currently satisfy both the 50 EMA and 52W High criteria for this strategy."
        )
        return

    # Metrics
    avg_3m = df_subset["3M Return"].mean() if "3M Return" in df_subset.columns else 0.0
    avg_6m = df_subset["6M Return"].mean() if "6M Return" in df_subset.columns else 0.0
    syms = [s for s in df_subset["Symbol"] if s in adj_close.columns]

    corr_val: float | None = None
    corr_df: pd.DataFrame | None = None
    if len(syms) > 1:
        corr_df = adj_close[syms].iloc[-90:].pct_change(fill_method=None).corr()
        corr_val = float(corr_df.values[np.triu_indices_from(corr_df, k=1)].mean())

    corr_status = "Diversified" if corr_val and corr_val < 0.70 else "High Correlation"
    corr_clr = "#059669" if corr_val and corr_val < 0.70 else "#d97706"
    corr_str = f"{corr_val:.2f}" if corr_val is not None else "—"

    kpi_html = f"""
    <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 12px;">
        <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 10px 14px; box-shadow: 0 1px 2px rgba(0,0,0,0.02); border-top: 3px solid {theme_color};">
            <div style="font-family: 'Plus Jakarta Sans', sans-serif; font-size: 0.72rem; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em;">Qualified Count</div>
            <div style="font-family: 'Outfit', sans-serif; font-size: 1.5rem; font-weight: 800; color: #0f172a; margin-top: 2px;">{len(df_subset)}</div>
            <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.70rem; color: #059669; font-weight: 600;">Top Selection</div>
        </div>
        <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 10px 14px; box-shadow: 0 1px 2px rgba(0,0,0,0.02);">
            <div style="font-family: 'Plus Jakarta Sans', sans-serif; font-size: 0.72rem; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em;">Avg 3M Return</div>
            <div style="font-family: 'Outfit', sans-serif; font-size: 1.5rem; font-weight: 800; color: #059669; margin-top: 2px;">{avg_3m:+.1%}</div>
            <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.70rem; color: #64748b;">Trailing 63 Days</div>
        </div>
        <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 10px 14px; box-shadow: 0 1px 2px rgba(0,0,0,0.02);">
            <div style="font-family: 'Plus Jakarta Sans', sans-serif; font-size: 0.72rem; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em;">Avg 6M Return</div>
            <div style="font-family: 'Outfit', sans-serif; font-size: 1.5rem; font-weight: 800; color: #059669; margin-top: 2px;">{avg_6m:+.1%}</div>
            <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.70rem; color: #64748b;">Trailing 126 Days</div>
        </div>
        <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 10px 14px; box-shadow: 0 1px 2px rgba(0,0,0,0.02);">
            <div style="font-family: 'Plus Jakarta Sans', sans-serif; font-size: 0.72rem; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em;">Avg 90D Correlation</div>
            <div style="font-family: 'Outfit', sans-serif; font-size: 1.5rem; font-weight: 800; color: #0f172a; margin-top: 2px;">{corr_str}</div>
            <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.70rem; color: {corr_clr}; font-weight: 600;">{corr_status}</div>
        </div>
    </div>
    """
    st.markdown(kpi_html, unsafe_allow_html=True)

    render_master_screener_table(
        df_subset, prices_df=adj_close, key=f"{key_prefix}_table"
    )

    st.markdown(" ")
    ca, cb = st.columns([1, 1.35], gap="medium")
    with ca:
        st.markdown("##### Industry Concentration")
        alloc = df_subset["Industry"].value_counts().reset_index()
        alloc.columns = ["Industry", "Count"]
        total_q = len(df_subset)
        alloc["Pct"] = (alloc["Count"] / total_q) * 100

        ind_items_html = []
        for _, r in alloc.iterrows():
            ind_items_html.append(f"""
                <div style="margin-bottom: 9px;">
                    <div style="display: flex; justify-content: space-between; font-size: 0.76rem; font-family: 'Plus Jakarta Sans', sans-serif; margin-bottom: 3px;">
                        <span style="font-weight: 600; color: #0f172a;">{r['Industry']}</span>
                        <span style="font-family: 'JetBrains Mono', monospace; color: #475569; font-weight: 700;">{int(r['Count'])} stock{'s' if r['Count']>1 else ''} ({r['Pct']:.0f}%)</span>
                    </div>
                    <div style="width: 100%; height: 6px; background-color: #f1f5f9; border-radius: 99px; overflow: hidden;">
                        <div style="width: {r['Pct']}%; height: 100%; background: linear-gradient(90deg, {theme_color}, #06b6d4); border-radius: 99px;"></div>
                    </div>
                </div>
                """)
        breakdown_html = f"""
        <div style="background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 14px 16px; box-shadow: 0 1px 2px rgba(0,0,0,0.02);">
            {''.join(ind_items_html)}
        </div>
        """
        st.html(breakdown_html)

    with cb:
        c_hdr, c_sel = st.columns([1.5, 1], vertical_alignment="center")
        with c_hdr:
            st.markdown("##### 90-Day Return Correlation Matrix")
        with c_sel:
            n_disp = st.segmented_control(
                "Matrix Size",
                [8, 10, 12, 15],
                default=10,
                key=f"{key_prefix}_corr_matrix_size",
                label_visibility="collapsed",
            )
            if not n_disp:
                n_disp = 10

        if corr_df is not None and len(syms) > 1:
            try:
                disp_syms = syms[: int(n_disp)]
                sub_corr = corr_df.loc[disp_syms, disp_syms]

                z_vals = sub_corr.values
                text_vals = np.round(z_vals, 2)

                fig_corr = go.Figure(
                    data=go.Heatmap(
                        z=z_vals,
                        x=disp_syms,
                        y=disp_syms,
                        colorscale=[
                            [0.0, "#ffffff"],
                            [0.25, "#f0f9ff"],
                            [0.5, "#bae6fd"],
                            [0.75, "#38bdf8"],
                            [1.0, "#0284c7"],
                        ],
                        zmin=-0.2,
                        zmax=1.0,
                        text=text_vals,
                        texttemplate="%{text:.2f}",
                        textfont={
                            "family": "JetBrains Mono, monospace",
                            "size": 10.5,
                            "color": "#0f172a",
                        },
                        hovertemplate="<b>%{x}</b> × <b>%{y}</b><br>Correlation: <b>%{z:.2f}</b><extra></extra>",
                        colorbar={
                            "thickness": 10,
                            "len": 0.9,
                            "tickfont": {
                                "family": "JetBrains Mono, monospace",
                                "size": 9,
                                "color": "#64748b",
                            },
                            "outlinewidth": 0,
                        },
                    )
                )
                fig_corr.update_layout(
                    height=400,
                    margin={"l": 40, "r": 10, "t": 10, "b": 40},
                    paper_bgcolor="#ffffff",
                    plot_bgcolor="#ffffff",
                    xaxis={
                        "tickfont": {
                            "family": "Outfit, sans-serif",
                            "size": 10,
                            "color": "#0f172a",
                        },
                        "tickangle": -45,
                        "showgrid": False,
                    },
                    yaxis={
                        "tickfont": {
                            "family": "Outfit, sans-serif",
                            "size": 10,
                            "color": "#0f172a",
                        },
                        "showgrid": False,
                        "autorange": "reversed",
                    },
                )
                st.plotly_chart(
                    fig_corr, width="stretch", config={"displayModeBar": False}
                )
            except Exception:
                st.info("Unable to render correlation heatmap.")
        else:
            st.info("Insufficient stock history to construct correlation matrix.")


def render_qualified_view(rank_df: pd.DataFrame, adj_close: pd.DataFrame) -> None:
    """Renders Top 30 Qualified Stocks across Composite Multi-Window and Residual Momentum."""
    c_filt, c_ctrl = st.columns([3, 1], vertical_alignment="center")
    with c_filt:
        st.markdown(
            "<div style=\"font-family: 'Plus Jakarta Sans', sans-serif; font-size: 0.85rem; color: #475569; padding-top: 4px;\">"
            'Institutional Strict Filter: <strong style="color: #059669;">Price > 50 EMA</strong> &nbsp;·&nbsp; <strong style="color: #4f46e5;">Within 20% of 52W High</strong>'
            "</div>",
            unsafe_allow_html=True,
        )
    top_n = c_ctrl.selectbox(
        "Show Top N",
        [10, 15, 20, 25, 30],
        index=4,
        key="qual_top_n",
        label_visibility="collapsed",
    )

    # .map() preserves the source dtype when there are no rows to infer from,
    # so on an empty frame these came back str and float64 and "ab_ema & nr_hi"
    # died in Arrow's and_kleene. to_bool_mask always yields a real bool mask.
    ab_ema = (
        to_bool_mask(rank_df["Above 50 EMA"])
        if "Above 50 EMA" in rank_df.columns
        else pd.Series(True, index=rank_df.index, dtype=bool)
    )
    nr_hi = (
        to_bool_mask(rank_df["Near 52W High"])
        if "Near 52W High" in rank_df.columns
        else pd.Series(True, index=rank_df.index, dtype=bool)
    )

    # ── Section 1: Standard / Composite Momentum Qualified (Top 30) ──────────
    qualified_composite = rank_df[ab_ema & nr_hi].sort_values("Rank").head(top_n).copy()

    _render_qualified_section(
        title=f"🏆 Top {top_n} Qualified Momentum Stocks",
        subtitle="Multi-Window Risk-Adjusted Momentum Composite",
        df_subset=qualified_composite,
        adj_close=adj_close,
        key_prefix="qual_composite",
        theme_color="#4f46e5",
    )

    st.divider()

    # ── Section 2: Residual Momentum Qualified (Top 30) ──────────────────────
    if "Residual Rank" in rank_df.columns:
        qualified_residual = (
            rank_df[ab_ema & nr_hi].sort_values("Residual Rank").head(top_n).copy()
        )
    else:
        qualified_residual = pd.DataFrame()

    if not qualified_residual.empty:
        _render_qualified_section(
            title=f"🔬 Top {top_n} Qualified Residual Momentum Stocks",
            subtitle="Idiosyncratic Beta-Stripped Alpha",
            df_subset=qualified_residual,
            adj_close=adj_close,
            key_prefix="qual_residual",
            theme_color="#0284c7",
        )

    render_data_quality_footer(
        total_stocks=len(rank_df),
        gap_count=int((rank_df.get("Data Gap", pd.Series()) == "🔴").sum()),
        short_count=int((rank_df.get("Short History", pd.Series()) == "Yes").sum()),
    )
