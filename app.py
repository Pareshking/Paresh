"""PARESH QUANT v2 verification entry point.

Only Screener and Stock Detail are exposed during the visual/functional test.
The underlying quantitative engine remains the existing production engine.
"""
import streamlit as st
from src.ui.v2_app import run

st.set_page_config(page_title="PARESH QUANT v2", page_icon="📈", layout="wide", initial_sidebar_state="collapsed")
run()
