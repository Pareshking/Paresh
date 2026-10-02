"""A system that starts this month (Nano Cap, Combined) has a book from its first fill.

Its first book is signalled at the last close before inception and filled on the
first session after. That rebalance sits outside the window of COMPLETED months,
and no earlier month holds one, so the run used to return nothing and Actions
said "the model book is not available".
"""
import numpy as np
import pandas as pd

import src.engine.pipeline  # noqa: F401  (imported before momentum: they import each other)
from src.engine.backtester import run_backtest


def _prices(last="2026-10-01", n_sessions=420, n_stocks=40):
    idx = pd.bdate_range(end=last, periods=n_sessions)
    rng = np.random.default_rng(7)
    drift = np.linspace(0.0002, 0.0012, n_stocks)
    steps = rng.normal(drift, 0.01, size=(n_sessions, n_stocks))
    return pd.DataFrame(100 * np.exp(np.cumsum(steps, axis=0)), index=idx,
                        columns=[f"S{i:02d}" for i in range(n_stocks)])


def _run(prices, history_start):
    # The name keys the engine's cache, so it must differ with the data.
    return run_backtest(
        f"first_month_{prices.index[-1]:%Y%m%d}", prices, top_n=10, rebal_freq=21, ema_period=20, high_pct=0.0,
        weight_method="Equal", backtest_months=1, stateful_history=True,
        history_start=history_start, _actions=[], stock_cap=0.5, sector_cap=1.0,
        sector_map={c: "X" for c in prices.columns},
    )


def test_the_first_fill_is_a_book_even_with_no_completed_month():
    prices = _prices()
    res = _run(prices, pd.Timestamp("2026-10-01"))
    assert res is not None
    book = res["live_book"]
    assert len(book) == 10
    assert res["live_meta"]["signal_date"] == pd.Timestamp("2026-09-30")
    assert res["live_meta"]["fill_date"] == pd.Timestamp("2026-10-01")
    assert res["equity_curve"].empty and res["monthly"].empty    # nothing accrued yet


def test_no_signal_after_inception_still_means_no_result():
    prices = _prices(last="2026-09-30")
    assert _run(prices, pd.Timestamp("2026-10-01")) is None
