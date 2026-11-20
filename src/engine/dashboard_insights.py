"""The Dashboard's inferences (S149, owner 20 Nov 2026: "dashboard must be
insightful, not showing same data but inference from that data").

Pure functions over data the app already holds; the view
(src/ui/views/dashboard_view.py) only formats what these return.

- The market is Nifty Total Market, the 750 stocks this site ranks
  (data/benchmark_indices.csv). The frozen track-record months stay against
  the Nifty 500 as recorded; this module compares them with Total Market
  beside the record, never inside it.
- Momentum indices are NSE's (Nifty200 Momentum 30, Nifty500 Momentum 50,
  Midcap150 Momentum 50, Smallcap250 Momentum Quality 100, Total Market
  Momentum Quality 50), each checked nightly against an ETF.
- Trails (3 months ago, 1 month ago, now) are given for levels and ranks,
  never for returns, which are windows already. "Ago" is the session on or
  before the same date that many months back; month-end measures read the
  month-ends before those dates.
- Every claimed regularity is computed here from the data, not typed into the
  page, so it updates and a test can check it.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

# ── Dates and returns ────────────────────────────────────────────────────────


def on_or_before(index: pd.DatetimeIndex, when: pd.Timestamp) -> pd.Timestamp | None:
    pos = index.searchsorted(pd.Timestamp(when), side="right") - 1
    return index[pos] if pos >= 0 else None


def value_at(series: pd.Series | None, when: pd.Timestamp) -> float | None:
    if series is None:
        return None
    s = series.dropna().sort_index()
    if s.empty:
        return None
    d = on_or_before(s.index, when)
    return None if d is None else float(s.loc[d])


def window_return(close: pd.Series | None, start: pd.Timestamp, end: pd.Timestamp) -> float | None:
    """Percent from the close on or before `start` to the close on or before `end`."""
    a, b = value_at(close, start), value_at(close, end)
    if a is None or b is None or a == 0:
        return None
    return (b / a - 1) * 100


def trail_dates(end: pd.Timestamp) -> dict[str, pd.Timestamp]:
    end = pd.Timestamp(end)
    return {"3m": end - pd.DateOffset(months=3), "1m": end - pd.DateOffset(months=1), "now": end}


def month_end_before(index: pd.DatetimeIndex, when: pd.Timestamp) -> pd.Timestamp | None:
    """The last session of the month before `when`'s month."""
    first = pd.Timestamp(when).to_period("M").to_timestamp()
    return on_or_before(index, first - pd.Timedelta(days=1))


def calendar_month_returns(close: pd.Series) -> pd.Series:
    """Percent per calendar month, by month-end closes, indexed by Period."""
    s = close.dropna().sort_index()
    me = s.groupby(s.index.to_period("M")).last()
    return me.pct_change().dropna() * 100


# ── 1. The book this month ───────────────────────────────────────────────────


@dataclass
class BookMonth:
    book_mtd: float | None
    market_mtd: float | None
    book_ytd: float | None
    market_ytd: float | None
    months_ahead: int
    months: int
    behind_months: list[str]
    momentum_mtd: dict[str, float]            # name -> percent, month so far
    momentum_ytd: dict[str, float]
    ahead_of_momentum: int                     # momentum indices the book beat by 0.05 pts or more
    level_with_momentum: int


