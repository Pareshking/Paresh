"""Two follow-ups of 28 Nov 2026 (owner approved the first; asked the second).

1. DAILY EXIT on a relative-strength flip (the one version of the RS idea the monthly engine cannot test).
   The baseline engine's books are replayed day by day: each month's holdings at their fill weights, from fill to
   next fill. A holding whose RS line (close / Nifty 500) flips from up to down at a close is sold at the next
   close and its money sits in cash (0%) until the next rebalance; the exit and the later re-buy or replacement
   cost 30 bps on its weight. The same replay WITHOUT exits is the comparison, so both carry the same simplifications
   (no monthly turnover cost, cash 0%); only the difference is read.
   Fixed before running: flips of Supertrend(10,3) on RS (first), (14,3), (20,3), and RS crossing below its 50D EMA.
   Pass: >= +0.5 pts a year in the run and both halves, worst fall no deeper.

2. COMBINATIONS, run once (owner: "should we add RS above its 50-day EMA as one more combination and test it
   once?"): skip 5 alone, skip 5 + RS above its 50D EMA, skip 5 + the overextension gates. In-sample, descriptive:
   every cell here is another look at the same 16 years.

3. POWER: how many years of a forward (shadow) record it takes to tell each candidate's gain from luck, from the
   spread of its monthly difference against the baseline.

    python scripts/research/rs_daily_exit.py <nse_long_close.parquet> <nse_long_value.parquet>
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from indicator_screen import build  # noqa: E402
from rs_supertrend import HALF, run, stats, supertrend_bull  # noqa: E402
from src.engine import index_universe as iu  # noqa: E402
from src.engine.metrics import drawdown  # noqa: E402
from src.engine.model_record import record_sector_map  # noqa: E402

COST = 0.003


def curve(res) -> pd.Series:
    e = pd.Series(res["equity_curve"]).dropna()
    e.index = pd.DatetimeIndex(e.index)
    return e


def replay(tb: pd.DataFrame, pf: pd.DataFrame, bull: pd.DataFrame | None) -> pd.Series:
    """Daily equity of the engine's monthly books, with an optional exit on a bull -> bear flip."""
    tb = tb[tb["Action"].str.contains("BUY|HOLD")].copy()
    tb["s"] = pd.to_datetime(tb["Period Start"])
    tb["e"] = pd.to_datetime(tb["Period"].str.split("→").str[1].str.strip(), format="%d %b %Y")
    dates = pf.index
    level, out = 1.0, []
    for (s, e), g in tb.groupby(["s", "e"], sort=True):
        i, j = dates.get_loc(s), dates.get_loc(e)
        syms = [x for x in g["Symbol"] if x in pf.columns]
        w = g.set_index("Symbol")["Weight %"].reindex(syms).to_numpy() / 100
        px = pf[syms].iloc[i:j + 1].to_numpy()
        rel = px / px[0]
        val = rel * w                                   # each holding's value path
        if bull is not None:
            b = bull[syms].iloc[i:j + 1].to_numpy()
            for k in range(len(syms)):
                flips = np.where(b[:-1, k] & ~b[1:, k])[0] + 1   # bearish at close t, was bullish at t-1
                flips = flips[flips < len(rel) - 1]
                if len(flips):
                    t = flips[0] + 1                             # sold at the next close
                    val[t:, k] = val[t, k] * (1 - COST)
        cash = 1 - w.sum()
        path = (np.nansum(val, axis=1) + cash) * level
        out.append(pd.Series(path[1:], index=dates[i + 1:j + 1]))
        level = path[-1]
    return pd.concat(out)


