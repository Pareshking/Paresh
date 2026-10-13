"""
Sector leadership: did a sector beat the Nifty 500 over the last month, and do
most of its stocks agree?

Two readings per sector, a month apart:

- x: the sector's 1-month return less the Nifty 500's over the same closes.
  The sector return is the equal-weighted mean of its stocks' price returns
  (adjusted closes), not an NSE sector index: we hold no sector index series,
  and an equal weight shows the breadth an index can hide.
- y: the share of its stocks above their N-day EMA, out of the stocks that have
  both a close and an EMA that day (a stock with no print is not "below").

A period is calendar months (1 or 3): the last session on or before the same
date that many months earlier.

Each sector also names the two stocks doing the heavy lifting: in an equal
weight every stock adds its own return / N to the sector's, so the largest
contributions are the largest returns over the latest period.
"""

from __future__ import annotations

import pandas as pd

EMA_SPANS: tuple[int, ...] = (20, 50, 100, 200)
# A group of one is a stock, not a sector.
MIN_STOCKS = 2


def _session_on_or_before(index: pd.DatetimeIndex, when: pd.Timestamp) -> pd.Timestamp | None:
    pos = index.searchsorted(when, side="right") - 1
    return index[pos] if pos >= 0 else None


def _ret(frame: pd.DataFrame | pd.Series, a: pd.Timestamp, b: pd.Timestamp):
    return frame.loc[b] / frame.loc[a] - 1


def leadership_dates(index: pd.DatetimeIndex, months: int = 1
                     ) -> tuple[pd.Timestamp, pd.Timestamp, pd.Timestamp] | None:
    """(two periods back, one period back, today) as sessions in `index`."""
    if len(index) == 0:
        return None
    now = index[-1]
    then = _session_on_or_before(index, now - pd.DateOffset(months=months))
    if then is None:
        return None
    before = _session_on_or_before(index, then - pd.DateOffset(months=months))
    if before is None:
        return None
    return before, then, now


def sector_leadership(
    prices: pd.DataFrame,
    groups: pd.Series,
    bench: pd.Series,
    span: int = 200,
    min_stocks: int = MIN_STOCKS,
    months: int = 1,
) -> pd.DataFrame:
    """One row per sector: where it is today and where it was a month ago.

    prices: adjusted closes, dates x symbols. groups: symbol -> sector.
    bench: Nifty 500 closes by date (read as of each session, so a benchmark a
    day ahead of the prices does not matter).
    """
    cols = ["Sector", "Stocks", "Then", "Now", "x_then", "x_now", "y_then", "y_now",
            "above_then", "obs_then", "above_now", "obs_now", "ret_now", "bench_now", "Months", "Leaders"]
    if prices is None or prices.empty or groups is None or groups.empty:
        return pd.DataFrame(columns=cols)
    groups = groups.dropna().astype(str).str.strip()
    groups = groups[(groups != "") & groups.index.isin(prices.columns)]
    prices = prices[groups.index].sort_index()
    dates = leadership_dates(prices.index, months)
    bench = pd.to_numeric(bench, errors="coerce").dropna().sort_index()
    if dates is None or bench.empty:
        return pd.DataFrame(columns=cols)
    before, then, now = dates
    b = {d: bench.asof(d) for d in dates}
    if any(pd.isna(v) for v in b.values()):
        return pd.DataFrame(columns=cols)
    bench_then = b[then] / b[before] - 1
    bench_now = b[now] / b[then] - 1

    ema = prices.ewm(span=span, min_periods=max(int(span * 0.8), 5)).mean()
    snap = {}
    for d in (then, now):
        p, e = prices.loc[d], ema.loc[d]
        observed = p.notna() & e.notna()
        snap[d] = ((p > e) & observed, observed)
    r_then = _ret(prices, before, then)
    r_now = _ret(prices, then, now)

    rows = []
    for name, members in groups.groupby(groups).groups.items():
        members = list(members)
        if len(members) < min_stocks:
            continue
        a_t, o_t = snap[then][0][members].sum(), snap[then][1][members].sum()
        a_n, o_n = snap[now][0][members].sum(), snap[now][1][members].sum()
        rt, rn = r_then[members].dropna(), r_now[members].dropna()
        if not o_t or not o_n or rt.empty or rn.empty:
            continue
        rows.append({
            "Sector": str(name), "Stocks": len(members), "Then": then, "Now": now,
            "x_then": float(rt.mean() - bench_then), "x_now": float(rn.mean() - bench_now),
            "y_then": float(a_t / o_t), "y_now": float(a_n / o_n),
            "above_then": int(a_t), "obs_then": int(o_t),
            "above_now": int(a_n), "obs_now": int(o_n),
            "ret_now": float(rn.mean()), "bench_now": float(bench_now),
            "Months": int(months),
            # The two largest contributions to the latest period's move.
            "Leaders": [(str(k), float(v)) for k, v in rn.sort_values(ascending=False).head(2).items()],
        })
    return pd.DataFrame(rows, columns=cols)