def book_month(ledger_months: dict, book_mtd: float | None, market: pd.Series,
               momentum: dict[str, pd.Series], as_of: pd.Timestamp, year: int | None = None) -> BookMonth:
    """`ledger_months`: the track record's {"YYYY-MM": {"strategy": fraction, ...}}.
    `book_mtd`: percent. Months compared with the market's calendar month."""
    as_of = pd.Timestamp(as_of)
    year = year or as_of.year
    mkt_m = calendar_month_returns(market[market.index <= as_of])
    start = pd.Timestamp(f"{year - 1}-12-31")
    month_open = as_of.to_period("M").to_timestamp() - pd.Timedelta(days=1)
    rows = []
    for key in sorted(ledger_months):
        p = pd.Period(key, freq="M")
        if p.year != year:
            continue
        s = ledger_months[key].get("strategy")
        if s is None or p not in mkt_m.index:
            continue
        rows.append((p, float(s) * 100, float(mkt_m.loc[p])))
    if book_mtd is not None:
        m_mtd = window_return(market, month_open, as_of)
        if m_mtd is not None:
            rows.append((as_of.to_period("M"), float(book_mtd), m_mtd))
    ahead = sum(1 for _, b, m in rows if b > m)
    behind = [p.strftime("%b") for p, b, m in rows if b <= m]
    book_ytd = (float(np.prod([1 + b / 100 for _, b, _ in rows])) - 1) * 100 if rows else None
    mom_mtd = {k: v for k, s in momentum.items() if (v := window_return(s, month_open, as_of)) is not None}
    mom_ytd = {k: v for k, s in momentum.items() if (v := window_return(s, start, as_of)) is not None}
    ahead_m = sum(1 for v in mom_mtd.values() if book_mtd is not None and round(book_mtd - v, 1) >= 0.1)
    level_m = sum(1 for v in mom_mtd.values() if book_mtd is not None and abs(round(book_mtd - v, 1)) < 0.1)
    return BookMonth(book_mtd, window_return(market, month_open, as_of), book_ytd,
                     window_return(market, start, as_of), ahead, len(rows), behind,
                     mom_mtd, mom_ytd, ahead_m, level_m)


# ── 3. Momentum's lead, longest window first ────────────────────────────────


def momentum_lead(spreads: pd.DataFrame, mom_index: pd.Series | None, market: pd.Series,
                  as_of: pd.Timestamp) -> list[tuple[str, float | None, str]]:
    """(window, points, note): the top 100 of the ranking less the Nifty 500
    (data/momentum_health.csv, the history's benchmark) over 12 months, the
    last 3 completed months and the last completed month; then the month so far
    from NSE's Nifty500 Momentum 50 less the market, until the month closes."""
    d = spreads.dropna(subset=["top", "nifty500"]).sort_values("month")
    out: list[tuple[str, float | None, str]] = []

    def lead(rows: pd.DataFrame) -> float | None:
        if rows.empty:
            return None
        top = float(np.prod(1 + rows["top"].astype(float) / 100) - 1)
        idx = float(np.prod(1 + rows["nifty500"].astype(float) / 100) - 1)
        return (top - idx) * 100

    last = d.iloc[-1]["month"] if len(d) else None
    out.append(("12 months", lead(d.tail(12)), "Top 100 of the ranking"))
    out.append(("Last 3 months", lead(d.tail(3)), _span(d.tail(3))))
    out.append((pd.Period(last, freq="M").strftime("%B") if last else "Last month", lead(d.tail(1)), ""))
    if mom_index is not None:
        open_ = pd.Timestamp(as_of).to_period("M").to_timestamp() - pd.Timedelta(days=1)
        a, b = window_return(mom_index, open_, as_of), window_return(market, open_, as_of)
        out.append(("Month so far", None if a is None or b is None else a - b, "Nifty500 Momentum 50"))
    return out


def _span(rows: pd.DataFrame) -> str:
    if rows.empty:
        return ""
    first, last = pd.Period(rows.iloc[0]["month"], freq="M"), pd.Period(rows.iloc[-1]["month"], freq="M")
    return f"{first:%b} to {last:%b}"


def losing_streak(spreads: pd.DataFrame, month_so_far: float | None) -> int:
    """Months in a row, newest first, that momentum trailed (month so far included)."""
    d = spreads.dropna(subset=["top", "nifty500"]).sort_values("month")
    leads = list((d["top"] - d["nifty500"]).astype(float))
    if month_so_far is not None:
        leads.append(month_so_far)
    n = 0
    for v in reversed(leads):
        if v < 0:
            n += 1
        else:
            break
    return n


# ── 3. Signals with trails ───────────────────────────────────────────────────


