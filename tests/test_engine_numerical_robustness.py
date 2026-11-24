"""The ranking engine on awkward synthetic input (S138, V1_AUDIT_TRACKER NEXT 8).

Missing observations, short histories, ties, a one-stock industry, constant
prices, a zero close, repeated dates and a reversed index. Each case pins what
the engine does today, so a change to any of them is a decision, not an accident.
Before 24 Nov 2026 a repeated date crashed the constructor and a reversed index
ranked nothing without saying why (momentum.time_ordered).
"""
import numpy as np
import pandas as pd
import pytest

from src.engine.momentum import MomentumEngine, time_ordered


def _frame(rows: int = 400, cols: int = 6, seed: int = 3) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2025-01-01", periods=rows)
    return pd.DataFrame(100 * np.exp(np.cumsum(rng.normal(0.0006, 0.012, (rows, cols)), 0)),
                        index=idx, columns=[f"S{i}" for i in range(cols)])


def _rank(px: pd.DataFrame, industries=None) -> pd.DataFrame:
    info = pd.DataFrame({"Symbol": list(px.columns),
                         "Industry": industries or [f"I{i % 2}" for i in range(px.shape[1])]})
    return MomentumEngine(px).get_rankings(info, pd.Series(1000.0, index=px.columns))


@pytest.fixture(scope="module")
def base():
    return _frame()


@pytest.fixture(scope="module")
def baseline(base):
    return _rank(base)


def _no_infinities(r: pd.DataFrame) -> None:
    num = r.select_dtypes("number").to_numpy(dtype=float)
    assert not np.isinf(num).any()


def test_the_baseline_ranks_every_stock_once(baseline):
    assert len(baseline) == 6 and list(baseline["Rank"]) == [1, 2, 3, 4, 5, 6]
    _no_infinities(baseline)


def test_a_repeated_date_is_dropped_and_ranks_as_the_clean_frame(base, baseline):
    doubled = pd.concat([base, base.iloc[[-5]]]).sort_index()
    pd.testing.assert_series_equal(_rank(doubled)["Score"], baseline["Score"])


def test_a_reversed_index_is_put_in_order_and_ranks_as_the_clean_frame(base, baseline):
    pd.testing.assert_series_equal(_rank(base.sort_index(ascending=False))["Score"], baseline["Score"])


def test_time_ordered_keeps_the_last_copy_of_a_date():
    idx = pd.to_datetime(["2026-01-02", "2026-01-01", "2026-01-02"])
    out = time_ordered(pd.DataFrame({"A": [1.0, 2.0, 3.0]}, index=idx))
    assert list(out.index) == list(pd.to_datetime(["2026-01-01", "2026-01-02"]))
    assert list(out["A"]) == [2.0, 3.0]


def test_a_constant_price_is_not_ranked(base):
    flat = base.copy()
    flat["S0"] = 50.0                    # no volatility: a risk-adjusted score has no value
    r = _rank(flat)
    assert "S0" not in set(r["Symbol"]) and len(r) == 5
    _no_infinities(r)


def test_identical_series_share_a_rank(base):
    twin = base.copy()
    twin["S1"] = twin["S2"]
    r = _rank(twin).set_index("Symbol")
    assert r.loc["S1", "Score"] == r.loc["S2", "Score"]
    assert r.loc["S1", "Rank"] == r.loc["S2", "Rank"]


def test_holes_in_a_series_leave_finite_scores(base):
    holed = base.copy()
    holed.iloc[100:130, 3] = np.nan
    holed.iloc[::7, 4] = np.nan
    r = _rank(holed)
    assert len(r) >= 5
    _no_infinities(r)


def test_a_short_history_has_no_six_month_rank_but_is_still_ranked(base):
    late = base.copy()
    late.iloc[:300, 5] = np.nan          # 100 sessions: enough to rank, too few for -6M
    r = _rank(late).set_index("Symbol")
    assert "S5" in r.index and pd.isna(r.loc["S5", "Rank (-6M)"])


def test_a_one_stock_industry_ranks_as_any_other(base, baseline):
    r = _rank(base, industries=["A"] * 5 + ["B"])
    pd.testing.assert_series_equal(r["Score"], baseline["Score"])


def test_a_zero_close_ranks_last_and_is_never_a_buy(base):
    zero = base.copy()
    zero.iloc[-1, 5] = 0.0               # a data fault; the score reads it as a total loss
    r = _rank(zero)
    assert r.iloc[-1]["Symbol"] == "S5"
    _no_infinities(r)


def test_one_stock_alone_has_no_ranking(base):
    """A z-score across one stock is undefined: nothing is ranked rather than a made-up score."""
    assert _rank(base[["S0"]]).empty
