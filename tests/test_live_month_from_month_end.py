"""The live month is measured as its frozen month will be (owner, 12 Oct 2026).

A month that holds a rebalance was marked from the FILL close, so the fill-day
session -- earned by the old book -- sat in neither the frozen month before nor
the live one until the month froze. On 12 Oct 2026 Portfolio showed the Nifty 500
at -7.6% in the record and -8.4% from daily closes for the same months; measured
like-for-like from the first fill, both are -8.5%.
"""

import numpy as np
import pandas as pd
import pytest

from src.engine.backtester import run_backtest

DATES = pd.bdate_range("2023-01-02", "2026-11-04")


def _market(seed: int = 11, cols: int = 40):
    rng = np.random.default_rng(seed)
    steps = rng.normal(0.0004, 0.02, (len(DATES), cols))
    px = pd.DataFrame(100 * np.exp(np.cumsum(steps, axis=0)), index=DATES,
                      columns=[f"S{i}" for i in range(cols)])
    bench = pd.Series(1000 * np.exp(np.cumsum(rng.normal(0.0002, 0.01, len(DATES)))),
                      index=DATES)
    return px, bench


def _run(px, bench, tag, end, start="2025-11-01", months=12):
    return run_backtest(
        tag, px.loc[:end], _benchmark_close=bench.loc[:end], top_n=10, rebal_freq=21,
        ema_period=20, high_pct=0.0, cost_bps=30.0, buffer_n=15,
        stateful_history=True, history_start=pd.Timestamp(start), backtest_months=months,
    )


def test_the_live_month_equals_its_frozen_month_over_the_same_days():
    px, bench = _market()
    live = _run(px, bench, "lm_live", "2026-10-09")["live_meta"]
    frozen = _run(px, bench, "lm_frozen", "2026-11-04", months=13)
    assert live["mtd_basis"] == "rebalanced book" and live["fill_date"] == pd.Timestamp("2026-10-01")
    assert live["mtd_from"] == pd.Timestamp("2026-09-30"), "from the last close of September"
    assert live["mtd_pre_fill"] != 0.0, "the old book earned the fill day"

    eq, bm = frozen["equity_curve"], frozen["benchmark"]
    s30, o9 = pd.Timestamp("2026-09-30"), pd.Timestamp("2026-10-09")
    assert live["strategy_mtd"] == pytest.approx(eq[o9] / eq[s30] - 1.0, abs=2e-4)
    assert live["benchmark_mtd"] == pytest.approx(bm[o9] / bm[s30] - 1.0, rel=1e-9)
    assert live["benchmark_mtd"] == pytest.approx(bench[o9] / bench[s30] - 1.0, rel=1e-9)


def test_portfolio_counts_the_index_from_the_first_fill():
    """Portfolio's top row: since inception from the first fill, MTD from the month-end."""
    from src.ui.views.portfolio_view import _benchmark_returns_from_daily

    idx = pd.to_datetime(["2025-12-31", "2026-01-01", "2026-01-02",
                          "2026-09-30", "2026-10-01", "2026-10-09"])
    s = pd.Series([100.0, 101.0, 102.0, 90.0, 89.0, 91.0], index=idx)
    as_of = pd.Timestamp("2026-10-09")
    _, mtd, total = _benchmark_returns_from_daily(s, as_of, pd.Period("2026-01", "M"))
    assert total == pytest.approx(91 / 101 - 1), "from the 01 Jan fill, not the 31 Dec close"
    assert mtd == pytest.approx(91 / 90 - 1), "from the 30 Sep close"
    # A system that started this month: both from its first fill.
    _, mtd_new, total_new = _benchmark_returns_from_daily(s, as_of, pd.Period("2026-10", "M"))
    assert mtd_new == pytest.approx(91 / 89 - 1) and total_new == pytest.approx(91 / 89 - 1)


def test_a_systems_first_month_starts_at_its_first_fill():
    """No old book before the first fill: the strategy and the index both start there."""
    px, bench = _market(seed=5)
    meta = _run(px, bench, "lm_first", "2026-10-09", start="2026-10-01", months=1)["live_meta"]
    fill = meta["fill_date"]
    assert fill == pd.Timestamp("2026-10-01")
    assert meta["mtd_from"] == fill and meta["mtd_pre_fill"] == 0.0
    o9 = pd.Timestamp("2026-10-09")
    assert meta["benchmark_mtd"] == pytest.approx(bench[o9] / bench[fill] - 1.0, rel=1e-9)
