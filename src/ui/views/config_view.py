"""
Configuration & System Settings View Controller.
Institutional-grade modern configuration terminal with Pure Paper White design.
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


def render_config_view(rank_df: pd.DataFrame) -> None:
    """Renders high-density institutional system configuration and quantitative parameters."""
    sync_meta = get_sync_metadata()
    last_sync = sync_meta.get("last_synced") or "Never synced"
    # ``.get(key, default)`` does not help here, and that was the bug: a failed
    # sync RECORDS zero, so the key is present, the default never fires, and
    # the tab printed a green "Engine Active (0 Stocks)" while the engine was
    # ranking 750 of them. ``or`` falls through on the zero as well as on the
    # absence.
    synced_stocks = sync_meta.get("total_stocks") or 0
    tot_stk = synced_stocks or len(rank_df)
    # How many stocks the engine is ACTUALLY working with, which is the only
    # honest thing to put next to the word "Active". It comes from the ranking
    # in hand, not from a note the sync job left behind.
    engine_stocks = len(rank_df)
    sync_ok = sync_meta.get("last_attempt_ok")
    last_attempt = sync_meta.get("last_attempt")
    attempt_fetched = sync_meta.get("last_attempt_fetched")
    attempt_errors = sync_meta.get("last_attempt_errors") or {}
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
                        🟢 Engine Active ({engine_stocks} Stocks)
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

    # A failed run is now visible instead of hiding behind the previous run's
    # date. Silence here is what let a total sync failure read as a success.
    failed_attempt_html = ""
    if sync_ok is False:
        failed_attempt_html = (
            '<div style="font-family: \'JetBrains Mono\', monospace; font-size: 0.74rem; '
            'color: #d97706; margin-top: 6px; font-weight: 600;">'
            f"&#9888;&#65039; Last attempt {html.escape(str(last_attempt or 'unknown'))} "
            f"fetched {attempt_fetched if attempt_fetched is not None else '?'} index "
            f"file(s), {len(attempt_errors)} failed &mdash; the figures above are from "
            "the last complete sync.</div>"
        )

    sync_c1, sync_c2 = st.columns([1.8, 1.2], vertical_alignment="center")
    with sync_c1:
        st.html(f"""
            <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 14px 16px; box-shadow: 0 1px 2px rgba(0,0,0,0.02);">
                <div style="font-size: 0.84rem; font-weight: 700; color: #0f172a;">Official NSE Constituents Cache</div>
                <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.76rem; color: #64748b; margin-top: 4px;">
                    Last Synced: <strong style="color: #0f172a;">{last_sync}</strong> &nbsp;·&nbsp; Total Universe: <strong style="color: #4f46e5;">{tot_stk} stocks</strong>
                </div>
                {failed_attempt_html}
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
                    if res.get("last_attempt_ok"):
                        st.success(f"Synced {res['total_stocks']} constituents!")
                    else:
                        # "Synced 0 constituents!" in a green success toast is
                        # how fifteen consecutive failed downloads got reported
                        # as an achievement.
                        st.error(
                            f"Sync incomplete: {res.get('last_attempt_fetched', 0)} "
                            f"index file(s) downloaded, "
                            f"{len(res.get('last_attempt_errors') or {})} failed. "
                            "The previous constituents are still in use."
                        )
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
                    Relative weights across 5 calendar-month windows for System 1. Sliders automatically normalize.
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
        ("1M", "cfg_w1", 0.10),
        ("3M", "cfg_w2", 0.30),
        ("6M", "cfg_w3", 0.30),
        ("9M", "cfg_w4", 0.20),
        ("12M", "cfg_w5", 0.10),
    ]
    # Bind each widget DIRECTLY to the canonical session-state key.
    #
    # These sliders used to write to "slider_cfg_wN" and copy the value into
    # "cfg_wN" afterwards. app.py reads cfg_w1..cfg_w5 at the TOP of the script,
    # which has already run by the time this tab body executes, so the copy
    # landed one rerun too late: moving a weight slider re-ranked nothing, and
    # the change only appeared after some unrelated later interaction. The
    # index multiselect above avoided this by calling st.rerun(); the weights
    # never did.
    #
    # With key=<canonical key>, Streamlit writes the new value into session
    # state BEFORE the rerun, so the top-of-script read sees it on the same
    # pass. No st.rerun() needed, and no double computation.
    for col, (label, key, default) in zip(wc, windows):
        col.slider(label, min_value=0.0, max_value=1.0, step=0.05, key=key)

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
        # Same one-rerun lag as the weight sliders above; same fix.
        new_sc = st.slider(
            "Sector Exposure Cap (%)", min_value=15, max_value=50, step=5,
            key="cfg_sc",
        )
        new_stc = st.slider(
            "Individual Stock Cap (%)", min_value=2, max_value=15, step=1,
            key="cfg_stc",
        )

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
            "Enable Dynamic Volatility Targeting", key="cfg_vt",
        )
        st.slider(
            "Target Portfolio Volatility (%)", min_value=10, max_value=40, step=5,
            key="cfg_vtv", disabled=not new_vt,
        )

    st.divider()

    # ── Section 5: Corporate Actions Detected ────────────────────────────────
    st.markdown("##### 5. Corporate Actions Detected in Price History")
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
                    "First Seen": e.get("first_seen", "—"),
                }
            )
        render_saas_table(pd.DataFrame(_rows), key="cfg_corporate_actions")
        st.caption(
            "A **split or bonus** should have been adjusted away by the data "
            "provider and was not — re-fetching that symbol fixes it. A "
            "**possible demerger** matches no standard ratio; providers "
            "generally do not adjust for these at all, because the parent's "
            "price genuinely falls while shareholders receive stock in the new "
            "entity. No money was lost, but an unadjusted series records a loss."
        )

    # ── Section 6: Cache & Data Paths ────────────────────────────────────────
    st.markdown("##### 6. Cache & Data Paths")
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
    st.dataframe(pd.DataFrame(cache_rows), hide_index=True, width="stretch")
    render_data_quality_footer(
        total_stocks=len(rank_df),
        gap_count=int((rank_df.get("Data Gap", pd.Series()) == "🔴").sum()),
        short_count=int((rank_df.get("Short History", pd.Series()) == "Yes").sum()),
    )
