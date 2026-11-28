"""Level B for the one family that came close in the Level A screen (indicator_screen.py): "overextension",
a stock stretched above its own recent range does worse next month, in three forms (Bollinger %B t=3.2,
RSI(14) t=2.3, close over its 50D EMA t=2.2). Does a gate built on it improve the real book? (28 Nov 2026.)

Fixed BEFORE the engine was run:
  gates (True = may be bought / kept), at the month-end signal close:
    pctb_1     Bollinger %B(20,2) <= 1.0  (close not above the upper band)
    rsi_70     RSI(14) <= 70
    pctb_q80   %B within the lowest 80% of that day's Nifty 500 members (blocks the most stretched fifth)
  modes: entry (a held name may stay) and both (a held name that is stretched is sold).
  pass rule: >= +0.5 pts a year in the whole run AND in 2010-17 AND in 2018-26 against the baseline, worst fall no
    deeper, AND the whole-run gain above the 90th percentile of a NULL: a random gate that blocks the same share
    of the book's new buys, 30 seeds.

    python scripts/research/overextension_gate.py <nse_long_close.parquet> <nse_long_value.parquet>
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from indicator_screen import build  # noqa: E402
from rs_supertrend import run, stats  # noqa: E402
from src.engine import index_universe as iu  # noqa: E402
from src.engine.model_record import record_sector_map  # noqa: E402


def curve(res) -> pd.Series:
    e = pd.Series(res["equity_curve"]).dropna()
    e.index = pd.DatetimeIndex(e.index)
    return e


def main(close_path: str, value_path: str, seeds: int = 30) -> None:
    close = pd.read_parquet(close_path)
    close.index = pd.DatetimeIndex(close.index)
    value = pd.read_parquet(value_path)
    value.index = pd.DatetimeIndex(value.index)
    bench = pd.read_csv(ROOT / "data" / "benchmarks.csv", parse_dates=["date"]).set_index("date")["nifty500"]
    cols = sorted(iu.ever_members(iu.index_history("nifty_500")) & set(close.columns))
    pf = close.loc[:, cols].astype("float64").ffill()
    ind = build(pf, bench.reindex(pf.index).ffill(), value.reindex(columns=cols), record_sector_map(cols))
    gates = {
        "pctb_1": (ind["boll_b"] <= 1.0),
        "rsi_70": (ind["rsi14"] <= 70),
        "pctb_q80": (ind["boll_b"].rank(axis=1, pct=True) <= 0.80),
    }
    base_res = run(close, bench)
    base = stats(curve(base_res))
    print("baseline", {k: round(v, 2) for k, v in base.items()}, flush=True)
    tb = base_res["tradebook"]
    tb = tb[tb["Action"].str.contains("BUY|HOLD")].copy()
    tb["date"] = pd.to_datetime(tb["Period Start"])
    new = tb["Action"].str.contains("BUY").to_numpy()
    rows, q_new = {}, {}
    for name, g in gates.items():
        ok = np.array([bool(g.at[d, s]) if (d in g.index and s in g.columns) else False
                       for d, s in zip(tb["date"], tb["Symbol"], strict=True)])
        q_new[name] = 1 - ok[new].mean()
        print(f"{name}: blocks {100 * q_new[name]:.1f}% of new buys, {100 * (1 - ok[~new].mean()):.1f}% of kept names", flush=True)
        for mode in ("entry", "both"):
            st = stats(curve(run(close, bench, g, mode)))
            rows[f"{name}/{mode}"] = {**st, **{f"{k} vs base": st[k] - base[k] for k in ("a year %", "2010-17 %", "2018-26 %")}}
            print(name, mode, {k: round(v, 2) for k, v in rows[f"{name}/{mode}"].items()}, flush=True)
    df = pd.DataFrame(rows).T
    pd.set_option("display.width", 200)
    print("\n" + df.round(2).to_string())
    rng = np.random.default_rng(5)
    print("\nNULL (random gate, same share of new buys blocked), change in a year against the baseline, pts:")
    for name, q in q_new.items():
        d = []
        for _ in range(seeds):
            rg = pd.DataFrame(rng.random(pf.shape) >= q, index=pf.index, columns=pf.columns)
            d.append(stats(curve(run(close, bench, rg, "both")))["a year %"] - base["a year %"])
        d = np.array(d)
        best = df.loc[[f"{name}/entry", f"{name}/both"], "a year % vs base"].max()
        print(f"  {name} (q={100 * q:.1f}%): mean {d.mean():+.2f}, p90 {np.percentile(d, 90):+.2f}, max {d.max():+.2f}; "
              f"real best {best:+.2f}  -> {'above' if best > np.percentile(d, 90) else 'inside'} the null's p90")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
