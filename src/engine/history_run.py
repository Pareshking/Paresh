"""History from 2010: one way to prepare and run it, shared by the app and the precompute.

Owner, 2026-10-07: the app goes down on the free plan, and a History backtest
computed live peaked at ~870 MB on top of the app's ~380 MB. So the default
runs are computed once on GitHub after each long-file build
(scripts/precompute_history.py, src/loaders/history_store.py) and the
Backtest page reads them; a run with other settings is computed here, live,
exactly as before. Both paths go through prepare() and run(), so a stored
result is the result the page would have computed.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from src.engine import index_universe as iu
from src.engine.backtester import run_backtest
from src.engine.pipeline import price_fingerprint
from src.loaders import former_members, nse_long


def month_range(close_index: pd.DatetimeIndex, membership: dict) -> list[pd.Period]:
    """The months a History run may report: a year of warm-up first, the last one completed."""
    first = max(iu.first_month(membership), pd.Period(close_index[0], freq="M") + 13)
    last = pd.Period(close_index[-1], freq="M") - 1
    return list(pd.period_range(first, last, freq="M")) if first <= last else []


def industries(rank_industry: dict[str, str], cols: list[str], historical: dict[str, str]) -> tuple[dict, int]:
    """(industry per symbol for the cap, how many have none on record).

    The current lists, then TradingView mapped to NSE's names, then NSE's sector
    for names that left before today's lists (data/reference/historical_industries.csv).
    A stock nothing places is its own group, not one shared "Other".
    """
    sec = dict(rank_industry)
    sec.update(former_members.industry_for([c for c in cols if c not in sec]))
    sec.update({c: historical[c] for c in cols if sec.get(c, "Other") == "Other" and c in historical})
    unlabelled = [c for c in cols if sec.get(c, "Other") == "Other"]
    sec.update({c: f"Unlabelled · {c}" for c in unlabelled})
    return sec, len(unlabelled)


def prepare(close: pd.DataFrame, value: pd.DataFrame | None, key: str, start: pd.Period, end: pd.Period,
            floor: float, rank_industry: dict[str, str], historical: dict[str, str]) -> dict[str, Any]:
    """The frames and settings one History run needs (what the Backtest page used to build inline)."""
    membership = iu.index_history(key)
    # The frame ends at the first session after the end month: the engine reports
    # the completed months before its last session's month.
    after = close.index[close.index >= (end + 1).start_time]
    cut = after[0] if len(after) else close.index[-1]
    cols = sorted(iu.ever_members(membership) & set(close.columns))
    traded = None
    if floor and value is not None:
        traded = nse_long.average_value(value.reindex(columns=cols).loc[:cut])
    sec, unlabelled = industries(rank_industry, cols, historical)
    return {
        "close": close.loc[:cut, cols], "membership": membership, "start": start, "end": end,
        "months": (end - start).n + 1, "floor": floor if traded is not None else 0.0,
        # The Nifty 50 against its own index; the others against the Nifty 500.
        "benchmark": ("^NSEI", "Nifty 50") if key == "nifty_50" else ("^CRSLDX", "Nifty 500"),
        "traded_value": traded, "sector_map": sec, "unlabelled": unlabelled, "name": iu.INDICES[key],
    }


def settings(*, top_n: int, rebal_freq: int, weight_method: str, weights, stock_cap: float,
             sector_cap: float, cost_bps: float, buffer_n: int) -> dict[str, Any]:
    """The engine settings of one run, in one canonical form (the stored runs' key)."""
    return {"top_n": int(top_n), "rebal_freq": int(rebal_freq), "weight_method": str(weight_method),
            "weights": [round(float(w), 6) for w in weights], "stock_cap": round(float(stock_cap), 6),
            "sector_cap": round(float(sector_cap), 6), "cost_bps": round(float(cost_bps), 6),
            "buffer_n": int(buffer_n)}


def run(prep: dict[str, Any], s: dict[str, Any], benchmark_close: pd.Series) -> dict[str, Any] | None:
    """One History backtest, exactly as the Backtest page runs it."""
    ph = price_fingerprint(prep["close"]) + "_"
    if prep["floor"] and prep["traded_value"] is not None:
        ph += f"_{price_fingerprint(prep['traded_value'])}"
    return run_backtest(
        ph, prep["close"], _benchmark_close=benchmark_close, top_n=s["top_n"], rebal_freq=s["rebal_freq"],
        weight_method=s["weight_method"], config_weights=tuple(s["weights"]), stock_cap=s["stock_cap"],
        sector_cap=s["sector_cap"], sector_map=prep["sector_map"], cost_bps=s["cost_bps"],
        buffer_n=s["buffer_n"], _membership=prep["membership"], backtest_months=prep["months"],
        stateful_history=True, history_start=prep["start"].start_time, _actions=[],
        liquidity_floor_cr=prep["floor"], _traded_value=prep["traded_value"])
