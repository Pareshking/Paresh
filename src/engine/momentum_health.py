"""Momentum health: how momentum itself has been paying, month by month (S91).

Each month-end, the index's members are ranked by this site's own composite
score (rank_history.snapshots, the backtester's _composite_z_score with the live
lookback weights, scored among that day's members). The measure is the next
month's equal-weighted return of the top fifth minus the bottom fifth: a
winners-minus-losers spread built from our ranking, the same idea as the
academic momentum factor (WML).

  spread        that month's top-fifth minus bottom-fifth return, in points
  trailing_12m  the sum of the last 12 monthly spreads
  percentile    where today's trailing_12m sits among every past one (0-100)
  crash         the latest month's spread is negative and in the worst 10% of all months
  qualified     the share of the month-end's index members passing the strategy's
                own gates (above the 50D EMA, within 20% of the 52-week high;
                rank_history.snapshots' `qualifies`), TODO S110 item 2: in the
                quarter of months with the lowest share since 2010 the next
                month's spread averaged -0.4 pts, against +1.9 in the highest

Checked against an independent series before use: IIM Ahmedabad's Indian WML
factor (survivorship-bias adjusted; docs/MOMENTUM_HEALTH.md). Nothing here is a
forecast; it says how the factor has been paying, not how it will.
"""
from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd

from src.engine.rank_history import snapshots

TOP_FRACTION = 0.2
CRASH_PERCENTILE = 10.0
MIN_STOCKS = 100           # a month with fewer scored members has no reading


def month_ends(prices: pd.DataFrame) -> list[pd.Timestamp]:
    """The last session of every month in the frame."""
    idx = pd.DatetimeIndex(prices.index)
    s = pd.Series(idx, index=idx)
    return list(s.groupby([idx.year, idx.month]).max())


def _complete(day: pd.Timestamp) -> bool:
    """A month counts only once its last weekday has traded (3 days' grace for holidays)."""
    return day >= pd.offsets.BMonthEnd().rollforward(day) - pd.Timedelta(days=3)


