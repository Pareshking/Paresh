"""What the Portfolio page says about the record (S151, mock-up v3 approved 20 Nov 2026).

Pure functions over three daily series: the book's value (src/ui/book_series.py),
Nifty Total Market and Nifty500 Momentum 50 (data/benchmark_indices.csv). Every
table here grows with the record by itself: 1 year, 3 years, 5 years and a
yearly rate join the periods once the record is that old; risk adds the last 12
months and each calendar year from the record's second year (owner, 20 Nov:
"from Jan 2027 onwards it will have yearly data automatically").

Definitions (owner, 20 Nov: "Is our daily % fall wording correct?"):
  below its peak     value ÷ the highest close so far − 1, today
  largest fall       the deepest "below its peak" so far (maximum drawdown),
                     with its peak, its low and the day it was back at the peak
  worst day          the largest fall from one close to the next
  worst month-end    the largest fall counting month-end values only
  tracking error     the spread of the daily gaps (book − market), × √250
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.engine.metrics import drawdown

YEAR = 250  # sessions in a year, for annualising


def _clean(s: pd.Series | None) -> pd.Series:
    if s is None:
        return pd.Series(dtype=float)
    s = pd.to_numeric(pd.Series(s), errors="coerce").dropna()
    s.index = pd.DatetimeIndex(s.index).normalize()
    return s[~s.index.duplicated(keep="last")].sort_index()


def ret(s: pd.Series, start: pd.Timestamp, end: pd.Timestamp) -> float | None:
    """Percent change from the last close on or before `start` to the last on or before `end`."""
    s = _clean(s)
    a, b = s.loc[:start], s.loc[:end]
    if a.empty or b.empty or a.iloc[-1] <= 0:
        return None
    return float((b.iloc[-1] / a.iloc[-1] - 1) * 100)


# ── Periods ─────────────────────────────────────────────────────────────────


def periods(book: pd.Series, market: pd.Series, mom: pd.Series, as_of: pd.Timestamp,
            fill: pd.Timestamp | None = None) -> list[tuple]:
    """(label, book %, market %, momentum %) for each period the record covers.

    `fill`: the system's first fill. A row that starts with the record measures the indices from that
    close, as the book is (owner, 23 Nov 2026: "2: from the fill"; S193 A12 one level up)."""
    b = _clean(book).loc[:as_of]
    if len(b) < 2:
        return []
    start, end = b.index[0], b.index[-1]
    days = b.index
    fy0 = pd.Timestamp(year=end.year if end.month >= 4 else end.year - 1, month=3, day=31)
    rows = [("Today", days[-2]), ("1 week", days[max(0, len(days) - 6)]),
            ("Month so far", (end.to_period("M") - 1).to_timestamp(how="end").normalize()),
            ("1 month", end - pd.DateOffset(months=1)), ("3 months", end - pd.DateOffset(months=3)),
            ("6 months", end - pd.DateOffset(months=6)),
            ("This year" + (", since start" if start.year == end.year - 1 and start.month == 12 else ""),
             pd.Timestamp(year=end.year - 1, month=12, day=31))]
    if fy0 > start:
        rows.append((f"FY {fy0.year}-{str(fy0.year + 1)[2:]}", fy0))
    for n in (1, 3, 5):
        t = end - pd.DateOffset(years=n)
        if t >= start:
            rows.append((f"{n} year{'s' if n > 1 else ''}", t))
    # A window that starts before the record is not that window: "3 months" on a book begun
    # 1 Oct showed its since-start figures beside indices measured over 3 months (S193 A3,
    # owner 23 Nov 2026: drop the row and keep the dated since-start row).
    kept = [(label, t) for label, t in rows if t >= start]
    if start < pd.Timestamp(year=end.year - 1, month=12, day=31) or len(kept) < len(rows):
        kept.append(("Since start", start))
    rows = kept
    out = []
    # An index not yet published for the book's latest session has no "today": None, not a 0.0% from a stale close.
    m_today = _clean(market).index.max() >= end if len(_clean(market)) else False
    o_today = _clean(mom).index.max() >= end if len(_clean(mom)) else False
    for label, t in rows:
        today = label == "Today"
        ti = fill if fill is not None and t <= start < fill else t
        out.append((label, ret(b, t, end), None if today and not m_today else ret(market, ti, end),
                    None if today and not o_today else ret(mom, ti, end)))
    yrs = (end - start).days / 365.25
    if yrs > 1:
        total = b.iloc[-1] / b.iloc[0]
        m = _clean(market)
        mt = ret(m, fill if fill is not None and start < fill else start, end)
        out.append(("A year, since start", float((total ** (1 / yrs) - 1) * 100),
                    None if mt is None else float(((1 + mt / 100) ** (1 / yrs) - 1) * 100), None))
    return out


# ── Drawdown ────────────────────────────────────────────────────────────────


@dataclass
class Fall:
    now: float                    # % below the peak today
    peak_now: pd.Timestamp        # the peak today's figure is measured from
    worst: float                  # the largest fall from a peak
    peak: pd.Timestamp
    low: pd.Timestamp
    recovered: pd.Timestamp | None
    worst_day: float
    worst_day_on: pd.Timestamp


def falls(value: pd.Series) -> Fall | None:
    v = _clean(value)
    if len(v) < 2:
        return None
    dd = drawdown(v)
    low = dd.idxmin()
    pk = v.loc[:low].idxmax()
    back = v[(v.index > low) & (v >= v.loc[pk])]
    r = v.pct_change().dropna()
    return Fall(now=float(dd.iloc[-1] * 100), peak_now=v.loc[:v.index[-1]].idxmax(), worst=float(dd.min() * 100),
                peak=pk, low=low, recovered=back.index[0] if len(back) else None,
                worst_day=float(r.min() * 100), worst_day_on=r.idxmin())


def worst_month_end(monthly: list[float]) -> tuple[float, int] | None:
    """The largest fall counting month-end values only: (%, index of that month)."""
    if not monthly:
        return None
    v = pd.Series(np.concatenate([[1.0], np.cumprod([1 + m / 100 for m in monthly])]))
    dd = drawdown(v)
    i = int(dd.values.argmin())
    return float(dd.iloc[i] * 100), i - 1


def drawdown_series(value: pd.Series) -> pd.Series:
    v = _clean(value)
    return drawdown(v) * 100


# ── Risk ────────────────────────────────────────────────────────────────────


@dataclass
class Risk:
    label: str
    sessions: int
    vol: float
    market_vol: float
    beta: float
    tracking: float


def _risk(b: pd.Series, m: pd.Series, label: str) -> Risk | None:
    x = pd.concat([b.pct_change(), m.pct_change()], axis=1, join="inner").dropna()
    if len(x) < 20:
        return None
    x.columns = ["b", "m"]
    # Population SDs, ddof=0, as everywhere on the site (TODO S119).
    beta = float(((x.b - x.b.mean()) * (x.m - x.m.mean())).mean() / x.m.var(ddof=0))
    return Risk(label, len(x), float(x.b.std(ddof=0) * np.sqrt(YEAR) * 100), float(x.m.std(ddof=0) * np.sqrt(YEAR) * 100),
                beta, float((x.b - x.m).std(ddof=0) * np.sqrt(YEAR) * 100))


# The fewest sessions of the book a risk figure is worked out from (the pages say so beside a "–").
RISK_MIN_SESSIONS = 21


def risk(book: pd.Series, market: pd.Series) -> list[Risk]:
    """Since start; from the record's second year also the last 12 months and each calendar year."""
    b, m = _clean(book), _clean(market).reindex(_clean(book).index).ffill()
    if len(b) < RISK_MIN_SESSIONS:
        return []
    start, end = b.index[0], b.index[-1]
    out = [_risk(b, m, f"Since {start + pd.Timedelta(days=1):%-d %b %Y}")]
    if end - pd.DateOffset(years=1) >= start:
        t = end - pd.DateOffset(years=1)
        out.append(_risk(b.loc[t:], m.loc[t:], "Last 12 months"))
        for y in sorted(set(b.index.year)):
            yb = b.loc[pd.Timestamp(year=y - 1, month=12, day=31):pd.Timestamp(year=y, month=12, day=31)]
            if yb.index[-1].year == y and len(yb) > 21:
                out.append(_risk(yb, m.reindex(yb.index).ffill(), str(y) + ("" if y < end.year else ", so far")))
    return [r for r in out if r is not None]


