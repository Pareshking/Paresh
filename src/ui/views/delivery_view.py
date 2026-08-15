"""
NSE Bhavcopy Delivery & Volume Surge View Controller.
"""

from datetime import datetime
import pandas as pd
import streamlit as st

from src.core.types import SurgeMode
from src.loaders.delivery_loader import compute_delivery_metrics, fetch_delivery_data
from src.ui.components import render_data_quality_footer
from src.ui.theme import render_saas_table


def render_delivery_view(rank_df: pd.DataFrame) -> None:
    """Renders NSE Delivery & Volume Surge institutional accumulation screens."""
    with st.spinner("Fetching NSE Bhavcopy delivery archives…"):
        raw_deliv = fetch_delivery_data()

    if raw_deliv.empty:
        st.error("❌ Unable to load NSE delivery data. Please check network connection.")
        return

    deliv_df = compute_delivery_metrics(raw_deliv)
    if deliv_df.empty:
        st.warning("No delivery metrics available.")
        return

    data_date = deliv_df["Data Date"].iloc[0]

    # Merge metadata
    meta_cols = ["Symbol", "Industry", "Indices", "Rank", "TV_Sector", "TV_Industry"]
    meta = rank_df[[c for c in meta_cols if c in rank_df.columns]].copy()
    merged = deliv_df.merge(meta, left_on="SYMBOL", right_on="Symbol", how="left")
    merged.drop(columns=["Symbol"], errors="ignore", inplace=True)

    # ── Section 1: Dual Surge ────────────────────────────────────────────────
    c_hdr, c_mode = st.columns([2, 1], vertical_alignment="center")
    with c_hdr:
        st.markdown(
            f'<div style="font-family: \'IBM Plex Mono\', monospace; font-size: 0.8rem; color: #475569;">'
            f'Institutional Accumulation (Del & Vol ≥ 1.25×) · Archive: <strong style="color: #4f46e5;">{data_date}</strong>'
            f'</div>',
            unsafe_allow_html=True,
        )

    dual_mode = c_mode.segmented_control(
        "Surge Mode",
        [SurgeMode.DAILY_VS_20D.value, SurgeMode.TREND_20D_VS_PREV.value],
        default=SurgeMode.DAILY_VS_20D.value,
        key="dual_surge_basis",
        label_visibility="collapsed",
    )
    if not dual_mode:
        dual_mode = SurgeMode.DAILY_VS_20D.value

    dual_del_col = "Del_Surge_Daily" if dual_mode == SurgeMode.DAILY_VS_20D.value else "Del_Surge_20D"
    dual_vol_col = "Vol_Surge_Daily" if dual_mode == SurgeMode.DAILY_VS_20D.value else "Vol_Surge_20D"

    if all(c in merged.columns for c in [dual_del_col, dual_vol_col, "Del %"]):
        dual = merged[
            (merged[dual_del_col] >= 1.25)
            & (merged[dual_vol_col] >= 1.25)
            & (merged["Del %"] >= 30)
        ].copy()
        dual = dual.sort_values(dual_del_col, ascending=False).reset_index(drop=True)

        top_del_str = f"{dual[dual_del_col].iloc[0]:.2f}×" if not dual.empty else "—"
        top_vol_str = f"{dual[dual_vol_col].iloc[0]:.2f}×" if not dual.empty else "—"

        kpi_deliv_html = f"""
        <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-bottom: 12px;">
            <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 10px 14px; box-shadow: 0 1px 2px rgba(0,0,0,0.02);">
                <div style="font-family: 'Plus Jakarta Sans', sans-serif; font-size: 0.72rem; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em;">Dual Surge Stocks</div>
                <div style="font-family: 'Outfit', sans-serif; font-size: 1.5rem; font-weight: 800; color: #059669; margin-top: 2px;">{len(dual)}</div>
                <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.70rem; color: #059669; font-weight: 600;">Volume + Delivery > 1.25×</div>
            </div>
            <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 10px 14px; box-shadow: 0 1px 2px rgba(0,0,0,0.02);">
                <div style="font-family: 'Plus Jakarta Sans', sans-serif; font-size: 0.72rem; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em;">Top Delivery Surge</div>
                <div style="font-family: 'Outfit', sans-serif; font-size: 1.5rem; font-weight: 800; color: #0f172a; margin-top: 2px;">{top_del_str}</div>
                <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.70rem; color: #64748b;">Peak Delivery Multiplier</div>
            </div>
            <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 10px 14px; box-shadow: 0 1px 2px rgba(0,0,0,0.02);">
                <div style="font-family: 'Plus Jakarta Sans', sans-serif; font-size: 0.72rem; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em;">Top Volume Surge</div>
                <div style="font-family: 'Outfit', sans-serif; font-size: 1.5rem; font-weight: 800; color: #0f172a; margin-top: 2px;">{top_vol_str}</div>
                <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.70rem; color: #64748b;">Peak Volume Multiplier</div>
            </div>
        </div>
        """
        st.markdown(kpi_deliv_html, unsafe_allow_html=True)

        if not dual.empty:
            d_cols = ["SYMBOL", "CMP", "Day Chg %", "Del %", dual_del_col, dual_vol_col, "Industry", "Market Cap (Cr)", "Rank"]
            active_d = [c for c in d_cols if c in dual.columns]
            render_saas_table(
                dual[active_d],
                key="dual_surge_table",
            )
            st.download_button(
                "⬇️ Export Dual Surge CSV",
                dual[active_d].to_csv(index=False).encode(),
                f"dual_surge_{datetime.now():%Y%m%d}.csv",
                "text/csv",
                key="dl_dual_surge_csv",
            )
        else:
            st.info("No stocks currently satisfy the Dual Surge (>1.25×) criteria.")

    st.divider()

    # ── Section 2: Full Delivery Surge Explorer ──────────────────────────────
    st.markdown("#### 📋 Full Delivery Surge Explorer")

    f1, f2, f3, f4 = st.columns(4)
    surge_mode = f1.selectbox("Surge Mode", [SurgeMode.DAILY_VS_20D.value, SurgeMode.TREND_20D_VS_PREV.value], key="full_del_mode")
    mcap_filter = f2.selectbox("Market Cap Filter", ["All", "Large (>₹20K Cr)", "Mid (₹5K–₹20K Cr)", "Small (₹500–₹5K Cr)", "Micro (<₹500 Cr)"], key="full_del_mcap")
    min_del_pct = f3.slider("Min Delivery %", 20, 80, 40, 5, key="full_del_min_pct")
    min_surge = f4.slider("Min Delivery Surge Ratio", 1.0, 3.0, 1.2, 0.1, key="full_del_min_surge")

    view = merged.copy()

    # Market Cap filtering
    if mcap_filter != "All" and "Market Cap (Cr)" in view.columns:
        if "Large" in mcap_filter:
            view = view[view["Market Cap (Cr)"] >= 20000]
        elif "Mid" in mcap_filter:
            view = view[(view["Market Cap (Cr)"] >= 5000) & (view["Market Cap (Cr)"] < 20000)]
        elif "Small" in mcap_filter:
            view = view[(view["Market Cap (Cr)"] >= 500) & (view["Market Cap (Cr)"] < 5000)]
        elif "Micro" in mcap_filter:
            view = view[view["Market Cap (Cr)"] < 500]

    view = view[view["Del %"] >= min_del_pct]
    s_col = "Del_Surge_Daily" if surge_mode == SurgeMode.DAILY_VS_20D.value else "Del_Surge_20D"
    v_col = "Vol_Surge_Daily" if surge_mode == SurgeMode.DAILY_VS_20D.value else "Vol_Surge_20D"

    view = view[view[s_col] >= min_surge].sort_values(s_col, ascending=False).reset_index(drop=True)

    disp_cols = ["SYMBOL", "CMP", "Day Chg %", "Del %", "Del% 20D Avg", s_col, v_col, "Industry", "Market Cap (Cr)", "Rank"]
    active_disp = [c for c in disp_cols if c in view.columns]
    top_surge_str = f"{view[s_col].iloc[0]:.2f}×" if not view.empty else "—"
    avg_del_str = f"{view['Del %'].mean():.1f}%" if not view.empty else "—"

    kpi_deliv2_html = f"""
    <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-bottom: 12px;">
        <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 10px 14px; box-shadow: 0 1px 2px rgba(0,0,0,0.02);">
            <div style="font-family: 'Plus Jakarta Sans', sans-serif; font-size: 0.72rem; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em;">Stocks Found</div>
            <div style="font-family: 'Outfit', sans-serif; font-size: 1.5rem; font-weight: 800; color: #0f172a; margin-top: 2px;">{len(view)}</div>
            <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.70rem; color: #059669; font-weight: 600;">Passing Delivery Screen</div>
        </div>
        <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 10px 14px; box-shadow: 0 1px 2px rgba(0,0,0,0.02);">
            <div style="font-family: 'Plus Jakarta Sans', sans-serif; font-size: 0.72rem; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em;">Top Surge</div>
            <div style="font-family: 'Outfit', sans-serif; font-size: 1.5rem; font-weight: 800; color: #0f172a; margin-top: 2px;">{top_surge_str}</div>
            <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.70rem; color: #64748b;">Highest Multiplier</div>
        </div>
        <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 10px 14px; box-shadow: 0 1px 2px rgba(0,0,0,0.02);">
            <div style="font-family: 'Plus Jakarta Sans', sans-serif; font-size: 0.72rem; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em;">Avg Delivery %</div>
            <div style="font-family: 'Outfit', sans-serif; font-size: 1.5rem; font-weight: 800; color: #059669; margin-top: 2px;">{avg_del_str}</div>
            <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.70rem; color: #64748b;">Filtered Average</div>
        </div>
    </div>
    """
    st.html(kpi_deliv2_html)

    if not view.empty:
        render_saas_table(view[active_disp], key="full_delivery_table")
        st.download_button(
            "⬇️ Export Delivery Surge CSV",
            view[active_disp].to_csv(index=False).encode(),
            f"delivery_surge_{datetime.now():%Y%m%d}.csv",
            "text/csv",
            key="dl_deliv_full_csv",
        )
    else:
        st.info("No stocks match the selected delivery criteria. Try lowering the thresholds.")

    render_data_quality_footer(
        total_stocks=len(rank_df),
        gap_count=int((rank_df.get("Data Gap", pd.Series()) == "🔴").sum()),
        short_count=int((rank_df.get("Short History", pd.Series()) == "Yes").sum()),
    )
