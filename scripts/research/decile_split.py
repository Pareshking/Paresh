#!/usr/bin/env python3
"""Which slice of the ranking should the Dashboard's Momentum health show?

Owner, 8 Nov 2026: "give bifurcation of top two deciles also, like top decile
and second top decile?" The card shows the top fifth of the Nifty 500 (about
100 stocks). Our own book holds 20 names, so the card may be measuring a far
gentler thing than the book does.

This builds, for every month since the membership starts, the next month's
equal-weighted return of each candidate slice of our ranking:

  top20     the best 20 by our score   (the book's own size)
  top50     the top decile             (about 50 of the Nifty 500)
  d2        the second decile          (ranks 51-100)
  top100    the top fifth              (what the card shows today)

and compares each one's 12-month lead over the Nifty 500 with OUR BOOK's
12-month lead over the Nifty 500 (the `portfolio` column that
data/momentum_health.csv already carries, from the same backtest the Backtest
page runs). The test is the one that chose the present measure
(docs/MOMENTUM_HEALTH.md): correlation and share of months with the same sign.

Read-only: writes nothing into data/. Run on a GitHub runner, where NSE's long
price file is reachable (.github/workflows/decile_research.yml).

    python scripts/research/decile_split.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

SLICES: dict[str, tuple[int, int]] = {      # name: (first rank, last rank), 1-based
    "top20": (1, 20),
    "top50": (1, 50),
    "d2": (51, 100),
    "top100": (1, 100),
}
MIN_STOCKS = 100


def monthly_slices() -> pd.DataFrame:
    """One row per month: each slice's next-month equal-weighted return, in %."""
    from src.engine import index_universe as iu
    from src.engine.momentum_health import _complete, month_ends
    from src.engine.rank_history import snapshots
    from src.loaders import nse_long

    loaded = nse_long.load(with_value=False)
    if loaded is None:
        raise SystemExit("::error::NSE's long file could not be read")
    close = loaded[0]
    membership = iu.index_history("nifty_500")
    cols = sorted(iu.ever_members(membership) & set(close.columns))
    prices = close[cols].astype("float64")

    ends = month_ends(prices)
    if ends and not _complete(ends[-1]):
        ends = ends[:-1]
    first = iu.first_month(membership)
    if first is not None:
        ends = [d for d in ends if pd.Period(d, freq="M") >= first]
    snaps = snapshots(prices, ends[:-1], membership=membership)

    rows = []
    for t0, t1 in zip(ends[:-1], ends[1:]):
        day = snaps[snaps["date"] == t0]
        day = day[day["in_index"] & day["score"].notna()]
        if len(day) < MIN_STOCKS:
            continue
        ret = (prices.loc[t1] / prices.loc[t0] - 1.0).reindex(day["symbol"].to_numpy())
        scored = pd.Series(day["score"].to_numpy(), index=day["symbol"].to_numpy())[ret.notna()]
        if len(scored) < MIN_STOCKS:
            continue
        order = scored.sort_values(ascending=False).index
        row = {"month": str(pd.Period(t1, freq="M")), "n": len(scored)}
        for name, (lo, hi) in SLICES.items():
            names = order[lo - 1:hi]
            row[name] = float(ret[names].mean()) * 100 if len(names) else np.nan
        rows.append(row)
    return pd.DataFrame(rows)


def _roll12(x: pd.Series) -> pd.Series:
    """Rolling 12-month compounded return, in %, from monthly returns in %."""
    return (1.0 + x / 100.0).rolling(12).apply(np.prod, raw=True).sub(1.0).mul(100.0)


def main() -> None:
    sl = monthly_slices()
    health = pd.read_csv(ROOT / "data" / "momentum_health.csv")
    need = {"month", "portfolio", "nifty500"}
    if not need <= set(health.columns):
        raise SystemExit("::error::data/momentum_health.csv has no portfolio column to compare with")
    d = sl.merge(health[["month", "portfolio", "nifty500"]], on="month", how="inner")
    d = d.dropna(subset=["portfolio", "nifty500"])
    print(f"months: {len(d)}  ({d['month'].iloc[0]} to {d['month'].iloc[-1]})", flush=True)
    print(f"stocks scored a month: {int(d['n'].min())} to {int(d['n'].max())}\n", flush=True)

    idx12 = _roll12(d["nifty500"])
    book12 = _roll12(d["portfolio"]) - idx12          # our book's 12-month lead
    rows = {}
    for name in SLICES:
        lead12 = _roll12(d[name]) - idx12
        both = pd.concat([lead12, book12], axis=1).dropna()
        monthly_lead = d[name] - d["nifty500"]
        rows[name] = {
            "a month, mean lead pts": monthly_lead.mean(),
            "a month, worst pts": monthly_lead.min(),
            "12m lead now pts": lead12.iloc[-1],
            "12m lead median pts": lead12.median(),
            "12m lead negative %": (lead12 < 0).mean() * 100,
            "corr with the book": both.iloc[:, 0].corr(both.iloc[:, 1]),
            "same sign as the book %": (np.sign(both.iloc[:, 0]) == np.sign(both.iloc[:, 1])).mean() * 100,
        }
    out = pd.DataFrame(rows).T
    print(out.round(2).to_string(), flush=True)

    print("\nthe two deciles against each other, by 5-year block:", flush=True)
    d = d.assign(year=d["month"].str[:4].astype(int))
    for lo in range(int(d["year"].min()), int(d["year"].max()) + 1, 5):
        g = d[(d["year"] >= lo) & (d["year"] < lo + 5)]
        if len(g) < 12:
            continue
        print(f"  {lo}-{lo + 4}: top50 {g['top50'].mean():+.2f} pts a month, "
              f"ranks 51-100 {g['d2'].mean():+.2f}, index {g['nifty500'].mean():+.2f} "
              f"({len(g)} months)", flush=True)

    best = out["corr with the book"].idxmax()
    print(f"\nclosest to our own book: {best} "
          f"(correlation {out.loc[best, 'corr with the book']:.2f}); "
          f"the card shows top100 ({out.loc['top100', 'corr with the book']:.2f}).", flush=True)
    sl.to_csv("decile_split_monthly.csv", index=False)
    print("\nwrote decile_split_monthly.csv", flush=True)


if __name__ == "__main__":
    main()
