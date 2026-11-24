"""The Dashboard's inferences (S149, owner 20 Nov 2026: "dashboard must be
insightful, not showing same data but inference from that data").

Pure functions over data the app already holds; the view
(src/ui/views/dashboard_home_view.py) only formats what these return.

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


def as_of(close: pd.Series | None, end: pd.Timestamp) -> pd.Series:
    """The series if it has a close for `end`, else empty (S148, 21 Nov 2026).

    Every reader looks a close up "on or before" a date, so an index missing the
    page's session gave yesterday's figure under today's caption ("Indices, 19 Nov"
    showed Nifty 50 for 18 Nov). Empty reads as "–" everywhere instead."""
    if close is None:
        return pd.Series(dtype=float)
    s = close.dropna()
    return s if len(s) and s.index.max() >= pd.Timestamp(end) else s.iloc[0:0]


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


def first_fill(close: pd.Series | None, month: pd.Period | None) -> pd.Timestamp | None:
    """The first session of `month` in `close`: a system's first fill (S193 A12).

    A system's first month has no book before it, so the record measures the book and the
    Nifty 500 from that close (backtester.py, "A system's first month has no old book").
    Every index set beside it in that month starts there too (owner, 23 Nov 2026).
    """
    if close is None or month is None:
        return None
    s = close.dropna()
    days = s.index[(s.index >= month.start_time) & (s.index <= month.end_time)]
    return pd.Timestamp(days[0]) if len(days) else None


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
               momentum: dict[str, pd.Series], as_of: pd.Timestamp, year: int | None = None,
               first_month: pd.Period | None = None) -> BookMonth:
    """`ledger_months`: the track record's {"YYYY-MM": {"strategy": fraction, ...}}.
    `book_mtd`: percent. Months compared with the market's calendar month, except the
    system's `first_month`, which starts at its first fill for the market and momentum
    as it does for the book (S193 A12)."""
    as_of = pd.Timestamp(as_of)
    year = year or as_of.year
    mkt_m = calendar_month_returns(market[market.index <= as_of])
    start = pd.Timestamp(f"{year - 1}-12-31")
    month_open = as_of.to_period("M").to_timestamp() - pd.Timedelta(days=1)
    fill = first_fill(market, first_month)
    if fill is not None and as_of.to_period("M") == first_month:
        month_open = fill
    rows = []
    for key in sorted(ledger_months):
        p = pd.Period(key, freq="M")
        if p.year != year:
            continue
        s = ledger_months[key].get("strategy")
        if s is None or p not in mkt_m.index:
            continue
        m = float(mkt_m.loc[p])
        if fill is not None and p == first_month:
            m = window_return(market, fill, p.end_time)
            if m is None:
                continue
        rows.append((p, float(s) * 100, m))
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
    out.append(("12 months", lead(d.tail(12)), "Top 100 of the ranking" + (f", finished months {_span(d.tail(12))}" if len(d) >= 12 else "")))
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
    if first.year != last.year:   # "Nov 2025 to Oct 2026"; within one year "Aug to Oct"
        return f"{first:%b %Y} to {last:%b %Y}"
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
    month_from: pd.Timestamp | None = None   # first session of the month so far

    @property
    def month_span(self) -> str:
        """The month so far's days, as the domestic tile names them: "1 to 20 Nov"."""
        a = self.month_from if self.month_from is not None else self.as_of
        return f"{a:%-d %b}" if a == self.as_of else f"{a:%-d} to {self.as_of:%-d %b}"


def cut_at(frame: pd.DataFrame | None, end: pd.Timestamp | None, col: str = "date") -> pd.DataFrame | None:
    """Rows dated on or before `end`: a file that runs ahead of the page's session (NSDL's ended on 23 Nov
    under a page of 20 Nov prices) is read to that session only (S193 E)."""
    if frame is None or end is None or col not in getattr(frame, "columns", ()):
        return frame
    return frame[pd.to_datetime(frame[col], errors="coerce") <= pd.Timestamp(end)]


def flows_summary(nsdl: pd.DataFrame, end: pd.Timestamp | None = None) -> Flows | None:
    """NSDL FPI equity, ₹ crore (data/nsdl_fpi_daily.csv: date, equity_net), to `end` (the page's session)
    when given."""
    if nsdl is None or nsdl.empty or "equity_net" not in nsdl:
        return None
    s = pd.Series(pd.to_numeric(nsdl["equity_net"], errors="coerce").values,
                  index=pd.to_datetime(nsdl["date"])).dropna().sort_index()
    if end is not None:
        s = s[s.index <= pd.Timestamp(end)]
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
                 trail_of(r20, as_of), s.index[0], s.index[s.index.to_period("M") == cur][0])


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
    heavy_months: int = 0              # months in the top quarter
    tested: int = 0                    # months with a next month to test (S193 B row 24)
    tested_heavy: int = 0              # top-quarter months among them: the after_heavy sample


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
    for _name, part in (("first half", nxt[nxt.index < mid]), ("second half", nxt[nxt.index >= mid])):
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
        f"{d.index[0]:%b %Y}", f"{d.index[-1]:%b %Y}", int(len(heavy_all)), int(len(nxt)), int(len(hi)))


