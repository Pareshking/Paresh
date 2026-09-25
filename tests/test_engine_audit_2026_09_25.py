"""Regressions from the 2026-09-25 line-by-line engine audit."""
import json
import logging

import numpy as np
import pandas as pd
import pytest

from src.engine.breadth import compute_hl_timeseries
from src.engine.calendar_momentum import _calendar_period_metrics
from src.engine.corporate_actions import adjust_prices, load_events
from src.engine.momentum import MomentumEngine


def _frame(n: int, cols: int = 4, end: str = "2026-08-18", seed: int = 1):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range(end=end, periods=n)
    return pd.DataFrame(
        100 * np.exp(np.cumsum(rng.normal(0.0005, 0.02, (n, cols)), axis=0)),
        index=idx,
        columns=[f"S{i}" for i in range(cols)],
    )


def test_12m_return_is_nan_when_the_frame_is_shorter_than_twelve_months():
    px = _frame(170)  # ~8 months
    lr = np.log(px / px.shift(1))
    _, last_ret_12, sharpe_12, _ = _calendar_period_metrics(
        px, lr, 12, latest_as_of=px.index[-1]
    )
    _, last_ret_3, _, _ = _calendar_period_metrics(px, lr, 3, latest_as_of=px.index[-1])
    assert last_ret_12.isna().all(), "12M return must not be measured over 8 months"
    assert sharpe_12.iloc[-1].isna().all()
    assert last_ret_3.notna().all()


def test_max_dd_is_nan_for_a_horizon_the_frame_cannot_cover():
    px = _frame(170)
    calc = MomentumEngine(px)
    calc._precompute_signals(pd.DataFrame({"Symbol": px.columns}), pd.Series(dtype=float))
    signals = calc._static_signals
    assert signals["Max DD 12M"].isna().all()
    assert signals["Max DD 3M"].notna().all()


def test_persistence_counts_the_sessions_inside_the_window_only():
    px = _frame(300)
    calc = MomentumEngine(px)
    from src.engine.calendar_momentum import apply_calendar_momentum

    apply_calendar_momentum(calc)
    start = calc.period_dates[6]["actual_start"]
    inside = calc.log_ret.loc[start:].iloc[1:]
    expected = ((inside > 0).sum() / inside.notna().sum() * 100).round(1)
    pd.testing.assert_series_equal(calc.compute_persistence(months=6), expected)


def test_split_is_neutralised_even_when_its_own_session_is_a_hole():
    idx = pd.bdate_range("2026-06-01", periods=10)
    px = pd.DataFrame({"X": [300.0] * 5 + [np.nan] + [100.0] * 4}, index=idx)
    event = {"symbol": "X", "date": str(idx[5].date()), "ratio": 1 / 3}
    out, applied = adjust_prices(px, [event])
    assert applied, "the step is still in the data one session later"
    assert out["X"].iloc[:5].tolist() == pytest.approx([100.0] * 5)


def test_an_unreadable_corporate_actions_log_is_reported(tmp_path, caplog):
    bad = tmp_path / "corporate_actions_log.json"
    bad.write_text("{not json", encoding="utf-8")
    with caplog.at_level(logging.ERROR):
        assert load_events(bad) == []
    assert any("unreadable" in r.getMessage() for r in caplog.records)
    good = tmp_path / "ok.json"
    good.write_text(json.dumps({"events": {"a": {"symbol": "X"}}}), encoding="utf-8")
    assert load_events(good) == [{"symbol": "X"}]


def test_new_high_share_is_measured_over_stocks_that_can_have_one():
    idx = pd.bdate_range("2025-01-01", periods=300)
    seasoned = pd.Series(np.linspace(100, 200, 300), index=idx)  # new high daily
    listed_late = pd.Series(np.nan, index=idx)
    listed_late.iloc[-50:] = 100.0  # too young for a 252-day window
    px = pd.DataFrame({"OLD": seasoned, "NEW": listed_late})
    hl = compute_hl_timeseries("hl-denominator", px, window=252, lookback=10)
    assert (hl["Total Stocks"] == 1).all()
    assert (hl["% New Highs"] == 100.0).all()


def test_windows_count_back_from_the_last_price_not_from_today():
    """Decision 1B: one unchanged file must rank identically on any day."""
    from src.engine.calendar_momentum import latest_as_of_date

    recent = pd.bdate_range(end=pd.Timestamp.today().normalize() - pd.Timedelta(days=2), periods=30)
    assert latest_as_of_date(recent) == recent[-1].normalize()
