"""The Guide renders each section, states the defaults from the engine's
constants, and no longer gives regime advice the strategy does not follow
(UI audit 7 Oct 2026, J1-J8)."""
from __future__ import annotations

import pytest
from streamlit.testing.v1 import AppTest

import src.engine.pipeline  # noqa: F401  (pipeline first: it and momentum import each other)
from src.core.config import DEFAULT_LOOKBACK_WEIGHTS
from src.engine.track_record import TRACK_RECORD_CONFIG
from src.ui.views import guide_view

SECTIONS = ["How it works", "Formulas", "Trading it", "FAQ"]


def _app():
    import pandas as pd

    from src.ui.views.guide_view import render_guide_view

    render_guide_view(pd.DataFrame({"Symbol": ["AAA", "BBB"], "Short History": ["No", "Yes"]}))


def _text(at: AppTest) -> str:
    parts = [m.value for m in at.markdown] + [h.value for h in at.get("html")]
    return "\n".join(str(p) for p in parts)


def _render(section: str) -> str:
    at = AppTest.from_function(_app)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    if section != SECTIONS[0]:
        at.button_group[0].set_value(section).run()
        assert not at.exception, [e.value for e in at.exception]
    return _text(at)


def test_the_sections_are_the_four_plain_names():
    assert guide_view.SECTIONS == SECTIONS


@pytest.mark.parametrize("section", SECTIONS)
def test_every_section_renders(section):
    assert _render(section)


def test_no_regime_allocation_advice():
    """The model does not change exposure by regime: no playbook remains."""
    text = "\n".join(_render(s) for s in SECTIONS)
    for removed in ("85% Equity", "70% Equity", "40% Equity", "100% Equity", "Cash)",
                    "Playbook", "VIX", "Weight tilt", "Target Allocation"):
        assert removed not in text, removed
    assert "The strategy does not use it." in text
    assert "200-day average" in text


def test_defaults_are_stated_once_and_from_the_constants():
    text = _render("How it works")
    shown = " ".join(f"{w:.0%}" for w in DEFAULT_LOOKBACK_WEIGHTS)
    assert all(f"| {m}M | {w:.0%} |" in text for m, w in
               zip((1, 3, 6, 9, 12), DEFAULT_LOOKBACK_WEIGHTS)), shown
    assert f"The {TRACK_RECORD_CONFIG['top_n']} best-ranked qualified stocks" in text
    assert f"top {TRACK_RECORD_CONFIG['buffer_n']} qualified stocks" in text
    assert TRACK_RECORD_CONFIG["config_weights"] == list(DEFAULT_LOOKBACK_WEIGHTS)
    everything = "\n".join(_render(s) for s in SECTIONS)
    assert "10/30/30/20/10" not in everything
    assert everything.count("before tax") == 1


def test_stale_instructions_are_gone():
    text = "\n".join(_render(s) for s in SECTIONS)
    for stale in ("Download Zerodha Kite Basket CSV", "Portfolio tab", "NIFTY > 50 EMA",
                  "Microstructure liquidity", "none quoted here", "21 trading days",
                  "Methodology Framework", "Strategy Comparison Matrix"):
        assert stale not in text, stale
    assert "Kite basket" in _render("Trading it")
