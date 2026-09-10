"""Probe app that honours the Configuration tab's CONDITIONAL left-nav.

`_config_probe_app.py` deliberately bypasses the nav and calls every section
function directly, "so that all widgets are always visible to AppTest". That is
what makes it blind to this bug: the momentum weight sliders live inside a
section that is rendered ONLY when it is the active one, and Streamlit discards
widget state for keys whose widget was not rendered on the previous run.

This probe reproduces app.py faithfully in the two respects that matter:
  1. the canonical cfg_w* values are seeded once, and only when absent;
  2. the weights are read at the TOP of the script, before any section renders;
  3. exactly ONE section renders per run, chosen by session state.
"""

import streamlit as st

from src.ui.views.config_view import (
    _section_momentum_signal,
    _section_portfolio_risk,
)

# ── app.py's state initialisation, verbatim in behaviour ─────────────────────
if "cfg_w1" not in st.session_state:
    st.session_state.update(
        {"cfg_w1": 0.10, "cfg_w2": 0.30, "cfg_w3": 0.30, "cfg_w4": 0.20, "cfg_w5": 0.10}
    )
if "cfg_sc" not in st.session_state:
    st.session_state.update({"cfg_sc": 30, "cfg_stc": 5, "cfg_vt": False, "cfg_vtv": 25})

# ── what the ENGINE is handed, read before any section body runs ─────────────
raw_w = [st.session_state[f"cfg_w{i}"] for i in range(1, 6)]
total_w = sum(raw_w)
weights = list([w / total_w for w in raw_w] if total_w > 0 else [0.2] * 5)
st.text(f"RAW={raw_w}")
st.text(f"ENGINE_WEIGHTS={[round(w, 4) for w in weights]}")
st.text(f"FELL_BACK_TO_EQUAL={total_w <= 0}")

# ── one section per run, exactly as config_view's nav does it ────────────────
section = st.session_state.get("nav_section", "Momentum Signal")
if section == "Momentum Signal":
    _section_momentum_signal()
elif section == "Portfolio Risk":
    _section_portfolio_risk()
