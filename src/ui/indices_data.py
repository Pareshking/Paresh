"""The app's copy of NSE's index files as the Indices page's frames, cached (S170).
Shared by the Indices page and the Dashboard's "Valuation and styles" card."""
from __future__ import annotations

import streamlit as st

from src.engine import indices_page as ip
from src.loaders import nse_indices as ni


def _stamp() -> str:
    return "|".join(f"{p.stat().st_mtime_ns}" if p.exists() else "-" for p in (ni.COMPACT_HISTORY, ni.COMPACT_RECENT))


@st.cache_data(show_spinner=False, ttl=3600)
def _frames(stamp: str) -> ip.Frames | None:
    store = ni.read_compact()
    if store.empty:
        return None
    return ip.frames(store, ni.groups())


def frames() -> ip.Frames | None:
    """None when the copy is missing (the page then says so)."""
    return _frames(_stamp())
