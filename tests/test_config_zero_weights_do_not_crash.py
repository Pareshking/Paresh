"""Dragging every weight to zero must not take the Configuration tab down.

Introduced by the repair in 2170ed7 and confirmed before this fix: that commit
restored the defaults by writing `st.session_state[key]` AFTER the slider with
that key had been instantiated in the same run, which raises

    StreamlitWidgetAlreadyInstantiatedError: `st.session_state.cfg_w1` cannot be
    modified after the widget with key `cfg_w1` is instantiated

and the whole tab rendered as an error box. A user who set all five to zero --
precisely the state that was being reported -- would have hit it.

The panel now says what ranking is using and leaves the controls alone;
`app.py` warns separately and ranks on the documented defaults.
"""
from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest

from src.core.config import DEFAULT_LOOKBACK_WEIGHTS

APP = str(Path(__file__).parent / "_config_zero_probe_app.py")
KEYS = [f"cfg_w{i}" for i in range(1, 6)]


def _run(state: dict) -> AppTest:
    at = AppTest.from_file(APP, default_timeout=60)
    for k, v in state.items():
        at.session_state[k] = v
    return at.run()


def test_all_five_weights_at_zero_renders_instead_of_raising():
    at = _run(dict.fromkeys(KEYS, 0.0))
    assert not at.exception, [e.value[:200] for e in at.exception]


def test_all_five_at_zero_says_what_the_ranking_is_actually_using():
    at = _run(dict.fromkeys(KEYS, 0.0))
    said = " ".join(w.value for w in at.warning)
    assert "cannot rank anything" in said
    assert "documented defaults" in said, (
        "the panel left five dead controls on screen without saying what the "
        "engine is ranking on"
    )


def test_the_sliders_still_show_the_zeros_the_reader_set():
    """Do not lie about the control's own position while warning about it."""
    at = _run(dict.fromkeys(KEYS, 0.0))
    shown = {s.label: s.value for s in at.slider}
    assert [shown[k] for k in ("1M", "3M", "6M", "9M", "12M")] == [0.0] * 5


def test_a_custom_weight_survives_navigating_away_and_back():
    """The eviction fix. This is what a reader actually loses."""
    at = _run({"cfg_w1": 0.55})
    assert not at.exception, [e.value[:200] for e in at.exception]

    at.session_state["nav_section"] = "Portfolio Risk"
    at.run()

    # Streamlit's widget-state garbage collection, made explicit. Deleting the
    # keys is the whole point of the test, so assert the eviction happened --
    # an earlier version of this guarded the delete behind a `hasattr` that is
    # False on AppTest's session state, so it evicted nothing and passed
    # vacuously. A test that cannot fail on its target is worse than none.
    for k in KEYS:
        if k in at.session_state:
            del at.session_state[k]
    assert all(k not in at.session_state for k in KEYS), "eviction not simulated"

    at.session_state["nav_section"] = "Momentum Signal"
    at.run()

    shown = {s.label: s.value for s in at.slider}
    assert shown["1M"] == 0.55, (
        f"a custom weight was replaced by the default after navigation: {shown}"
    )


def test_the_reset_button_restores_the_documented_defaults():
    at = _run(dict.fromkeys(KEYS, 0.0))
    at.button(key="cfg_w_reset").click().run()
    shown = {s.label: s.value for s in at.slider}
    assert [shown[k] for k in ("1M", "3M", "6M", "9M", "12M")] == list(
        DEFAULT_LOOKBACK_WEIGHTS
    ), f"reset left the panel at {shown}"
    assert not at.exception, [e.value[:200] for e in at.exception]


# ── Actually moving the controls ─────────────────────────────────────────────
# The crash was only ever reachable by CHANGING values, so reasoning about the
# code is not enough: these drag the widgets the way a reader does.

def test_dragging_one_weight_does_not_raise_and_takes_effect():
    at = _run({})
    at.slider(key="cfg_w1").set_value(0.45).run()
    assert not at.exception, [e.value[:200] for e in at.exception]
    assert {s.label: s.value for s in at.slider}["1M"] == 0.45


def test_dragging_every_weight_down_to_zero_does_not_raise():
    """The exact motion that raised StreamlitWidgetAlreadyInstantiatedError."""
    at = _run({})
    for key in KEYS:
        at.slider(key=key).set_value(0.0).run()
        assert not at.exception, (
            f"setting {key} to 0.0 raised: "
            f"{[e.value[:200] for e in at.exception]}"
        )
    shown = {s.label: s.value for s in at.slider}
    assert [shown[k] for k in ("1M", "3M", "6M", "9M", "12M")] == [0.0] * 5
    assert "cannot rank anything" in " ".join(w.value for w in at.warning)


def test_a_dragged_value_then_reset_then_dragged_again_never_raises():
    at = _run({})
    at.slider(key="cfg_w3").set_value(0.55).run()
    at.button(key="cfg_w_reset").click().run()
    at.slider(key="cfg_w3").set_value(0.15).run()
    assert not at.exception, [e.value[:200] for e in at.exception]
    assert {s.label: s.value for s in at.slider}["6M"] == 0.15


def test_dragging_the_risk_caps_does_not_raise():
    """These bind the book, so a crash here is worse than a cosmetic one."""
    at = _run({"nav_section": "Portfolio Risk"})
    at.slider(key="cfg_sc").set_value(45).run()
    at.slider(key="cfg_stc").set_value(12).run()
    at.checkbox(key="cfg_vt").set_value(True).run()
    at.slider(key="cfg_vtv").set_value(35).run()
    assert not at.exception, [e.value[:200] for e in at.exception]
    shown = {s.label: s.value for s in at.slider}
    assert shown["Sector Exposure Cap (%)"] == 45
    assert shown["Individual Stock Cap (%)"] == 12
    assert shown["Target Portfolio Volatility (%)"] == 35


def test_a_dragged_weight_survives_navigation_and_eviction():
    """Change it, leave, have Streamlit evict it, come back. Still yours."""
    at = _run({})
    at.slider(key="cfg_w2").set_value(0.65).run()

    at.session_state["nav_section"] = "Portfolio Risk"
    at.run()
    for k in KEYS:
        if k in at.session_state:
            del at.session_state[k]
    assert all(k not in at.session_state for k in KEYS), "eviction not simulated"
    at.session_state["nav_section"] = "Momentum Signal"
    at.run()

    assert not at.exception, [e.value[:200] for e in at.exception]
    assert {s.label: s.value for s in at.slider}["3M"] == 0.65, (
        "a weight the reader set was lost by navigating away"
    )
