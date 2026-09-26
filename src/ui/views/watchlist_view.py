"""
Custom watchlist view. The list lives in the reader's own browser
(src/ui/watchlist_store.py): private to them, kept across visits, and added to
from any stock page with one click.
"""

import re

import pandas as pd
import streamlit as st

from src.core.market_time import ist_now

from src.ui import watchlist_store
from src.ui.components import gap_count, render_data_quality_footer, stat_pill
from src.ui.theme import render_master_screener_table


# There used to be a second layer: data/user_watchlist.json on the server's
# disk, read back whenever the reader had no list of their own. On the public
# deployment that file is shared by every visitor, so one reader's saved
# watchlist became every other reader's default. The list is per-reader now,
# in their browser; the server never stores it.
def _save_from_input() -> None:
    watchlist_store.save(watchlist_store.parse(st.session_state.get("wl_input_main", "")))


def render_watchlist_view(rank_df: pd.DataFrame) -> None:
    """The reader's watchlist: edit it here, or star stocks on their pages."""
    st.markdown(
        """
        <div class="scr-head"><h1>Watchlist</h1>
        <p>Your stocks, ranked. Saved in this browser only; add a stock from its page with "Add to watchlist".</p></div>
        """,
        unsafe_allow_html=True,
    )

    current = ", ".join(watchlist_store.symbols())
    if st.session_state.get("_wl_input_shown") != current:
        # Follow the stored list (a star on a stock page, the browser loading
        # it) without fighting the reader's typing between saves.
        st.session_state["wl_input_main"] = current
        st.session_state["_wl_input_shown"] = current

    w1, w2 = st.columns([4, 1], vertical_alignment="center")
    wl_input = w1.text_input(
        "Enter Tickers",
        placeholder="Comma-separated symbols, e.g. RELIANCE, TCS, CUPID, INFY, DIACABS",
        key="wl_input_main",
        label_visibility="collapsed",
    )
    w2.button("Save watchlist", width="stretch", type="primary", key="wl_update_btn",
              on_click=_save_from_input)

    user_symbols = watchlist_store.symbols() or watchlist_store.parse(wl_input)

    if not user_symbols:
        st.info(
            "Your watchlist is empty. Type symbols above and save, or open any stock and "
            "press \"Add to watchlist\"."
        )
        return

    matched = rank_df[rank_df["Symbol"].isin(user_symbols)].sort_values("Rank").copy()
    missing = set(user_symbols) - set(rank_df["Symbol"])

    if missing:
        # Echoed back from input a shared ?wl= link can supply, into Markdown:
        # reduce each to ticker characters before showing it.
        shown = sorted({re.sub(r"[^A-Z0-9&._-]", "", str(m).upper())[:20] for m in missing} - {""})
        st.warning(
            f"{len(missing)} symbol(s) not found in loaded index universe: {', '.join(shown)}"
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
            f"watchlist_momentum_{ist_now():%Y%m%d}.csv",
            "text/csv",
            key="dl_wl_csv",
        )
    else:
        st.info(
            "None of the specified symbols match the currently selected market index universe."
        )

    render_data_quality_footer(
        total_stocks=len(rank_df),
        gap_count=gap_count(rank_df),
        short_count=int((rank_df.get("Short History", pd.Series()) == "Yes").sum()),
    )
