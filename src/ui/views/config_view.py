"""
Configuration & System Settings View Controller.
Institutional-grade modern configuration terminal with Pure Paper White design.
"""

import os
from datetime import datetime

import pandas as pd
import streamlit as st

from src.core.config import (
    DATA_DIR,
    DELIVERY_FILE,
    INDICES_LOCAL,
    INDICES_URLS,
    MCAPS_FILE,
    PRICES_FILE,
    STORAGE_MODE,
    TV_CLASSIFICATION_FILE,
)
from src.loaders.delivery_loader import _read_meta
from src.loaders.indices_loader import get_sync_metadata, sync_official_nse_indices
from src.ui.components import render_data_quality_footer


def render_config_view(rank_df: pd.DataFrame) -> None:
    """Renders high-density institutional system configuration and quantitative parameters."""
    sync_meta = get_sync_metadata()
    last_sync = sync_meta.get("last_synced", "Never synced")
    tot_stk = sync_meta.get("total_stocks", len(rank_df))
    mode_label = (
        "Streamlit Cloud" if STORAGE_MODE == "streamlit-cloud" else "Local Production"
    )

    # ── Top Hero / System Status Bar ─────────────────────────────────────────
    st.markdown(
        f"""
        <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 16px 20px; margin-bottom: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.02);">
            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px;">
                <div>
                    <div style="font-family: 'Outfit', sans-serif; font-size: 1.25rem; font-weight: 800; color: #0f172a; display: flex; align-items: center; gap: 8px;">
                        ⚙️ System Configuration & Quantitative Parameters
                    </div>
                    <div style="font-family: 'Plus Jakarta Sans', sans-serif; font-size: 0.80rem; color: #64748b; margin-top: 3px;">
                        Manage constituent synchronization, momentum factor weights, portfolio risk constraints, and parquet storage caches.
                    </div>
                </div>
                <div style="display: flex; align-items: center; gap: 10px;">
                    <span style="font-family: 'JetBrains Mono', monospace; font-size: 0.75rem; background: #f0fdf4; border: 1px solid #86efac; color: #166534; padding: 4px 10px; border-radius: 6px; font-weight: 700;">
                        🟢 Engine Active ({tot_stk} Stocks)
                    </span>
                    <span style="font-family: 'JetBrains Mono', monospace; font-size: 0.75rem; background: #eef2ff; border: 1px solid #c7d2fe; color: #4338ca; padding: 4px 10px; border-radius: 6px; font-weight: 700;">
                        {mode_label}
                    </span>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Section 1: Data Synchronization & Constituents ───────────────────────
    st.markdown("##### 1. Official NSE Constituent Synchronization")
    st.caption(
        "Synchronize constituent baskets directly with official CSV feeds on `niftyindices.com`."
    )

    sync_c1, sync_c2 = st.columns([1.8, 1.2], vertical_alignment="center")
    with sync_c1:
        st.html(f"""
            <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 14px 16px; box-shadow: 0 1px 2px rgba(0,0,0,0.02);">
                <div style="font-size: 0.84rem; font-weight: 700; color: #0f172a;">Official NSE Constituents Cache</div>
                <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.76rem; color: #64748b; margin-top: 4px;">
                    Last Synced: <strong style="color: #0f172a;">{last_sync}</strong> &nbsp;·&nbsp; Total Universe: <strong style="color: #4f46e5;">{tot_stk} stocks</strong>
                </div>
            </div>
            """)
    with sync_c2:
        btn_c1, btn_c2 = st.columns(2)
        with btn_c1:
            if st.button(
                "Sync NSE CSVs", type="primary", width="stretch", key="btn_sync_indices"
            ):
                with st.spinner(
                    "Downloading official index CSVs from niftyindices.com…"
                ):
                    res = sync_official_nse_indices(force=True)
                    st.session_state["force_refresh"] = True
                    st.session_state.pop("data_loaded_key", None)
                    st.cache_data.clear()
                    st.success(f"Synced {res['total_stocks']} constituents!")
                    st.rerun()
        with btn_c2:
            if st.button(
                "Purge Cache",
                type="secondary",
                width="stretch",
                key="btn_force_sync_top",
            ):
                st.session_state["force_refresh"] = True
                st.session_state.pop("data_loaded_key", None)
                st.cache_data.clear()
                st.rerun()

    with st.expander("📁 Inspect Local Index Files on Disk", expanded=False):
        for idx_name, path in INDICES_LOCAL.items():
            if os.path.exists(path):
                size = os.path.getsize(path)
                mtime = datetime.fromtimestamp(os.path.getmtime(path)).strftime(
                    "%d %b %Y, %H:%M"
                )
                with open(path, "r", encoding="utf-8") as f:
                    lines = sum(1 for _ in f) - 1
                st.caption(
                    f"**{idx_name}**: `{lines}` constituents ({size/1024:.1f} KB) · Modified: {mtime}"
                )
            else:
                st.caption(f"**{idx_name}**: File missing at `{path}`")

    st.divider()

    # ── Section 2: Active Index Universe ─────────────────────────────────────
    st.markdown("##### 2. Active Screening Universe")
    st.caption(
        "Select which index constituent baskets are merged into the real-time screening pipeline."
    )

    available_indices = list(INDICES_URLS.keys())
    curr_indices = st.session_state.get("cfg_indices", ["NIFTY TOTAL MARKET"])
    new_indices = st.multiselect(
        "Target Index Universe",
        available_indices,
        default=curr_indices,
        key="cfg_indices_multiselect",
        label_visibility="collapsed",
    )
    if new_indices != curr_indices:
        st.session_state["cfg_indices"] = new_indices
        st.session_state.pop("data_loaded_key", None)
        st.rerun()

    st.divider()

    # ── Section 3: Momentum Lookback Weights ─────────────────────────────────
    raw_w = [float(st.session_state.get(f"cfg_w{i}", 0.2)) for i in range(1, 6)]
    tot_w = sum(raw_w)
    norm_w = [w / tot_w for w in raw_w] if tot_w > 0 else [0.2] * 5

    st.markdown(
        f"""
        <div style="display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 4px;">
            <div>
                <span style="font-family: 'Outfit', sans-serif; font-size: 1.05rem; font-weight: 800; color: #0f172a;">
                    3. Momentum Lookback Multi-Window Weights
                </span>
                <div style="font-size: 0.76rem; color: #64748b; margin-top: 2px;">
                    Relative weights across 5 rolling windows for System 1 (Sharpe Composite). Sliders automatically normalize.
                </div>
            </div>
            <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.78rem; font-weight: 700; color: #4f46e5; background: #eef2ff; border: 1px solid #c7d2fe; padding: 4px 10px; border-radius: 6px;">
                Vector: {norm_w[0]:.0%} · {norm_w[1]:.0%} · {norm_w[2]:.0%} · {norm_w[3]:.0%} · {norm_w[4]:.0%}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    wc = st.columns(5)
    windows = [
        ("1M (21D)", "cfg_w1", 0.10),
        ("3M (63D)", "cfg_w2", 0.30),
        ("6M (126D)", "cfg_w3", 0.30),
        ("9M (189D)", "cfg_w4", 0.20),
        ("12M (252D)", "cfg_w5", 0.10),
    ]
    for col, (label, key, default) in zip(wc, windows):
        val = col.slider(
            label,
            0.0,
            1.0,
            float(st.session_state.get(key, default)),
            0.05,
            key=f"slider_{key}",
        )
        if val != st.session_state.get(key, default):
            st.session_state[key] = val

    st.divider()

    # ── Section 4: Portfolio Allocation & Risk Constraints ───────────────────
    st.markdown("##### 4. Portfolio Allocation & Risk Constraints")
    st.caption(
        "Configure single-sector exposure limits, individual stock position caps, and dynamic volatility targeting."
    )

    p_card1, p_card2 = st.columns(2, gap="medium")
    with p_card1:
        st.markdown(
            """
            <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 14px 16px; margin-bottom: 8px;">
                <div style="font-size: 0.85rem; font-weight: 700; color: #0f172a; margin-bottom: 4px;">Concentration Limits</div>
                <div style="font-size: 0.74rem; color: #64748b;">Sets maximum capital allocation for single sectors and individual stock holdings.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        new_sc = st.slider(
            "Sector Exposure Cap (%)",
            15,
            50,
            int(st.session_state.get("cfg_sc", 30)),
            5,
            key="slider_sc",
        )
        new_stc = st.slider(
            "Individual Stock Cap (%)",
            2,
            15,
            int(st.session_state.get("cfg_stc", 8)),
            1,
            key="slider_stc",
        )
        if new_sc != st.session_state.get("cfg_sc"):
            st.session_state["cfg_sc"] = new_sc
        if new_stc != st.session_state.get("cfg_stc"):
            st.session_state["cfg_stc"] = new_stc

        if new_stc > new_sc:
            st.warning(f"Stock cap ({new_stc}%) cannot exceed sector cap ({new_sc}%).")

    with p_card2:
        st.markdown(
            """
            <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 14px 16px; margin-bottom: 8px;">
                <div style="font-size: 0.85rem; font-weight: 700; color: #0f172a; margin-bottom: 4px;">Volatility Targeting & Risk Engine</div>
                <div style="font-size: 0.74rem; color: #64748b;">Dynamically scales cash allocation to maintain stable realized annual portfolio volatility.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        new_vt = st.checkbox(
            "Enable Dynamic Volatility Targeting",
            value=st.session_state.get("cfg_vt", False),
            key="check_vt",
        )
        new_vtv = st.slider(
            "Target Portfolio Volatility (%)",
            10,
            40,
            int(st.session_state.get("cfg_vtv", 25)),
            5,
            key="slider_vtv",
            disabled=not new_vt,
        )
        if new_vt != st.session_state.get("cfg_vt"):
            st.session_state["cfg_vt"] = new_vt
        if new_vtv != st.session_state.get("cfg_vtv"):
            st.session_state["cfg_vtv"] = new_vtv

    st.divider()

    # ── Section 5: Cache Storage Diagnostics ────────────────────────────────
    st.markdown("##### 5. Disk Storage & Parquet Diagnostics")
    st.caption(f"Environment: **{mode_label}** · Storage Path: `{DATA_DIR}`")

    cache_records = []
    for label, path in [
        ("Price History Parquet", PRICES_FILE),
        ("Market Cap Parquet", MCAPS_FILE),
        ("Delivery Bhavcopy Parquet", DELIVERY_FILE),
        ("TradingView Classification CSV", TV_CLASSIFICATION_FILE),
    ]:
        if os.path.exists(path):
            size = os.path.getsize(path)
            sz = (
                f"{size/(1024*1024):.1f} MB"
                if size >= 1024 * 1024
                else f"{size/1024:.0f} KB"
            )
            mod = datetime.fromtimestamp(os.path.getmtime(path)).strftime(
                "%d %b %Y, %H:%M"
            )
            extra = ""
            if label == "Delivery Bhavcopy Parquet":
                meta = _read_meta()
                if meta:
                    extra = f"{meta.get('n_days', '?')} days / {meta.get('n_symbols', '?')} tickers"
            cache_records.append(
                {
                    "Dataset": label,
                    "File Size": sz,
                    "Records / Detail": extra or "Active",
                    "Last Modified": mod,
                    "Status": "🟢 Cached",
                }
            )
        else:
            cache_records.append(
                {
                    "Dataset": label,
                    "File Size": "—",
                    "Records / Detail": "Missing",
                    "Last Modified": "—",
                    "Status": "⚪ Not Cached",
                }
            )

    cache_df = pd.DataFrame(cache_records)
    st.dataframe(
        cache_df,
        width="stretch",
        hide_index=True,
    )

    render_data_quality_footer(
        total_stocks=len(rank_df),
        gap_count=int((rank_df.get("Data Gap", pd.Series()) == "🔴").sum()),
        short_count=int((rank_df.get("Short History", pd.Series()) == "Yes").sum()),
    )
