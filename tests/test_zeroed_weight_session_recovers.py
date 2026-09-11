"""A session that ALREADY holds five zeroed weights must recover, and say so.

Every repair before this one was guarded on the key being ABSENT. That cannot
fix a key which is PRESENT and wrong -- and a phone that has been left open on
this app for a week is exactly a session with present, wrong keys. This runs
the real `app.py`, not a probe, with the broken state pre-loaded.

The claim being pinned is the one that actually matters to a user: whatever the
Configuration panel is displaying, the weight vector handed to the scoring
engine is never all zeros, and a repair is never silent.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from streamlit.testing.v1 import AppTest

from src.core.config import DEFAULT_LOOKBACK_WEIGHTS

APP = str(Path(__file__).resolve().parents[1] / "app.py")
KEYS = [f"cfg_w{i}" for i in range(1, 6)]


def _run_with(state: dict) -> AppTest:
    at = AppTest.from_file(APP, default_timeout=300)
    for k, v in state.items():
        at.session_state[k] = v
    return at.run()


def test_a_session_holding_five_zeros_is_repaired_to_the_documented_defaults():
    at = _run_with(dict.fromkeys(KEYS, 0.0))
    assert not at.exception, [e.value for e in at.exception]
    assert [at.session_state[k] for k in KEYS] == pytest.approx(
        list(DEFAULT_LOOKBACK_WEIGHTS)
    ), "the engine would have been handed a vector that cannot rank anything"


def test_the_repair_is_reported_never_silent():
    """A different strategy under the configured one's name is the failure."""
    at = _run_with(dict.fromkeys(KEYS, 0.0))
    said = " ".join(w.value for w in at.warning)
    assert "were zero" in said, (
        f"weights were repaired without telling anyone; warnings were {said!r}"
    )


def test_a_healthy_session_is_left_alone_and_not_warned_at():
    at = _run_with(dict(zip(KEYS, DEFAULT_LOOKBACK_WEIGHTS)))
    assert not at.exception, [e.value for e in at.exception]
    assert [at.session_state[k] for k in KEYS] == pytest.approx(
        list(DEFAULT_LOOKBACK_WEIGHTS)
    )
    assert not any("were zero" in w.value for w in at.warning), (
        "a correctly configured session was warned at"
    )


def test_the_app_boots_with_no_weight_keys_at_all():
    """A brand-new visitor. The absence guard is the only path that runs."""
    at = _run_with({})
    assert not at.exception, [e.value for e in at.exception]
    assert [at.session_state[k] for k in KEYS] == pytest.approx(
        list(DEFAULT_LOOKBACK_WEIGHTS)
    )
