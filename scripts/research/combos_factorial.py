"""Owner, 28 Nov 2026 (S239): before a shadow book "skip 5 + no buy above the upper Bollinger band", check it;
and test, in combination, (a) dropping the 1-month window from the score, (b) "3-month return > 0" at entry.

Fixed BEFORE running:
  Factorial, 2 x 2 x 2 x 2 = 16 engine runs on the record's rules (Nifty 500 as it stood, Jan 2010 - Nov 2026):
    S  skip 5 sessions in the score (score_skip 5)           off / on
    W  1-month window weight 0 (weights 0/.30/.30/.20/.10)   off / on
    B  no NEW buy with Bollinger %B(20,2) > 1                off / on
    R  no NEW buy with a 3-month return <= 0                 off / on
  Each factor's MAIN EFFECT = mean of its 8 "on" cells minus its 8 "off" cells (sturdier than the best cell).
  The same 16 on Nifty Total Market (the live universe) from Jan 2022, its first full year as a point-in-time list.
  The shadow candidate S+B passes only if, against skip 5 alone (the shadow already recorded): B adds >= +0.5 pts a
  year in the run and in both halves, the worst fall is no deeper, the gain is above the 90th percentile of a null
  (skip 5 + a random gate blocking the same share of new buys, 30 seeds), and the neighbours (%B 0.9 and 1.1 with
  skip 5; skip 3 and 7 with %B 1) keep a gain over their own skip-alone run.

    python scripts/research/combos_factorial.py <nse_long_close.parquet> <nse_long_value.parquet>
"""
import itertools
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from indicator_screen import months_ret  # noqa: E402
from rs_supertrend import run, stats  # noqa: E402
from src.engine import index_universe as iu  # noqa: E402

NO_1M = [0.0, 0.30, 0.30, 0.20, 0.10]


def curve(res) -> pd.Series:
    e = pd.Series(res["equity_curve"]).dropna()
    e.index = pd.DatetimeIndex(e.index)
    return e


def pct_b(pf: pd.DataFrame) -> pd.DataFrame:
    ma, sd = pf.rolling(20).mean(), pf.rolling(20).std()
    return (pf - (ma - 2 * sd)) / (4 * sd)


def cell(close, bench, gates, s, w, b, r, b_thr=1.0, skip=5, **uni):
    g = None
    if b or r:
        g = pd.DataFrame(True, index=gates["pb"].index, columns=gates["pb"].columns)
        if b:
            g &= gates["pb"] <= b_thr
        if r:
            g &= gates["r3"] > 0
    kw = {"score_skip": skip if s else 0}
    if w:
        kw["config_weights"] = NO_1M
    return curve(run(close, bench, g, "entry", **uni, **kw))


