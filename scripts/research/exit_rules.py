"""Exit rules chosen from what exit_diagnostics.py showed (S239, 28 Nov 2026):
  * the month-end sales are about neutral: a sold stock does about as well as what the book keeps (1M mean +0.35,
    median -0.12 pts); holdings at rank 21-40 do as well as rank 1-20 (+0.17, t 0.4)  -> try LOOSER month-end exits;
  * inside a month a holding down 10-20% then beats the other holdings (+0.3 to +0.6 pts mean, 60-65% rise)
    -> stops should hurt; tested to confirm, not expected to pass;
  * the deep falls are the book's own, not the market's (2024-26 -38.7% vs the index -10.1%; 2022 -30.9 vs -17.9)
    -> a tighter industry cap, so one crowded theme cannot carry the book down.

Fixed BEFORE running, each on two bases, the baseline (18.81%) and skip 5 (23.06%):
  exit EMA 100 / 200 (entry stays 50); keep while in the top 60 / 90 (now 40); keep within 30% of the 52W high
  (entry stays 20%); exit EMA 200 + top 90 together; industry cap 30% / 25% (now 40%).
  Daily stops (replay of the baseline's books, cash at 6.5%): -15% from the fill; -15% from the high since the fill.
Two ways to pass:
  RETURN    >= +0.5 pts a year in the run and both halves, worst fall no deeper;
  DRAWDOWN  worst fall >= 3 pts shallower, a year no more than 0.25 pts lower in the run and 0.5 in either half.

    python scripts/research/exit_rules.py <nse_long_close.parquet>
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from rs_supertrend import run, stats  # noqa: E402
from src.engine import index_universe as iu  # noqa: E402

CASH = 0.065


def curve(res) -> pd.Series:
    e = pd.Series(res["equity_curve"]).dropna()
    e.index = pd.DatetimeIndex(e.index)
    return e


def verdict(x: dict, b: dict) -> str:
    d = {k: x[k] - b[k] for k in ("a year %", "2010-17 %", "2018-26 %")}
    ret = all(v >= 0.5 for v in d.values()) and x["worst fall %"] >= b["worst fall %"]
    dd = (x["worst fall %"] - b["worst fall %"] >= 3 and d["a year %"] >= -0.25
          and d["2010-17 %"] >= -0.5 and d["2018-26 %"] >= -0.5)
    return "PASS return" if ret else "PASS drawdown" if dd else "fail"


def replay(tb, pf, stop, trailing):
    tb = tb[tb["Action"].str.contains("BUY|HOLD")].copy()
    tb["s"] = pd.to_datetime(tb["Period Start"])
    tb["e"] = pd.to_datetime(tb["Period"].str.split("→").str[1].str.strip(), format="%d %b %Y")
    dates = pf.index
    level, out = 1.0, []
    daily_cash = (1 + CASH) ** (1 / 252) - 1
    for (s, e), g in tb.groupby(["s", "e"], sort=True):
        i, j = dates.get_loc(s), dates.get_loc(e)
        syms = [x for x in g["Symbol"] if x in pf.columns]
        w = g.set_index("Symbol")["Weight %"].reindex(syms).to_numpy() / 100
        px = pf[syms].iloc[i:j + 1].to_numpy()
        val = px / px[0] * w
        if stop is not None:
            ref = np.maximum.accumulate(px, axis=0) if trailing else px[0]
            hit_m = px / ref - 1 <= stop
            for k in range(len(syms)):
                h = np.where(hit_m[:-1, k])[0]
                if len(h):
                    t = h[0] + 1
                    base = val[t, k] * (1 - 0.003)
                    val[t:, k] = base * (1 + daily_cash) ** np.arange(len(val) - t)
        path = (np.nansum(val, axis=1) + (1 - w.sum())) * level
        out.append(pd.Series(path[1:], index=dates[i + 1:j + 1]))
        level = path[-1]
    return pd.concat(out)


def main(close_path: str) -> None:
    close = pd.read_parquet(close_path)
    close.index = pd.DatetimeIndex(close.index)
    bench = pd.read_csv(ROOT / "data" / "benchmarks.csv", parse_dates=["date"]).set_index("date")["nifty500"]
    rules = {
        "exit EMA 100": {"exit_ema_period": 100},
        "exit EMA 200": {"exit_ema_period": 200},
        "keep in top 60": {"buffer_n": 60},
        "keep in top 90": {"buffer_n": 90},
        "keep within 30% of high": {"exit_high_pct": 0.70},
        "exit EMA 200 + top 90": {"exit_ema_period": 200, "buffer_n": 90},
        "industry cap 30%": {"sector_cap": 0.30},
        "industry cap 25%": {"sector_cap": 0.25},
    }
    rows = []
    for base_name, base_kw in (("baseline", {}), ("skip 5", {"score_skip": 5})):
        br = run(close, bench, **base_kw)
        b = stats(curve(br))
        rows.append({"base": base_name, "rule": "(none)", **b, "turnover %/mo": br["stats"]["avg_turnover"], "verdict": ""})
        for name, kw in rules.items():
            r = run(close, bench, **base_kw, **kw)
            x = stats(curve(r))
            rows.append({"base": base_name, "rule": name, **x, "turnover %/mo": r["stats"]["avg_turnover"],
                         "verdict": verdict(x, b)})
            print(base_name, name, round(x["a year %"], 2), round(x["worst fall %"], 1), flush=True)
    df = pd.DataFrame(rows)
    for c in ("a year %", "2010-17 %", "2018-26 %", "worst fall %"):
        df[f"{c} vs base"] = df[c] - df.groupby("base")[c].transform("first")
    pd.set_option("display.width", 220)
    show = ["base", "rule", "a year %", "a year % vs base", "2010-17 % vs base", "2018-26 % vs base", "worst fall %",
            "worst fall % vs base", "turnover %/mo", "verdict"]
    print("\nMONTH-END EXIT RULES AND INDUSTRY CAP (engine)")
    print(df[show].round(2).to_string(index=False))

    print("\nDAILY STOPS (replay of the baseline's books, sold stock's money in cash at 6.5% to the month's end)")
    cols = sorted(iu.ever_members(iu.index_history("nifty_500")) & set(close.columns))
    pf = close.loc[:, cols].astype("float64").ffill()
    tb = run(close, bench)["tradebook"]
    plain = stats(replay(tb, pf, None, False))
    print(f"  replay without stops: {plain['a year %']:.2f}% a year, worst {plain['worst fall %']:.1f}%")
    for label, stop, trailing in (("-15% from the fill", -0.15, False), ("-15% from the high since the fill", -0.15, True)):
        x = stats(replay(tb, pf, stop, trailing))
        print(f"  {label:34s} {x['a year %'] - plain['a year %']:+.2f} pts a year (2010-17 {x['2010-17 %'] - plain['2010-17 %']:+.2f},"
              f" 2018-26 {x['2018-26 %'] - plain['2018-26 %']:+.2f}); worst {x['worst fall %']:.1f}%  {verdict(x, plain)}")


if __name__ == "__main__":
    main(sys.argv[1])