# ── 5. Size, and momentum within each size ──────────────────────────────────

# (size, its size index, its momentum index, the index that momentum index picks from).
# Large is the Nifty 100, SEBI's top 100 and the Indices page's large caps (owner, 21 Nov 2026);
# its momentum index, Nifty200 Momentum 30, is read against the Nifty 200 it picks from.
SIZES = (
    ("Large", "nifty100", "nifty200_mom30", "nifty200"),
    ("Mid", "midcap150", "midcap150_mom50", "midcap150"),
    ("Small", "smallcap250", "smallcap250_mq100", "smallcap250"),
    ("Micro", "microcap250", None, "microcap250"),
)
WINDOWS = (1, 3, 6)


def size_table(closes: dict[str, pd.Series], market: pd.Series, as_of: pd.Timestamp
               ) -> list[tuple[str, list[float | None], list[float | None]]]:
    """(size, [size less market, 1M 3M 6M], [momentum less its size index])."""
    out = []
    for size, parent, mom, mom_parent in SIZES:
        vs, prem = [], []
        for m in WINDOWS:
            start = as_of - pd.DateOffset(months=m)
            p, mk = window_return(closes.get(parent), start, as_of), window_return(market, start, as_of)
            vs.append(None if p is None or mk is None else p - mk)
            q = window_return(closes.get(mom), start, as_of) if mom else None
            mp = window_return(closes.get(mom_parent), start, as_of)
            prem.append(None if q is None or mp is None else q - mp)
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
        # "Out": the site's one word for a stock failing the filters (src/ui/missing_words.OUT; S203, S193 E R1).
        return ("Fell out of the filters", "down") if (a is not None or b is not None) else ("Out", "down")
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


# ── v7 additions (S150) ─────────────────────────────────────────────────────


@dataclass
class Turnover:
    top: int
    new: int                                         # names in today's top `top` that were not there a month ago
    climbers: list[tuple[str, int | None, int | None, int]]   # (symbol, 3M ago, 1M ago, now), best now first
    fallers: list[tuple[str, int, int | None]]                # (symbol, 1M ago, now), best a month ago first


