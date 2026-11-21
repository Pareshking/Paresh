"""Where does skip 5 come from? Three tests through the app's engine (owner, 21 Nov 2026; TODO S160).

Read-only research. The record's configuration (as score_skip_engine.py), live
(score_skip 0) against skip 5, on point-in-time membership and NSE's long closes:

  segments   every index with point-in-time membership, from its first month,
             skips 0/3/5/7: one JSON line per (index, skip) with monthly returns
  bootstrap  random universes: each draw drops a random 20% of the index's ever-
             members (seeded, the same draw for both skips) and runs skip 0 and 5
  mix        the size mix of the book under each skip: the share of holdings in
             the Nifty 100, Midcap 150, Smallcap 250, Microcap 250 or none of them
             on each rebalance date, from April 2016 (the segments' first month)

    python scripts/research/score_skip_universes.py segments
    python scripts/research/score_skip_universes.py bootstrap nifty_500 100 [first_seed]
    python scripts/research/score_skip_universes.py mix nifty_500

Pass rule for bootstrap, fixed before results: skip 5 is robust to the universe
only if it beats skip 0 in at least 75% of draws and the median gap is above 0.
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
from src.engine.membership import members_on  # noqa: E402
from src.engine.model_record import record_sector_map  # noqa: E402
from src.engine.track_record import TRACK_RECORD_CONFIG as cfg  # noqa: E402
from src.engine.track_record import run_backtest_kwargs  # noqa: E402
from src.loaders import nse_long  # noqa: E402

INDICES = ["nifty_50", "nifty_next_50", "nifty_100", "nifty_midcap_150", "nifty_smallcap_250",
           "nifty_microcap_250", "nifty_500", "nifty_total_market"]
SEGMENTS = ["nifty_100", "nifty_midcap_150", "nifty_smallcap_250", "nifty_microcap_250"]
DROP = 0.20


def _data():
    close = nse_long.load(with_value=False)[0]
    bench = pd.read_csv(ROOT / "data" / "benchmarks.csv", parse_dates=["date"]).set_index("date")["nifty500"]
    return close, bench


def run(close, bench, key: str, skip: int, cols: list[str] | None = None, start: pd.Period | None = None) -> dict:
    mem = iu.index_history(key)
    start = start or max(iu.first_month(mem), pd.Period("2010-01", "M"))
    cols = cols if cols is not None else sorted(iu.ever_members(mem) & set(close.columns))
    frame = close.loc[:, cols].astype("float64")
    res = run_backtest(
        f"skipuni_{key}_{skip}_{len(cols)}_{hash(tuple(cols))}", frame,
        **run_backtest_kwargs({**cfg, "score_skip": skip}),
        sector_map=record_sector_map(cols), _benchmark_close=bench,
        backtest_months=(pd.Period(frame.index[-1], "M") - start).n, _membership=mem,
        stateful_history=True, history_start=start.start_time, _actions=[])
    eq = pd.Series(res["equity_curve"]).dropna()
    eq.index = pd.DatetimeIndex(eq.index)
    me = eq.resample("ME").last()
    r = pd.concat([pd.Series([eq.iloc[0]], index=[eq.index[0]]), me]).pct_change().dropna()
    r.index = r.index.to_period("M")
    r = r[~r.index.duplicated(keep="last")]
    return {"monthly": r, "tradebook": res["tradebook"]}


def cagr(r: pd.Series) -> float:
    return float((1 + r).prod() ** (12 / len(r)) - 1)


def segments() -> None:
    close, bench = _data()
    for key in INDICES:
        for skip in (0, 3, 5, 7):
            r = run(close, bench, key, skip)["monthly"]
            print(json.dumps({"index": key, "skip": skip, "monthly": {str(k): float(v) for k, v in r.items()}}),
                  flush=True)


def bootstrap(key: str, n: int, first_seed: int = 0) -> None:
    close, bench = _data()
    mem = iu.index_history(key)
    pool = sorted(iu.ever_members(mem) & set(close.columns))
    for seed in range(first_seed, first_seed + n):
        rng = np.random.default_rng(seed)
        keep = sorted(rng.choice(pool, size=int(round(len(pool) * (1 - DROP))), replace=False).tolist())
        r0 = run(close, bench, key, 0, keep)["monthly"]
        r5 = run(close, bench, key, 5, keep)["monthly"]
        d = (r5 - r0).dropna()
        print(json.dumps({"index": key, "seed": seed, "names": len(keep), "cagr0": cagr(r0), "cagr5": cagr(r5),
                          "diff_mean": float(d.mean()), "months_ahead": float((d > 0).mean())}), flush=True)


def _segment_of(sym: str, on: pd.Timestamp, hist: dict) -> str:
    for seg in SEGMENTS:
        if sym in hist[seg].get(on, set()):
            return seg
    return "none"


def mix(key: str) -> None:
    close, bench = _data()
    seg_hist = {s: iu.index_history(s) for s in SEGMENTS}
    start = max(iu.first_month(iu.index_history(key)), pd.Period("2016-04", "M"))
    for skip in (0, 5):
        tb = run(close, bench, key, skip, start=start)["tradebook"]
        tb = tb[~tb["Action"].astype(str).str.contains("SELL|EXIT", case=False, regex=True)]
        rows = []
        for when, g in tb.groupby("Period Start"):
            on = pd.Timestamp(when) - pd.Timedelta(days=1)
            memo = {s: {on: set(members_on(seg_hist[s], on) or [])} for s in SEGMENTS}
            segs = [_segment_of(x, on, memo) for x in g["Symbol"].astype(str).unique()]
            rows.append(pd.Series(segs).value_counts(normalize=True))
        share = pd.DataFrame(rows).fillna(0.0).mean().round(4).to_dict()
        print(json.dumps({"index": key, "skip": skip, "from": str(start), "rebalances": len(rows),
                          "share": share}), flush=True)


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "segments"
    if mode == "segments":
        segments()
    elif mode == "bootstrap":
        bootstrap(sys.argv[2], int(sys.argv[3]), int(sys.argv[4]) if len(sys.argv) > 4 else 0)
    elif mode == "mix":
        mix(sys.argv[2])
    else:
        raise SystemExit(f"unknown mode {mode!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
