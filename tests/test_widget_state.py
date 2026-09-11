"""The resolver behind every cfg_* setting.

Two faults in the Configuration tab motivated it, both confirmed and neither
reproducible in AppTest:

  1. Streamlit evicts widget state for any key whose widget did not render on
     the previous run, and this tab renders one section at a time.
  2. A slider with `key=` and no `value=` renders at its MINIMUM on the
     deployed frontend regardless of what session state holds.

So each setting keeps a mirror key no widget owns, and every widget is handed
an explicit value resolved from it.
"""
from __future__ import annotations

import math

import pytest

from streamlit.testing.v1 import AppTest


PROBE = """
import streamlit as st
from src.ui.widget_state import forget, remember, resolve

st.text(f"W={resolve('w', 0.10, lo=0.0, hi=1.0)}")
st.text(f"N={resolve('n', 30, lo=15, hi=50)}")
st.text(f"B={resolve('b', False)}")
"""


def _run(state: dict, tmp_path) -> dict:
    script = tmp_path / "probe.py"
    script.write_text(PROBE)
    at = AppTest.from_file(str(script), default_timeout=30)
    for k, v in state.items():
        at.session_state[k] = v
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    out = {}
    for t in at.text:
        name, _, val = t.value.partition("=")
        out[name] = val
    return out


def test_nothing_stored_yields_the_default(tmp_path):
    got = _run({}, tmp_path)
    assert got["W"] == "0.1" and got["N"] == "30" and got["B"] == "False"


def test_the_widget_key_wins_while_it_exists(tmp_path):
    """It is the fresher of the two the instant someone drags a slider."""
    got = _run({"w": 0.45, "w__v": 0.10}, tmp_path)
    assert got["W"] == "0.45"


def test_the_mirror_carries_the_value_when_the_widget_key_is_evicted(tmp_path):
    got = _run({"w__v": 0.45}, tmp_path)
    assert got["W"] == "0.45"


@pytest.mark.parametrize("bad", [None, "", "abc", float("nan"), float("inf"), 4.0, -1.0])
def test_a_present_but_impossible_value_is_treated_as_no_value(tmp_path, bad):
    """The case every absence-guarded repair before this one could not fix."""
    got = _run({"w": bad, "w__v": 0.25}, tmp_path)
    assert got["W"] == "0.25", f"{bad!r} was accepted as a weight"


def test_an_out_of_range_mirror_falls_through_to_the_default(tmp_path):
    got = _run({"n": 99, "n__v": 99}, tmp_path)
    assert got["N"] == "30"


def test_a_bool_setting_does_not_accept_a_float_and_vice_versa(tmp_path):
    """`cfg_vt` is a checkbox; a stray 0.5 must not become True."""
    got = _run({"b": 0.5, "w": True}, tmp_path)
    assert got["B"] == "False", "a float was accepted as a checkbox state"
    assert got["W"] == "0.1", "a bool was accepted as a weight"


def test_an_int_setting_keeps_its_type(tmp_path):
    """A slider declared with int bounds rejects a float value at runtime."""
    got = _run({"n": 35.0}, tmp_path)
    assert got["N"] == "35" and "." not in got["N"]


def test_mirror_keys_are_namespaced_away_from_widget_keys():
    from src.ui.widget_state import MIRROR_SUFFIX, mirror_key
    assert mirror_key("cfg_w1") == f"cfg_w1{MIRROR_SUFFIX}"
    assert mirror_key("cfg_w1") != "cfg_w1"
