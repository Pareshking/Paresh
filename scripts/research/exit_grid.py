"""Neighbours of the one exit rule that passed in exit_rules.py (S239, 28 Nov 2026): exit below the 200D EMA AND keep
while in the top 90 (entry unchanged: 50D EMA, top 20). Alone each loosening gave about +1 pt; together +5.6, so the
result is checked on its neighbours before it is believed.

Fixed BEFORE running: exit EMA 50 / 100 / 150 / 200 / 250 x keep within top 40 / 60 / 90 / 120, on the baseline and on
skip 5. The finding stands only if at least 7 of the 9 cells with both loosened (EMA 100-200 x top 60-120) pass the
RETURN rule against their base (>= +0.5 pts a year in the run and both halves, worst fall no deeper), AND it gains on
Nifty Total Market from Jan 2022, AND it is ahead in most calendar years.

    python scripts/research/exit_grid.py <nse_long_close.parquet>
"""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from exit_rules import curve, verdict  # noqa: E402
from rs_supertrend import run, stats  # noqa: E402

EMAS = (50, 100, 150, 200, 250)
KEEPS = (40, 60, 90, 120)


def main(close_path: str) -> None:
    close = pd.read_parquet(close_path)
    close.index = pd.DatetimeIndex(close.index)
    bench = pd.read_csv(ROOT / "data" / "benchmarks.csv", parse_dates=["date"]).set_index("date")["nifty500"]
    pd.set_option("display.width", 220)
    years = {}
    for base_name, base_kw in (("baseline", {}), ("skip 5", {"score_skip": 5})):
        b_res = run(close, bench, **base_kw)
        b = stats(curve(b_res))
        grid, tab, turn = {}, {}, {}
        for e in EMAS:
            for k in KEEPS:
                kw = {} if (e == 50 and k == 40) else {"exit_ema_period": e, "buffer_n": k}
                r = run(close, bench, **base_kw, **kw)
                eq = curve(r)
                x = stats(eq)
                grid[(e, k)] = verdict(x, b) if kw else "base"
                tab[(e, k)] = f"{x['a year %'] - b['a year %']:+.1f} ({x['2010-17 %'] - b['2010-17 %']:+.1f}/" \
                              f"{x['2018-26 %'] - b['2018-26 %']:+.1f}) dd {x['worst fall %']:.0f}"
                turn[(e, k)] = r["stats"]["avg_turnover"]
                if (e, k) in ((50, 40), (200, 90)):
                    years[(base_name, e, k)] = eq
            print(base_name, e, "done", flush=True)
        t = pd.Series(tab).unstack()
        t.index.name, t.columns.name = "exit EMA", "keep within top"
        print(f"\n=== {base_name} ({b['a year %']:.2f}% a year, worst {b['worst fall %']:.1f}%): change in a year, pts "
              "(2010-17 / 2018-26), worst fall %")
        print(t.to_string())
        print("  turnover, % a month:")
        print(pd.Series(turn).unstack().round(1).to_string())
        both = [(e, k) for e in (100, 150, 200) for k in (60, 90, 120)]
        n = sum(grid[c] == "PASS return" for c in both)
        print(f"  both loosened (EMA 100-200 x top 60-120): {n} of 9 pass the RETURN rule")

    print("\n=== YEAR BY YEAR, exit EMA 200 + top 90 minus its base, pts")
    yr = {}
    for base_name in ("baseline", "skip 5"):
        a, c = years[(base_name, 50, 40)], years[(base_name, 200, 90)]
        ya = a.resample("YE").last().pct_change()
        ya.iloc[0] = a.resample("YE").last().iloc[0] / a.iloc[0] - 1
        yc = c.resample("YE").last().pct_change()
        yc.iloc[0] = c.resample("YE").last().iloc[0] / c.iloc[0] - 1
        yr[base_name] = (yc - ya) * 100
    ydf = pd.DataFrame(yr)
    ydf.index = ydf.index.year
    print(ydf.round(1).to_string())
    print("  years ahead: " + ", ".join(f"{c} {int((ydf[c] > 0).sum())}/{len(ydf)}" for c in ydf))

    print("\n=== NIFTY TOTAL MARKET (live universe), Jan 2022 - Nov 2026")
    for base_name, base_kw in (("baseline", {}), ("skip 5", {"score_skip": 5})):
        uni = {"index_key": "nifty_total_market", "start": "2022-01-01"}
        b = stats(curve(run(close, bench, **uni, **base_kw)))
        for e, k in ((100, 60), (200, 90), (150, 90), (200, 120)):
            x = stats(curve(run(close, bench, **uni, **base_kw, exit_ema_period=e, buffer_n=k)))
            print(f"  {base_name:8s} exit EMA {e} + top {k}: {b['a year %']:.2f}% -> {x['a year %']:.2f}% "
                  f"({x['a year %'] - b['a year %']:+.2f}); worst {b['worst fall %']:.1f}% -> {x['worst fall %']:.1f}%")


if __name__ == "__main__":
    main(sys.argv[1])
