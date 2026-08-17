import pandas as pd
import numpy as np

def _monthly_rebalance_dates(dates, start_offset):
    dates = pd.DatetimeIndex(dates)
    eligible = dates[start_offset:]
    month_keys = eligible.to_period("M")
    idx_values = np.arange(start_offset, len(dates))
    return [int(i) for i in pd.Series(idx_values, index=eligible).groupby(month_keys).last().to_numpy()]

def test_month_end_is_last_available_session():
    dates = pd.DatetimeIndex([
        "2026-01-02", "2026-01-29", "2026-01-30", "2026-02-02",
        "2026-02-26", "2026-02-27", "2026-03-02", "2026-03-30", "2026-03-31",
    ])
    got = _monthly_rebalance_dates(dates, 0)
    assert [dates[i] for i in got] == [pd.Timestamp("2026-01-30"), pd.Timestamp("2026-02-27"), pd.Timestamp("2026-03-31")]

def test_next_session_is_execution_day():
    dates = pd.DatetimeIndex(["2026-01-29", "2026-01-30", "2026-02-02", "2026-02-27", "2026-03-02"])
    rebals = _monthly_rebalance_dates(dates, 0)
    assert dates[rebals[0] + 1] == pd.Timestamp("2026-02-02")
    assert dates[rebals[1] + 1] == pd.Timestamp("2026-03-02")
