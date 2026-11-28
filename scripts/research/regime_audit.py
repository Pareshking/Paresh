"""Does an indicator or a rule work in one kind of market and not another? (owner, 28 Nov 2026, S239: "some may work
better in bull market and some in bear market and some in between ... we should discard nothing without testing ...
month on month and year on year results audit might give you some hints").

Market states, read at each month-end SIGNAL close from data known then (so a rule keyed to them could be traded):
  trend    Nifty 500 above its 200D EMA AND up over 6 months = bull; below AND down = bear; anything else = sideways
  breadth  share of the Nifty 500's members (as they stood) above their 200D EMA: < 40% low, 40-60% mid, > 60% high
  vol      Nifty 500's 63-session volatility above / below its own median to date
Beside them, for description only (it is hindsight, so no rule can use it): the NEXT month's Nifty 500 return,
  up > +2%, down < -2%, flat between.

Two parts:
  A  the 27 indicators of indicator_screen.py: their monthly IC inside the book's pool, by state; 20 placebos show
     how many "state winners" chance gives. Bar (fixed first): t >= 3 inside a state and a positive mean in both
     halves of that state's months (by date).
  B  the 16 factorial books of combos_factorial.py (skip 5, no 1M window, Bollinger entry block, 3M > 0): the month's
     return minus the baseline's, by state (state at the previous month-end, the signal that formed the month's
     book); each factor's main effect per state; and every calendar year, each rule against the baseline.

    python scripts/research/regime_audit.py <nse_long_close.parquet> <nse_long_value.parquet> <out_dir>
"""
import itertools
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from combos_factorial import cell, pct_b  # noqa: E402
from indicator_screen import SPEC, months_ret, monthly_ics  # noqa: E402
from src.engine import index_universe as iu  # noqa: E402
from src.engine.track_record import breadth_on  # noqa: E402

N_PLACEBO = 20


def tstat(x: pd.Series) -> float:
    x = x.dropna()
    return x.mean() / (x.std(ddof=1) / np.sqrt(len(x))) if len(x) > 3 and x.std(ddof=1) > 0 else np.nan


def states(close: pd.DataFrame, bench: pd.Series, signals: pd.DatetimeIndex) -> pd.DataFrame:
    b = bench.reindex(close.index).ffill()
    ema200 = b.ewm(span=200, adjust=False).mean()
    r6 = months_ret(b.to_frame("b"), 6)["b"]
    vol = b.pct_change().rolling(63).std()
    med = vol.expanding(250).median()
    nxt = b.resample("ME").last().pct_change().shift(-1)
    membership = iu.index_history("nifty_500")
    out = []
    for d in signals:
        up, mom = b[d] > ema200[d], r6[d] > 0
        br = breadth_on(close, membership, d)
        n = nxt.get(pd.Timestamp(d) + pd.offsets.MonthEnd(0), np.nan)
        out.append({"date": d,
                    "trend": "bull" if (up and mom) else "bear" if (not up and not mom) else "sideways",
                    "breadth": None if br is None else "low" if br < 0.40 else "high" if br > 0.60 else "mid",
                    "vol": "high" if vol[d] > med[d] else "low",
                    "next month (hindsight)": None if pd.isna(n) else "up" if n > 0.02 else "down" if n < -0.02 else "flat"})
    return pd.DataFrame(out).set_index("date")


