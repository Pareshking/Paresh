"""History mode's call into the engine: a 2010 window on a per-index timeline."""
import numpy as np
import pandas as pd

import src.engine.pipeline  # noqa: F401  (import order, as the app has it)
from src.engine.backtester import run_backtest
from src.engine import index_universe as iu

DAYS = pd.bdate_range("2008-01-01", "2011-02-15")
SYMS = [f"S{i:02d}" for i in range(30)]


def _prices() -> pd.DataFrame:
    rng = np.random.default_rng(7)
    drift = np.linspace(0.0002, 0.0012, len(SYMS))
    steps = rng.normal(drift, 0.012, size=(len(DAYS), len(SYMS)))
    return pd.DataFrame(100 * np.exp(np.cumsum(steps, axis=0)), index=DAYS, columns=SYMS)


FULL = {
    "schema_version": 2, "baseline": {"date": "2021-10-29", "symbols": SYMS}, "changes": [],
    "aliases": {},
    "indices": {"nifty_500": {
        "baseline": {"date": "2010-01-01", "symbols": SYMS[:20]},
        "changes": [{"date": "2010-07-01", "added": SYMS[20:], "removed": SYMS[:5]}]}},
}


def test_a_2010_window_reports_from_its_start_month_on_the_index_as_it_stood():
    membership = iu.index_history("nifty_500", FULL)
    start, end = pd.Period("2010-01", "M"), pd.Period("2010-12", "M")
    close = _prices()
    # As _history_inputs cuts it: up to the first session after the end month.
    cut = close.index[close.index >= (end + 1).start_time][0]
    frame = close.loc[:cut]
    bench = frame.mean(axis=1)
    res = run_backtest(
        "test_long_window", frame, _benchmark_close=bench, top_n=5, rebal_freq=21,
        config_weights=(0.1, 0.3, 0.3, 0.2, 0.1), stock_cap=0.25, sector_cap=1.0,
        sector_map={s: f"Unlabelled · {s}" for s in SYMS}, cost_bps=30.0, buffer_n=10,
        _membership=membership, backtest_months=(end - start).n + 1, stateful_history=True,
        history_start=start.start_time, _actions=[],
    )
    assert res is not None
    eq = res["equity_curve"]
    assert eq.index[0] >= pd.Timestamp("2010-01-01") and eq.index[0] < pd.Timestamp("2010-01-08")
    assert eq.index[-1] <= pd.Timestamp("2010-12-31")
    stats = res["stats"]
    assert stats["current_universe_periods"] == 0 and stats["pit_periods"] > 0
    # Nothing outside the index on its signal date was ever bought.
    tb = res["tradebook"]
    buys = tb[tb["Action"].str.contains("BUY")]
    early = buys[pd.to_datetime(buys["Period"].str[:11], errors="coerce") < pd.Timestamp("2010-07-01")]
    assert not set(early["Symbol"]) & set(SYMS[20:])
