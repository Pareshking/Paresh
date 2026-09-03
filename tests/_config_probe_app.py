"""Probe app for test_config_widgets_apply_immediately.

Mirrors app.py's structure in the one respect that matters: the configuration
values are read at the TOP of the script, before any tab body renders.

With the Windows 11-style left-nav layout, sliders live inside conditionally
rendered sections. The probe bypasses the nav and calls the section functions
directly so that all widgets are always visible to AppTest, which probes the
rendered widget tree rather than clicking through the UI.
"""
import pandas as pd
import streamlit as st

from src.ui.views.config_view import (
    _section_momentum_signal,
    _section_portfolio_risk,
)

if "cfg_w1" not in st.session_state:
    st.session_state.update(
        {"cfg_w1": 0.10, "cfg_w2": 0.30, "cfg_w3": 0.30, "cfg_w4": 0.20, "cfg_w5": 0.10}
    )
if "cfg_sc" not in st.session_state:
    st.session_state.update({"cfg_sc": 30, "cfg_stc": 5, "cfg_vt": False, "cfg_vtv": 25})
if "cfg_indices" not in st.session_state:
    st.session_state["cfg_indices"] = ["NIFTY TOTAL MARKET"]

raw_w = [st.session_state[f"cfg_w{i}"] for i in range(1, 6)]
st.text(f"WEIGHTS={raw_w}")
st.text(f"SECTOR_CAP={st.session_state['cfg_sc']}")
st.text(f"STOCK_CAP={st.session_state['cfg_stc']}")

_section_momentum_signal()
_section_portfolio_risk()