def part_a(ic: pd.DataFrame, st: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for dim in st.columns:
        for lab, g in st.groupby(dim):
            m = ic.loc[ic.index.intersection(g.index)]
            mid = m.index[len(m) // 2] if len(m) else None
            for n in m.columns:
                s = m[n].dropna()
                rows.append({"state": f"{dim}={lab}", "indicator": n, "months": len(s), "mean IC": s.mean(), "t": tstat(s),
                             "h1 mean": s[s.index < mid].mean() if mid is not None else np.nan,
                             "h2 mean": s[s.index >= mid].mean() if mid is not None else np.nan})
    return pd.DataFrame(rows)


def part_b(mdf: pd.DataFrame, st: pd.DataFrame, bench: pd.Series, out: Path) -> None:
    diff = mdf.sub(mdf["baseline"], axis=0).drop(columns="baseline") * 100
    sig_state = st.copy()
    sig_state.index = sig_state.index + pd.offsets.MonthEnd(0) + pd.offsets.MonthEnd(1)  # last session -> next month's end
    sig_state = sig_state.reindex(diff.index)
    print("\nB. THE 16 BOOKS BY STATE: month's return minus the baseline's, pts a month")
    rows = []
    for dim in sig_state.columns:
        for lab, g in sig_state.groupby(dim):
            d = diff.loc[g.index]
            for c in d.columns:
                x = d[c]
                mid = x.index[len(x) // 2]
                rows.append({"state": f"{dim}={lab}", "book": c, "months": len(x), "mean": x.mean(), "t": tstat(x),
                             "hit %": (x > 0).mean() * 100, "h1": x[x.index < mid].mean(), "h2": x[x.index >= mid].mean()})
    bdf = pd.DataFrame(rows)
    bdf.to_csv(out / "books_by_state.csv", index=False)
    for dim in sig_state.columns:
        sub = bdf[bdf["state"].str.startswith(dim + "=")]
        print(f"  {dim}: mean pts a month (t)")
        piv = sub.pivot(index="book", columns="state", values="mean").round(2)
        tpiv = sub.pivot(index="book", columns="state", values="t").round(1)
        n = sub.groupby("state")["months"].first()
        print("   months: " + ", ".join(f"{k} {v}" for k, v in n.items()))
        print((piv.astype(str) + " (" + tpiv.astype(str) + ")").to_string())
    print("\n  MAIN EFFECTS by state (mean of the 8 books with the rule minus the 8 without), pts a month (t of the monthly series):")
    for dim in sig_state.columns:
        for lab, g in sig_state.groupby(dim):
            d = mdf.loc[g.index] * 100
            parts = []
            for f in "SWBR":
                on = [c for c in d.columns if f in c.split("+")]
                off = [c for c in d.columns if c not in on]
                eff = d[on].mean(axis=1) - d[off].mean(axis=1)
                parts.append(f"{f} {eff.mean():+.2f} ({tstat(eff):+.1f})")
            print(f"   {dim}={lab:9s} n={len(d):3d}  " + "  ".join(parts))
    print("\n  YEAR BY YEAR: calendar-year return minus the baseline's, pts (the Nifty 500's year beside)")
    yr = (1 + mdf).groupby(mdf.index.year).prod() - 1
    bmy = bench.resample("YE").last().pct_change()
    bmy.index = bmy.index.year
    ytab = (yr.sub(yr["baseline"], axis=0).drop(columns="baseline") * 100)
    keep = ["S", "W", "B", "R", "S+B", "S+W", "S+B+R"]
    show = ytab[keep].copy()
    show.insert(0, "baseline %", yr["baseline"] * 100)
    show.insert(0, "Nifty 500 %", bmy.reindex(show.index) * 100)
    print(show.round(1).to_string())
    print("  years ahead of the baseline: " + ", ".join(f"{c} {int((ytab[c] > 0).sum())}/{len(ytab)}" for c in keep))
    ytab.to_csv(out / "books_by_year.csv")


def main(close_path: str, value_path: str, out_dir: str) -> None:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    pd.set_option("display.width", 220)
    close = pd.read_parquet(close_path)
    close.index = pd.DatetimeIndex(close.index)
    bench = pd.read_csv(ROOT / "data" / "benchmarks.csv", parse_dates=["date"]).set_index("date")["nifty500"]
    cols = sorted(iu.ever_members(iu.index_history("nifty_500")) & set(close.columns))
    pf = close.loc[:, cols].astype("float64").ffill()
    dates = pf.index
    month_last = pd.DatetimeIndex(pd.Series(dates, index=dates).groupby([dates.year, dates.month]).max().to_numpy())
    b_only = (out / "book_months.csv").exists() and "--b-only" in sys.argv
    st = states(pf, bench, month_last[month_last >= "2009-12-01"])
    st.to_csv(out / "states.csv")
    if b_only:
        part_b(pd.read_csv(out / "book_months.csv", index_col=0, parse_dates=True), st, bench, out)
        return
    print("months in each state (signals Dec 2009 - ):")
    for c in st.columns:
        print(f"  {c}: {st[c].value_counts().to_dict()}")

    # ---- A: indicators by state
    ic, _ = monthly_ics(close_path, value_path, n_placebo=N_PLACEBO)
    a = part_a(ic, st)
    a.to_csv(out / "indicators_by_state.csv", index=False)
    real = a[~a["indicator"].str.startswith("placebo") & (a["indicator"] != "composite")]
    plac = a[a["indicator"].str.startswith("placebo")]
    a["pass"] = (a["t"] >= 3.0) & (a["h1 mean"] > 0) & (a["h2 mean"] > 0)
    print("\nA. INDICATORS BY STATE (signed IC inside the pool; + = the expected direction)")
    print(f"   cells tried: {len(real)} real, {len(plac)} placebo")
    print(f"   |t| >= 2: real {int((real['t'].abs() >= 2).sum())} of {len(real)} "
          f"({100 * (real['t'].abs() >= 2).mean():.0f}%), placebo {int((plac['t'].abs() >= 2).sum())} of {len(plac)} "
          f"({100 * (plac['t'].abs() >= 2).mean():.0f}%)")
    print(f"   t >= 3: real {int((real['t'] >= 3).sum())}, placebo {int((plac['t'] >= 3).sum())}; "
          f"t <= -3 (works the OTHER way): real {int((real['t'] <= -3).sum())}, placebo {int((plac['t'] <= -3).sum())}")
    hit = a[a["pass"] & ~a["indicator"].str.startswith("placebo")]
    print("   passing the bar (t >= 3 and both halves of the state's months positive):")
    print(hit.round(3).to_string(index=False) if len(hit) else "   none")
    strong = a[(a["t"].abs() >= 2.5) & ~a["indicator"].str.startswith("placebo")].sort_values("t")
    print("   every real cell with |t| >= 2.5 (either direction):")
    print(strong.round(3).to_string(index=False))
    composite = a[a["indicator"] == "composite"][["state", "months", "mean IC", "t"]]
    print("   our composite score inside the pool, by state:")
    print(composite.round(3).to_string(index=False))

    # ---- B: the 16 books by state, and year by year
    cols2 = sorted((iu.ever_members(iu.index_history("nifty_500"))) & set(close.columns))
    pf2 = close.loc[:, cols2].astype("float64").ffill()
    gates = {"pb": pct_b(pf2), "r3": months_ret(pf2, 3)}
    monthly = {}
    for s, w, b, r in itertools.product((0, 1), repeat=4):
        name = "+".join(n for n, f in zip("SWBR", (s, w, b, r), strict=True) if f) or "baseline"
        eq = cell(close, bench, gates, s, w, b, r)
        monthly[name] = eq.resample("ME").last().pct_change()
        print(f"   ran {name}", flush=True)
    mdf = pd.DataFrame(monthly).dropna()
    mdf.to_csv(out / "book_months.csv")
    # the book for month M is formed at the signal on the last session of M-1
    part_b(mdf, st, bench, out)
    _ = SPEC


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3])
