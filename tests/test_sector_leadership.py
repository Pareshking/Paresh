"""The sector leadership map: return against the equal-weighted market across
(S147), the share of a sector's stocks above their EMA up, a month ago and today."""

import numpy as np
import pandas as pd

from src.engine.sector_breadth import leadership_dates, sector_leadership


def _frame():
    idx = pd.bdate_range("2026-01-01", "2026-10-12")
    n = len(idx)
    up = np.linspace(100, 200, n)
    down = np.linspace(200, 100, n)
    prices = pd.DataFrame({"A1": up, "A2": up, "B1": down, "B2": up, "C1": up}, index=idx)
    groups = pd.Series({"A1": "Alpha", "A2": "Alpha", "B1": "Beta", "B2": "Beta", "C1": "Solo"})
    bench = pd.Series(np.full(n, 1000.0), index=idx)
    return prices, groups, bench


def test_dates_are_calendar_months_back_to_a_session():
    idx = pd.bdate_range("2026-08-01", "2026-10-12")
    before, then, now = leadership_dates(idx)
    assert now == pd.Timestamp("2026-10-12")
    # 12 Sep 2026 is a Saturday: the session on or before it is Friday the 11th.
    assert then == pd.Timestamp("2026-09-11")
    assert before == pd.Timestamp("2026-08-11")


def test_breadth_and_relative_return_by_hand():
    prices, groups, bench = _frame()
    board = sector_leadership(prices, groups, bench, span=20).set_index("Sector")
    # A sector of one is a stock, not a sector.
    assert set(board.index) == {"Alpha", "Beta"}
    a, b = board.loc["Alpha"], board.loc["Beta"]
    assert (a.above_now, a.obs_now, a.y_now) == (2, 2, 1.0)
    assert (b.above_now, b.obs_now, b.y_now) == (1, 2, 0.5)
    then, now = a.Then, a.Now
    # By hand: daily-rebalanced equal weights. The market is every grouped
    # stock (the single-stock sector's too); Alpha is A1 itself (A1 == A2).
    ew = lambda cols: (1 + prices[cols].pct_change().mean(axis=1)).fillna(1).cumprod()  # noqa: E731
    mkt = ew(["A1", "A2", "B1", "B2", "C1"])
    m_now = mkt.loc[now] / mkt.loc[then] - 1
    assert abs(a.x_now - ((prices.loc[now, "A1"] / prices.loc[then, "A1"] - 1) - m_now)) < 1e-12
    beta = ew(["B1", "B2"])
    assert abs(b.x_now - ((beta.loc[now] / beta.loc[then] - 1) - m_now)) < 1e-12
    assert abs(a.bench_now - m_now) < 1e-12


def test_the_nifty_500_no_longer_moves_the_reading():
    # S147: an equal-weighted sector against the cap-weighted Nifty 500 read a
    # large-company rally as every sector lagging. The index may soar; x stays.
    prices, groups, bench = _frame()
    board0 = sector_leadership(prices, groups, bench, span=20).set_index("Sector")
    then = board0.loc["Alpha", "Then"]
    bench = bench.copy()
    bench[bench.index > then] = 1100.0
    bench[pd.Timestamp("2026-10-13")] = 5000.0
    board = sector_leadership(prices, groups, bench, span=20).set_index("Sector")
    assert abs(board0.loc["Alpha", "x_now"] - board.loc["Alpha", "x_now"]) < 1e-12
    # Sectors are read against their own market, so they straddle zero.
    assert (board["x_now"] > 0).any() and (board["x_now"] < 0).any()


def test_a_stock_without_a_print_is_not_counted_below():
    prices, groups, bench = _frame()
    prices.loc[prices.index[-1], "B1"] = np.nan
    b = sector_leadership(prices, groups, bench, span=20).set_index("Sector").loc["Beta"]
    assert (b.above_now, b.obs_now) == (1, 1)


def test_short_history_returns_empty():
    idx = pd.bdate_range("2026-10-01", "2026-10-12")
    prices = pd.DataFrame({"A1": 1.0, "A2": 1.0}, index=idx)
    out = sector_leadership(prices, pd.Series({"A1": "X", "A2": "X"}), pd.Series(1.0, index=idx))
    assert out.empty






def test_three_month_period_and_the_two_heavy_lifters():
    prices, groups, bench = _frame()
    one = sector_leadership(prices, groups, bench, span=20).set_index("Sector")
    three = sector_leadership(prices, groups, bench, span=20, months=3).set_index("Sector")
    assert three.loc["Alpha", "Then"] == pd.Timestamp("2026-07-10")  # 12 Jul is a Sunday
    assert three.loc["Alpha", "Months"] == 3 and one.loc["Alpha", "Months"] == 1
    # Beta: B2 rose, B1 fell, so B2 leads; each leader carries its own return.
    lead = three.loc["Beta", "Leaders"]
    assert [s for s, _ in lead] == ["B2", "B1"]
    then, now = three.loc["Beta", "Then"], three.loc["Beta", "Now"]
    assert abs(lead[0][1] - (prices.loc[now, "B2"] / prices.loc[then, "B2"] - 1)) < 1e-12
