"""
Configuration & System Settings View Controller.
Windows 11-style left-nav + right-content layout.
"""

import html
import os
from datetime import datetime

import pandas as pd
import streamlit as st

from src.core.config import (
    DATA_DIR,
    INDICES_LOCAL,
    INDICES_URLS,
    MCAPS_FILE,
    PRICES_FILE,
    STORAGE_MODE,
    TV_CLASSIFICATION_FILE,
)
from src.engine.corporate_actions import load_events
from src.loaders.indices_loader import get_sync_metadata, sync_official_nse_indices
from src.ui.components import render_data_quality_footer
from src.ui.theme import render_saas_table

_NAV_SECTIONS = [
    "Data & Sync",
    "Momentum Signal",
    "Portfolio Risk",
    "Data Health",
]

_NAV_ICONS = {
    "Data & Sync": "🔄",
    "Momentum Signal": "📐",
    "Portfolio Risk": "🛡️",
    "Data Health": "🏥",
}

_NAV_DESCRIPTIONS = {
    "Data & Sync": "Constituent universe & cache",
    "Momentum Signal": "Lookback window weights",
    "Portfolio Risk": "Concentration & volatility",
    "Data Health": "Corporate actions & paths",
}


def _section_data_sync(sync_meta: dict, tot_stk: int, engine_stocks: int) -> None:
    last_sync = sync_meta.get("last_synced") or "Never synced"
    sync_ok = sync_meta.get("last_attempt_ok")
    last_attempt = sync_meta.get("last_attempt")
    attempt_fetched = sync_meta.get("last_attempt_fetched")
    attempt_errors = sync_meta.get("last_attempt_errors") or {}

    st.markdown(
        "<div style='font-size:0.83rem;font-weight:700;color:#0f172a;margin-bottom:2px;'>"
        "Official NSE Constituent Synchronization</div>"
        "<div style='font-size:0.74rem;color:#64748b;margin-bottom:12px;'>"
        "Synchronize constituent baskets directly with official CSV feeds on "
        "<code>niftyindices.com</code>.</div>",
        unsafe_allow_html=True,
    )

    failed_attempt_html = ""
    if sync_ok is False:
        failed_attempt_html = (
            '<div style="font-size:0.74rem;color:#d97706;margin-top:6px;font-weight:600;">'
            f"⚠️ Last attempt {html.escape(str(last_attempt or 'unknown'))} "
            f"fetched {attempt_fetched if attempt_fetched is not None else '?'} index "
            f"file(s), {len(attempt_errors)} failed — figures above are from "
            "the last complete sync.</div>"
        )

    status_c, btn_c = st.columns([2.2, 1], vertical_alignment="center")
    with status_c:
        st.html(
            f"""
            <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:12px 16px;">
                <div style="font-size:0.84rem;font-weight:700;color:#0f172a;">
                    NSE Constituents Cache
                </div>
                <div style="font-family:'JetBrains Mono',monospace;font-size:0.76rem;color:#64748b;margin-top:4px;">
                    Last Synced: <strong style="color:#0f172a;">{last_sync}</strong>
                    &nbsp;·&nbsp;
                    Universe: <strong style="color:#4f46e5;">{tot_stk} stocks</strong>
                    &nbsp;·&nbsp;
                    Active in engine: <strong style="color:#166534;">{engine_stocks}</strong>
                </div>
                {failed_attempt_html}
            </div>
            """
        )
    with btn_c:
        bc1, bc2 = st.columns(2)
        with bc1:
            if st.button("Sync", type="primary", key="btn_sync_indices", use_container_width=True):
                with st.status("Syncing NSE constituents…", expanded=True) as _sync_status:
                    _sync_status.write("📡 Downloading index CSV files from niftyindices.com…")
                    res = sync_official_nse_indices(force=True)
                    st.session_state["force_refresh"] = True
                    st.session_state.pop("data_loaded_key", None)
                    st.cache_data.clear()
                    if res.get("last_attempt_ok"):
                        n = res["total_stocks"]
                        _sync_status.update(
                            label=f"Synced {n} constituents successfully",
                            state="complete",
                            expanded=False,
                        )
                    else:
                        fetched = res.get("last_attempt_fetched", 0)
                        errors = len(res.get("last_attempt_errors") or {})
                        _sync_status.update(
                            label=f"Sync incomplete — {fetched} downloaded, {errors} failed",
                            state="error",
                            expanded=False,
                        )
                    st.rerun()
        with bc2:
            if st.button("Purge", type="secondary", key="btn_purge_cache", use_container_width=True):
                st.session_state["force_refresh"] = True
                st.session_state.pop("data_loaded_key", None)
                st.cache_data.clear()
                st.rerun()

    with st.expander("📁 Local Index Files", expanded=False):
        for idx_name, path in INDICES_LOCAL.items():
            if os.path.exists(path):
                size = os.path.getsize(path)
                mtime = datetime.fromtimestamp(os.path.getmtime(path)).strftime(
                    "%d %b %Y, %H:%M"
                )
                with open(path, "r", encoding="utf-8") as f:
                    lines = sum(1 for _ in f) - 1
                st.caption(
                    f"**{idx_name}**: `{lines}` constituents ({size/1024:.1f} KB) · {mtime}"
                )
            else:
                st.caption(f"**{idx_name}**: File missing at `{path}`")

    st.divider()

    st.markdown(
        "<div style='font-size:0.83rem;font-weight:700;color:#0f172a;margin-bottom:2px;'>"
        "Active Screening Universe</div>"
        "<div style='font-size:0.74rem;color:#64748b;margin-bottom:10px;'>"
        "Select which index constituent baskets are merged into the screening pipeline.</div>",
        unsafe_allow_html=True,
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


def _section_momentum_signal() -> None:
    raw_w = [float(st.session_state.get(f"cfg_w{i}", 0.2)) for i in range(1, 6)]
    tot_w = sum(raw_w)
    norm_w = [w / tot_w for w in raw_w] if tot_w > 0 else [0.2] * 5

    st.markdown(
        "<div style='font-size:0.83rem;font-weight:700;color:#0f172a;margin-bottom:2px;'>"
        "Momentum Lookback Multi-Window Weights</div>"
        "<div style='font-size:0.74rem;color:#64748b;margin-bottom:10px;'>"
        "Relative weights across 5 calendar-month windows. Sliders auto-normalize to 100%.</div>",
        unsafe_allow_html=True,
    )

    st.html(
        f"""
        <div style="font-family:'JetBrains Mono',monospace;font-size:0.80rem;font-weight:700;
                    color:#4f46e5;background:#eef2ff;border:1px solid #c7d2fe;
                    padding:6px 14px;border-radius:6px;display:inline-block;margin-bottom:12px;">
            Weight vector: {norm_w[0]:.0%} · {norm_w[1]:.0%} · {norm_w[2]:.0%} · {norm_w[3]:.0%} · {norm_w[4]:.0%}
        </div>
        """
    )

    wc = st.columns(5)
    windows = [
        ("1M", "cfg_w1", 0.10),
        ("3M", "cfg_w2", 0.30),
        ("6M", "cfg_w3", 0.30),
        ("9M", "cfg_w4", 0.20),
        ("12M", "cfg_w5", 0.10),
    ]
    for col, (label, key, _default) in zip(wc, windows):
        col.slider(label, min_value=0.0, max_value=1.0, step=0.05, key=key)

    lbl_col, pop_col = st.columns([4, 1], vertical_alignment="center")
    lbl_col.caption(
        "Weights normalize automatically. The 12M window excludes the most recent month "
        "(skip-month convention) to avoid short-term reversal contamination."
    )
    with pop_col.popover("ℹ️ Window guide", use_container_width=True):
        st.markdown(
            """
**Lookback Windows**

| Window | Trading days | What it captures |
|---|---|---|
| **1M** | 21 | Short momentum / mean reversion boundary |
| **3M** | 63 | Primary trend formation |
| **6M** | 126 | Intermediate momentum |
| **9M** | 189 | Extended trend persistence |
| **12M** | 252 | Long-cycle momentum (skip-month applied) |

Higher weight on **3M + 6M** favours fast breakouts.
Higher weight on **9M + 12M** favours slow, persistent trends.

*All windows skip the most recent month to reduce reversal noise.*
"""
        )


def _section_portfolio_risk() -> None:
    lc, rc = st.columns(2, gap="large")
    with lc:
        st.markdown(
            "<div style='font-size:0.83rem;font-weight:700;color:#0f172a;margin-bottom:2px;'>"
            "Concentration Limits</div>"
            "<div style='font-size:0.74rem;color:#64748b;margin-bottom:10px;'>"
            "Maximum capital allocation per sector and per individual holding.</div>",
            unsafe_allow_html=True,
        )
        new_sc = st.slider(
            "Sector Exposure Cap (%)", min_value=15, max_value=50, step=5, key="cfg_sc",
        )
        new_stc = st.slider(
            "Individual Stock Cap (%)", min_value=2, max_value=15, step=1, key="cfg_stc",
        )
        if new_stc > new_sc:
            st.warning(f"Stock cap ({new_stc}%) exceeds sector cap ({new_sc}%).")

    with rc:
        st.markdown(
            "<div style='font-size:0.83rem;font-weight:700;color:#0f172a;margin-bottom:2px;'>"
            "Volatility Targeting</div>"
            "<div style='font-size:0.74rem;color:#64748b;margin-bottom:10px;'>"
            "Dynamically scales cash allocation to maintain stable realized annual volatility.</div>",
            unsafe_allow_html=True,
        )
        new_vt = st.checkbox("Enable Dynamic Volatility Targeting", key="cfg_vt")
        st.slider(
            "Target Portfolio Volatility (%)", min_value=10, max_value=40, step=5,
            key="cfg_vtv", disabled=not new_vt,
        )


def _section_data_health(rank_df: pd.DataFrame) -> None:
    st.markdown(
        "<div style='font-size:0.83rem;font-weight:700;color:#0f172a;margin-bottom:2px;'>"
        "Corporate Actions Detected in Price History</div>",
        unsafe_allow_html=True,
    )

    _events = load_events()
    if not _events:
        st.success(
            "No corporate actions flagged. Every session in the price history "
            "moves within a plausible range."
        )
    else:
        _split = sum(1 for e in _events if e.get("kind") == "split/bonus")
        _other = len(_events) - _split
        st.info(
            f"**{len(_events)} sessions flagged** — {_split} valid split/bonus, "
            f"{_other} unmatched (probable demergers). Circuit-limit breaches "
            "treated as corporate actions; neutralised in backtest by rescaling "
            "history in memory — no stored-price edits, so provider restatements "
            "aren't double-applied."
        )
        _rows = []
        for e in sorted(_events, key=lambda x: x.get("date", ""), reverse=True):
            _move = e.get("move")
            _rows.append(
                {
                    "Date": e.get("date", "—"),
                    "Symbol": e.get("symbol", "—"),
                    "Move": f"{_move * 100:+.1f}%" if _move is not None else "—",
                    "Ratio": f"{e.get('ratio', float('nan')):.4f}",
                    "Looks Like": e.get("looks_like", "—"),
                    "Kind": (
                        "🔀 Split / bonus"
                        if e.get("kind") == "split/bonus"
                        else "❓ Possible demerger"
                    ),
                }
            )
        render_saas_table(pd.DataFrame(_rows), key="cfg_corporate_actions")
        st.caption(
            "A **split or bonus** should have been adjusted away by the data provider and was not — "
            "re-fetching fixes it. A **possible demerger** matches no standard ratio; providers "
            "generally don't adjust for these because the parent's price genuinely falls while "
            "shareholders receive stock in the new entity."
        )

    st.divider()

    st.markdown(
        "<div style='font-size:0.83rem;font-weight:700;color:#0f172a;margin-bottom:8px;'>"
        "Cache & Data Paths</div>",
        unsafe_allow_html=True,
    )
    cache_data = [
        ("Price History", PRICES_FILE),
        ("Market Caps", MCAPS_FILE),
        ("TV Classification", TV_CLASSIFICATION_FILE),
    ]
    cache_rows = []
    for label, path in cache_data:
        exists = os.path.exists(path)
        size_mb = os.path.getsize(path) / (1024 * 1024) if exists else 0
        cache_rows.append(
            {
                "Dataset": label,
                "Status": "🟢 Present" if exists else "🔴 Missing",
                "Size": f"{size_mb:.1f} MB" if exists else "—",
                "Path": path,
            }
        )
    st.dataframe(pd.DataFrame(cache_rows), hide_index=True, use_container_width=True)

    render_data_quality_footer(
        total_stocks=len(rank_df),
        gap_count=int((rank_df.get("Data Gap", pd.Series()) == "🔴").sum()),
        short_count=int((rank_df.get("Short History", pd.Series()) == "Yes").sum()),
    )


def render_config_view(rank_df: pd.DataFrame) -> None:
    """Renders system configuration with Windows 11-style left-nav layout."""
    sync_meta = get_sync_metadata()
    synced_stocks = sync_meta.get("total_stocks") or 0
    tot_stk = synced_stocks or len(rank_df)
    engine_stocks = len(rank_df)
    mode_label = (
        "Streamlit Cloud" if STORAGE_MODE == "streamlit-cloud" else "Local Production"
    )

    # ── Status bar (full-width) ───────────────────────────────────────────────
    st.html(
        f"""
        <div style="background:#ffffff;border:1px solid #e2e8f0;border-radius:10px;
                    padding:14px 20px;margin-bottom:20px;
                    display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px;">
            <div>
                <div style="font-family:'Outfit',sans-serif;font-size:1.10rem;font-weight:800;color:#0f172a;">
                    ⚙️ System Configuration
                </div>
                <div style="font-size:0.76rem;color:#64748b;margin-top:2px;">
                    Constituent sync · momentum weights · portfolio risk · data health
                </div>
            </div>
            <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;">
                <span style="font-family:'JetBrains Mono',monospace;font-size:0.74rem;
                             background:#f0fdf4;border:1px solid #86efac;color:#166534;
                             padding:4px 10px;border-radius:6px;font-weight:700;">
                    🟢 Engine Active ({engine_stocks} Stocks)
                </span>
                <span style="font-family:'JetBrains Mono',monospace;font-size:0.74rem;
                             background:#eef2ff;border:1px solid #c7d2fe;color:#4338ca;
                             padding:4px 10px;border-radius:6px;font-weight:700;">
                    {mode_label}
                </span>
            </div>
        </div>
        """
    )

    # ── Left nav + right content ──────────────────────────────────────────────
    nav_col, content_col = st.columns([1, 3.2], gap="large")

    with nav_col:
        st.markdown(
            "<div style='font-size:0.68rem;font-weight:700;color:#94a3b8;"
            "text-transform:uppercase;letter-spacing:0.08em;margin-bottom:8px;'>"
            "Settings</div>",
            unsafe_allow_html=True,
        )
        section = st.radio(
            "Settings",
            _NAV_SECTIONS,
            key="cfg_nav_section",
            label_visibility="collapsed",
            format_func=lambda s: f"{_NAV_ICONS[s]} {s}",
        )
        if not section:
            section = _NAV_SECTIONS[0]

        st.markdown(
            "<div style='font-size:0.68rem;color:#94a3b8;margin-top:16px;line-height:1.5;'>"
            + _NAV_DESCRIPTIONS.get(section, "") + "</div>",
            unsafe_allow_html=True,
        )

    with content_col:
        if section == "Data & Sync":
            _section_data_sync(sync_meta, tot_stk, engine_stocks)
        elif section == "Momentum Signal":
            _section_momentum_signal()
        elif section == "Portfolio Risk":
            _section_portfolio_risk()
        elif section == "Data Health":
            _section_data_health(rank_df)