def main(close_path: str, value_path: str) -> None:
    close = pd.read_parquet(close_path)
    close.index = pd.DatetimeIndex(close.index)
    value = pd.read_parquet(value_path)
    value.index = pd.DatetimeIndex(value.index)
    bench = pd.read_csv(ROOT / "data" / "benchmarks.csv", parse_dates=["date"]).set_index("date")["nifty500"]
    cols = sorted(iu.ever_members(iu.index_history("nifty_500")) & set(close.columns))
    pf = close.loc[:, cols].astype("float64").ffill()
    b = bench.reindex(pf.index).ffill()
    rs = pf.div(b, axis=0)

    base_res = run(close, bench)
    base_eq = curve(base_res)
    base = stats(base_eq)
    tb = base_res["tradebook"]

    print("1. DAILY EXIT ON AN RS FLIP (replay; read the difference only)")
    plain = replay(tb, pf, None)
    ps = stats(plain)
    print(f"   replay without exits: {ps['a year %']:.2f}% a year (engine 18.81% with monthly costs) worst {ps['worst fall %']:.1f}%")
    exits = {f"st{p}_{m:g}": supertrend_bull(rs, p, m) for p, m in ((10, 3.0), (14, 3.0), (20, 3.0))}
    exits["rs_ema50"] = rs > rs.ewm(span=50, adjust=False, min_periods=30).mean()
    for name, bull in exits.items():
        x = stats(replay(tb, pf, bull))
        d = {k: x[k] - ps[k] for k in ("a year %", "2010-17 %", "2018-26 %")}
        ok = all(v >= 0.5 for v in d.values()) and x["worst fall %"] >= ps["worst fall %"]
        print(f"   {name:9s} a year {d['a year %']:+.2f}  2010-17 {d['2010-17 %']:+.2f}  2018-26 {d['2018-26 %']:+.2f} pts;"
              f" worst {x['worst fall %']:.1f}%  {'PASS' if ok else 'fail'}")

    print("\n2. COMBINATIONS, ONCE (in-sample, descriptive), against the baseline")
    ind = build(pf, b, value.reindex(columns=cols), record_sector_map(cols))
    rs50 = rs > rs.ewm(span=50, adjust=False, min_periods=30).mean()
    q80 = ind["boll_b"].rank(axis=1, pct=True) <= 0.80
    p1 = ind["boll_b"] <= 1.0
    cells = {
        "skip 5 alone": (None, "both", 5),
        "RS above 50D EMA (both)": (rs50, "both", 0),
        "skip 5 + RS above 50D EMA (both)": (rs50, "both", 5),
        "%B top fifth blocked (entry)": (q80, "entry", 0),
        "skip 5 + %B top fifth blocked (entry)": (q80, "entry", 5),
        "%B above 1 blocked (entry)": (p1, "entry", 0),
        "skip 5 + %B above 1 blocked (entry)": (p1, "entry", 5),
    }
    curves = {"baseline": base_eq}
    for name, (g, mode, sk) in cells.items():
        eq = curve(run(close, bench, g, mode, score_skip=sk))
        curves[name] = eq
        x = stats(eq)
        print(f"   {name:38s} {x['a year %']:.2f}% ({x['a year %'] - base['a year %']:+.2f})  2010-17 "
              f"{x['2010-17 %'] - base['2010-17 %']:+.2f}  2018-26 {x['2018-26 %'] - base['2018-26 %']:+.2f}  worst {x['worst fall %']:.1f}%")

    print("\n3. POWER: years of forward record to see the in-sample gain at t = 2 (difference against the baseline)")
    bm = base_eq.resample("ME").last().pct_change().dropna()
    for name, eq in curves.items():
        if name == "baseline":
            continue
        m = eq.resample("ME").last().pct_change().dropna()
        d = (m - bm).dropna()
        sd_y = d.std() * np.sqrt(12) * 100
        gain = (stats(eq)["a year %"] - base["a year %"])
        yrs = (2 * sd_y / gain) ** 2 if gain > 0 else np.inf
        print(f"   {name:38s} spread {sd_y:.1f} pts a year; gain {gain:+.2f}; years needed ~{yrs:.0f}")
    _ = (drawdown, HALF)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