def monthly_spreads(prices: pd.DataFrame, membership=None, *, first_month: pd.Period | None = None,
                    config_weights: Sequence[float] = (0.10, 0.30, 0.30, 0.20, 0.10)) -> pd.DataFrame:
    """One row per month: `month` (the month the return is earned in), `date`
    (the formation month-end before it), the top and bottom fifth returns (%),
    the spread (points) and the count of stocks scored.

    `first_month`: the membership's first month. Earlier dates would score every
    stock that was EVER a member, a list that knows the future, so they are left
    out. A month still in progress is left out too."""
    ends = month_ends(prices)
    if ends and not _complete(ends[-1]):
        ends = ends[:-1]
    if first_month is not None:
        ends = [d for d in ends if pd.Period(d, freq="M") >= first_month]
    if len(ends) < 2:
        return pd.DataFrame(columns=["month", "date", "top", "bottom", "spread", "n", "qualified", "ew",
                                     "top50", "d2"])
    snaps = snapshots(prices, ends[:-1], membership=membership, config_weights=config_weights)
    rows = []
    for t0, t1 in zip(ends[:-1], ends[1:]):
        day = snaps[snaps["date"] == t0]
        members = day[day["in_index"] & prices.loc[t0].reindex(day["symbol"].to_numpy()).notna().to_numpy()]
        qualified = float(members["qualifies"].mean()) if len(members) else float("nan")
        day = day[day["in_index"] & day["score"].notna()]
        if len(day) < MIN_STOCKS:
            continue
        p0, p1 = prices.loc[t0], prices.loc[t1]
        ret = (p1 / p0 - 1.0).reindex(day["symbol"].to_numpy())
        scored = pd.Series(day["score"].to_numpy(), index=day["symbol"].to_numpy())[ret.notna()]
        if len(scored) < MIN_STOCKS:
            continue
        k = max(int(len(scored) * TOP_FRACTION), 1)
        order = scored.sort_values(ascending=False)
        top = float(ret[order.index[:k]].mean()) * 100
        bottom = float(ret[order.index[-k:]].mean()) * 100
        # The top fifth split in two (owner, 8 Nov 2026: "give bifurcation of
        # top two deciles also"). Research over 201 months: the top decile led
        # the index by 1.01 pts a month against 0.59 for the second, and that
        # order held in every five-year block (scripts/research/decile_split.py).
        half = max(k // 2, 1)
        top50 = float(ret[order.index[:half]].mean()) * 100
        d2 = float(ret[order.index[half:k]].mean()) * 100 if k > half else float("nan")
        # The equal-weighted average of every scored member: splits the long
        # leg into momentum (top - ew) and breadth (ew - the index); owner, 8 Nov 2026.
        ew = float(ret[scored.index].mean()) * 100
        rows.append({"month": str(pd.Period(t1, freq="M")), "date": t0, "top": top, "bottom": bottom, "spread": top - bottom, "n": len(scored),
                     "qualified": qualified, "ew": ew, "top50": top50, "d2": d2})
    return pd.DataFrame(rows)


def latest_qualified(prices: pd.DataFrame, membership=None, *,
                     first_month: pd.Period | None = None,
                     config_weights: Sequence[float] = (0.10, 0.30, 0.30, 0.20, 0.10)) -> dict | None:
    """The newest month-end's qualified share, with no next month needed.

    `monthly_spreads` can only write a month once the following month has
    closed, because its return is the point. The qualified share is not a
    return: it is a count taken at the month-end itself. Reading it from the
    spreads therefore left the card a month behind -- on 9 Nov 2026 it showed
    September (audit U-M8). This reads the same thing at the latest complete
    month-end, and the monthly job writes it beside the spreads.
    """
    ends = month_ends(prices)
    if ends and not _complete(ends[-1]):
        ends = ends[:-1]
    if first_month is not None:
        ends = [d for d in ends if pd.Period(d, freq="M") >= first_month]
    if not ends:
        return None
    t0 = ends[-1]
    day = snapshots(prices, [t0], membership=membership, config_weights=config_weights)
    members = day[day["in_index"] & prices.loc[t0].reindex(day["symbol"].to_numpy()).notna().to_numpy()]
    if len(members) < MIN_STOCKS:
        return None
    return {"date": str(pd.Timestamp(t0).date()),
            "qualified": float(members["qualifies"].mean()),
            "n": int(len(members))}


def qualified_on(prices: pd.DataFrame, dates, membership=None, *, config_weights=None) -> dict:
    """{session: the share of that day's index members passing the strategy's
    filters}, the reading `latest_qualified` takes at a month-end, on any
    session. The Dashboard's "Stocks that qualify" shows today's share beside
    the month-end one (staleness audit, 21 Nov 2026: the row read 30 Oct's 17%
    under a column headed "Now")."""
    kw = {} if config_weights is None else {"config_weights": config_weights}
    out = {}
    days = [pd.Timestamp(d) for d in dates if d is not None]
    if not days or prices is None or prices.empty:
        return out
    snap = snapshots(prices, days, membership=membership, **kw)
    for day, part in snap.groupby("date"):
        px = prices.loc[day].reindex(part["symbol"].to_numpy()).notna().to_numpy()
        members = part[part["in_index"].to_numpy() & px]
        if len(members) >= MIN_STOCKS:
            out[pd.Timestamp(day)] = float(members["qualifies"].mean())
    return out


def health(spreads: pd.DataFrame) -> dict | None:
    """Today's reading from the monthly spreads, or None with under two years."""
    if spreads is None or len(spreads) < 24:
        return None
    s = spreads.set_index("month")["spread"].astype(float)
    t12 = s.rolling(12).sum().dropna()
    now = float(t12.iloc[-1])
    last = float(s.iloc[-1])
    return {
        "month": str(s.index[-1]),
        "month_spread": last,
        "trailing_12m": now,
        "percentile": float((t12 <= now).mean() * 100),
        # A loss, and among the worst 10% of months: a weak positive month is not a crash.
        "crash": bool(last < 0 and last <= np.percentile(s.to_numpy(), CRASH_PERCENTILE)),
        "months": int(len(s)),
        "trailing_history": t12,
    }




# The Nifty 500's top fifth split in two, and winners against losers (owner, 8 Nov 2026: "give bifurcation of top two
# deciles also"; dropped with the old Dashboard on 20 Nov without his decision, restored S239 on his "Restore the 9", 28 Nov).
SPLIT_ROWS = (("top50", "Top 50", "nifty500"), ("d2", "Ranks 51–100", "nifty500"), ("top", "Top 100 (the top fifth)", "nifty500"),
              ("top", "Top 100 less bottom 100", "bottom"))


def top_fifth_split(spreads: pd.DataFrame | None) -> dict | None:
    """Each row's 12-month return less its benchmark's, both compounded over the same 12 months (the gap between two
    12-month returns a reader can check, as `docs/MOMENTUM_HEALTH.md` sets out), to the last month and to the month
    before, with the share of 12-month windows since 2010 at or below today's. None without two years of months."""
    if spreads is None or not {"month", "top", "nifty500"} <= set(spreads.columns):
        return None
    d = spreads.copy()
    for c in ("top", "bottom", "nifty500", "top50", "d2"):
        if c in d:
            d[c] = pd.to_numeric(d[c], errors="coerce")
    d = d.dropna(subset=["top", "nifty500"]).reset_index(drop=True)
    if len(d) < 24:
        return None

    def r12(c):
        return (1.0 + d[c] / 100.0).rolling(12).apply(np.prod, raw=True).sub(1.0).mul(100.0)
    rows = []
    for col, label, bench in SPLIT_ROWS:
        if col not in d or bench not in d or d[col].tail(13).isna().any():
            continue
        gap = (r12(col) - r12(bench)).dropna()
        if len(gap) < 2:
            continue
        hist = pd.Series(gap.to_numpy(), index=pd.PeriodIndex(d.loc[gap.index, "month"].astype(str), freq="M")
                         .to_timestamp(how="end").normalize())
        rows.append({"label": label, "col": col, "now": float(gap.iloc[-1]), "ago": float(gap.iloc[-2]),
                     "pct": float((gap <= gap.iloc[-1]).mean() * 100), "reference": bench == "bottom", "series": hist})
    return {"month": str(d["month"].iloc[-1]), "first": str(d["month"].iloc[0]), "rows": rows} if rows else None
