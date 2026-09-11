"""Renders the Momentum Signal section with whatever state the test sets."""
import streamlit as st

from src.ui.views.config_view import _section_momentum_signal, _section_portfolio_risk

section = st.session_state.get("nav_section", "Momentum Signal")
if section == "Momentum Signal":
    _section_momentum_signal()
else:
    _section_portfolio_risk()