def capture(book: pd.Series, market: pd.Series, n: int = 60) -> tuple[float, float] | None:
    """Up-day and down-day capture over the last n sessions, in %."""
    x = pd.concat([_clean(book).pct_change(), _clean(market).pct_change()], axis=1, join="inner").dropna().tail(n)
    if len(x) < 20:
        return None
    x.columns = ["b", "m"]
    up, dn = x[x.m > 0], x[x.m < 0]
    if up.empty or dn.empty:
        return None
    return float(up.b.mean() / up.m.mean() * 100), float(dn.b.mean() / dn.m.mean() * 100)


def daily_gaps(book: pd.Series, market: pd.Series, fill: pd.Timestamp | None = None) -> pd.DataFrame:
    """Each session: the book's day, the market's day, and the gap in points.

    `fill`: the system's first fill. The book holds cash until that close, so that session is not one
    the book could beat the market in; the sessions start after it (owner, 23 Nov 2026: "from the fill")."""
    x = pd.concat([_clean(book).pct_change(), _clean(market).pct_change()], axis=1, join="inner").dropna() * 100
    if fill is not None:
        x = x[x.index > pd.Timestamp(fill)]
    x.columns = ["book", "market"]
    x["gap"] = x["book"] - x["market"]
    return x


# ── Calendar ────────────────────────────────────────────────────────────────


