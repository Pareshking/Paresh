"""Sectors' answer and its leadership map read an industry the same way (S147).

Both build each industry as an equal-weighted index of its stocks and compare
it with the same construction over every ranked stock, not with the cap-weighted
Nifty 500. (RRG, which this test also covered, was removed on 21 Nov 2026, S169.)
"""
import numpy as np
import pandas as pd

from src.engine import market_questions as mq
from src.engine.sector_breadth import sector_leadership


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


def test_both_pages_put_the_strong_industry_ahead_and_the_weak_behind():
    prices, groups, rank_df, nifty = _market()
    leaders = mq.leaders_answer(prices, groups, nifty, None).sectors.set_index("Industry")
    board = sector_leadership(prices, groups, nifty, span=20, months=3).set_index("Sector")

    assert leaders.loc["Strong", "group"] == "ahead on both"
    assert leaders.loc["Weak", "group"] == "behind on both"
    assert board.loc["Strong", "x_now"] > 0 > board.loc["Weak", "x_now"]
    # Against the soaring index every industry would trail; against the market they straddle it.
    assert (board["x_now"] > 0).any() and (board["x_now"] < 0).any()


def test_the_soaring_index_is_still_there_as_size_leadership():
    prices, groups, _, nifty = _market()
    six, one = mq.leaders_answer(prices, groups, nifty, None).market_vs_index
    assert six < 0 and one < 0
