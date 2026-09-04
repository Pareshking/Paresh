"""PARESH QUANT — V2 verification branch with the V3 responsive UI merged in."""
import streamlit as st

from src.ui.v3_app import run

st.set_page_config(
    page_title="PARESH QUANT",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

run()