QUARTERS = (("Jan–Mar", (1, 2, 3)), ("Apr–Jun", (4, 5, 6)), ("Jul–Sep", (7, 8, 9)), ("Oct–Dec", (10, 11, 12)))


def chain(values) -> float | None:
    v = [x for x in values if x is not None and np.isfinite(x)]
    return float((np.prod([1 + x / 100 for x in v]) - 1) * 100) if v else None


def month_returns(level: pd.Series, months: list[pd.Period], as_of: pd.Timestamp) -> dict[pd.Period, float | None]:
    """An index's return in each calendar month (the month in progress to `as_of`)."""
    out = {}
    for p in months:
        a = (p - 1).to_timestamp(how="end").normalize()
        b = min(p.to_timestamp(how="end").normalize(), as_of)
        out[p] = ret(level, a, b)
    return out


def calendar(series: dict[str, dict[pd.Period, float | None]]) -> dict[int, dict]:
    """By year: each series' months, quarters and year. `series` maps a name to {month: %}."""
    years = sorted({p.year for s in series.values() for p in s})
    out = {}
    for y in years:
        row = {}
        for name, s in series.items():
            m = {p.month: v for p, v in s.items() if p.year == y}
            q = [chain([m.get(k) for k in ks]) if any(k in m for k in ks) else None for _, ks in QUARTERS]
            row[name] = {"months": [m.get(k) for k in range(1, 13)], "quarters": q, "year": chain(m.values())}
        out[y] = row
    return out


def financial_years(series: dict[str, dict[pd.Period, float | None]]) -> list[tuple[str, dict]]:
    """April to March: (label, {name: %})."""
    fys = sorted({p.year if p.month >= 4 else p.year - 1 for s in series.values() for p in s})
    out = []
    for fy in fys:
        lo, hi = pd.Period(f"{fy}-04", "M"), pd.Period(f"{fy + 1}-03", "M")
        out.append((f"FY {fy}-{str(fy + 1)[2:]}", {n: chain([v for p, v in s.items() if lo <= p <= hi]) for n, s in series.items()},
                    [p for p in next(iter(series.values())) if lo <= p <= hi]))
    return out


# ── The size-matched yardstick ──────────────────────────────────────────────


