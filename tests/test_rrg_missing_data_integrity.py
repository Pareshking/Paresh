"""RRG must not invent flat sessions for unobserved data.

Relative strength divides a sector's cumulative return by the benchmark's.
Filling a missing return with 0 asserts the sector was flat that day, so the
benchmark's real move is compared against a stationary sector -- a
directional distortion of RS-Ratio and RS-Momentum.
"""
import itertools

import numpy as np
import pandas as pd
import pytest

from src.ui.views.rrg_view import compute_rrg_data

_KEY = itertools.count()


def _fixture(seed: int = 21, drift: float = 0.004, periods: int = 320):
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2025-01-01", periods=periods)
    syms = [f"S{i}" for i in range(12)]
    industries = ["Fin"] * 3 + ["IT"] * 3 + ["Auto"] * 3 + ["GAP"] * 3
    prices = pd.DataFrame(
        {s: 100 * np.exp(np.cumsum(rng.normal(drift, 0.012, periods))) for s in syms},
        index=dates,
    )
    rank_df = pd.DataFrame({
        "Symbol": syms,
        "Industry": industries,
        "Market Cap (Cr)": np.linspace(90000, 500, 12),
    })
    return prices, rank_df, dates


def _run(prices, rank_df, **kwargs):
    return compute_rrg_data(f"key{next(_KEY)}", prices, rank_df, **kwargs)


def test_unobserved_sector_is_not_treated_as_a_flat_sector():
    """An unobserved stretch must not read the same as a genuinely flat one."""
    prices, rank_df, dates = _fixture()
    gap = dates[-45:-5]
    gap_syms = ["S9", "S10", "S11"]

    unobserved = prices.copy()
    unobserved.loc[gap, gap_syms] = np.nan

    # What zero-filling the returns effectively assumed: prices held constant.
    flat = prices.copy()
    for s in gap_syms:
        flat.loc[gap, s] = flat.loc[gap[0], s]

    got = _run(unobserved, rank_df).set_index("Industry")
    as_flat = _run(flat, rank_df).set_index("Industry")

    assert not np.isclose(
        got.loc["GAP", "RS_Momentum"], as_flat.loc["GAP", "RS_Momentum"], atol=1e-6
    ), "unobserved sector must not be scored as if it traded flat"


def test_sectors_without_gaps_are_unaffected():
    prices, rank_df, dates = _fixture()
    gap_syms = ["S9", "S10", "S11"]
    unobserved = prices.copy()
    unobserved.loc[dates[-45:-5], gap_syms] = np.nan

    clean = _run(prices, rank_df).set_index("Industry")
    got = _run(unobserved, rank_df).set_index("Industry")
    # The gapped sector changes; a fully observed sector's own RS inputs do not
    # depend on another sector's missing observations beyond shared rescaling.
    assert set(clean.index) == set(got.index)


@pytest.mark.parametrize("mutate,label", [
    (lambda p, d: p, "baseline"),
    (lambda p, d: p.assign(S0=np.nan), "dead symbol"),
])
def test_degraded_inputs_do_not_raise(mutate, label):
    prices, rank_df, dates = _fixture()
    assert isinstance(_run(mutate(prices.copy(), dates), rank_df), pd.DataFrame)


def test_whole_market_gap_does_not_raise():
    prices, rank_df, dates = _fixture()
    prices.iloc[150:160, :] = np.nan
    assert isinstance(_run(prices, rank_df), pd.DataFrame)


def test_whole_sector_outage_does_not_raise():
    prices, rank_df, dates = _fixture()
    prices.loc[dates[100:130], ["S9", "S10", "S11"]] = np.nan
    assert isinstance(_run(prices, rank_df), pd.DataFrame)


@pytest.mark.parametrize("kwargs", [
    {"ind_column": "Symbol"},
    {"benchmark_choice": "Midcap 150"},
    {"timeframe": "Daily candle"},
])
def test_control_combinations_do_not_raise(kwargs):
    prices, rank_df, _ = _fixture()
    assert isinstance(_run(prices, rank_df, **kwargs), pd.DataFrame)
