"""The parameter sweep must test what the page shows (TODO S74, 9 Oct 2026).

The sweep has since left the page (owner, 9 Oct); these pin the engine for
offline use, so a scripted sweep can be handed the same context.

The Backtest page passed the sweep none of its window, universe, floor or
corporate actions. In History mode a sweep therefore scored the last 6 months
against the Nifty 750's membership: on the real Nifty 500 history the base
run read Sharpe 4.74 over Apr-Sep 2026 against the page's 0.68 over
2010-2026, and the holdout split those 6 months 3 + 3.
"""

import numpy as np
import pandas as pd
import pytest

from src.engine import parameter_sweep as ps
from src.engine.backtester import run_backtest

_RUN = run_backtest
while hasattr(_RUN, "__wrapped__"):
    _RUN = _RUN.__wrapped__


def _prices(n_days=800, n=30, seed=11):
    idx = pd.bdate_range("2021-01-04", periods=n_days)
    rng = np.random.default_rng(seed)
    lr = rng.normal(rng.normal(0.0004, 0.0005, n), rng.uniform(0.01, 0.03, n), (n_days, n))
    return pd.DataFrame(100 * np.exp(np.cumsum(lr, axis=0)), index=idx,
                        columns=[f"S{i:02d}" for i in range(n)])


@pytest.mark.parametrize("months,freq", [(12, 21), (18, 21), (9, 10)])
def test_the_page_window_is_the_same_run_without_stateful_mode(months, freq):
    """Why the sweep can pass the page's months instead of its stateful start:
    a stateful run from the window's first month equals the non-stateful run
    over the same months, trade for trade (also checked on the 2010 Nifty 500
    history: equity curve and all 5,800 trades identical)."""
    prices = _prices()
    last = pd.Period(prices.index[-1], freq="M") - 1
    start = (last - months + 1).start_time
    page = _RUN("p", prices, rebal_freq=freq, backtest_months=months,
                stateful_history=True, history_start=start)
    sweep = _RUN("s", prices, rebal_freq=freq, backtest_months=months)
    pd.testing.assert_series_equal(page["equity_curve"], sweep["equity_curve"])
    pd.testing.assert_frame_equal(page["tradebook"], sweep["tradebook"])


def test_the_sweep_runs_on_the_pages_window_universe_floor_and_actions(monkeypatch):
    seen = []

    def fake_run(tag, prices, **kw):
        seen.append(kw)
        return None

    monkeypatch.setattr(ps, "run_backtest", fake_run)
    mem, actions, traded = {"index": "x"}, [{"symbol": "S01"}], pd.DataFrame()
    ps.run_parameter_sweep(_prices(), {"Holdings": [10, 20]}, backtest_months=120,
                           _membership=mem, _actions=actions, liquidity_floor_cr=5.0,
                           _traded_value=traded)
    assert len(seen) == 2
    for kw in seen:
        assert kw["backtest_months"] == 120
        assert kw["_membership"] is mem and kw["_actions"] is actions
        assert kw["liquidity_floor_cr"] == 5.0 and kw["_traded_value"] is traded
