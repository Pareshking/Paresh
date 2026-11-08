"""The conditions under which momentum crashes. RESEARCH ONLY, not on the Dashboard.

Owner, 8 Nov 2026 (TODO S110): taken off the Dashboard. The conditions
predict the long-short momentum FACTOR's bad months, as published, but tested
on our own long-only portfolio's backtest in 5-year blocks they gave no
reliable signal: the book's lead over the Nifty 500 vanished in flagged months
in 2010-14 and 2020-24, reversed in 2025-26, and 2015-19 had none; the
continuous readings changed sign between blocks.
scripts/research/crash_state_vs_portfolio.py reproduces this.


Daniel and Moskowitz, "Momentum crashes", Journal of Financial Economics
122(2), 2016, 221-247 (NBER w20439): momentum's crashes come "in 'panic'
states - following market declines and when market volatility is high" and
"are contemporaneous with market rebounds"; they are partly forecastable.
Their state variables: a bear-market flag (the market's past 24-month return
below zero) and the market's variance over the prior 126 sessions.

Checked on Indian data before use (owner, 8 Nov 2026): at each month-end from
2010, the state from the Nifty 500 (data/benchmarks.csv) against the next
month's top-minus-bottom spread (data/momentum_health.csv). In the months
that were both bear and high-volatility the next month averaged -1.6 pts
against +1.4 when calm, and three of the four worst months since 2010 (May
2020, Dec 2011, Mar 2020) came in that state. `evidence` recomputes this from
the committed files, so the page always shows the figures it rests on.

High volatility is the top quarter of month-end readings, judged at each date
against the readings before it (no look-ahead); today's reading is placed
among every month-end since the data allows.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

LOOKBACK_MONTHS = 24
VOL_SESSIONS = 126
HIGH_VOL_PCT = 0.75
CALM, ELEVATED, CRASH = "Calm", "Elevated", "Crash-prone"


@dataclass(frozen=True)
class CrashState:
    as_of: pd.Timestamp
    ret24: float          # the Nifty 500's return over 24 months
    vol: float            # annualised volatility over 126 sessions
    vol_pct: float        # share of month-end readings at or below today's
    verdict: str


def _reading(bench: pd.Series, t: pd.Timestamp) -> tuple[float, float] | None:
    hist = bench.loc[:t].dropna()
    past = hist.index[hist.index <= t - pd.DateOffset(months=LOOKBACK_MONTHS)]
    if len(past) == 0 or len(hist) < VOL_SESSIONS + 1:
        return None
    ret24 = float(hist.iloc[-1] / hist.loc[past[-1]] - 1)
    vol = float(hist.pct_change().iloc[-VOL_SESSIONS:].std() * np.sqrt(252))
    return ret24, vol


def _verdict(bear: bool, high: bool) -> str:
    return CRASH if bear and high else ELEVATED if bear or high else CALM


def month_end_states(bench: pd.Series) -> pd.DataFrame:
    """One row per month-end: ret24, vol, the expanding volatility percentile and the state."""
    b = pd.to_numeric(bench, errors="coerce").dropna().sort_index()
    b.index = pd.DatetimeIndex(b.index)
    ends = b.groupby(b.index.to_period("M")).apply(lambda s: s.index[-1])
    rows = []
    for t in ends:
        got = _reading(b, t)
        if got is not None:
            rows.append({"date": t, "ret24": got[0], "vol": got[1]})
    d = pd.DataFrame(rows)
    if d.empty:
        return d
    d["vol_pct"] = [float((d["vol"].iloc[: i + 1] <= v).mean()) for i, v in enumerate(d["vol"])]
    d["state"] = [_verdict(r < 0, p >= HIGH_VOL_PCT) for r, p in zip(d["ret24"], d["vol_pct"])]
    return d


def current(bench: pd.Series) -> CrashState | None:
    b = pd.to_numeric(bench, errors="coerce").dropna().sort_index()
    if b.empty:
        return None
    b.index = pd.DatetimeIndex(b.index)
    t = b.index[-1]
    got = _reading(b, t)
    states = month_end_states(b)
    if got is None or states.empty:
        return None
    ret24, vol = got
    pct = float((states["vol"] <= vol).mean())
    return CrashState(t, ret24, vol, pct, _verdict(ret24 < 0, pct >= HIGH_VOL_PCT))


def evidence(bench: pd.Series, spread: pd.DataFrame) -> pd.DataFrame:
    """Next month's momentum spread by the state at each month-end.

    `spread`: data/momentum_health.csv (date = the formation month-end,
    spread = the next month's top fifth less bottom fifth, in points).
    """
    states = month_end_states(bench)
    sp = spread.assign(date=pd.to_datetime(spread["date"]))[["date", "spread"]]
    # Month-ends in the two files can differ by a holiday: match on the month.
    states = states.assign(month=states["date"].dt.to_period("M"))
    sp = sp.assign(month=sp["date"].dt.to_period("M")).drop(columns="date")
    return states.merge(sp, on="month", how="inner")


def summary(ev: pd.DataFrame) -> dict:
    """The figures the page quotes: per state, and the worst months."""
    g = ev.groupby("state")["spread"]
    by_state = {s: {"months": int(len(x)), "mean": float(x.mean()), "worst": float(x.min())}
                for s, x in g}
    worst = ev.nsmallest(3, "spread")[["date", "spread", "state"]]
    last_crash = ev.loc[ev["state"] == CRASH, "date"]
    return {"by_state": by_state, "worst": worst,
            "last_crash": last_crash.iloc[-1] if len(last_crash) else None,
            "since": ev["date"].iloc[0] if len(ev) else None}
