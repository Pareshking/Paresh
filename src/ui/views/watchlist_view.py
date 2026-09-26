"""
Custom watchlist view. The list lives in the reader's own browser
(src/ui/watchlist_store.py): private to them, kept across visits, and added to
from any stock page with one click.
"""

import re

import pandas as pd
import streamlit as st

from src.core.market_time import ist_now

from src.ui import page_kit as kit
from src.ui import watchlist_store
from src.ui.components import gap_count, render_data_quality_footer
from src.ui.screener_table import render_screener_table


# There used to be a second layer: data/user_watchlist.json on the server's
# disk, read back whenever the reader had no list of their own. On the public
# deployment that file is shared by every visitor, so one reader's saved
# watchlist became every other reader's default. The list is per-reader now,
# in their browser; the server never stores it.
def _save_from_input() -> None:
    watchlist_store.save(watchlist_store.parse(st.session_state.get("wl_input_main", "")))


def _remove_picked() -> None:
    sym = st.session_state.pop("wl_remove_pick", None)
    if sym:
        watchlist_store.save([s for s in watchlist_store.symbols() if s != sym])


def render_watchlist_view(rank_df: pd.DataFrame, adj_close: pd.DataFrame | None = None) -> None:
    """The reader's watchlist: edit it here, or star stocks on their pages."""
    user_symbols = watchlist_store.symbols()
    matched = rank_df[rank_df["Symbol"].isin(user_symbols)].sort_values("Rank").copy()

    count = f"{len(matched)} stock{'s' if len(matched) != 1 else ''}, ranked" if user_symbols else "Nothing saved yet"
    actions = kit.page_head(
        "Watchlist",
        f"{count}. Saved in this browser only; add a stock from its page with \"Add to watchlist\".",
        actions=True,
    )
    if not matched.empty:
        actions.download_button("Export CSV", matched.to_csv(index=False).encode(),
                                f"watchlist_momentum_{ist_now():%Y%m%d}.csv", "text/csv",
                                key="dl_wl_csv", icon=":material/download:")

    current = ", ".join(user_symbols)
    if st.session_state.get("_wl_input_shown") != current:
        # Follow the stored list (a star on a stock page, the browser loading
        # it) without fighting the reader's typing between saves.
        st.session_state["wl_input_main"] = current
        st.session_state["_wl_input_shown"] = current

    with st.container(horizontal=True, key="wl_editbar", vertical_alignment="bottom"):
        st.text_input(
            "Symbols",
            placeholder="Comma-separated symbols, e.g. RELIANCE, TCS, CUPID, INFY, DIACABS",
            key="wl_input_main",
            label_visibility="collapsed",
        )
        st.button("Save watchlist", type="primary", key="wl_update_btn",
                  on_click=_save_from_input)
        if user_symbols:
            with st.popover("Remove a stock", icon=":material/remove_circle_outline:"):
                st.pills("Remove", user_symbols, key="wl_remove_pick",
                         on_change=_remove_picked, label_visibility="collapsed")

    if not user_symbols:
        st.info(
            "Your watchlist is empty. Type symbols above and save, or open any stock and "
            "press \"Add to watchlist\"."
        )
        return

    missing = set(user_symbols) - set(rank_df["Symbol"])
    if missing:
        # Echoed back from input a shared ?wl= link can supply: reduce each to
        # ticker characters before showing it.
        shown = sorted({re.sub(r"[^A-Z0-9&._-]", "", str(m).upper())[:20] for m in missing} - {""})
        kit.note(f"{len(missing)} not found among the {len(rank_df)} ranked stocks:", ", ".join(shown))

    if matched.empty:
        st.info("None of your symbols is in the ranked universe.")
    else:
        with kit.card("Your stocks", "wl_list", "Same table as the Screener · click a row to open the stock"):
            render_screener_table(matched, adj_close, "Core")

    render_data_quality_footer(
        total_stocks=len(rank_df),
        gap_count=gap_count(rank_df),
        short_count=int((rank_df.get("Short History", pd.Series()) == "Yes").sum()),
    )
