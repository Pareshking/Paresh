"""The momentum weight sliders must survive navigating away and back.

Reported from the live app on a phone: all five Lookback Window sliders read
**0.00** while the pill directly above them read "Weight vector: 10% · 30% ·
30% · 20% · 10%". Two numbers on one screen, disagreeing about the same thing.

The mechanism is Streamlit's widget-state garbage collection. The Configuration
tab renders its sections ON DEMAND from a left-nav, so the weight sliders exist
only while "Momentum Signal" is the active section. Streamlit discards widget
state for any key whose widget was not rendered on the previous run, so
navigating to another section evicts all five `cfg_w*` keys. A slider declared
with a `key` but no `value` then falls back to its `min_value` — 0.00.

The pre-existing config test cannot see this: `_config_probe_app.py` bypasses
the nav and calls every section function directly, "so that all widgets are
always visible to AppTest". Always-rendered widgets are never evicted. This
probe honours the nav instead.

The consequence is worse than a cosmetic mismatch. Touching any one slider
submits the displayed zeros for the other four, and a weight vector summing to
zero used to fall through to `[0.2] * 5` — the whole universe silently re-ranked
on EQUAL weights while the Configuration tab still described 10/30/30/20/10.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from streamlit.testing.v1 import AppTest

from src.core.config import DEFAULT_LOOKBACK_WEIGHTS

APP = str(Path(__file__).parent / "_config_nav_probe_app.py")
WEIGHT_KEYS = [f"cfg_w{i}" for i in range(1, 6)]
SLIDER_LABELS = ["1M", "3M", "6M", "9M", "12M"]


def _app() -> AppTest:
    return AppTest.from_file(APP, default_timeout=30).run()


def _slider_values(at: AppTest) -> list[float]:
    by_label = {s.label: s.value for s in at.slider}
    return [by_label[lbl] for lbl in SLIDER_LABELS]


def test_navigating_away_and_back_leaves_the_weights_intact():
    """The exact sequence from the bug report."""
    at = _app()
    assert _slider_values(at) == pytest.approx(list(DEFAULT_LOOKBACK_WEIGHTS))

    # Away: a different section renders, the weight sliders do not.
    at.session_state["nav_section"] = "Portfolio Risk"
    at.run()

    # Back.
    at.session_state["nav_section"] = "Momentum Signal"
    at.run()

    assert _slider_values(at) == pytest.approx(list(DEFAULT_LOOKBACK_WEIGHTS)), (
        "sliders reset after navigation — the panel would show 0.00 beside a "
        "pill claiming the configured weights"
    )


def test_the_sliders_and_the_weight_vector_pill_never_disagree():
    """Whatever the sliders show is what the engine is handed."""
    at = _app()
    for _ in range(3):
        at.session_state["nav_section"] = "Portfolio Risk"
        at.run()
        at.session_state["nav_section"] = "Momentum Signal"
        at.run()

        shown = _slider_values(at)
        engine = [float(at.session_state[k]) for k in WEIGHT_KEYS]
        assert shown == pytest.approx(engine), (
            f"sliders show {shown} while the engine is handed {engine}"
        )
        assert sum(shown) > 0, "a zeroed weight vector cannot rank anything"


def test_a_zero_weight_vector_is_repaired_and_reported_never_silently_equal_weighted():
    """`sum(w) == 0` used to fall through to [0.2]*5 with nothing said.

    Equal weighting is a different strategy from 10/30/30/20/10. Presenting it
    under the configured one's name is the silent-methodology-swap the README
    forbids elsewhere in this codebase.
    """
    import app as _app_module  # noqa: F401  (import guard only)

    src = Path(__file__).resolve().parents[1].joinpath("app.py").read_text()
    assert "else [0.2] * 5" not in src, (
        "the silent equal-weight fallback is back"
    )
    assert "st.warning(" in src and "were zero" in src, (
        "a zeroed weight vector must be reported to the user"
    )


def test_the_defaults_have_one_source():
    """app.py and the Configuration sliders must not carry separate literals."""
    root = Path(__file__).resolve().parents[1]
    app_src = root.joinpath("app.py").read_text()
    assert "DEFAULT_LOOKBACK_WEIGHTS" in app_src
    assert '"cfg_w1": 0.10' not in app_src, "hardcoded default reintroduced"


def test_the_window_guide_does_not_claim_a_skip_month_convention():
    """The engine applies no skip-month; the caption said it did.

    An earlier repair replaced only part of an implicitly-concatenated string
    literal and left a self-contradicting run-on: "…excludes the most recent
    month The engine does NOT apply a skip-month…".
    """
    src = Path(__file__).resolve().parents[1].joinpath(
        "src/ui/views/config_view.py"
    ).read_text()
    assert "excludes the most recent month" not in src
    assert "skip-month convention" not in src
    assert "No window skips the most recent month" in src


def test_the_portfolio_risk_widgets_survive_navigation_too():
    """Sector cap, stock cap and vol target have the same eviction exposure.

    Worse, in fact: a zeroed weight vector is at least detectable, but an
    evicted slider here comes back as a plausible number -- a 30% sector cap
    returns as 15% and a 5% stock cap as 2%, the minimum of each range. Both now
    genuinely bind the backtest and the Portfolio tab.
    """
    at = AppTest.from_file(APP, default_timeout=30)
    at.session_state["nav_section"] = "Portfolio Risk"
    at.run()

    def caps(a):
        return {s.label: s.value for s in a.slider}

    before = caps(at)
    assert before["Sector Exposure Cap (%)"] == 30
    assert before["Individual Stock Cap (%)"] == 5

    at.session_state["nav_section"] = "Momentum Signal"
    at.run()
    at.session_state["nav_section"] = "Portfolio Risk"
    at.run()

    assert caps(at) == before, "risk caps reset to the minimum of their range"
