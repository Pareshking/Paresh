"""The Dashboard's signal tests: the rule fixed before looking (S150)."""

import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.engine import signal_tests as stt


def _lead(values):
    months = pd.period_range("2010-01", periods=len(values), freq="M")
    return pd.Series(values, index=months)


def test_a_signal_that_works_in_both_halves_passes():
    rng = np.random.default_rng(0)
    on = pd.Series(rng.random(120) < 0.3, index=pd.period_range("2009-12", periods=120, freq="M"))
    lead = _lead([(-2.0 if on.iloc[i] else 1.0) + rng.normal(0, 0.1) for i in range(120)])
    r = stt.run("x", "x", on, lead, "weaker")
    assert r.passed and r.on < r.off and all(h < 0 for h in r.halves)


def test_the_wrong_direction_or_a_small_gap_does_not_pass():
    rng = np.random.default_rng(1)
    on = pd.Series(rng.random(120) < 0.3, index=pd.period_range("2009-12", periods=120, freq="M"))
    lead = _lead([(-2.0 if on.iloc[i] else 1.0) for i in range(120)])
    assert not stt.run("x", "x", on, lead, "stronger").passed
    small = _lead([(0.5 if on.iloc[i] else 0.0) for i in range(120)])
    assert not stt.run("x", "x", on, small, "stronger").passed


def test_a_signal_that_flips_between_halves_does_not_pass():
    on = pd.Series([i % 3 == 0 for i in range(120)], index=pd.period_range("2009-12", periods=120, freq="M"))
    lead = _lead([(3.0 if on.iloc[i] else 0.0) if i < 60 else (-0.5 if on.iloc[i] else 0.0) for i in range(120)])
    r = stt.run("x", "x", on, lead, "stronger")
    assert r.on - r.off >= 1 and not r.passed


def test_the_committed_results_say_what_the_page_shows():
    """Pinned 20 Nov 2026: breadth counted on the members of each date passes;
    the participation jump, which the old page counted for momentum, does not."""
    got = json.loads((Path(__file__).resolve().parents[1] / "data" / "signal_tests.json").read_text())
    t = got["tests"]
    assert t["breadth_thin"]["passed"] and t["breadth_thin"]["claim"] == "weaker"
    assert not t["participation_jump"]["passed"]
    assert t["trend_fast"]["passed"] and t["qualify"]["passed"] and t["fpi"]["passed"]
    assert t["fpi"]["threshold"] > 0
    assert 0 < got["average"] < 2
