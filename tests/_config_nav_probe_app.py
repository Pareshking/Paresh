"""Probe app that honours the Configuration tab's CONDITIONAL left-nav.

`_config_probe_app.py` deliberately bypasses the nav and calls every section
function directly, "so that all widgets are always visible to AppTest". That is
what made it blind: the momentum weight sliders live in a section rendered ONLY
when it is the active one, and Streamlit discards widget state for keys whose
widget was not rendered on the previous run.

This probe reproduces app.py faithfully in the respects that matter:
  1. nothing is seeded into session state -- app.py resolves each setting
     through src/ui/widget_state.py rather than writing it, because writing a
     widget key is what evicts, warns, and in one branch crashed the tab;
  2. the weights are read at the TOP of the script, before any section renders;
  3. exactly ONE section renders per run, chosen by session state.
"""

import streamlit as st

from src.core.config import DEFAULT_LOOKBACK_WEIGHTS
from src.ui.views.config_view import (
    _section_momentum_signal,
    _section_portfolio_risk,
)
from src.ui.widget_state import resolve

# ── what the ENGINE is handed, read before any section body runs ─────────────
raw_w = [
    resolve(f"cfg_w{i}", float(DEFAULT_LOOKBACK_WEIGHTS[i - 1]), lo=0.0, hi=1.0)
    for i in range(1, 6)
]
total_w = sum(raw_w)
weights = list([w / total_w for w in raw_w] if total_w > 0
               else list(DEFAULT_LOOKBACK_WEIGHTS))
st.text(f"RAW={raw_w}")
st.text(f"ENGINE_WEIGHTS={[round(w, 4) for w in weights]}")
st.text(f"FELL_BACK_TO_EQUAL={total_w <= 0}")

# ── one section per run, exactly as config_view's nav does it ────────────────
section = st.session_state.get("nav_section", "Momentum Signal")
if section == "Momentum Signal":
    _section_momentum_signal()
elif section == "Portfolio Risk":
    _section_portfolio_risk()
