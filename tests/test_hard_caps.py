"""Stock and industry caps are hard everywhere (owner, 2026-10-02).

A cap is never raised: selection gives no industry more than its slots, and the
weight projection leaves what it cannot place as cash instead of lifting names
back through the cap.
"""
import numpy as np
import pandas as pd
import pytest

from src.engine.actions import plan_rebalance
from src.engine.backtester import _select_holdings, sector_slots
from src.engine.portfolio import apply_caps


def test_slots_for_the_account():
    assert sector_slots(20, 0.05, 0.40) == 8
    assert sector_slots(20, 0.05, 0.30) == 6
    assert sector_slots(10, 0.05, 0.40) == 8   # 5% per name binds before 1/10


def test_projection_never_exceeds_stated_caps_on_random_shapes():
    rng = np.random.default_rng(1)
    for _ in range(200):
        n = int(rng.integers(1, 41))
        syms = [f"S{i}" for i in range(n)]
        smap = {s: f"SEC{int(rng.integers(0, 7))}" for s in syms}
        raw = pd.Series(rng.random(n) + 0.01, index=syms)
        raw /= raw.sum()
        sc, kc = float(rng.uniform(0.05, 1.0)), float(rng.uniform(0.01, 0.5))
        w = apply_caps(raw, smap, sector_cap=sc, stock_cap=kc)
        by_sector = pd.Series(w.to_numpy(), index=[smap[s] for s in w.index]).groupby(level=0).sum()
        assert w.max() <= kc + 1e-8
        assert by_sector.max() <= sc + 1e-8
        assert w.sum() <= 1.0 + 1e-9
        assert w.attrs["cash"] == pytest.approx(1.0 - w.sum(), abs=1e-9)
        assert w.attrs["caps_relaxed"] is False


def test_infeasible_caps_leave_cash_not_a_breach():
    syms = [f"S{i}" for i in range(20)]
    smap = {s: ("ALPHA" if i < 14 else "BETA") for i, s in enumerate(syms)}
    w = apply_caps(pd.Series(1 / 20, index=syms), smap, sector_cap=0.40, stock_cap=0.06)
    alpha = float(w[[s for s in syms if smap[s] == "ALPHA"]].sum())
    assert alpha <= 0.40 + 1e-9
    assert w.attrs["cash"] > 0
    assert w.attrs["effective_sector_cap"] == 0.40


def test_selection_holds_no_industry_past_its_slots_and_skips_to_next_rank():
    # 30 ranked names, the best 12 all in industry A, the rest spread over 6 others.
    order = [f"A{i}" for i in range(12)] + [f"B{i}" for i in range(18)]
    ranked = pd.Series(range(len(order), 0, -1), index=order, dtype=float)
    smap = {s: ("A" if s[0] == "A" else f"B{int(s[1:]) % 6}") for s in order}
    book = _select_holdings(ranked, [], 20, 40, sector_map=smap, max_per_sector=8)
    assert len(book) == 20
    assert sum(s.startswith("A") for s in book) == 8
    assert book[:8] == order[:8]                         # best eight A's kept
    assert [s for s in book if s.startswith("B")] == order[12:24]


def test_overfull_incumbents_keep_their_best_ranked():
    order = [f"A{i}" for i in range(10)] + [f"B{i}" for i in range(20)]
    ranked = pd.Series(range(len(order), 0, -1), index=order, dtype=float)
    smap = {s: ("A" if s[0] == "A" else f"B{int(s[1:]) % 6}") for s in order}
    held = list(reversed(order[:10]))                    # 10 A's held, worst first
    book = _select_holdings(ranked, held, 20, 40, sector_map=smap, max_per_sector=8)
    assert sorted(s for s in book if s.startswith("A")) == sorted(order[:8])


def test_no_limit_given_means_the_old_selection():
    order = [f"S{i}" for i in range(30)]
    ranked = pd.Series(range(30, 0, -1), index=order, dtype=float)
    assert _select_holdings(ranked, ["S25"], 20, 30) == \
        _select_holdings(ranked, ["S25"], 20, 30, sector_map=None, max_per_sector=None)


def test_actions_plan_applies_the_same_industry_limit():
    n = 30
    syms = [f"A{i}" for i in range(12)] + [f"B{i}" for i in range(n - 12)]
    rank_df = pd.DataFrame({
        "Symbol": syms,
        "Industry": ["Alpha"] * 12 + [f"Beta{i % 6}" for i in range(n - 12)],
        "Rank": range(1, n + 1),
        "Above 50 EMA": True,
        "Near 52W High": True,
    })
    plan = plan_rebalance(rank_df, [], top_n=20, buffer_n=40,
                          stock_cap=0.05, sector_cap=0.40)
    assert len(plan.buys) == 20
    assert sum(s.startswith("A") for s in plan.buys) == 8
    assert float(plan.weights.max()) <= 0.05 + 1e-9
    assert float(plan.weights.sum()) == pytest.approx(1.0)
    assert not any(s.startswith("A") for s in plan.next_in_line)
