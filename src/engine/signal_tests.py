"""Which of the Dashboard's signals have said anything about next month (S150).

Each signal is a yes/no reading at a month-end. Its test, fixed before any
result was seen (20 Nov 2026): momentum's lead the next month (the top 100 of
the ranking less the Nifty 500, data/momentum_health.csv) must differ by at
least PASS_PTS points between months when the signal was on and months when it
was off, in the direction the signal claims, and with the same sign in both
halves of the record. A signal that fails stays on the page, marked so.

Breadth and participation are read on the Nifty 500's members of each month
(src/engine/pit_breadth.py). Counted on today's members, the first run said thin
breadth was no signal and a participation jump pointed against momentum; on the
members of the day the first passes and the second is not confirmed.

All of this is in-sample: the thresholds and the rule were set on the record
they are tested on.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

PASS_PTS = 1.0
START = pd.Period("2010-01", "M")


@dataclass
class Result:
    key: str
    name: str
    claim: str              # "stronger" or "weaker": what the signal says when on
    on: float               # mean next-month lead after on months, pts
    off: float
    n_on: int
    n: int
    halves: tuple[float, float]
    first: str
    last: str
    passed: bool
    threshold: float | None = None   # the reading that turns the signal on, where it is a level

    def to_dict(self) -> dict:
        d = asdict(self)
        d["halves"] = list(self.halves)
        return d


def lead_by_month(spreads: pd.DataFrame) -> pd.Series:
    """Momentum's lead in each month, pts, indexed by the month the return belongs to."""
    return pd.Series((pd.to_numeric(spreads["top"], errors="coerce")
                      - pd.to_numeric(spreads["nifty500"], errors="coerce")).values,
                     index=pd.PeriodIndex(spreads["month"], freq="M")).dropna()


def run(key: str, name: str, state: pd.Series, lead: pd.Series, claim: str) -> Result | None:
    """`state`: bool by month-end Period (on at that month-end); tested against the next month's lead."""
    d = pd.DataFrame({"on": state.astype("boolean")})
    d["next"] = [lead.get(p + 1, np.nan) for p in d.index]
    d = d.dropna()
    d = d[d.index >= START]
    if len(d) < 24 or d["on"].all() or not d["on"].any():
        return None
    d["on"] = d["on"].astype(bool)
    on, off = d[d["on"]]["next"], d[~d["on"]]["next"]
    mid = d.index[len(d) // 2]
    halves = []
    for part in (d[d.index < mid], d[d.index >= mid]):
        a, b = part[part["on"]]["next"], part[~part["on"]]["next"]
        halves.append(float(a.mean() - b.mean()) if len(a) and len(b) else float("nan"))
    diff = float(on.mean() - off.mean())
    sign = -1 if claim == "weaker" else 1
    ok = sign * diff >= PASS_PTS and all(np.isfinite(h) and sign * h > 0 for h in halves)
    return Result(key, name, claim, round(float(on.mean()), 2), round(float(off.mean()), 2), int(len(on)),
                  int(len(d)), (round(halves[0], 2), round(halves[1], 2)), str(d.index[0]), str(d.index[-1]), bool(ok))


def month_end_values(series: pd.Series, through: pd.Period | None = None) -> pd.Series:
    """The last reading of each month, by Period; months after `through` dropped."""
    s = series.dropna().sort_index()
    out = s.groupby(s.index.to_period("M")).last()
    return out if through is None else out[out.index <= through]


def all_tests(spreads: pd.DataFrame, n500: pd.Series, fpi_daily: pd.Series | None,
              breadth: pd.DataFrame | None, through: pd.Period) -> dict:
    """Every signal's test. `breadth`: point-in-time Nifty 500 readings by date
    (columns above_200, above_50). `through`: the last completed month."""
    from src.engine import market_questions as mq
    lead = lead_by_month(spreads)
    out: dict[str, Result | None] = {}
    me = lambda s: month_end_values(s, through)  # noqa: E731
    ema, ten, fh = me(mq._ema_gap_series(n500)), me(mq._ten_month_series(n500)), me(mq._from_high_series(n500))
    out["trend_fast"] = run("trend_fast", "Nifty 500 above its 200D EMA", ema > 0, lead, "stronger")
    out["trend_slow"] = run("trend_slow", "Nifty 500 above its 10-month average", ten > 0, lead, "stronger")
    out["rebound"] = run("rebound", "Sharp rebound: within 3% of the 52W high after a 5-pt jump in a month",
                         (fh - fh.shift(1) >= 5) & (fh >= -3), lead, "weaker")
    q = pd.Series(pd.to_numeric(spreads["qualified"], errors="coerce").values,
                  index=pd.PeriodIndex(spreads["month"], freq="M") - 1).dropna()
    out["qualify"] = run("qualify", "Few stocks qualify: bottom quarter of month-ends",
                         q <= q.quantile(0.25), lead, "weaker")
    if fpi_daily is not None and len(fpi_daily):
        fm = fpi_daily.groupby(fpi_daily.index.to_period("M")).sum()
        fm = fm[fm.index <= through]
        cut = float(fm.quantile(0.75))
        out["fpi"] = run("fpi", "Heavy foreign buying: top quarter of months", fm >= cut, lead, "stronger")
        if out["fpi"] is not None:
            out["fpi"].threshold = round(cut, 0)   # ₹ crore in a month
    if breadth is not None and len(breadth):
        a200, a50 = me(breadth["above_200"]), me(breadth["above_50"])
        out["breadth_thin"] = run("breadth_thin", "Breadth thin: 40% or fewer above the 200D EMA",
                                  a200 <= 40, lead, "weaker")
        out["participation_jump"] = run("participation_jump", "Participation jump: 50D share up 15 pts in a month",
                                        (a50 - a50.shift(1)) >= 15, lead, "stronger")
    return {"average": round(float(lead[lead.index >= START].loc[:str(through)].mean()), 2),
            "through": str(through),
            "tests": {k: v.to_dict() for k, v in out.items() if v is not None}}