def leadership_turnover(ranks: pd.DataFrame, top: int = 40, show: int = 6) -> Turnover | None:
    """`ranks`: index symbol, columns "3m", "1m", "now" (NaN = not ranked that day)."""
    if ranks is None or ranks.empty or not {"1m", "now"} <= set(ranks.columns):
        return None
    now, m1 = ranks["now"], ranks["1m"]
    m3 = ranks["3m"] if "3m" in ranks else pd.Series(np.nan, index=ranks.index)
    in_now = now <= top
    was = m1 <= top
    new = ranks[in_now & ~was.fillna(False)].sort_values("now")
    gone = ranks[was & ~in_now.fillna(False)].sort_values("1m")
    iv = lambda v: None if pd.isna(v) else int(v)  # noqa: E731
    climbers = [(str(s), iv(m3[s]), iv(m1[s]), int(now[s])) for s in new.index[:show]]
    fallers = [(str(s), int(m1[s]), iv(now[s])) for s in gone.index[:max(show // 2, 3)]]
    return Turnover(top, int(len(new)), climbers, fallers)


def typical_stock(prices: pd.DataFrame, market: pd.Series, as_of: pd.Timestamp,
                  windows=(1, 3, 6, 12)) -> dict[str, list[float | None]] | None:
    """The 750 three ways against the market, percent: equal-weighted,
    median stock, and the share of stocks ahead of the market."""
    from src.engine import peer_index as pi
    if prices is None or prices.empty or market is None or market.empty:
        return None
    px = prices.loc[:as_of]
    ew = pi.equal_weight_level(px)
    out = {"market": [], "equal_weight": [], "median": [], "beat_share": []}
    for m in windows:
        start = as_of - pd.DateOffset(months=m)
        mk = window_return(market, start, as_of)
        e_ = pi.window_return(ew, start, as_of)
        d0, d1 = on_or_before(px.index, start), on_or_before(px.index, as_of)
        r = ((px.loc[d1] / px.loc[d0] - 1) * 100).dropna() if d0 is not None and d1 is not None else pd.Series(dtype=float)
        out["market"].append(mk)
        out["equal_weight"].append(None if e_ is None else e_ * 100)
        out["median"].append(float(r.median()) if len(r) else None)
        out["beat_share"].append(float((r > mk).mean() * 100) if len(r) and mk is not None else None)
    return out


def size_breadth(prices: pd.DataFrame, lists: dict[str, list[str]], as_of: pd.Timestamp
                 ) -> list[tuple[str, list[float | None]]]:
    """Share above the 200D EMA by size list: 3 months ago, 1 month ago, now."""
    from src.engine import market_questions as mq
    out = []
    for name, syms in lists.items():
        cols = [s for s in syms if s in prices.columns]
        if not cols:
            continue
        out.append((name, trail_of(mq._share_above_ema(prices[cols], 200), as_of)))
    return out


def fpi_share_of_value(flows: Flows, market_value_cr: float | None) -> tuple[float, float] | None:
    """(this month, the 11 months before) as % of the ranked list's market value (the chosen system's)."""
    if flows is None or not market_value_cr:
        return None
    return flows.mtd / market_value_cr * 100, flows.before / market_value_cr * 100


def rank_trails(prices: pd.DataFrame, symbols, snap: pd.DataFrame | None = None,
                now: pd.Series | None = None) -> tuple[dict, dict]:
    """Each stock's rank 3 months ago, a month ago and now, under today's rule.

    One definition for every page (S151, S154): `rank_history.snapshots`, the rank
    among the stocks that pass the rule's filters on that date; None is "Out".
    `now`, when given, is today's place among the qualified from the ranking the plan
    trades on (`exit_watch.qualified_ranks`), so the trail's last point is the plan's
    rank on every page (Actions redesign, 20 Nov 2026). Returns (dates, {symbol: [3m, 1m, now]}).
    """
    from src.engine.rank_history import snapshots
    px = prices.sort_index()
    dates = {k: on_or_before(px.index, d) for k, d in trail_dates(px.index[-1]).items()}
    if snap is None:
        snap = snapshots(px, [d for d in dates.values() if d is not None])
    ranks = {}
    for sym in symbols:
        row = []
        for d in dates.values():
            hit = snap[(snap["date"] == d) & (snap["symbol"] == sym)]["rank"]
            row.append(None if hit.empty or pd.isna(hit.iloc[0]) else int(hit.iloc[0]))
        if now is not None:
            q = now.get(sym)
            row[-1] = None if q is None or pd.isna(q) else int(q)
        ranks[sym] = row
    return dates, ranks


@dataclass
class LagEpisode:
    peak: pd.Timestamp          # month-end of the relative line's best before the fall
    low: pd.Timestamp           # month-end of the fall's deepest point
    depth: float                # % below the peak at the low
    recovered: pd.Timestamp | None
    months_to_recover: int | None


@dataclass
class MomentumLag:
    """How far this ranking's top 100 sits below its best against the Nifty 500, and its past
    falls (owner, 21 Nov 2026: what the Dashboard takes from the Indices page). Descriptive: no
    forecast; a recovery time rests on as many episodes as are listed."""
    now: float                  # % below the best so far, at the last completed month
    best: pd.Timestamp          # month-end of that best
    as_of: pd.Timestamp
    episodes: list[LagEpisode]  # deepest first


def momentum_lag(spreads: pd.DataFrame, min_depth: float = 10.0) -> MomentumLag | None:
    """The relative line top 100 / Nifty 500 from momentum_health.csv's monthly returns, and
    every fall from a peak deeper than `min_depth` %, with the month it got back."""
    from src.engine import metrics
    d = spreads.dropna(subset=["top", "nifty500"]).sort_values("month")
    if len(d) < 13:
        return None
    when = pd.to_datetime(d["month"]) + pd.offsets.MonthEnd(0)
    rel = pd.Series(((1 + d["top"].to_numpy() / 100).cumprod() / (1 + d["nifty500"].to_numpy() / 100).cumprod()),
                    index=pd.DatetimeIndex(when))
    dd = metrics.drawdown(rel) * 100
    eps, i, n = [], 0, len(rel)
    while i < n:
        if dd.iloc[i] < 0:
            j = i
            while j < n and dd.iloc[j] < 0:
                j += 1
            seg = dd.iloc[i:j]
            if -seg.min() >= min_depth:
                peak = rel.index[i - 1] if i > 0 else rel.index[0]
                low = seg.idxmin()
                rec = rel.index[j] if j < n else None
                months = None if rec is None else (rec.year - peak.year) * 12 + rec.month - peak.month
                eps.append(LagEpisode(peak, low, float(seg.min()), rec, months))
            i = j
        else:
            i += 1
    best = rel[: rel.index[-1]].idxmax()
    return MomentumLag(float(dd.iloc[-1]), pd.Timestamp(best), rel.index[-1], sorted(eps, key=lambda e: e.depth))
