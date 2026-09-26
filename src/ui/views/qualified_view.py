"""
Qualified Momentum Picks View Controller.
Contains the Top 30 Qualified Composite Momentum section.
"""

import html
import numpy as np
import pandas as pd
import streamlit as st

from src.ui.charts import render_correlation_heatmap
from src.ui.components import gap_count, render_data_quality_footer, to_bool_mask
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
            <div style="font-family: 'Bricolage Grotesque', sans-serif; font-size: 1.15rem; font-weight: 800; color: #0E1726;">
                {title}
            </div>
            <div style="font-family: 'Geist Mono', monospace; font-size: 0.75rem; color: {theme_color}; font-weight: 700; background: #F4F5F8; border: 1px solid #E3E6EB; padding: 3px 8px; border-radius: 6px;">
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
    # These two were hard-coded emerald, so a -15.4% average printed green.
    # Colour that contradicts the number is worse than no colour: the reader
    # takes the colour first.
    avg_3m_clr = "#067647" if avg_3m >= 0 else "#B42318"
    avg_6m_clr = "#067647" if avg_6m >= 0 else "#B42318"
    syms = [s for s in df_subset["Symbol"] if s in adj_close.columns]

    corr_val: float | None = None
    corr_df: pd.DataFrame | None = None
    if len(syms) > 1:
        corr_df = adj_close[syms].iloc[-90:].pct_change(fill_method=None).corr()
        corr_val = float(corr_df.values[np.triu_indices_from(corr_df, k=1)].mean())

    # `corr_val and corr_val < 0.70` is a truthiness test, and 0.0 is falsy: a
    # PERFECTLY uncorrelated book fell through to "High Correlation". A book of
    # one name, where corr_val is None, did the same -- labelling an unknown as
    # a bad state beside a "—". Test for None explicitly and compare numbers as
    # numbers.
    if corr_val is None:
        corr_status, corr_clr = "Not measurable", "#5E6878"
    elif corr_val < 0.70:
        corr_status, corr_clr = "Diversified", "#067647"
    else:
        corr_status, corr_clr = "High Correlation", "#B54708"
    corr_str = f"{corr_val:.2f}" if corr_val is not None else "—"

    kpi_html = f"""
    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 12px; margin-bottom: 12px;">
        <div style="background: #ffffff; border: 1px solid #E3E6EB; border-radius: 10px; padding: 10px 14px; box-shadow: 0 1px 2px rgba(0,0,0,0.02); border-top: 3px solid {theme_color};">
            <div style="font-family: 'Geist', sans-serif; font-size: 0.72rem; font-weight: 700; color: #5E6878; text-transform: uppercase; letter-spacing: 0.05em;">Qualified Count</div>
            <div style="font-family: 'Bricolage Grotesque', sans-serif; font-size: 1.5rem; font-weight: 800; color: #0E1726; margin-top: 2px;">{len(df_subset)}</div>
            <div style="font-family: 'Geist Mono', monospace; font-size: 0.70rem; color: #067647; font-weight: 600;">Top Selection</div>
        </div>
        <div style="background: #ffffff; border: 1px solid #E3E6EB; border-radius: 10px; padding: 10px 14px; box-shadow: 0 1px 2px rgba(0,0,0,0.02);">
            <div style="font-family: 'Geist', sans-serif; font-size: 0.72rem; font-weight: 700; color: #5E6878; text-transform: uppercase; letter-spacing: 0.05em;">Avg 3M Return</div>
            <div style="font-family: 'Bricolage Grotesque', sans-serif; font-size: 1.5rem; font-weight: 800; color: {avg_3m_clr}; margin-top: 2px;">{"—" if pd.isna(avg_3m) else f"{avg_3m:+.1%}"}</div>
            <div style="font-family: 'Geist Mono', monospace; font-size: 0.70rem; color: #5E6878;">Calendar 3 months</div>
        </div>
        <div style="background: #ffffff; border: 1px solid #E3E6EB; border-radius: 10px; padding: 10px 14px; box-shadow: 0 1px 2px rgba(0,0,0,0.02);">
            <div style="font-family: 'Geist', sans-serif; font-size: 0.72rem; font-weight: 700; color: #5E6878; text-transform: uppercase; letter-spacing: 0.05em;">Avg 6M Return</div>
            <div style="font-family: 'Bricolage Grotesque', sans-serif; font-size: 1.5rem; font-weight: 800; color: {avg_6m_clr}; margin-top: 2px;">{"—" if pd.isna(avg_6m) else f"{avg_6m:+.1%}"}</div>
            <div style="font-family: 'Geist Mono', monospace; font-size: 0.70rem; color: #5E6878;">Calendar 6 months</div>
        </div>
        <div style="background: #ffffff; border: 1px solid #E3E6EB; border-radius: 10px; padding: 10px 14px; box-shadow: 0 1px 2px rgba(0,0,0,0.02);">
            <div style="font-family: 'Geist', sans-serif; font-size: 0.72rem; font-weight: 700; color: #5E6878; text-transform: uppercase; letter-spacing: 0.05em;">Avg 90D Correlation</div>
            <div style="font-family: 'Bricolage Grotesque', sans-serif; font-size: 1.5rem; font-weight: 800; color: #0E1726; margin-top: 2px;">{corr_str}</div>
            <div style="font-family: 'Geist Mono', monospace; font-size: 0.70rem; color: {corr_clr}; font-weight: 600;">{corr_status}</div>
        </div>
    </div>
    """
    st.markdown(kpi_html, unsafe_allow_html=True)

    render_master_screener_table(
        df_subset, prices_df=adj_close
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
                    <div style="display: flex; justify-content: space-between; font-size: 0.76rem; font-family: 'Geist', sans-serif; margin-bottom: 3px;">
                        <span style="font-weight: 600; color: #0E1726;">{html.escape(str(r['Industry']))}</span>
                        <span style="font-family: 'Geist Mono', monospace; color: #3C4657; font-weight: 700;">{int(r['Count'])} stock{'s' if r['Count']>1 else ''} ({r['Pct']:.0f}%)</span>
                    </div>
                    <div style="width: 100%; height: 6px; background-color: #F1F3F6; border-radius: 99px; overflow: hidden;">
                        <div style="width: {r['Pct']}%; height: 100%; background: linear-gradient(90deg, {theme_color}, #06b6d4); border-radius: 99px;"></div>
                    </div>
                </div>
                """)
        breakdown_html = f"""
        <div style="background-color: #ffffff; border: 1px solid #E3E6EB; border-radius: 10px; padding: 14px 16px; box-shadow: 0 1px 2px rgba(0,0,0,0.02);">
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
            render_correlation_heatmap(corr_df, syms, n_disp)
        else:
            st.info("Insufficient stock history to construct correlation matrix.")


def render_qualified_view(rank_df: pd.DataFrame, adj_close: pd.DataFrame) -> None:
    """Renders the Top 30 Qualified Stocks by Composite Multi-Window Momentum."""
    c_filt, c_ctrl = st.columns([3, 1], vertical_alignment="center")
    with c_filt:
        st.markdown(
            "<div style=\"font-family: 'Geist', sans-serif; font-size: 0.85rem; color: #3C4657; padding-top: 4px;\">"
            'Institutional Strict Filter: <strong style="color: #067647;">Price > 50 EMA</strong> &nbsp;·&nbsp; <strong style="color: #4f46e5;">Within 20% of 52W High</strong>'
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


    render_data_quality_footer(
        total_stocks=len(rank_df),
        gap_count=gap_count(rank_df),
        short_count=int((rank_df.get("Short History", pd.Series()) == "Yes").sum()),
    )