@dataclass
class Signal:
    key: str
    side: str                          # "for", "against", "neutral"
    now: float | None
    trail: list[float | None]          # 3m, 1m, now
    percentile: float | None = None
    since: str | None = None
    extra: dict = field(default_factory=dict)


def percentile_of(history: pd.Series, value: float | None) -> tuple[float | None, str | None]:
    h = history.dropna()
    if value is None or h.empty:
        return None, None
    return float((h < value).mean() * 100), f"{h.index[0]:%b %Y}"


def trail_of(series: pd.Series, as_of: pd.Timestamp) -> list[float | None]:
    return [value_at(series, d) for d in trail_dates(as_of).values()]


def month_end_trail(monthly: pd.Series, as_of: pd.Timestamp) -> list[float | None]:
    """For a month-end measure indexed by month-end date: the month-ends before
    3 months ago, 1 month ago, and the latest one."""
    s = monthly.dropna().sort_index()
    if s.empty:
        return [None, None, None]
    out = []
    for key, d in trail_dates(as_of).items():
        if key == "now":
            out.append(float(s.iloc[-1]))
        else:
            me = month_end_before(s.index, d)
            out.append(None if me is None else float(s.loc[me]))
    return out


def direction(trail: list[float | None], higher_is_better: bool = True, tol: float = 0.5) -> str:
    """'up', 'down', 'v' (fell then recovered), 'flat' on the 1m→now step."""
    a, b, c = trail
    if b is None or c is None:
        return "flat"
    if abs(c - b) < tol:
        return "flat"
    rising = c > b
    if a is not None and rising and b < a and abs(c - a) <= max(tol * 4, abs(a) * 0.1):
        return "v"
    return "up" if rising == higher_is_better else "down"


# ── 4. Money flows ───────────────────────────────────────────────────────────


@dataclass
class Flows:
    as_of: pd.Timestamp
    mtd: float
    month_rank: int                    # 1 = largest month in the record
    months_in_record: int
    prior_record: tuple[str, float] | None
    last20: float
    last20_is_record: bool
    streak: int                        # sessions of net buying in a row, newest first
    before: float                      # net over the 11 months before this one
    before_selling_months: int
    monthly: list[tuple[str, float]]   # last 12 months, ₹ thousand crore
    trail20: list[float | None]
    since: pd.Timestamp | None = None  # first session in the record


def flows_summary(nsdl: pd.DataFrame) -> Flows | None:
    """NSDL FPI equity, ₹ crore (data/nsdl_fpi_daily.csv: date, equity_net)."""
    if nsdl is None or nsdl.empty or "equity_net" not in nsdl:
        return None
    s = pd.Series(pd.to_numeric(nsdl["equity_net"], errors="coerce").values,
                  index=pd.to_datetime(nsdl["date"])).dropna().sort_index()
    if s.empty:
        return None
    as_of = s.index[-1]
    mo = s.groupby(s.index.to_period("M")).sum()
    cur = as_of.to_period("M")
    mtd = float(mo.get(cur, 0.0))
    ranked = mo.sort_values(ascending=False)
    rank = int(list(ranked.index).index(cur)) + 1
    prior = ranked.drop(cur)
    prior_record = (prior.index[0].strftime("%b %Y"), float(prior.iloc[0])) if len(prior) else None
    r20 = s.rolling(20).sum()
    streak = 0
    for v in s.iloc[::-1]:
        if v > 0:
            streak += 1
        else:
            break
    prev11 = mo[(mo.index < cur) & (mo.index >= cur - 11)]
    last12 = mo[mo.index > cur - 12]
    return Flows(as_of, mtd, rank, len(mo), prior_record, float(r20.iloc[-1]),
                 bool(r20.iloc[-1] >= r20.max()), streak, float(prev11.sum()), int((prev11 < 0).sum()),
                 [(p.strftime("%b"), float(v) / 1000) for p, v in last12.items()],
                 trail_of(r20, as_of), s.index[0])


