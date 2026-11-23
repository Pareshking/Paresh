"""Skip the last N sessions of the score, through the app's own engine (owner, 20 Nov 2026; TODO S160).

Read-only research. The Backtest page's "History from 2010" run (the record's
configuration, as src/engine/portfolio_history.py: point-in-time Nifty 500,
20 holdings kept while in the top 40, 50-day EMA, within 20% of the 52-week
high, lookback weights 10/30/30/20/10, 5% stock / 40% sector caps, 30 bps), with
run_backtest's research option `score_skip`: the composite is read N sessions
before the signal; gates, membership and fills stay on the signal date.

    python scripts/research/score_skip_engine.py 0 1 3 5 7 10 21

Writes one JSON line per skip to stdout: CAGR, max drawdown, Sharpe (6.5% cash),
worst 12 months, per period, and the yearly returns.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.engine import index_universe as iu  # noqa: E402
from src.engine.backtester import run_backtest  # noqa: E402
from src.engine.metrics import max_drawdown  # noqa: E402
from src.engine.model_record import record_sector_map  # noqa: E402
from src.engine.track_record import TRACK_RECORD_CONFIG as cfg  # noqa: E402
from src.loaders import nse_long  # noqa: E402

START = pd.Period("2010-01", "M")
PERIODS = {"all": ("2010-01", "2026-12"), "2010-17": ("2010-01", "2017-12"), "2018-26": ("2018-01", "2026-12")}
RF = 0.065


def stats(r: pd.Series) -> dict:
    q = (1 + r).cumprod()
    return {"cagr": float(q.iloc[-1] ** (12 / len(r)) - 1),
            "maxdd": max_drawdown(q),
            "sharpe": float((r.mean() - RF / 12) / r.std(ddof=0) * np.sqrt(12)),
            "worst12": float(((1 + r).rolling(12).apply(np.prod, raw=True) - 1).min()),
            "months": len(r)}


def run(close: pd.DataFrame, bench: pd.Series, skip: int) -> dict:
    membership = iu.index_history("nifty_500")
    cols = sorted(iu.ever_members(membership) & set(close.columns))
    frame = close.loc[:, cols].astype("float64")
    months = (pd.Period(frame.index[-1], "M") - START).n
    res = run_backtest(
        f"score_skip_{skip}", frame, top_n=cfg["top_n"], rebal_freq=21, ema_period=cfg["ema_period"],
        high_pct=cfg["high_pct"], weight_method=cfg["weight_method"], config_weights=cfg["config_weights"],
        cost_bps=cfg["cost_bps"], buffer_n=cfg["buffer_n"], stock_cap=cfg["stock_cap"],
        sector_cap=cfg["sector_cap"], sector_map=record_sector_map(cols), _benchmark_close=bench,
        backtest_months=months, _membership=membership, stateful_history=True,
        history_start=START.start_time, _actions=[],
        members_only_scoring_from=cfg.get("members_only_scoring_from"),
        ema_warmup_from=cfg.get("ema_warmup_from"), window_rule_from=cfg.get("window_rule_from"),
        hold_cap=cfg.get("hold_cap"), hold_cap_from=cfg.get("hold_cap_from"),
        buy_size=cfg.get("buy_size"),
        weight_reset_months=tuple(cfg.get("weight_reset_months") or ()) or None,
        score_skip=skip)
    eq = pd.Series(res["equity_curve"]).dropna()
    eq.index = pd.DatetimeIndex(eq.index)
    me = eq.resample("ME").last()
    r = me.pct_change().dropna()
    r.index = r.index.to_period("M")
    out = {"skip": skip, "first": str(r.index.min()), "last": str(r.index.max()),
           "turnover": res.get("metrics", {}).get("Avg Turnover") if isinstance(res.get("metrics"), dict) else None}
    for name, (lo, hi) in PERIODS.items():
        out[name] = stats(r[(r.index >= pd.Period(lo, "M")) & (r.index <= pd.Period(hi, "M"))])
    ye = eq.resample("YE").last()
    yr = pd.concat([pd.Series([eq.iloc[0]], index=[eq.index[0]]), ye]).pct_change().dropna()
    out["years"] = {str(d.year): round(float(v) * 100, 1) for d, v in yr.items()}
    out["monthly"] = {str(k): float(v) for k, v in r.items()}
    return out


def main() -> int:
    skips = [int(x) for x in sys.argv[1:]] or [0, 5]
    close = nse_long.load(with_value=False)[0]
    bench = pd.read_csv(ROOT / "data" / "benchmarks.csv", parse_dates=["date"]).set_index("date")["nifty500"]
    for s in skips:
        print(json.dumps(run(close, bench, s)), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
