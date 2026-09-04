"""PARESH QUANT v2 verification application.

For this validation phase the application intentionally contains only two
surfaces: Screener and Stock Detail. Existing quantitative engines/loaders are
used unchanged; the old UI is not imported.
"""

from __future__ import annotations

import streamlit as st

from src.ui.v2.runtime import load_runtime
from src.ui.v2.screener import render as render_screener
from src.ui.v2.stock_detail import render as render_stock_detail
from src.ui.v2.theme import inject

st.set_page_config(page_title="PARESH QUANT v2", page_icon="📈", layout="wide", initial_sidebar_state="collapsed")
inject()

if "v2_page" not in st.session_state:
    st.session_state["v2_page"] = "Screener"
if "v2_selected_symbol" not in st.session_state:
    st.session_state["v2_selected_symbol"] = None

# Minimal terminal header. Only the two pages being verified are exposed.
nav_left, nav_mid, nav_right = st.columns([1.0, 2.8, 1.0])
with nav_left:
    st.markdown("**PARESH QUANT**")
with nav_mid:
    page = st.pills("Navigation", ["Screener", "Stock Detail"], default=st.session_state["v2_page"], key="v2_navigation", label_visibility="collapsed")
    if page:
        st.session_state["v2_page"] = page
with nav_right:
    if st.button("↻ Refresh data", key="v2_refresh"):
        st.session_state["v2_force_refresh"] = True
        st.rerun()

with st.spinner("Loading quantitative universe…"):
    data = load_runtime()

if not data:
    st.error("Unable to initialize the quantitative universe. The existing data loaders/engine returned no ranked data.")
    st.stop()

if st.session_state["v2_page"] == "Stock Detail":
    render_stock_detail(data, st.session_state.get("v2_selected_symbol"))
else:
    render_screener(data)