def size_mix(exposure: pd.DataFrame, indices: dict[str, pd.Series], as_of: pd.Timestamp) -> float | None:
    """The four NSE size indices held in the book's own size split, reset at each rebalance (%)."""
    if exposure is None or exposure.empty:
        return None
    size = exposure[exposure["kind"] == "size"].pivot_table(index="date", columns="name", values="weight").sort_index()
    if size.empty:
        return None
    dates = list(size.index) + [as_of + pd.Timedelta(days=1)]
    value = 1.0
    for i, d in enumerate(dates[:-1]):
        a, b = d - pd.Timedelta(days=1), min(dates[i + 1] - pd.Timedelta(days=1), as_of)
        w = size.loc[d]
        part = 0.0
        tot = 0.0
        for name, s in indices.items():
            r = ret(s, a, b)
            if r is None or name not in w:
                continue
            part += w[name] / 100 * r / 100
            tot += w[name] / 100
        if tot <= 0:
            return None
        value *= 1 + part / tot
    return float((value - 1) * 100)


# ── Trades, for checking ────────────────────────────────────────────────────

TRADE_FIELDS = ["Symbol", "Industry", "Entry signal date", "Entry date", "Entry price", "Entry rank",
                "Entry weight %", "Exit signal date", "Exit date", "Exit price", "Exit rank", "Return %",
                "Days held", "Exit rule", "Status"]


def _date(v):
    t = pd.to_datetime(str(v)[:11] if isinstance(v, str) else v, errors="coerce", format="mixed")
    return None if pd.isna(t) else pd.Timestamp(t).normalize()


def trades_table(trades: pd.DataFrame, tradebook: pd.DataFrame, sessions: pd.DatetimeIndex,
                 industry: dict[str, str] | None = None) -> pd.DataFrame:
    """Every trade with the 15 fields a reader needs to check it against NSE's files.

    Open trades come from the live month without an entry signal date or rank;
    the rank is in that rebalance's line ("New Momentum Leader (Rank #11)") and
    the signal is the session before the fill.
    """
    if trades is None or trades.empty:
        return pd.DataFrame(columns=TRADE_FIELDS)
    sessions = pd.DatetimeIndex(sessions).normalize()
    rank_at = {}
    if tradebook is not None and len(tradebook):
        for _, r in tradebook[tradebook["Action"].astype(str).str.contains("BUY")].iterrows():
            start = _date(str(r["Period"]).split("→")[0].strip())
            m = pd.Series([str(r.get("Reason / Signal", ""))]).str.extract(r"Rank #(\d+)")[0].iloc[0]
            if start is not None:
                rank_at[(str(r["Symbol"]), start)] = (int(m) if isinstance(m, str) else None,
                                                     pd.to_numeric(r.get("Weight %"), errors="coerce"))

    def before(d):
        if d is None:
            return None
        prior = sessions[sessions < d]
        return prior[-1] if len(prior) else None
    rows = []
    for _, t in trades.iterrows():
        sym, ein = str(t["Symbol"]), _date(t.get("Entry Date"))
        es = _date(t.get("Entry Signal Date")) or before(ein)
        er = t.get("Entry Rank")
        line = rank_at.get((sym, ein), (None, np.nan))
        er = int(er) if pd.notna(er) else line[0]
        ew = pd.to_numeric(t.get("Entry Weight %"), errors="coerce")
        ew = float(ew) if pd.notna(ew) else float(line[1])
        open_ = str(t.get("Status")) == "Open"
        eout = None if open_ else _date(t.get("Exit Date"))
        xs = None if open_ else (_date(t.get("Exit Signal Date")) or before(eout))
        xr = t.get("Exit Rank")
        sec = t.get("Sector")
        rows.append([sym, sec if isinstance(sec, str) and sec else (industry or {}).get(sym, ""),
                     es, ein, float(t["Entry Price"]), er, ew,
                     xs, eout, float(t["Exit Price"]) if pd.notna(t.get("Exit Price")) else None,
                     int(xr) if pd.notna(xr) else None, float(t["Return %"]) * 100, int(t["Holding (Days)"]),
                     "Still held" if open_ else str(t.get("Reason for Exit", "")), "Open" if open_ else "Closed"])
    out = pd.DataFrame(rows, columns=TRADE_FIELDS)
    return out.sort_values(["Status", "Exit date", "Entry date"], ascending=[False, False, False], na_position="first").reset_index(drop=True)
