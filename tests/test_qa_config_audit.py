"""The production probe must be able to SEE the reported config defect.

The bug report was five Lookback Window sliders reading 0.00 beside a pill
claiming "Weight vector: 10% · 30% · 30% · 20% · 10%". The existing probe walks
every tab but only asks whether each one renders without a traceback -- and
that panel renders perfectly, it just shows the wrong numbers. A check that
cannot fail on the defect it is aimed at is not evidence of anything, so these
tests feed `judge_configuration` the exact shapes the live reader can return
and pin what it must call a failure.
"""
import importlib.util
import pathlib

_spec = importlib.util.spec_from_file_location(
    "production_qa",
    pathlib.Path(__file__).resolve().parents[1] / "scripts" / "production_qa.py",
)
production_qa = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(production_qa)

judge = production_qa.judge_configuration

HEALTHY = {
    "sliders": {"1M": 0.10, "3M": 0.30, "6M": 0.30, "9M": 0.20, "12M": 0.10},
    "pill": [10.0, 30.0, 30.0, 20.0, 10.0],
}
ZEROED = {
    "sliders": {"1M": 0.0, "3M": 0.0, "6M": 0.0, "9M": 0.0, "12M": 0.0},
    "pill": [10.0, 30.0, 30.0, 20.0, 10.0],
}


def _ev(initial, after=None):
    ev = {"panel_reached": True, "initial": initial}
    if after is not None:
        ev["after_nav"] = after
    return ev


def test_a_correct_panel_produces_no_failures():
    assert judge("desktop_1280x800", _ev(HEALTHY, HEALTHY)) == []


def test_the_reported_defect_is_a_failure():
    """Exactly the phone screenshot: zeros beside a 10/30/30/20/10 pill."""
    found = judge("mobile_390x844", _ev(ZEROED))
    assert found, "the probe would have passed the screenshot the user sent"
    assert any(f["kind"] == "APPLICATION" for f in found)
    assert any("zeroed weight vector" in f["detail"] for f in found)


def test_zeros_that_appear_only_after_navigating_are_caught():
    """The eviction hypothesis: fine on arrival, zeroed after a round trip."""
    found = judge("mobile_390x844", _ev(HEALTHY, ZEROED))
    assert any("after_nav" in f["detail"] for f in found)


def test_sliders_disagreeing_with_the_pill_is_a_failure():
    """Non-zero but inconsistent is still two numbers contradicting each other."""
    snap = {
        "sliders": {"1M": 0.20, "3M": 0.20, "6M": 0.20, "9M": 0.20, "12M": 0.20},
        "pill": [10.0, 30.0, 30.0, 20.0, 10.0],
    }
    found = judge("desktop_1280x800", _ev(snap))
    assert any("disagrees with itself" in f["detail"] for f in found)


def test_rounding_in_the_pill_is_not_a_failure():
    """The pill prints whole percent; 1/3 of the vector is 33%, not 33.33%."""
    snap = {
        "sliders": {"1M": 0.15, "3M": 0.15, "6M": 0.15, "9M": 0.15, "12M": 0.15},
        "pill": [20.0, 20.0, 20.0, 20.0, 20.0],
    }
    assert judge("desktop_1280x800", _ev(snap)) == []


def test_navigation_that_silently_changes_a_weight_is_a_failure():
    """Not zeroed, but not what the user set either."""
    moved = {
        "sliders": {"1M": 0.10, "3M": 0.30, "6M": 0.30, "9M": 0.20, "12M": 0.05},
        "pill": [10.5, 31.6, 31.6, 21.1, 5.3],
    }
    found = judge("desktop_1280x800", _ev(HEALTHY, moved))
    assert any("navigating away and back changed the sliders" in f["detail"]
               for f in found)


def test_an_unreachable_panel_is_reported_as_a_qa_gap_not_a_pass():
    found = judge("mobile_360x800", {"panel_reached": False, "error": "no nav"})
    assert len(found) == 1 and found[0]["kind"] == "QA"


def test_a_missing_pill_is_never_silently_accepted():
    snap = {"sliders": HEALTHY["sliders"], "pill": None}
    found = judge("desktop_1280x800", _ev(snap))
    assert any("pill not found" in f["detail"] for f in found)


def test_a_short_slider_read_is_reported_rather_than_assumed_healthy():
    snap = {"sliders": {"1M": 0.10, "3M": 0.30}, "pill": [10.0, 30.0]}
    found = judge("desktop_1280x800", _ev(snap))
    assert any("expected 5 lookback sliders" in f["detail"] for f in found)


def test_the_reset_phase_is_judged_and_named_for_what_it_proves():
    """Zeros surviving the panel's own unconditional write is a stronger claim.

    "Reset to defaults" writes all five keys as plain floats and reruns. If the
    sliders still read zero after that, the defect is not a stale or evicted
    value -- no write to session state is reaching these widgets at all, and
    the failure text has to say so or the next reader will re-derive it.
    """
    found = judge("desktop_1280x800", {
        "panel_reached": True, "initial": ZEROED, "after_reset": ZEROED,
    })
    reset = [f for f in found if "after_reset" in f["detail"]]
    assert reset, "the reset phase was not judged at all"
    assert "no write to session state is reaching these widgets" in reset[0]["detail"]


def test_a_reset_that_repairs_the_panel_is_not_reported_as_a_failure():
    found = judge("desktop_1280x800", {
        "panel_reached": True, "initial": ZEROED, "after_reset": HEALTHY,
    })
    assert not any("after_reset" in f["detail"] for f in found)
    assert any("initial" in f["detail"] for f in found), (
        "the original defect must still be reported even once reset repairs it"
    )


def test_the_precomputed_weight_subset_is_used_when_present():
    """The reader now hands the judge a filtered `weights` map.

    The full slider map contains every slider in the app's DOM -- st.tabs
    renders all eleven tab bodies -- including the Backtest tab's own
    "1M (21D)" lookback weights. Judging must use the Configuration panel's
    five, not whatever else happens to be on the page.
    """
    snap = {
        "sliders": {"1M (21D)": 0.10, "Holdings (Top N)": 20.0,
                    "1M": 0.0, "3M": 0.0, "6M": 0.0, "9M": 0.0, "12M": 0.0},
        "weights": {"1M": 0.0, "3M": 0.0, "6M": 0.0, "9M": 0.0, "12M": 0.0},
        "pill": [10.0, 30.0, 30.0, 20.0, 10.0],
    }
    found = judge("desktop_1280x800", _ev(snap))
    assert any("zeroed weight vector" in f["detail"] for f in found)
