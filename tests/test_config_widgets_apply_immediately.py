"""Configuration widgets must take effect on the SAME rerun that changes them.

Reported as "changing the Momentum Lookback Multi-Window Weights doesn't show
the stocks correctly".

The sliders wrote to "slider_cfg_wN" and copied into the canonical "cfg_wN"
AFTER rendering. app.py reads cfg_w1..cfg_w5 at the top of the script, which has
already executed by the time the Configuration tab body runs, so the copy landed
one rerun too late: moving a weight re-ranked nothing until some later, unrelated
interaction happened to trigger another pass. The engine was never at fault --
it weights correctly; it was simply handed the previous values.

Driven through Streamlit's own AppTest so this asserts real widget behaviour
rather than the shape of the source.
"""
from pathlib import Path

import pytest

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).parent / "_config_probe_app.py")


def _app():
    at = AppTest.from_file(APP, default_timeout=90)
    at.run()
    return at


def _line(at, prefix):
    return next(t.value for t in at.text if t.value.startswith(prefix))


def test_weight_change_is_visible_to_the_top_of_the_script_immediately():
    at = _app()
    assert _line(at, "WEIGHTS=") == "WEIGHTS=[0.1, 0.3, 0.3, 0.2, 0.1]"

    next(s for s in at.slider if s.label == "1M").set_value(0.90).run()

    # Before the fix this still read 0.1 -- the change appeared only on the
    # NEXT rerun, which is what "doesn't show the stocks correctly" looked like.
    assert _line(at, "WEIGHTS=") == "WEIGHTS=[0.9, 0.3, 0.3, 0.2, 0.1]"


@pytest.mark.parametrize("label,index,value", [
    ("1M", 0, 0.85), ("3M", 1, 0.05), ("6M", 2, 0.75),
    ("9M", 3, 0.55), ("12M", 4, 0.95),
])
def test_every_weight_slider_applies_on_the_same_pass(label, index, value):
    at = _app()
    next(s for s in at.slider if s.label == label).set_value(value).run()
    weights = eval(_line(at, "WEIGHTS=").split("=", 1)[1])
    assert weights[index] == pytest.approx(value)


def test_a_changed_weight_does_not_disturb_the_others():
    at = _app()
    next(s for s in at.slider if s.label == "6M").set_value(0.75).run()
    weights = eval(_line(at, "WEIGHTS=").split("=", 1)[1])
    assert weights == pytest.approx([0.10, 0.30, 0.75, 0.20, 0.10])


def test_sector_and_stock_caps_apply_on_the_same_pass():
    at = _app()
    next(s for s in at.slider if "Sector Exposure Cap" in s.label).set_value(45).run()
    assert _line(at, "SECTOR_CAP=") == "SECTOR_CAP=45"

    next(s for s in at.slider if "Individual Stock Cap" in s.label).set_value(12).run()
    assert _line(at, "STOCK_CAP=") == "STOCK_CAP=12"


def test_weights_survive_an_unrelated_rerun():
    """The value must persist, not bounce back to the default."""
    at = _app()
    next(s for s in at.slider if s.label == "1M").set_value(0.65).run()
    at.run()
    weights = eval(_line(at, "WEIGHTS=").split("=", 1)[1])
    assert weights[0] == pytest.approx(0.65)
