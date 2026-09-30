"""Backtest reporting must not inherit pre-inception portfolio ownership."""
import pandas as pd

from src.engine.backtester import _build_rebalance_schedule


def test_stateful_schedule_starts_at_canonical_inception_but_keeps_warmup():
    dates = pd.bdate_range("2024-01-01", "2026-09-30")
    schedule = _build_rebalance_schedule(
        dates.to_frame(name="x"),
        start_offset=260,
        rebal_freq=21,
        backtest_months=8,
        stateful_history=True,
        history_start=pd.Timestamp("2026-01-01"),
    )
    assert schedule is not None
    rebal_dates, _all_signals, _last_sim_idx, window_end = schedule
    executions = [dates[i + 1] for i in rebal_dates]
    assert executions
    assert min(executions) >= pd.Timestamp("2026-01-01")
    assert max(executions) <= window_end
    assert window_end == pd.Timestamp("2026-08-31")
