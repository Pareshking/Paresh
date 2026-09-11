"""The Configuration widgets must never rely on session state alone.

Measured against https://paresh.streamlit.app/ on 2026-09-11, on the build the
deploy check confirmed was serving (`3a54bd3`):

    sliders  1M=0.00  3M=0.00  6M=0.00  9M=0.00  12M=0.00
    pill     10% · 30% · 30% · 20% · 10%

Fourteen sliders were readable in that one DOM. Every one that passed an
explicit `value=` rendered correctly -- including the Backtest tab's own five
lookback weights, identical in range and step, given `float(weights[i])`. The
only five that rendered at their minimum were the only five declared with a
`key=` and no value. Session state held the right numbers throughout: the pill
six lines above the sliders is computed from it and read correctly.

`AppTest` cannot see this. It exercises the Python side, where session state
does reach the widget, which is why four local environments and the pre-session
code all render these correctly. So this test asserts the property at the level
that DID distinguish the working sliders from the broken ones: the call itself.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
VIEWS = ROOT / "src" / "ui" / "views"

# Widgets whose value must be explicit. Every one of these is read by the
# engine or binds the portfolio, so a silent fallback to `min_value` is a
# changed strategy, not a cosmetic defect.
GUARDED_KEYS = {"cfg_w1", "cfg_w2", "cfg_w3", "cfg_w4", "cfg_w5",
                "cfg_sc", "cfg_stc", "cfg_vt", "cfg_vtv"}

VALUED = {"slider", "checkbox", "number_input", "select_slider", "radio",
          "selectbox", "multiselect"}


def _widget_calls(path: Path):
    """(widget name, keywords) for every st.<widget>/col.<widget> call."""
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        name = node.func.attr
        if name not in VALUED:
            continue
        kw = {k.arg for k in node.keywords if k.arg}
        key = next((k.value.value for k in node.keywords
                    if k.arg == "key" and isinstance(k.value, ast.Constant)), None)
        yield name, key, kw, len(node.args), node.lineno


@pytest.mark.parametrize("path", sorted(VIEWS.glob("*.py")), ids=lambda p: p.name)
def test_every_engine_bound_widget_is_given_an_explicit_value(path):
    offenders = []
    for name, key, kw, n_positional, lineno in _widget_calls(path):
        if key not in GUARDED_KEYS:
            continue
        # `value=` by keyword, or positionally after label/min/max.
        has_value = "value" in kw or n_positional >= 4
        if not has_value:
            offenders.append(f"{path.name}:{lineno} {name}(key={key!r})")
    assert not offenders, (
        "these widgets rely on session state alone and render at their minimum "
        "on the deployed frontend: " + "; ".join(offenders)
    )


def test_the_guard_would_actually_catch_the_defect_it_was_written_for():
    """A test that cannot fail on its target proves nothing.

    This is the exact shape that shipped and broke, checked against the same
    parser the real assertion uses.
    """
    import tempfile
    src = (
        "import streamlit as st\n"
        "st.slider('1M', min_value=0.0, max_value=1.0, step=0.05, key='cfg_w1')\n"
    )
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as fh:
        fh.write(src)
        tmp = Path(fh.name)
    found = [(k, kw, n) for _name, k, kw, n, _ln in _widget_calls(tmp)]
    assert found == [("cfg_w1", {"min_value", "max_value", "step", "key"}, 1)]
    assert "value" not in found[0][1] and found[0][2] < 4
