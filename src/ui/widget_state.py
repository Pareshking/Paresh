"""Settings that survive Streamlit's widget-state garbage collection.

Two independent faults met in the Configuration tab. Both are confirmed, and
neither is reproducible in `AppTest`, which is why three rounds of repairs
missed them.

1. EVICTION. Streamlit discards widget state for any key whose widget did not
   render on the previous run. The Configuration tab renders ONE section per
   run from its left-nav, so opening Portfolio Risk evicts every `cfg_w*` key
   and a reader's custom weights silently revert to the documented defaults --
   while the engine carries on ranking, and the panel carries on describing the
   configuration the reader chose.

2. NO EXPLICIT VALUE. A slider declared with `key=` and no `value=` renders at
   its MINIMUM on the deployed frontend even when session state holds the right
   number. Measured against https://paresh.streamlit.app/ on 2026-09-11:
   fourteen sliders in one DOM, and the only five that rendered wrong were the
   only five that passed no explicit value. The Backtest tab's five lookback
   sliders, identical in range and step but given `float(weights[i])`, rendered
   correctly in the same frame.

So every setting here carries a plain MIRROR key that no widget owns and
nothing evicts, and every widget is handed an explicit value resolved from it.
The widget's own key stays authoritative while it exists, because it is the
fresher of the two the instant someone drags a slider.
"""
from __future__ import annotations

import math
from typing import Any

import streamlit as st

MIRROR_SUFFIX = "__v"


def mirror_key(key: str) -> str:
    return f"{key}{MIRROR_SUFFIX}"


def _coerce(candidate: Any, default: Any, lo: Any, hi: Any) -> Any | None:
    """The candidate as the default's type, or None if it cannot stand in.

    Out-of-range is treated as no value at all. A key that is PRESENT and wrong
    is the case every absence-guarded repair before this one could not fix.
    """
    if candidate is None:
        return None
    if isinstance(default, bool):
        return bool(candidate) if isinstance(candidate, (bool, int)) else None
    if isinstance(candidate, bool):
        return None
    try:
        value = type(default)(candidate)
    except (TypeError, ValueError):
        return None
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if lo is not None and value < lo:
        return None
    if hi is not None and value > hi:
        return None
    return value


def resolve(key: str, default: Any, *, lo: Any = None, hi: Any = None) -> Any:
    """The live value of a setting: widget, then mirror, then the default."""
    for candidate in (st.session_state.get(key), st.session_state.get(mirror_key(key))):
        value = _coerce(candidate, default, lo, hi)
        if value is not None:
            return value
    return default


def remember(key: str, value: Any) -> None:
    """Record a widget's value where eviction cannot reach it.

    The mirror is never a widget key, so this is always legal -- unlike writing
    `st.session_state[key]` after the widget exists, which raises
    StreamlitWidgetAlreadyInstantiatedError and took the whole tab down when a
    reader set all five weights to zero.
    """
    st.session_state[mirror_key(key)] = value


def forget(key: str) -> None:
    """Drop a widget's own state so the mirror is what it reads next run."""
    st.session_state.pop(key, None)
