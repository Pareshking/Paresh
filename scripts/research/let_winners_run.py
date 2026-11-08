"""Let winners run to 15% against the monthly reset to 5% (owner, 8 Nov 2026;
read-only research, TODO S111).

Today's rule: at every monthly rebalance every holding goes back to its target
(1/20 = 5%), so a winner is trimmed and a laggard topped up. The variant
(backtester `hold_cap`): a kept holding keeps the weight the market gave it,
trimmed only above 15%; money from sells and trims goes to the new buys in
equal shares. Same selection, filters, buffer, costs (30 bps on one-way
turnover, trims included) and prices.

Two runs each:
  history   Nifty 500 as it stood, Jan 2010 to date (Backtest's History from 2010)
  record    Nifty Total Market (the live 750), Jan 2026 to date: the live
            record's universe; months compared with data/track_record.json

    python scripts/research/let_winners_run.py <nse_long_close.parquet>
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.engine import index_universe as iu  # noqa: E402
from src.engine.backtester import run_backtest  # noqa: E402
from src.engine.model_record import record_sector_map  # noqa: E402
from src.engine.track_record import TRACK_RECORD_CONFIG as cfg  # noqa: E402

HOLD_CAP = 0.15


def run(close, bench, index_key, start, hold_cap):
    membership = iu.index_history(index_key)
    cols = sorted(iu.ever_members(membership) & set(close.columns))
    frame = close.loc[:, cols].astype("float64")
    months = (pd.Period(frame.index[-1], "M") - pd.Period(start, "M")).n
    fn = getattr(run_backtest, "__wrapped__", run_backtest)
    while hasattr(fn, "__wrapped__"):
        fn = fn.__wrapped__
    return fn(f"lwr-{index_key}-{hold_cap}", frame, top_n=cfg["top_n"], rebal_freq=21, ema_period=cfg["ema_period"],
              high_pct=cfg["high_pct"], weight_method=cfg["weight_method"], config_weights=cfg["config_weights"],
              cost_bps=cfg["cost_bps"], buffer_n=cfg["buffer_n"], stock_cap=cfg["stock_cap"],
              sector_cap=cfg["sector_cap"], sector_map=record_sector_map(cols), _benchmark_close=bench,
              backtest_months=months, _membership=membership, stateful_history=True,
              history_start=pd.Timestamp(start), _actions=[], hold_cap=hold_cap)


def summary(res, bench) -> dict:
    eq = pd.Series(res["equity_curve"]).dropna()
    eq.index = pd.DatetimeIndex(eq.index)
    yrs = (eq.index[-1] - eq.index[0]).days / 365.25
    daily = eq.pct_change().dropna()
    dd = eq / eq.cummax() - 1
    m = eq.resample("ME").last().pct_change().dropna()
    b = bench.reindex(eq.index, method="ffill")
    out = {"total %": (eq.iloc[-1] / eq.iloc[0] - 1) * 100, "a year %": ((eq.iloc[-1] / eq.iloc[0]) ** (1 / yrs) - 1) * 100,
           "volatility %": daily.std() * np.sqrt(252) * 100, "worst drawdown %": dd.min() * 100,
           "Nifty 500 total %": (b.iloc[-1] / b.iloc[0] - 1) * 100,
           "turnover / month %": float(pd.DataFrame(res.get("monthly_df", res.get("periods", []))).get("Turnover %", pd.Series(dtype=float)).mean())}
    return out, m


def main(path: str) -> None:
    close = pd.read_parquet(path)
    if "date" in close.columns:
        close = close.set_index("date")
    close.index = pd.DatetimeIndex(close.index)
    bench = pd.read_csv(ROOT / "data" / "benchmarks.csv", parse_dates=["date"]).set_index("date")["nifty500"]
    rows, monthly = {}, {}
    for label, key, start in (("history", "nifty_500", "2010-01-01"), ("record", "nifty_total_market", "2026-01-01")):
        for name, cap in (("reset to 5%", None), (f"run to {HOLD_CAP:.0%}", HOLD_CAP)):
            res = run(close, bench, key, start, cap)
            s, m = summary(res, bench)
            rows[(label, name)] = s
            monthly[(label, name)] = m
            print(label, name, {k: round(v, 1) for k, v in s.items()}, flush=True)
    print("\n" + pd.DataFrame(rows).T.round(1).to_string())
    rec = json.load(open(ROOT / "data" / "track_record.json"))["months"]
    live = pd.Series({k: v["strategy"] * 100 for k, v in rec.items()})
    a, b = monthly[("record", "reset to 5%")], monthly[("record", f"run to {HOLD_CAP:.0%}")]
    t = pd.DataFrame({"recorded": live, "reset (rerun)": a.set_axis(a.index.strftime("%Y-%m")) * 100,
                      f"run to {HOLD_CAP:.0%}": b.set_axis(b.index.strftime("%Y-%m")) * 100})
    print("\nrecord months, % (recorded = data/track_record.json):")
    print(t.round(2).to_string())
    h_a, h_b = monthly[("history", "reset to 5%")], monthly[("history", f"run to {HOLD_CAP:.0%}")]
    yr = pd.DataFrame({"reset": (1 + h_a / 1).groupby(h_a.index.year).prod() - 1,
                       "run": (1 + h_b / 1).groupby(h_b.index.year).prod() - 1}) * 100
    yr["run - reset"] = yr["run"] - yr["reset"]
    print("\nhistory by calendar year, %:")
    print(yr.round(1).to_string())
    print(f"\nyears the variant beat the reset: {(yr['run - reset'] > 0).sum()} of {len(yr)}")


if __name__ == "__main__":
    main(sys.argv[1])
