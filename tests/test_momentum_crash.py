"""Is momentum risky right now? (Daniel and Moskowitz's crash conditions)."""
import numpy as np
import pandas as pd

from src.engine import momentum_crash as mc


def _bench(drift_then: float, drift_now: float, vol_now: float, seed: int = 1):
    """Ten calm years, then 24 months of `drift_now` with daily volatility `vol_now`."""
    rng = np.random.default_rng(seed)
    days = pd.bdate_range("2005-01-03", "2017-12-29")
    n_now = 520
    r = np.r_[rng.normal(drift_then, 0.008, len(days) - n_now), rng.normal(drift_now, vol_now, n_now)]
    return pd.Series(100 * np.cumprod(1 + r), index=days)


def test_a_falling_violent_market_is_crash_prone():
    s = mc.current(_bench(0.0005, -0.004, 0.03))
    assert s.ret24 < 0 and s.vol_pct >= mc.HIGH_VOL_PCT and s.verdict == mc.CRASH


def test_a_rising_quiet_market_is_calm_and_one_condition_is_elevated():
    assert mc.current(_bench(0.0003, 0.0006, 0.006)).verdict == mc.CALM
    assert mc.current(_bench(0.0005, -0.0010, 0.006)).verdict == mc.ELEVATED   # bear, quiet


def test_the_evidence_matches_states_to_the_next_months_spread():
    b = _bench(0.0004, -0.001, 0.03)
    ends = b.groupby(b.index.to_period("M")).apply(lambda s: s.index[-1])
    spread = pd.DataFrame({"date": ends.values, "spread": np.linspace(-5, 5, len(ends))})
    ev = mc.evidence(b, spread)
    assert {"state", "spread", "ret24", "vol_pct"} <= set(ev.columns) and len(ev) > 100
    s = mc.summary(ev)
    assert sum(v["months"] for v in s["by_state"].values()) == len(ev)
