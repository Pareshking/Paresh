"""Do the loose exits (and skip 5) hold beyond the Nifty 500 with 20 holdings? (owner, 28 Nov 2026, S239: "check
above rules for 25 and 30 stocks portfolio as well ... on different indices universe we already have in Backtest").

Fixed BEFORE running:
  universes  every one the Backtest offers, each from its first point-in-time list: Nifty 50, Nifty 100, Nifty 500
             (Jan 2010), Midcap 150, Smallcap 250 (Apr 2016), Microcap 250 (Oct 2021), Total Market (Nov 2021)
  holdings   20, 25, 30 (everything else the record's: 50D EMA and within 20% of the 52-week high to buy, 5% stock
             and 40% industry caps, monthly reset, 30 bps)
  books      today      keep within 2x the holdings, sell below the buy EMA (the live shape)
             loose      sell below the 200D EMA, keep within the top 90 (the shadow's absolute band)
             loose x4.5 the same with the band scaled to the book (90 / 113 / 135); for 20 holdings it is "loose"
             skip 5     today's exits, score read 5 sessions early
             loose+s5   loose exits and skip 5
  read       each book against "today" for the same universe and size: a year, the two halves of the window
             (split at its middle date), worst fall, turnover.
  the loose exits "hold" if they beat today's rules in at least two thirds of the 21 universe x size cells, and in
  both halves for the universes with a 2010 or 2016 start.

    python scripts/research/exit_universes.py <nse_long_close.parquet> [out.csv]
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from rs_supertrend import run  # noqa: E402
from src.engine import index_universe as iu  # noqa: E402
from src.engine.metrics import drawdown  # noqa: E402

UNIVERSES = {"nifty_50": "2010-01-01", "nifty_100": "2010-01-01", "nifty_500": "2010-01-01",
             "nifty_midcap_150": "2016-05-01", "nifty_smallcap_250": "2016-05-01",
             "nifty_microcap_250": "2021-11-01", "nifty_total_market": "2022-01-01"}


def cagr(e: pd.Series) -> float:
    if len(e) < 2:
        return np.nan
    return ((e.iloc[-1] / e.iloc[0]) ** (365.25 / (e.index[-1] - e.index[0]).days) - 1) * 100


def summary(res) -> dict:
    e = pd.Series(res["equity_curve"]).dropna()
    e.index = pd.DatetimeIndex(e.index)
    mid = e.index[0] + (e.index[-1] - e.index[0]) / 2
    return {"a year %": cagr(e), "first half %": cagr(e[e.index <= mid]), "second half %": cagr(e[e.index >= mid]),
            "worst fall %": drawdown(e).min() * 100, "turnover %/mo": res["stats"]["avg_turnover"]}


def main(close_path: str, out: str | None) -> None:
    close = pd.read_parquet(close_path)
    close.index = pd.DatetimeIndex(close.index)
    bench = pd.read_csv(ROOT / "data" / "benchmarks.csv", parse_dates=["date"]).set_index("date")["nifty500"]
    rows = []
    for key, start in UNIVERSES.items():
        h = iu.index_history(key)
        ever = iu.ever_members(h)
        priced = len(ever & set(close.columns))
        print(f"{iu.INDICES[key]}: {priced} of {len(ever)} ever-members priced; from {start}", flush=True)
        for n in (20, 25, 30):
            books = {"today": {"buffer_n": 2 * n},
                     "loose": {"buffer_n": 90, "exit_ema_period": 200},
                     "loose x4.5": {"buffer_n": int(round(4.5 * n)), "exit_ema_period": 200},
                     "skip 5": {"buffer_n": 2 * n, "score_skip": 5},
                     "loose+s5": {"buffer_n": 90, "exit_ema_period": 200, "score_skip": 5}}
            if n == 20:
                books.pop("loose x4.5")
            for name, kw in books.items():
                r = run(close, bench, index_key=key, start=start, top_n=n, **kw)
                if r is None:
                    continue
                rows.append({"universe": iu.INDICES[key], "holdings": n, "book": name, **summary(r)})
            t = next(x for x in rows[::-1] if x["book"] == "today" and x["universe"] == iu.INDICES[key] and x["holdings"] == n)
            print(f"  {n} holdings: today {t['a year %']:.2f}%", flush=True)
    df = pd.DataFrame(rows)
    base = df[df["book"] == "today"].set_index(["universe", "holdings"])
    for c in ("a year %", "first half %", "second half %", "worst fall %", "turnover %/mo"):
        df[f"{c} vs today"] = df.apply(lambda r, c=c: r[c] - base.loc[(r["universe"], r["holdings"]), c], axis=1)
    if out:
        df.round(3).to_csv(out, index=False)
    pd.set_option("display.width", 230)
    order = list(dict.fromkeys(iu.INDICES[k] for k in UNIVERSES))
    print("\nA YEAR, % (today's rules), and each book's change against it, pts (first half / second half; worst fall)")
    for u in order:
        sub = df[df["universe"] == u]
        print(f"\n=== {u}")
        for n in (20, 25, 30):
            s = sub[sub["holdings"] == n].set_index("book")
            if "today" not in s.index:
                continue
            t = s.loc["today"]
            line = f"  {n} holdings: today {t['a year %']:.1f}% (worst {t['worst fall %']:.0f}%, turnover {t['turnover %/mo']:.0f}%)"
            for b in ("loose", "loose x4.5", "skip 5", "loose+s5"):
                if b in s.index:
                    x = s.loc[b]
                    line += (f" | {b} {x['a year % vs today']:+.1f} ({x['first half % vs today']:+.1f}/"
                             f"{x['second half % vs today']:+.1f}; dd {x['worst fall % vs today']:+.1f})")
            print(line)
    print("\nCOUNTS over the 21 universe x holdings cells (beats today's rules in a year / in both halves / worst fall no deeper):")
    for b in ("loose", "loose x4.5", "skip 5", "loose+s5"):
        s = df[df["book"] == b]
        if b == "loose x4.5":
            s = pd.concat([s, df[(df["book"] == "loose") & (df["holdings"] == 20)]])
        print(f"  {b:10s} {int((s['a year % vs today'] > 0).sum())}/{len(s)} | "
              f"{int(((s['first half % vs today'] > 0) & (s['second half % vs today'] > 0)).sum())}/{len(s)} | "
              f"{int((s['worst fall % vs today'] >= 0).sum())}/{len(s)}; median {s['a year % vs today'].median():+.2f} pts, "
              f"turnover {s['turnover %/mo vs today'].median():+.1f} pts a month")
    long = df[df["universe"].isin(["Nifty 50", "Nifty 100", "Nifty 500", "Nifty Midcap 150", "Nifty Smallcap 250"])]
    lo = long[long["book"] == "loose"]
    print(f"  loose, universes from 2010 / 2016 only: ahead in both halves in "
          f"{int(((lo['first half % vs today'] > 0) & (lo['second half % vs today'] > 0)).sum())} of {len(lo)}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