@dataclass
class FlowEvidence:
    months: int
    threshold: float                   # ₹ crore a month that starts the top quarter
    after_heavy: float                 # next-month momentum lead after top-quarter months, pts
    after_rest: float
    hit_heavy: float                   # share of those next months with a positive lead, %
    hit_rest: float
    halves: list[tuple[str, float, float]]
    corr_same: float                   # monthly flows vs the Nifty 500, same month
    corr_next: float
    large_minus_broad: float           # Nifty 50 less Nifty 500 in top-quarter months, pts
    first: str
    last: str


def flow_evidence(nsdl: pd.DataFrame, spreads: pd.DataFrame, bench: pd.DataFrame) -> FlowEvidence | None:
    """Does heavy foreign buying in a month tell us about momentum next month?
    Monthly NSDL FPI equity net against data/momentum_health.csv (top 100 less
    the Nifty 500, `month` labels the month the return belongs to) and
    data/benchmarks.csv. Only completed months; in-sample."""
    if nsdl is None or spreads is None or bench is None:
        return None
    s = pd.Series(pd.to_numeric(nsdl["equity_net"], errors="coerce").values,
                  index=pd.to_datetime(nsdl["date"])).dropna().sort_index()
    cur = s.index[-1].to_period("M")
    mo = s.groupby(s.index.to_period("M")).sum()
    mo = mo[mo.index < cur]
    m = spreads.dropna(subset=["top", "nifty500"]).copy()
    m["p"] = pd.PeriodIndex(m["month"], freq="M")
    lead = pd.Series((m["top"] - m["nifty500"]).astype(float).values, index=m["p"])
    b = bench.sort_index()
    b_m = b[["nifty500", "nifty50"]].groupby(b.index.to_period("M")).last().pct_change() * 100
    d = pd.DataFrame({"fpi": mo}).join(lead.rename("lead")).join(b_m)
    d["lead_next"] = d["lead"].shift(-1)
    d = d.dropna(subset=["fpi", "lead", "nifty500", "nifty50"])
    if len(d) < 24:
        return None
    q = float(d["fpi"].quantile(0.75))
    nxt = d.dropna(subset=["lead_next"])
    hi, lo = nxt[nxt["fpi"] >= q], nxt[nxt["fpi"] < q]
    mid = nxt.index[len(nxt) // 2]
    halves = []
    for name, part in (("first half", nxt[nxt.index < mid]), ("second half", nxt[nxt.index >= mid])):
        qq = float(part["fpi"].quantile(0.75))
        halves.append((f"{part.index[0]:%Y}-{part.index[-1]:%Y}",
                       float(part[part["fpi"] >= qq]["lead_next"].mean()),
                       float(part[part["fpi"] < qq]["lead_next"].mean())))
    heavy_all = d[d["fpi"] >= q]
    return FlowEvidence(
        len(d), q, float(hi["lead_next"].mean()), float(lo["lead_next"].mean()),
        float((hi["lead_next"] > 0).mean() * 100), float((lo["lead_next"] > 0).mean() * 100),
        halves, float(d["fpi"].corr(d["nifty500"])), float(d["fpi"].corr(d["nifty500"].shift(-1))),
        float((heavy_all["nifty50"] - heavy_all["nifty500"]).mean()),
        f"{d.index[0]:%b %Y}", f"{d.index[-1]:%b %Y}")


def dii_window(nse: pd.DataFrame | None) -> tuple[pd.Timestamp, pd.Timestamp, float, int, int] | None:
    """(from, to, net ₹ crore, sessions, selling sessions) for DII in the NSE
    provisional file (data/fii_dii_flows.csv), the current month only."""
    if nse is None or nse.empty:
        return None
    x = nse[nse["category"] == "DII"].copy()
    if x.empty:
        return None
    x["date"] = pd.to_datetime(x["date"])
    cur = x["date"].max().to_period("M")
    x = x[x["date"].dt.to_period("M") == cur].sort_values("date")
    net = pd.to_numeric(x["net"], errors="coerce")
    return x["date"].iloc[0], x["date"].iloc[-1], float(net.sum()), len(x), int((net < 0).sum())


# ── 5. Size, and momentum within each size ──────────────────────────────────

SIZES = (
    ("Large", "nifty200", "nifty200_mom30"),
    ("Mid", "midcap150", "midcap150_mom50"),
    ("Small", "smallcap250", "smallcap250_mq100"),
    ("Micro", "microcap250", None),
)
WINDOWS = (1, 3, 6)


def size_table(closes: dict[str, pd.Series], market: pd.Series, as_of: pd.Timestamp
               ) -> list[tuple[str, list[float | None], list[float | None]]]:
    """(size, [size less market, 1M 3M 6M], [momentum less its size index])."""
    out = []
    for size, parent, mom in SIZES:
        vs, prem = [], []
        for m in WINDOWS:
            start = as_of - pd.DateOffset(months=m)
            p, mk = window_return(closes.get(parent), start, as_of), window_return(market, start, as_of)
            vs.append(None if p is None or mk is None else p - mk)
            q = window_return(closes.get(mom), start, as_of) if mom else None
            prem.append(None if q is None or p is None else q - p)
        out.append((size, vs, prem))
    return out


# ── 6. The book by industry status ──────────────────────────────────────────


def industry_bucket(rel_6m: float, rel_1m: float) -> str:
    if rel_6m > 0 and rel_1m > 0:
        return "strong"
    if rel_6m <= 0 and rel_1m <= 0:
        return "weak"
    return "turning"


def book_by_status(weights: pd.Series, sectors: pd.DataFrame) -> dict[str, float]:
    """Percent of the book in strong, turning and weak industries.
    `weights`: industry -> percent; `sectors`: Industry, rel_6m, rel_1m."""
    s = sectors.set_index("Industry")
    out = {"strong": 0.0, "turning": 0.0, "weak": 0.0, "unknown": 0.0}
    for ind, w in weights.items():
        if ind in s.index:
            out[industry_bucket(float(s.loc[ind, "rel_6m"]), float(s.loc[ind, "rel_1m"]))] += float(w)
        else:
            out["unknown"] += float(w)
    return out


def rotation_moves(paths: dict[str, list[str]]) -> dict[str, list[str]]:
    """From {industry: [3m, 1m, now]} quadrants: who rose to Leading from Lagging
    or Improving 3 months ago, and who led a month ago and now loses pace."""
    risen = [k for k, p in paths.items() if len(p) == 3 and p[2] == "Leading" and p[0] in ("Lagging", "Improving")]
    fading = [k for k, p in paths.items() if len(p) == 3 and p[1] == "Leading" and p[2] in ("Weakening", "Lagging")]
    slid = [k for k, p in paths.items() if len(p) == 3 and p == ["Improving", "Weakening", "Lagging"]]
    stuck = [k for k, p in paths.items() if len(p) == 3 and len(set(p)) == 1 and p[0] == "Weakening"]
    return {"risen": sorted(risen), "fading": sorted(fading), "slid": sorted(slid), "weakening_3m": sorted(stuck)}


# ── 2. Ranks then and now ───────────────────────────────────────────────────


def rank_trail_word(trail: list[int | None], cut: int) -> tuple[str, str]:
    """(word, tone) for a holding's rank trail [3m, 1m, now]; None = did not pass."""
    a, b, c = trail
    if c is None:
        return ("Fell out of the filters", "down") if (a is not None or b is not None) else ("Out of the filters", "down")
    if b is None:
        if a is not None and c > a:
            return f"Faded from #{a}", "down" if c > cut else "watch"
        return ("Back in, past the cut-off" if c > cut else "Back in", "watch" if c > cut else "up")
    if c > cut and c < b:
        return "Climbing, not fast enough", "flat"
    if c - b >= 15:
        return "Sliding fast", "down" if c > cut else "watch"
    if c - b >= 8:
        return "Slipping", "watch"
    if b - c >= 15:
        return "Rising fast", "up"
    return "Steady", "flat"
