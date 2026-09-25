"""
Custom watchlist view. The list lives in the URL (?wl=...), so it is private to
the reader, survives a refresh and can be bookmarked or shared.
"""

from datetime import datetime

import pandas as pd
import streamlit as st

from src.core.tickers import normalise_symbol

from src.ui.components import render_data_quality_footer, stat_pill
from src.ui.theme import render_master_screener_table


# There used to be a second layer: data/user_watchlist.json on the server's
# disk, read back whenever the URL carried no list. On the public deployment
# that file is shared by every visitor, so one reader's saved watchlist became
# every other reader's default. The URL is per-reader; the disk never was.
def _load_persisted_watchlist() -> str:
    """The watchlist carried in this reader's URL, or an empty one."""
    param_wl = st.query_params.get("wl")
    return str(param_wl).strip() if param_wl and str(param_wl).strip() else ""


def _save_persisted_watchlist(text: str) -> None:
    """Keep the watchlist in this reader's URL."""
    if text.strip():
        st.query_params["wl"] = text.strip()
    else:
        st.query_params.pop("wl", None)


def render_watchlist_view(rank_df: pd.DataFrame) -> None:
    """Renders user custom watchlist tracking view with cloud & local persistence."""
    st.markdown(
        """
        <div style="font-family: 'Plus Jakarta Sans', sans-serif; font-size: 1.10rem; font-weight: 800; color: #0f172a; margin-bottom: 2px;">
            Personal Watchlist & Custom Monitor
        </div>
        <div style="font-size: 0.76rem; color: #64748b; margin-bottom: 14px;">
            Track high-conviction stocks across multi-window momentum, trailing stops, and rank dynamics. Persists across local and Streamlit Cloud sessions.
        </div>
        """,
        unsafe_allow_html=True,
    )

    if (
        "watchlist_text" not in st.session_state
        or not st.session_state["watchlist_text"]
    ):
        st.session_state["watchlist_text"] = _load_persisted_watchlist()

    w1, w2 = st.columns([4, 1], vertical_alignment="center")
    wl_input = w1.text_input(
        "Enter Tickers",
        value=st.session_state.get("watchlist_text", ""),
        placeholder="Enter comma-separated tickers (e.g. RELIANCE, TCS, CUPID, INFY, DIACABS)…",
        key="wl_input_main",
        label_visibility="collapsed",
    )
    if w2.button(
        "Update Watchlist", width="stretch", type="primary", key="wl_update_btn"
    ):
        st.session_state["watchlist_text"] = wl_input
        _save_persisted_watchlist(wl_input)
        st.rerun()

    raw_text = st.session_state.get("watchlist_text", "") or wl_input
    user_symbols: list[str] = []
    if raw_text:
        parts = raw_text.replace("\n", ",").split(",")
        user_symbols = [
            normalise_symbol(s) for s in parts if s.strip()
        ]

    if not user_symbols:
        st.info(
            "Enter comma-separated stock symbols above to monitor their momentum rankings, return metrics, and stop losses."
        )
        return

    matched = rank_df[rank_df["Symbol"].isin(user_symbols)].sort_values("Rank").copy()
    missing = set(user_symbols) - set(rank_df["Symbol"])

    if missing:
        st.warning(
            f"{len(missing)} symbol(s) not found in loaded index universe: {', '.join(sorted(missing))}"
        )

    if not matched.empty:
        st.html(
            stat_pill("Tracking", f"{len(matched)} stocks", "indigo")
            + (
                stat_pill("Missing", f"{len(missing)} stocks", "amber")
                if missing
                else ""
            )
        )
        st.markdown(" ")

        render_master_screener_table(matched)

        st.download_button(
            "Download Watchlist CSV",
            matched.to_csv(index=False).encode(),
            f"watchlist_momentum_{datetime.now():%Y%m%d}.csv",
            "text/csv",
            key="dl_wl_csv",
        )
    else:
        st.info(
            "None of the specified symbols match the currently selected market index universe."
        )

    render_data_quality_footer(
        total_stocks=len(rank_df),
        gap_count=int((rank_df.get("Data Gap", pd.Series()) == "🔴").sum()),
        short_count=int((rank_df.get("Short History", pd.Series()) == "Yes").sum()),
    )
