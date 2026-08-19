"""A failed sweep combination must say why it failed.

Audit finding F3. Every combination that raised became None and was counted,
but the reason was discarded. A count is not a diagnosis: if one systematic
error kills a whole region of the space, the sweep still ranks the survivors
and presents a winner, and the excluded region is invisible. The "optimal"
parameters are then optimal among whatever happened not to crash.
"""
import pandas as pd
import pytest

from src.engine import parameter_sweep as ps

BASE = {"rebal_freq": 21, "cost_bps": 30.0}


@pytest.fixture
def prices():
    idx = pd.date_range("2024-01-01", periods=420, freq="B")
    import numpy as np
    rng = np.random.default_rng(2)
    return pd.DataFrame(
        {f"S{i}": 100 * np.exp(np.cumsum(rng.normal(0.0005, 0.012, len(idx))))
         for i in range(8)},
        index=idx,
    )


def test_the_reason_reaches_the_warnings(monkeypatch, prices):
    def explode(*a, **k):
        raise ValueError("covariance matrix is singular")

    monkeypatch.setattr(ps, "run_backtest", explode)
    res = ps.run_parameter_sweep(
        prices, space={"Holdings": [3, 5]}, base=BASE, objective="Sharpe"
    )

    joined = " ".join(res.warnings)
    assert "singular" in joined, f"the reason was discarded: {res.warnings}"
    assert "ValueError" in joined
    assert res.combinations_failed == 2


def test_a_mostly_failed_sweep_says_the_winner_is_from_a_subset(monkeypatch, prices):
    """The finding's real danger: a plausible winner drawn from survivors."""
    calls = {"n": 0}

    def flaky(*a, **k):
        calls["n"] += 1
        if calls["n"] > 1:
            raise RuntimeError("optimiser did not converge")
        return {"stats": {"sharpe": 1.0, "total_return": 0.2, "alpha": 0.05,
                          "max_drawdown": -0.1, "win_rate": 0.6, "turnover": 0.3}}

    monkeypatch.setattr(ps, "run_backtest", flaky)
    res = ps.run_parameter_sweep(
        prices, space={"Holdings": [3, 5, 8, 10]}, base=BASE, objective="Sharpe"
    )

    joined = " ".join(res.warnings)
    assert "surviving subset" in joined
    assert "converge" in joined


def test_a_clean_sweep_adds_no_failure_noise(monkeypatch, prices):
    def fine(*a, **k):
        return {"stats": {"sharpe": 1.0, "total_return": 0.2, "alpha": 0.05,
                          "max_drawdown": -0.1, "win_rate": 0.6, "turnover": 0.3}}

    monkeypatch.setattr(ps, "run_backtest", fine)
    res = ps.run_parameter_sweep(
        prices, space={"Holdings": [3, 5]}, base=BASE, objective="Sharpe"
    )

    assert res.combinations_failed == 0
    assert not any("produced no result" in w for w in res.warnings)
