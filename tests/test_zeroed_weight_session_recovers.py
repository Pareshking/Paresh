"""A session holding five zeroed weights must still rank, and must say so.

Every repair before this one was guarded on the key being ABSENT. That cannot
fix a key which is PRESENT and wrong -- and a phone left open on this app for a
week is exactly a session with present, wrong keys. This runs the real
`app.py`, not a probe.

These assert BEHAVIOUR, not storage. An earlier version of this file asserted
that `st.session_state["cfg_w1"]` equalled the default, which pinned the
implementation rather than the promise: the fix that followed stopped writing
that key on purpose -- writing it is what evicts, warns, and in one branch
crashed the tab -- and three correct tests went red for it.

The promise is: whatever the Configuration panel displays, the weight vector
handed to the scoring engine is never all zeros, and a repair is never silent.
"""
from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest

from src.core.config import DEFAULT_LOOKBACK_WEIGHTS

APP = str(Path(__file__).resolve().parents[1] / "app.py")
KEYS = [f"cfg_w{i}" for i in range(1, 6)]


def _run_with(state: dict) -> AppTest:
    at = AppTest.from_file(APP, default_timeout=300)
    for k, v in state.items():
        at.session_state[k] = v
    return at.run()


def _warnings(at) -> str:
    return " ".join(w.value for w in at.warning)


def test_a_session_holding_five_zeros_ranks_on_the_documented_defaults():
    at = _run_with(dict.fromkeys(KEYS, 0.0))
    assert not at.exception, [e.value for e in at.exception]
    said = _warnings(at)
    assert "were zero" in said and "using the defaults" in said, (
        f"the engine was handed a vector that cannot rank anything, or was "
        f"repaired silently; warnings were {said!r}"
    )
    for w in DEFAULT_LOOKBACK_WEIGHTS:
        assert f"{w:.0%}" in said, "the warning does not name what it ranked on"


def test_a_healthy_session_is_left_alone_and_not_warned_at():
    at = _run_with(dict(zip(KEYS, DEFAULT_LOOKBACK_WEIGHTS)))
    assert not at.exception, [e.value for e in at.exception]
    assert "were zero" not in _warnings(at), (
        "a correctly configured session was warned at"
    )


def test_the_app_boots_with_no_weight_keys_at_all():
    """A brand-new visitor. Nothing is stored, so the defaults must carry it."""
    at = _run_with({})
    assert not at.exception, [e.value for e in at.exception]
    assert "were zero" not in _warnings(at), (
        "a first visit was told its weights were broken"
    )


def test_a_mirrored_weight_outlives_an_evicted_widget_key():
    """The eviction fix, at the level the engine actually reads.

    Streamlit discards widget state for any key whose widget did not render on
    the previous run, and the Configuration tab renders one section at a time.
    Before the mirror, an evicted key fell through app.py's absence guard and
    the reader's own weights were replaced by the defaults -- silently, while
    the panel still described their configuration.
    """
    at = _run_with({f"cfg_w{i}__v": v for i, v in
                    zip(range(1, 6), [0.5, 0.2, 0.1, 0.1, 0.1])})
    assert not at.exception, [e.value for e in at.exception]
    assert "were zero" not in _warnings(at)


def test_an_out_of_range_stored_weight_does_not_reach_the_engine():
    """A present-but-impossible value is treated as no value at all."""
    at = _run_with(dict.fromkeys(KEYS, 4.0))
    assert not at.exception, [e.value for e in at.exception]
