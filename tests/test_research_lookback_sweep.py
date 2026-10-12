"""The lookback-weight research script's statistics (scripts/research_lookback_sweep.py)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_PATH = Path(__file__).resolve().parents[1] / "scripts" / "research_lookback_sweep.py"
_spec = importlib.util.spec_from_file_location("research_lookback_sweep", _PATH)
rs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rs)


def _returns(n_days: int = 2520, n_mix: int = 12, seed: int = 1, edge: np.ndarray | None = None) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    x = rng.normal(0.0004, 0.01, (n_days, n_mix))
    if edge is not None:
        x += edge
    idx = pd.bdate_range("2012-01-02", periods=n_days)
    return pd.DataFrame(x, index=idx, columns=[f"m{i}" for i in range(n_mix)])


def test_the_grid_is_every_split_of_four_quarters_plus_live_and_equal():
    g = rs.grid()
    assert len(g) == 72
    assert all(abs(sum(w) - 1) < 1e-9 for w in g)
    assert rs.LIVE_WEIGHTS in g and (0.2,) * 5 in g
    assert (1.0, 0.0, 0.0, 0.0, 0.0) in g and (0.0, 0.0, 0.0, 0.0, 1.0) in g


def test_sharpe_matches_the_backtester_definition():
    r = _returns(n_mix=1)
    x = r.iloc[:, 0]
    expected = (x.mean() * 252 - 0.065) / (x.std() * np.sqrt(252))
    assert rs.sharpe(r, 0.065)[0] == pytest.approx(expected)


def test_a_mix_against_itself_differs_by_nothing():
    r = _returns(n_mix=2)
    r["m1"] = r["m0"]
    boot = rs.paired_bootstrap(r, "m0", 0.065, n=200)
    assert boot.loc["m1", "dSharpe"] == pytest.approx(0.0)
    assert boot.loc["m1", "lo90"] == pytest.approx(0.0) and boot.loc["m1", "hi90"] == pytest.approx(0.0)


def test_pure_noise_overfits_about_half_the_time():
    pbo, lam = rs.pbo_cscv(_returns(n_mix=20, seed=3), 0.065, blocks=10)
    assert len(lam) == 252  # 10 choose 5
    assert 0.25 < pbo < 0.75


def test_a_real_edge_is_not_called_overfitting():
    edge = np.zeros(12)
    edge[0] = 0.002  # one mix earns 0.2% a day more, every day
    pbo, _ = rs.pbo_cscv(_returns(edge=edge), 0.065, blocks=10)
    assert pbo < 0.05


def test_neighbours_move_one_quarter_between_two_windows():
    weights = pd.DataFrame(
        [w for w in rs.grid() if w not in (rs.LIVE_WEIGHTS, (0.2,) * 5)],
        columns=[f"w{m}" for m in rs.WINDOWS],
    )
    weights.index = [rs.label(tuple(w)) for w in weights.to_numpy()]
    near = rs.neighbours(weights)
    assert len(near) == 70
    assert sorted(near[rs.label((1.0, 0.0, 0.0, 0.0, 0.0))]) == sorted(
        rs.label(w) for w in [(0.75, 0.25, 0, 0, 0), (0.75, 0, 0.25, 0, 0),
                              (0.75, 0, 0, 0.25, 0), (0.75, 0, 0, 0, 0.25)]
    )
    assert len(near[rs.label((0.25, 0.25, 0.25, 0.25, 0.0))]) == 16
