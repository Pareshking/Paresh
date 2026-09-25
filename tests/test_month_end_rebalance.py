"""The backtester rebalances on the last session of each month and trades the next.

This file used to define its own copy of the month-end rule and test that copy,
so a change to the real schedule in src/engine/backtester.py could never fail
it. It now calls the production function.
"""
import numpy as np
import pandas as pd

from src.engine.backtester import _build_rebalance_schedule

DATES = pd.DatetimeIndex([
    "2026-01-02", "2026-01-29", "2026-01-30", "2026-02-02",
    "2026-02-26", "2026-02-27", "2026-03-02", "2026-03-30", "2026-03-31",
])


def _schedule(dates, **kw):
    prices = pd.DataFrame({"A": np.linspace(100, 110, len(dates))}, index=dates)
    return _build_rebalance_schedule(prices, start_offset=0, rebal_freq=21,
                                     backtest_months=kw.get("months", 120))


def test_the_signal_is_the_last_available_session_of_each_month():
    _rebal, all_signal, _last, _end = _schedule(DATES)
    assert [DATES[i] for i in all_signal] == [
        pd.Timestamp("2026-01-30"), pd.Timestamp("2026-02-27"), pd.Timestamp("2026-03-31"),
    ]


def test_each_rebalance_executes_on_the_next_session_inside_completed_months():
    rebal, _all, last_sim, window_end = _schedule(DATES)
    # The January signal trades on 2 Feb. The February signal would trade on
    # 2 Mar, but March is the month in progress (the data ends in it), and the
    # reported window holds only completed months -- so it is not reported.
    assert [DATES[i + 1] for i in rebal] == [pd.Timestamp("2026-02-02")]
    assert window_end == pd.Timestamp("2026-02-28")
    assert DATES[last_sim] == pd.Timestamp("2026-02-27")
