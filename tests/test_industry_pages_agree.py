"""RRG and Sectors read an industry the same way (S147, owner 20 Nov 2026).

Both build each industry as an equal-weighted index of its stocks and compare
it with the same construction over every ranked stock. Before, both compared
with the cap-weighted Nifty 500, and on 18 Nov 2026 RRG called Financial
Services, FMCG and Realty Leading while Sectors had them behind on both.
"""
import itertools

import numpy as np
import pandas as pd

from src.engine import market_questions as mq
from src.engine.sector_breadth import sector_leadership
from src.ui.views.rrg_view import BENCHMARK_EW, BENCHMARK_OPTIONS, compute_rrg_data

_KEY = itertools.count()


def _market(periods: int = 300):
    """Three industries of five stocks: one gains on the others all along,
    one loses, one sits between. A Nifty 500 that soars past all of them
    stands for a large-company rally."""
    rng = np.random.default_rng(3)
    idx = pd.bdate_range(end="2026-11-18", periods=periods)
    drift = {"Strong": 0.0015, "Middle": 0.0003, "Weak": -0.0010}
    cols, groups = {}, {}
    for ind, mu in drift.items():
        for k in range(5):
            sym = f"{ind[0]}{k}"
            cols[sym] = 100 * np.exp(np.cumsum(mu + rng.normal(0, 0.003, periods)))
            groups[sym] = ind
    prices = pd.DataFrame(cols, index=idx)
    rank_df = pd.DataFrame({"Symbol": list(groups), "Industry": list(groups.values())})
    nifty = pd.Series(100 * np.exp(np.cumsum(np.full(periods, 0.004))), index=idx)
    return prices, pd.Series(groups), rank_df, nifty


def test_the_default_benchmark_is_the_equal_weighted_market():
    assert BENCHMARK_OPTIONS[0] == BENCHMARK_EW


def test_both_pages_put_the_strong_industry_ahead_and_the_weak_behind():
    prices, groups, rank_df, nifty = _market()
    rrg = compute_rrg_data(f"agree{next(_KEY)}", prices, rank_df).set_index("Industry")
    leaders = mq.leaders_answer(prices, groups, nifty, None).sectors.set_index("Industry")
    board = sector_leadership(prices, groups, nifty, span=20, months=3).set_index("Sector")

    assert rrg.loc["Strong", "RS_Ratio"] > 100 > rrg.loc["Weak", "RS_Ratio"]
    assert leaders.loc["Strong", "group"] == "ahead on both"
    assert leaders.loc["Weak", "group"] == "behind on both"
    assert board.loc["Strong", "x_now"] > 0 > board.loc["Weak", "x_now"]
    # Against the soaring index every industry would trail; against the market they straddle it.
    assert (rrg["RS_Ratio"] > 100).any() and (rrg["RS_Ratio"] < 100).any()


def test_the_soaring_index_is_still_there_as_size_leadership():
    prices, groups, _, nifty = _market()
    six, one = mq.leaders_answer(prices, groups, nifty, None).market_vs_index
    assert six < 0 and one < 0
