"""The owner's buy rule against the others (owner, 8 Nov 2026; read-only research, TODO S111).

  reset        today's record until 30 Nov 2026: every holding back to 5% each month
  run15_freed  winners run to 15%; new buys share the money freed by sales (the merged
               code, which the owner said is not the rule)
  owner        winners run to 15%; each new buy is 5% of the account at the last
               31 March, paid from cash; short of cash, fewer shares; leftover stays
               cash; no kept name sold to fund a buy (backtester `buy_size`)

Same selection, filters, buffer, 30 bps on every trade, NSE long adjusted closes.
Runs: Nifty 500 as it stood, Jan 2010 to date; the live 750, Jan 2026 to date.

    python scripts/research/fixed_buys.py <nse_long_close.parquet>
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import src.engine.backtester as bt  # noqa: E402
from src.engine import index_universe as iu  # noqa: E402
from src.engine.model_record import record_sector_map  # noqa: E402
from src.engine.track_record import TRACK_RECORD_CONFIG as cfg  # noqa: E402

CASH: list[float] = []
_orig = bt._fixed_buys


def _spy(*a, **k):
    out = _orig(*a, **k)
    CASH.append(float(out.attrs.get("cash", 0.0)))
    return out


bt._fixed_buys = _spy


def run(close, bench, key, start, hold_cap, buy_size):
    membership = iu.index_history(key)
    cols = sorted(iu.ever_members(membership) & set(close.columns))
    frame = close.loc[:, cols].astype("float64")
    months = (pd.Period(frame.index[-1], "M") - pd.Period(start, "M")).n
    fn = bt.run_backtest
    while hasattr(fn, "__wrapped__"):
        fn = fn.__wrapped__
    return fn(f"fb-{key}-{hold_cap}-{buy_size}", frame, top_n=cfg["top_n"], rebal_freq=21,
              ema_period=cfg["ema_period"], high_pct=cfg["high_pct"], weight_method=cfg["weight_method"],
              config_weights=cfg["config_weights"], cost_bps=cfg["cost_bps"], buffer_n=cfg["buffer_n"],
              stock_cap=cfg["stock_cap"], sector_cap=cfg["sector_cap"], sector_map=record_sector_map(cols),
              _benchmark_close=bench, backtest_months=months, _membership=membership,
              stateful_history=True, history_start=pd.Timestamp(start), _actions=[],
              hold_cap=hold_cap, buy_size=buy_size)


def stats(res):
    eq = pd.Series(res["equity_curve"]).dropna()
    eq.index = pd.DatetimeIndex(eq.index)
    yrs = (eq.index[-1] - eq.index[0]).days / 365.25
    d = eq.pct_change().dropna()
    m = eq.resample("ME").last().pct_change().dropna()
    return {"total %": (eq.iloc[-1] / eq.iloc[0] - 1) * 100,
            "a year %": ((eq.iloc[-1] / eq.iloc[0]) ** (1 / yrs) - 1) * 100,
            "volatility %": d.std() * np.sqrt(252) * 100,
            "worst drawdown %": (eq / eq.cummax() - 1).min() * 100}, m


def main(path: str) -> None:
    close = pd.read_parquet(path)
    if "date" in close.columns:
        close = close.set_index("date")
    close.index = pd.DatetimeIndex(close.index)
    bench = pd.read_csv(ROOT / "data" / "benchmarks.csv", parse_dates=["date"]).set_index("date")["nifty500"]
    rules = {"reset": (None, None), "run15_freed": (0.15, None), "owner": (0.15, 0.05)}
    table, months = {}, {}
    for label, key, start in (("history", "nifty_500", "2010-01-01"), ("record", "nifty_total_market", "2026-01-01")):
        for name, (cap, size) in rules.items():
            CASH.clear()
            s, m = stats(run(close, bench, key, start, cap, size))
            if size is not None and CASH:
                s["avg cash after buys %"] = float(np.mean(CASH)) * 100
                s["max cash after buys %"] = float(np.max(CASH)) * 100
            table[(label, name)] = s
            months[(label, name)] = m
            print(label, name, {k: round(v, 1) for k, v in s.items()}, flush=True)
    print("\n" + pd.DataFrame(table).T.round(1).to_string())
    h = {n: months[("history", n)] for n in rules}
    yr = pd.DataFrame({n: (1 + m).groupby(m.index.year).prod() - 1 for n, m in h.items()}) * 100
    yr["owner - reset"] = yr["owner"] - yr["reset"]
    print("\nhistory by calendar year, %:")
    print(yr.round(1).to_string())
    print(f"\nyears the owner's rule beat the reset: {(yr['owner - reset'] > 0).sum()} of {len(yr)}")
    rec = json.load(open(ROOT / "data" / "track_record.json"))["months"]
    r = pd.DataFrame({"recorded": {k: v["strategy"] * 100 for k, v in rec.items()},
                      **{n: (months[("record", n)] * 100).set_axis(months[("record", n)].index.strftime("%Y-%m"))
                         for n in rules}})
    print("\nrecord months, %:")
    print(r.round(2).to_string())


if __name__ == "__main__":
    main(sys.argv[1])
