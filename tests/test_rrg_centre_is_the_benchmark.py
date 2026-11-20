"""RRG's 100 is the benchmark, not the average industry (S147, 19 Nov 2026).

The chart centred on the cross-section's mean, so in a market where every
industry trailed the index the least-bad half still read "Leading". On 18 Nov
2026 Financial Services, FMCG and Realty were 3-4% behind the Nifty 500 over
12 weeks and the RRG called them Leading while Sectors had them behind.
"""
import itertools

import numpy as np
import pandas as pd

from src.ui.views.rrg_view import compute_rrg_data

_KEY = itertools.count()


def _market(drifts: dict[str, float], bench_drift: float, periods: int = 260):
    """Each industry of three stocks with a steady daily drift; a benchmark that
    beats or trails them by construction."""
    rng = np.random.default_rng(7)
    dates = pd.bdate_range("2025-06-02", periods=periods)
    cols, inds = {}, []
    for ind, mu in drifts.items():
        for k in range(3):
            # The industry's drift begins halfway, so relative strength is
            # rising or falling inside the 12-week lookback, not flat.
            path = np.r_[np.zeros(periods // 2), np.full(periods - periods // 2, mu)]
            cols[f"{ind}{k}"] = 100 * np.exp(np.cumsum(path + rng.normal(0, 0.0005, periods)))
            inds.append(ind)
    prices = pd.DataFrame(cols, index=dates)
    rank_df = pd.DataFrame({"Symbol": list(cols), "Industry": inds})
    bench_path = np.r_[np.zeros(periods // 2), np.full(periods - periods // 2, bench_drift)]
    bench = pd.Series(100 * np.exp(np.cumsum(bench_path)), index=dates)
    return prices, rank_df, bench


def _rrg(drifts, bench_drift):
    prices, rank_df, bench = _market(drifts, bench_drift)
    out = compute_rrg_data(f"centre{next(_KEY)}", prices, rank_df, _benchmark=bench)
    return out.set_index("Industry")


def test_every_industry_trailing_the_index_reads_left_of_centre():
    # All four fall behind a rising index; one falls behind least.
    out = _rrg({"Least": 0.0010, "Mid": 0.0005, "Worse": 0.0, "Worst": -0.0010}, bench_drift=0.0020)
    assert len(out) == 4
    assert (out["RS_Ratio"] < 100).all(), out[["RS_Ratio", "Quadrant"]]
    assert not out["Quadrant"].isin(["Leading", "Weakening"]).any(), out["Quadrant"].to_dict()
    # Under the old centring, the least-bad half was shown right of 100.
    assert out.loc["Least", "RS_Ratio"] > out.loc["Worst", "RS_Ratio"]


def test_every_industry_beating_the_index_reads_right_of_centre():
    out = _rrg({"A": 0.0030, "B": 0.0025, "C": 0.0022, "D": 0.0021}, bench_drift=0.0)
    assert (out["RS_Ratio"] > 100).all(), out[["RS_Ratio", "Quadrant"]]
    assert not out["Quadrant"].isin(["Lagging", "Improving"]).any()


def test_trail_ends_at_the_point_and_shares_its_centre():
    out = _rrg({"A": 0.0030, "B": -0.0010, "C": 0.0005}, bench_drift=0.0010)
    for ind, row in out.iterrows():
        assert row["Trail_R"][-1] == row["RS_Ratio"] and row["Trail_M"][-1] == row["RS_Momentum"], ind