def main(close_path: str, value_path: str, seeds: int = 30, skip_n500: bool = False) -> None:
    close = pd.read_parquet(close_path)
    close.index = pd.DatetimeIndex(close.index)
    bench = pd.read_csv(ROOT / "data" / "benchmarks.csv", parse_dates=["date"]).set_index("date")["nifty500"]
    cols = sorted((iu.ever_members(iu.index_history("nifty_500")) | iu.ever_members(iu.index_history("nifty_total_market")))
                  & set(close.columns))
    pf = close.loc[:, cols].astype("float64").ffill()
    gates = {"pb": pct_b(pf), "r3": months_ret(pf, 3)}
    pd.set_option("display.width", 200)

    for label, uni, halves in (("NIFTY 500, Jan 2010 - Nov 2026", {}, True),
                               ("NIFTY TOTAL MARKET, Jan 2022 - Nov 2026", {"index_key": "nifty_total_market", "start": "2022-01-01"}, False)):
        if skip_n500 and halves:
            continue
        rows = {}
        for s, w, b, r in itertools.product((0, 1), repeat=4):
            st = stats(cell(close, bench, gates, s, w, b, r, **uni))
            name = "+".join(n for n, f in zip("SWBR", (s, w, b, r), strict=True) if f) or "baseline"
            rows[name] = {"S": s, "W": w, "B": b, "R": r, **st}
            print(label[:10], name, round(st["a year %"], 2), flush=True)
        df = pd.DataFrame(rows).T
        cols_out = ["a year %", "worst fall %"] + (["2010-17 %", "2018-26 %"] if halves else [])
        for c in cols_out:
            df[f"{c} vs base"] = df[c] - df.loc["baseline", c]
        print(f"\n=== {label}: 16 cells (S skip 5, W no 1M window, B no buy above upper band, R 3M > 0 at entry)")
        print(df[cols_out + [f"{c} vs base" for c in cols_out]].astype(float).round(2).sort_values("a year %", ascending=False).to_string())
        print("main effects, pts (mean of 8 cells with the factor minus 8 without):")
        for f in "SWBR":
            on, off = df[df[f] == 1], df[df[f] == 0]
            parts = "  ".join(f"{c} {on[c].astype(float).mean() - off[c].astype(float).mean():+.2f}" for c in cols_out)
            print(f"  {f}: {parts}")

    print("\n=== CHECK of the shadow candidate S + B against skip 5 alone (Nifty 500, 2010 -)")
    s_only = stats(cell(close, bench, gates, 1, 0, 0, 0))
    sb_eq = cell(close, bench, gates, 1, 0, 1, 0)
    sb = stats(sb_eq)
    d = {k: sb[k] - s_only[k] for k in ("a year %", "2010-17 %", "2018-26 %")}
    print(f"  skip 5 alone {s_only['a year %']:.2f}% worst {s_only['worst fall %']:.1f}; S+B {sb['a year %']:.2f}% worst "
          f"{sb['worst fall %']:.1f}; B adds {d['a year %']:+.2f} (2010-17 {d['2010-17 %']:+.2f}, 2018-26 {d['2018-26 %']:+.2f})")
    for thr in (0.9, 1.1):
        x = stats(cell(close, bench, gates, 1, 0, 1, 0, b_thr=thr))
        print(f"  neighbour %B {thr}: {x['a year %']:.2f}% ({x['a year %'] - s_only['a year %']:+.2f} vs skip 5 alone)")
    for sk in (3, 7):
        alone = stats(cell(close, bench, gates, 1, 0, 0, 0, skip=sk))
        x = stats(cell(close, bench, gates, 1, 0, 1, 0, skip=sk))
        print(f"  neighbour skip {sk}: alone {alone['a year %']:.2f}%, with B {x['a year %']:.2f}% ({x['a year %'] - alone['a year %']:+.2f})")
    res = run(close, bench, None, "entry", score_skip=5)
    tb = res["tradebook"]
    tb = tb[tb["Action"].str.contains("BUY")]
    dts = pd.to_datetime(tb["Period Start"])
    prev = {d: pf.index[pf.index.get_loc(d) - 1] for d in dts.unique()}   # signal close = session before the fill
    ok_b = np.array([bool(gates["pb"].at[prev[d], s] <= 1.0) for d, s in zip(dts, tb["Symbol"], strict=True)])
    ok_r = np.array([bool(gates["r3"].at[prev[d], s] > 0) for d, s in zip(dts, tb["Symbol"], strict=True)])
    q = 1 - ok_b.mean()
    print(f"  on skip 5's new buys: %B > 1 blocks {100 * q:.1f}%; 3M <= 0 blocks {100 * (1 - ok_r.mean()):.1f}%")
    rng = np.random.default_rng(3)
    null = []
    for _ in range(seeds):
        rg = pd.DataFrame(rng.random(pf.shape) >= q, index=pf.index, columns=pf.columns)
        null.append(stats(curve(run(close, bench, rg, "entry", score_skip=5)))["a year %"] - s_only["a year %"])
    null = np.array(null)
    print(f"  NULL skip 5 + random gate: mean {null.mean():+.2f}, p90 {np.percentile(null, 90):+.2f}, max {null.max():+.2f}; "
          f"B adds {d['a year %']:+.2f} -> {'above' if d['a year %'] > np.percentile(null, 90) else 'inside'} p90")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], skip_n500="--skip-n500" in sys.argv)
