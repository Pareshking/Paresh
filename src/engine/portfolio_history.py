"""Our strategy's monthly returns from 2010, for evidence about OUR book (TODO S110).

Owner, 8 Nov 2026: a signal goes on the Dashboard only if it shows in the
portfolio's own results, not only in the momentum factor's. This runs the
record's configuration (track_record.TRACK_RECORD_CONFIG) on NSE's long
adjusted closes over the Nifty 500 as it stood (index_universe), and returns
each month's return beside the Nifty 500's. It is NOT the Backtest page's
default run: the record's config keeps the monthly reset until the 30 Nov 2026
signal (and the record's industry map), while the Backtest applies the
six-monthly reset from 2010 (owner, 21 Nov 2026, decision G), so the two read
about 19.3% (data/momentum_health.csv, Feb 2010 to Oct 2026) and 18.8% a year. Moving these signal tests
to the new rule was not part of that decision.

Used by scripts/build_momentum_health.py (written into
data/momentum_health.csv as `portfolio` and `nifty500`) and the research in
scripts/research/.
"""

from __future__ import annotations

import pandas as pd

START = pd.Period("2010-01", "M")


def portfolio_months(close: pd.DataFrame, bench: pd.Series, index_key: str = "nifty_500") -> pd.DataFrame:
    """One row per month: `month` (str, YYYY-MM), `portfolio` and `nifty500` returns in %."""
    from src.engine import index_universe as iu
    from src.engine.backtester import run_backtest
    from src.engine.model_record import record_sector_map
    from src.engine.track_record import TRACK_RECORD_CONFIG as cfg

    membership = iu.index_history(index_key)
    cols = sorted(iu.ever_members(membership) & set(close.columns))
    frame = close.loc[:, cols].astype("float64")
    months = (pd.Period(frame.index[-1], "M") - START).n
    res = run_backtest(
        "portfolio_history", frame, top_n=cfg["top_n"], rebal_freq=21, ema_period=cfg["ema_period"],
        high_pct=cfg["high_pct"], weight_method=cfg["weight_method"], config_weights=cfg["config_weights"],
        cost_bps=cfg["cost_bps"], buffer_n=cfg["buffer_n"], stock_cap=cfg["stock_cap"],
        sector_cap=cfg["sector_cap"], sector_map=record_sector_map(cols), _benchmark_close=bench,
        backtest_months=months, _membership=membership, stateful_history=True,
        history_start=START.start_time, _actions=[],
        members_only_scoring_from=cfg.get("members_only_scoring_from"),
        ema_warmup_from=cfg.get("ema_warmup_from"),
        hold_cap=cfg.get("hold_cap"), hold_cap_from=cfg.get("hold_cap_from"),
        buy_size=cfg.get("buy_size"),
        weight_reset_months=tuple(cfg.get("weight_reset_months") or ()) or None)
    eq = pd.Series((res or {}).get("equity_curve")).dropna()
    if eq.empty:
        return pd.DataFrame(columns=["month", "portfolio", "nifty500"])
    eq.index = pd.DatetimeIndex(eq.index)
    b = pd.to_numeric(bench, errors="coerce").dropna()
    b.index = pd.DatetimeIndex(b.index)
    me = eq.resample("ME").last()
    bm = b.resample("ME").last().reindex(me.index)
    out = pd.DataFrame({"portfolio": me.pct_change() * 100, "nifty500": bm.pct_change() * 100}).dropna()
    out["month"] = out.index.to_period("M").astype(str)
    return out.reset_index(drop=True)[["month", "portfolio", "nifty500"]]


