"""The backtest reports the last N COMPLETED calendar months, nothing else.

The month in progress is excluded deliberately. Showing a part-month return
beside whole ones invites comparing three weeks against six full months, and
the partial figure changes every session until the month closes.

The formation history BEFORE the window is untouched: a rebalance inside the
window still scores on a full 12-month lookback. Only the reported span is cut.
"""
import numpy as np
import pandas as pd
import pytest

from src.engine.backtester import (
    DEFAULT_BACKTEST_MONTHS,
    completed_month_window,
    run_backtest,
)


def _prices(end: str, periods: int = 760, cols: int = 40, seed: int = 7):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range(end=end, periods=periods)
    return pd.DataFrame(
        100 + np.cumsum(rng.normal(0, 1, (periods, cols)), axis=0),
        index=idx,
        columns=[f"S{i}" for i in range(cols)],
    )


def _run(prices, tag, **kw):
    return run_backtest(
        tag, prices, top_n=20, rebal_freq=21,
        ranking_method="Composite (Multi-Window)", lookback_ret=126,
        ema_period=20, high_pct=0.0, cost_bps=30.0, buffer_n=30, **kw,
    )


def test_default_is_six_completed_months():
    assert DEFAULT_BACKTEST_MONTHS == 6


@pytest.mark.parametrize("as_of,expected", [
    ("2026-08-18", ("2026-02-01", "2026-07-31")),   # mid-month
    ("2026-08-31", ("2026-02-01", "2026-07-31")),   # last day of a month
    ("2026-01-04", ("2025-07-01", "2025-12-31")),   # window crosses the year
    ("2026-03-02", ("2025-09-01", "2026-02-28")),   # ends on a short month
])
def test_window_excludes_the_month_in_progress(as_of, expected):
    dates = pd.bdate_range("2023-01-01", as_of)
    start, end = completed_month_window(dates, 6)
    assert (str(start.date()), str(end.date())) == expected


def test_first_of_month_still_excludes_that_month():
    """On the 1st, the current month has one day -- it is still incomplete."""
    dates = pd.bdate_range("2023-01-01", "2026-08-03")
    start, end = completed_month_window(dates, 6)
    assert str(end.date()) == "2026-07-31"
    assert str(start.date()) == "2026-02-01"


def test_backtest_reports_exactly_six_monthly_periods():
    result = _run(_prices("2026-08-18"), "six")
    assert result is not None
    assert len(result["monthly"]) == 6


def test_backtest_stops_at_the_last_completed_month():
    result = _run(_prices("2026-08-18"), "stops")
    eq = result["equity_curve"]
    assert eq.index[-1] <= pd.Timestamp("2026-07-31")
    assert eq.index[0] >= pd.Timestamp("2026-02-01")


def test_window_length_is_configurable_and_honoured():
    prices = _prices("2026-08-18")
    assert len(_run(prices, "m3", backtest_months=3)["monthly"]) == 3
    assert len(_run(prices, "m12", backtest_months=12)["monthly"]) == 12


def test_formation_history_is_not_shortened_by_the_window():
    """Cutting the report must not cut the lookback: too little history -> None."""
    # 18 months of sessions is roughly 12 formation + 6 reported.
    assert _run(_prices("2026-08-18", periods=200), "short") is None
    assert _run(_prices("2026-08-18", periods=760), "long") is not None


@pytest.mark.parametrize("bad", [0, -1])
def test_non_positive_window_is_rejected(bad):
    with pytest.raises(ValueError):
        completed_month_window(pd.bdate_range("2025-01-01", "2026-08-18"), bad)


def test_empty_dates_are_rejected():
    with pytest.raises(ValueError):
        completed_month_window(pd.DatetimeIndex([]), 6)
