"""PARESH QUANT V3 — responsive verification entry point."""
import streamlit as st

from src.ui.v3_app import run

st.set_page_config(
    page_title="PARESH QUANT",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

run()
