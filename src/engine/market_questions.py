"""Three questions the Dashboard answers about the market, from data the app
already holds (owner, 7 Nov: tipsheet's question pages as the model, our own
sources as the data).

* Are most stocks taking part?  (breadth of the ranked universe)
* Is the market in an uptrend?  (Nifty Total Market, joined to the Nifty 500
  before its launch, and the size indices against their averages and highs)
* What is leading?               (size indices and NSE industries against the
  Nifty 500)

Each answer is a set of measures that vote with stated cut-offs, read now, a
month ago and a year ago, so the reader sees the evidence and what changed.
No forward returns and no claim about what follows: the store does not reach
back far enough to test one, and the site makes no outcome claims.

Pure functions on frames; no Streamlit, so every rule is tested directly.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from src.engine import peer_index as pi

UP, MID, DOWN = "up", "mid", "down"


@dataclass(frozen=True)
class Measure:
    name: str            # "Stocks above their 200D EMA"
    unit: str            # "pct" (a share in %), "pts" (signed points), "count"
    now: float | None
    month_ago: float | None
    year_ago: float | None
    vote: str            # UP / MID / DOWN, from `now`
    rule: str            # "60% or more is up, 40% or less is down"
    up_at: float = 0.0
    down_at: float = 0.0
    primary: bool = False
    # Where today sits in the measure's own history (the store's span):
    # (low, 25th pct, 75th pct, high, percentile of today, first date).
    history: tuple | None = None
    first: pd.Timestamp | None = None   # the measure's history's first date, also when it is too short to rank


@dataclass(frozen=True)
class Answer:
    question: str
    verdict: str
    sentence: str
    score: float                  # -1 .. +1, weighted votes
    score_month_ago: float | None
    score_year_ago: float | None
    measures: list[Measure] = field(default_factory=list)
    words: tuple[str, ...] = ()   # five words, lowest to highest


def _on_or_before(index: pd.DatetimeIndex, when: pd.Timestamp) -> pd.Timestamp | None:
    """The last index entry at or before `when`, or None.

    None rather than an exception when the index cannot be compared with a
    date at all: a truncated benchmarks.csv gives a string index, and this
    function is on the path of every market question (launch slot 5)."""
    try:
        pos = index.searchsorted(when, side="right") - 1
    except TypeError:
        return None
    return None if pos < 0 else index[pos]


def anchor_dates(index: pd.DatetimeIndex) -> dict[str, pd.Timestamp | None]:
    """Today, the session a calendar month back and a calendar year back."""
    idx = pd.DatetimeIndex(index).sort_values()
    if idx.empty:
        return {"now": None, "month_ago": None, "year_ago": None}
    now = idx[-1]
    return {"now": now,
            "month_ago": _on_or_before(idx, now - pd.DateOffset(months=1)),
            "year_ago": _on_or_before(idx, now - pd.DateOffset(years=1))}


# The market every live figure is read against (S165; owner, 21 Nov 2026: "use Nifty total market 750 as
# benchmark everywhere unless we need historical data"). NSE launched it on 14 Oct 2021 and publishes no
# back-calculated years (S165 G1), so a reading that needs a longer history joins the Nifty 500 before
# that day (owner-approved, 21 Nov 2026).
MARKET = "Nifty Total Market"
EARLIER = "Nifty 500"


def join_market(earlier: pd.Series | None, market: pd.Series | None) -> tuple[pd.Series, str]:
    """Nifty Total Market's closes from its first session, the Nifty 500's before it scaled to meet them on
    that session: one continuous line whose every level from the join on is NSE's own Total Market close.
    Returns (closes, the name to print). With no Total Market closes it returns the Nifty 500 under its own
    name, so a page never labels one index with the other's name."""
    e = pd.Series(dtype=float) if earlier is None else pd.to_numeric(earlier, errors="coerce").dropna().sort_index()
    m = pd.Series(dtype=float) if market is None else pd.to_numeric(market, errors="coerce").dropna().sort_index()
    m = m[~m.index.duplicated(keep="last")]
    if m.empty:
        return e, EARLIER
    first = m.index[0]
    at = _on_or_before(e.index, first) if len(e) else None
    if at is None:
        return m, MARKET
    before = e[e.index < first] * (float(m.iloc[0]) / float(e.loc[at]))
    return pd.concat([before, m]).sort_index(), MARKET


def _vote(v: float | None, up_at: float, down_at: float) -> str:
    if v is None or not np.isfinite(v):
        return MID
    return UP if v >= up_at else DOWN if v <= down_at else MID


def _score(measures: list[Measure], which: str) -> float | None:
    """Weighted mean of votes (+1 up, 0 between, -1 down); primary counts twice.
    `which` reads the vote for now, a month ago or a year ago from the values."""
    total = weight = full = 0.0
    for m in measures:
        full += 2.0 if m.primary else 1.0
        v = getattr(m, which)
        if v is None or not np.isfinite(v):
            continue
        vote = _vote(v, m.up_at, m.down_at)
        w = 2.0 if m.primary else 1.0
        total += w * (1 if vote == UP else -1 if vote == DOWN else 0)
        weight += w
    # A verdict from a few measures would not be the same question: a past
    # reading needs most of the weight (the store may not reach back a year).
    return None if weight == 0 or weight < 0.6 * full else total / weight


def history_stats(series: pd.Series | None, now: float | None) -> tuple | None:
    """Low, middle half and high of a measure over its history, and today's
    percentile in it. None under a year of readings: too short to say."""
    if series is None or now is None:
        return None
    s = pd.to_numeric(series, errors="coerce").dropna()
    if len(s) < 200 and not (len(s) >= 12 and isinstance(s.index, pd.DatetimeIndex)
                             and (s.index[-1] - s.index[0]).days >= 330):
        return None
    pct = float((s <= now).mean() * 100)
    return (float(s.min()), float(s.quantile(0.25)), float(s.quantile(0.75)), float(s.max()),
            pct, pd.Timestamp(s.index[0]) if isinstance(s.index, pd.DatetimeIndex) else None)


def _first_date(series) -> pd.Timestamp | None:
    if series is None or not isinstance(getattr(series, "index", None), pd.DatetimeIndex):
        return None
    s = pd.to_numeric(series, errors="coerce").dropna()
    return pd.Timestamp(s.index[0]) if len(s) else None


def share_history(series: pd.Series | None, warm: int, past) -> pd.Series | None:
    """The history a share-above-EMA measure is ranked in, the same in every table that shows it: the readings
    on the members of each date when `past` joins them, else today's members' readings after the EMA's `warm`
    sessions. The breadth and trend tables built it two ways (one with blanks kept, one without, the trend
    skipping the warm-up even on the members of the day), so one reading read the 26th and the 28th percentile
    on the 1000's Market page (S193 B, found 23 Nov 2026)."""
    if series is None:
        return None
    s = pd.to_numeric(series, errors="coerce").dropna()
    return s if past is not None else s.iloc[warm:]


def _measure(name, unit, values, up_at, down_at, rule, primary=False, history=None) -> Measure:
    now, month, year = values
    return Measure(name, unit, now, month, year, _vote(now, up_at, down_at), rule,
                   up_at, down_at, primary, history_stats(history, now), _first_date(history))


def _f(x) -> float | None:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if np.isfinite(v) else None


# ── Are most stocks taking part? ────────────────────────────────────────────

def _enough(counts: pd.Series) -> pd.Series:
    """True where a reading rests on enough stocks: at least 40% of the most
    ever counted, and at least 100. The early years of the history hold a few
    dozen names, whose shares swing from 0% to 100% and are not the market."""
    peak = float(counts.max() or 0)
    floor = max(min(100.0, 0.5 * peak), 0.4 * peak)
    return counts >= floor


def _share_above_ema(prices: pd.DataFrame, span: int, members: pd.DataFrame | None = None) -> pd.Series:
    """Share above the EMA. `members` (same shape, bool) counts a stock only on
    the days it was in the index; its EMA still reads its whole history."""
    ema = prices.ewm(span=span, min_periods=max(int(span * 0.8), 5)).mean()
    observed = prices.notna() & ema.notna()
    if members is not None:
        observed &= members.reindex_like(prices).fillna(False).astype(bool)
    share = (prices > ema).where(observed).astype(float).mean(axis=1) * 100
    return share.where(_enough(observed.sum(axis=1)))


def _net_new_highs(prices: pd.DataFrame, window: str = "7D", members: pd.DataFrame | None = None) -> pd.Series:
    """Net new 52-week highs over the last `window` of calendar days (a week): stocks that
    made a new high less those that made a new low, each counted once, as a
    share of the stocks that can make one. The 52 weeks are a calendar window, not
    252 rows: the deep price history holds fewer rows a year in its early
    years, and a row count read those years as too short (no reading at all).
    The week is a calendar window too (S193 B): five ROWS of a weekly stretch
    are five weeks, and of a twice-a-week one two to three."""
    prices = prices.sort_index()
    hi = prices.rolling("365D", min_periods=20).max()
    lo = prices.rolling("365D", min_periods=20).min()
    # a stock needs most of a year of prices before it can set a 52W extreme
    first = prices.apply(lambda c: c.first_valid_index())
    old_enough = pd.DataFrame({c: prices.index >= (first[c] + pd.Timedelta(days=330)) if pd.notna(first[c])
                               else np.zeros(len(prices), bool) for c in prices.columns}, index=prices.index)
    tol = prices * 0.001
    can = prices.notna() & hi.notna() & lo.notna() & old_enough
    if members is not None:
        can &= members.reindex_like(prices).fillna(False).astype(bool)
    # Each stock once a week: made a new high on any session of the last seven
    # days, less made a new low, over the stocks that could. Summing daily shares
    # counted a stock that set highs on three days three times (+140%).
    made_hi = ((prices >= hi - tol) & can).astype(float).rolling(window, min_periods=1).max()
    made_lo = ((prices <= lo + tol) & can).astype(float).rolling(window, min_periods=1).max()
    counts = can.sum(axis=1)
    n = counts.replace(0, np.nan)
    return ((made_hi.sum(axis=1) - made_lo.sum(axis=1)) / n * 100).where(_enough(counts))


def _beat_series(prices: pd.DataFrame, bench: pd.Series,
                 members: pd.DataFrame | None = None) -> tuple[pd.Series, pd.Series]:
    """The two year-long measures at each month end: share of stocks ahead of
    the Nifty 500 over the year, and the median stock less the index (pts)."""
    ends = prices.groupby(prices.index.to_period("M")).apply(lambda f: f.index[-1]).tolist()
    share, gap = {}, {}
    for t in ends:
        a, b = _beat_index_12m(prices, bench, t, members)
        if a is not None:
            share[t], gap[t] = a, b
    return pd.Series(share, dtype=float), pd.Series(gap, dtype=float)


def last_close_in_week(prices: pd.DataFrame, when: pd.Timestamp) -> pd.Series:
    """Each stock's last close in the week to `when` (NaN if none): the history holds dates on which
    few or no stocks have a price (4 Nov 2024 has none). Market and the Dashboard read window returns
    this way (owner, 25 Nov 2026, S193 A11: "1"), so a stock that missed one session is kept."""
    w = prices.loc[pd.Timestamp(when) - pd.Timedelta(days=7):when]
    return w.ffill().iloc[-1] if len(w) else pd.Series(np.nan, index=prices.columns)


def _beat_index_12m(prices: pd.DataFrame, bench: pd.Series, when: pd.Timestamp | None,
                    members: pd.DataFrame | None = None) -> tuple[float | None, float | None]:
    """Share of stocks ahead of the Nifty 500 over the year to `when`, and the
    median stock's return less the index's (points). With `members`, over the
    stocks in the index on `when`, leavers included."""
    if when is None:
        return None, None
    if members is not None:
        row = members.loc[:when]
        if row.empty:
            return None, None
        on = row.iloc[-1]
        prices = prices[[c for c in on.index[on.astype(bool)] if c in prices.columns]]
    start = _on_or_before(prices.index, when - pd.DateOffset(years=1))
    if start is None:
        return None, None
    b = bench.dropna()
    b0, b1 = _on_or_before(b.index, start), _on_or_before(b.index, when)
    if b0 is None or b1 is None:
        return None, None
    rb = float(b.loc[b1] / b.loc[b0] - 1)
    p1, p0 = last_close_in_week(prices, when), last_close_in_week(prices, start)
    r = (p1 / p0 - 1).dropna()
    if len(r) < max(min(100, 0.5 * prices.shape[1]), 0.2 * prices.shape[1]):
        return None, None
    return float((r > rb).mean() * 100), float((r.median() - rb) * 100)


def breadth_answer(prices: pd.DataFrame, bench: pd.Series, past: pd.DataFrame | None = None,
                   market: str = "the Nifty 500") -> Answer | None:
    """`past`: readings on the members of each date (src/engine/pit_breadth.py).
    With it, a month and a year back and every history figure come from the
    members of the day; today's reading from `prices` either way."""
    from src.engine.pit_breadth import splice
    if prices is None or prices.empty or bench is None or bench.dropna().empty:
        return None
    prices = prices.sort_index()
    d = anchor_dates(prices.index)
    a200 = splice(_share_above_ema(prices, 200), past, "above_200")
    a50 = splice(_share_above_ema(prices, 50), past, "above_50")
    nnh = splice(_net_new_highs(prices), past, "net_new_highs")

    def at(s: pd.Series, key):
        t = d[key]
        return None if t is None else _f(s.get(t))

    beat = {k: _beat_index_12m(prices, bench, d[k]) for k in d}
    beat_share, beat_gap = _beat_series(prices, bench)
    if past is not None and {"beat_share", "beat_gap"} <= set(past.columns):
        live_share = pd.Series({d["now"]: beat["now"][0]}, dtype=float).dropna()
        live_gap = pd.Series({d["now"]: beat["now"][1]}, dtype=float).dropna()
        daily_share, daily_gap = splice(live_share, past, "beat_share"), splice(live_gap, past, "beat_gap")
        for k in ("month_ago", "year_ago"):
            if d[k] is not None:
                beat[k] = (_f(daily_share.get(d[k])), _f(daily_gap.get(d[k])))
        beat_share = daily_share.groupby(daily_share.index.to_period("M")).last()
        beat_share.index = [daily_share.loc[daily_share.index.to_period("M") == p].index[-1] for p in beat_share.index]
        beat_gap = daily_gap.reindex(beat_share.index)
    ms = [
        _measure("Stocks above their 200D EMA", "pct", [at(a200, k) for k in d], 60, 40,
                 "60% or more is broad, 40% or less is narrow", primary=True, history=share_history(a200, 200, past)),
        _measure(f"Stocks ahead of {market} over 12 months", "pct", [beat[k][0] for k in d], 55, 45,
                 "55% or more is broad, 45% or less is narrow", primary=True, history=beat_share),
        _measure("Stocks above their 50D EMA", "pct", [at(a50, k) for k in d], 60, 40,
                 "60% or more is broad, 40% or less is narrow", history=share_history(a50, 50, past)),
        _measure("Net new 52W highs this week, share of stocks", "pts", [at(nnh, k) for k in d], 5, -5,
                 "+5 or more is broad, −5 or less is narrow", history=nnh),
        _measure(f"Median stock less {market}, 12M", "pts", [beat[k][1] for k in d], 3, -3,
                 "+3 points or more is broad, −3 or less is narrow", history=beat_gap),
    ]
    return _answer("Are most stocks taking part?", ms,
                   ("Very narrow", "Narrow", "About usual", "Broad", "Very broad"),
                   lambda word, m: _breadth_sentence(word, ms, market))


def _share(v: float) -> str:
    """A whole share, half up (glossary 12): 42.5 -> "43%"."""
    from decimal import ROUND_HALF_UP, Decimal
    return f"{Decimal(repr(float(v))).quantize(Decimal(1), rounding=ROUND_HALF_UP)}%"


def _breadth_sentence(word: str, ms: list[Measure], market: str = "the Nifty 500") -> str:
    """S203 mk.q.1: "43% of the ranked stocks are above their 200D EMA, and 45% beat the Nifty 500 over 12
    months." One missing: that clause only; both: no sentence."""
    a200, beat = ms[0].now, ms[1].now
    parts = []
    if a200 is not None:
        parts.append(f"{_share(a200)} of the ranked stocks are above their 200D EMA")
    if beat is not None:
        parts.append(f"{_share(beat)} beat {market} over 12 months")
    text = ", and ".join(parts) + "."
    return text[:1].upper() + text[1:] if parts else ""


# ── Is the market in an uptrend? ────────────────────────────────────────────

def ten_month_gap(close: pd.Series, when: pd.Timestamp | None) -> float | None:
    """The 10-month rule as it is usually read: the last COMPLETED month's
    closing level against the average of the last ten month-end closes, in
    percent. The month in progress does not count, so the reading moves once a
    month (on 6 Nov it is October's close against Jan-Oct)."""
    if when is None:
        return None
    s = close.dropna().loc[:when]
    if s.empty:
        return None
    month_ends = s.groupby(s.index.to_period("M")).last()
    if month_ends.index[-1] == pd.Timestamp(when).to_period("M") and s.index[-1] < (
            pd.Timestamp(when).to_period("M").to_timestamp(how="end").normalize()):
        month_ends = month_ends.iloc[:-1]       # the month is not over yet
    if len(month_ends) < 10:
        return None
    avg = float(month_ends.iloc[-10:].mean())
    return (float(month_ends.iloc[-1]) / avg - 1) * 100


def ten_month_today(close: pd.Series, when: pd.Timestamp | None) -> float | None:
    """The 10-month rule read on a monthly chart: the close on `when` against the
    average of the last ten monthly closes, the month in progress counted at
    `when`'s close. On a month's last session it equals `ten_month_gap`.

    Staleness audit, 21 Nov 2026: `ten_month_gap` alone made Breadth's trend
    verdict read October's close for most of November (on 20 Nov the Nifty 500
    read 3.1% below its average at the 30 Oct close and 6% above it on the
    day). A verdict about today reads today; the month-end reading is shown
    beside it, named as such."""
    if when is None:
        return None
    s = close.dropna().loc[:when]
    if s.empty:
        return None
    monthly = s.groupby(s.index.to_period("M")).last()
    if len(monthly) < 10:
        return None
    avg = float(monthly.iloc[-10:].mean())
    return (float(s.iloc[-1]) / avg - 1) * 100


def last_month_end(close: pd.Series, when: pd.Timestamp | None) -> pd.Timestamp | None:
    """The session `ten_month_gap` reads on `when`: the last completed month's close."""
    if when is None:
        return None
    s = close.dropna().loc[:when]
    if s.empty:
        return None
    ends = s.groupby(s.index.to_period("M")).apply(lambda x: x.index[-1])
    if ends.index[-1] == pd.Timestamp(when).to_period("M") and s.index[-1] < (
            pd.Timestamp(when).to_period("M").to_timestamp(how="end").normalize()):
        ends = ends.iloc[:-1]
    return None if ends.empty else pd.Timestamp(ends.iloc[-1])


def _ten_month_rule_text(close: pd.Series, when) -> str:
    me, at = ten_month_gap(close, when), last_month_end(close, when)
    tail = "" if me is None or at is None else f". At the {at:%-d %b} month-end it read {_signed1(me)}."
    return "today's close against the last ten monthly closes; above is up, below is down" + tail


def _signed1(v: float) -> str:
    """A figure with its sign to one decimal, half up: "+2.3", "−1.9", "0.0"."""
    from decimal import ROUND_HALF_UP, Decimal
    r = Decimal(repr(float(v))).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    return f"{'+' if r > 0 else '−' if r < 0 else ''}{abs(r):.1f}"


def ema_gap(close: pd.Series, when: pd.Timestamp | None, span: int = 200) -> float | None:
    if when is None:
        return None
    s = close.dropna()
    ema = s.ewm(span=span, min_periods=int(span * 0.8)).mean()
    t = _on_or_before(s.index, when)
    if t is None or not np.isfinite(ema.get(t, np.nan)):
        return None
    return (float(s.loc[t]) / float(ema.loc[t]) - 1) * 100


def from_high(close: pd.Series, when: pd.Timestamp | None) -> float | None:
    if when is None:
        return None
    s = close.dropna().loc[:when]
    from src.engine.calendar_momentum import year_window_start
    s = s.iloc[year_window_start(s.index, len(s) - 1):] if len(s) else s   # on or before a year back
    if s.empty:
        return None
    return (float(s.iloc[-1]) / float(s.max()) - 1) * 100


def _ten_month_series(close: pd.Series) -> pd.Series:
    """The 10-month rule's reading at each month end, in percent."""
    m = close.dropna().groupby(close.dropna().index.to_period("M")).last()
    m.index = m.index.to_timestamp(how="end").normalize()
    return ((m / m.rolling(10).mean() - 1) * 100).dropna()


def _ema_gap_series(close: pd.Series, span: int = 200) -> pd.Series:
    s = close.dropna()
    return ((s / s.ewm(span=span, min_periods=int(span * 0.8)).mean() - 1) * 100).dropna()


def _from_high_series(close: pd.Series, min_sessions: int = 200) -> pd.Series:
    """The distance from the 52W high at each session, over the calendar year (from the last session on or before the date a year back), the window
    `from_high` reads (owner, 24 Nov 2026: "Use calendar date everywhere"; was 252 sessions, which parted from
    Market's reading on 9 of 750 sessions, S154). A session with fewer than `min_sessions` in its year is left out."""
    s = close.dropna().sort_index()
    if s.empty:
        return s
    from src.engine.calendar_momentum import year_window_starts
    idx, v = s.index, s.to_numpy(dtype=float)
    starts = year_window_starts(idx)
    out = np.full(len(v), np.nan)
    for i, a in enumerate(starts):
        if i + 1 - a >= min_sessions:
            out[i] = (v[i] / v[a:i + 1].max() - 1) * 100
    return pd.Series(out, index=idx).dropna()


def trend_answer(bench: pd.Series, size_closes: dict[str, pd.Series] | None,
                 share_above_200: pd.Series | None, index_name: str = EARLIER, past=None) -> Answer | None:
    """`index_name` names the index `bench` holds, in each measure and in the question."""
    if bench is None or bench.dropna().empty:
        return None
    b = bench.dropna().sort_index()
    d = anchor_dates(b.index)
    keys = list(d)
    ms = [
        _measure(f"{index_name} against its 10-month average", "pts", [ten_month_today(b, d[k]) for k in keys],
                 0.0001, -0.0001, _ten_month_rule_text(b, d["now"]), primary=True, history=_ten_month_series(b)),
        _measure(f"{index_name} against its 200D EMA", "pts", [ema_gap(b, d[k]) for k in keys],
                 0.0001, -0.0001, "above is up, below is down", primary=True, history=_ema_gap_series(b)),
        _measure(f"{index_name} from its 52W high", "pts", [from_high(b, d[k]) for k in keys],
                 -5, -15, "within 5% is up, 15% or more below is down", history=_from_high_series(b)),
    ]
    for name, s in (size_closes or {}).items():
        s = s.dropna().sort_index()
        if len(s) < 200:
            continue
        ms.append(_measure(f"{name} against its 10-month average", "pts",
                           [ten_month_today(s, d[k]) for k in keys], 0.0001, -0.0001,
                           _ten_month_rule_text(s, d["now"]), history=_ten_month_series(s)))
    if share_above_200 is not None and not share_above_200.dropna().empty:
        s = share_above_200.dropna()
        ms.append(_measure("Stocks above their 200D EMA", "pct",
                           [_f(s.get(_on_or_before(s.index, d[k]))) if d[k] is not None and
                            _on_or_before(s.index, d[k]) is not None else None for k in keys],
                           60, 40, "60% or more is up, 40% or less is down",
                           history=share_history(share_above_200, 200, past)))
    return _answer(f"Is {'the ' if index_name == EARLIER else ''}{index_name} in an uptrend?", ms,
                   ("Strong downtrend", "Downtrend", "No clear trend", "Uptrend", "Strong uptrend"),
                   lambda word, m: _trend_sentence(word, ms))


def _trend_sentence(word: str, ms: list[Measure]) -> str:
    """S203 mk.q.2: "3 of 5 measures say up, 1 says down."; 0 reads "none say down" / "None of the 5 measures
    says up"."""
    ups = sum(m.vote == UP for m in ms)
    downs = sum(m.vote == DOWN for m in ms)
    up = (f"None of the {len(ms)} measures says up" if ups == 0 else
          f"{ups} of {len(ms)} measures {'says' if ups == 1 else 'say'} up")
    down = "none say down" if downs == 0 else f"{downs} {'says' if downs == 1 else 'say'} down"
    return f"{up}, {down}."


# ── What is leading? ────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Leaders:
    sentence: str
    size: list[tuple[str, float | None, float | None]]          # name, 6M rel, 1M rel (pts)
    sectors: pd.DataFrame                                         # Industry, Stocks, rel_6m, rel_1m, group
    as_of: pd.Timestamp
    # Size leadership (S147): the equal-weighted ranked market less the
    # Nifty 500, points, over 6M and 1M. Below zero, large companies led.
    market_vs_index: tuple[float | None, float | None] = (None, None)


def _rel(close: pd.Series, bench: pd.Series, when: pd.Timestamp, months: int) -> float | None:
    """The index's return less the Nifty 500's over the SAME dates: both end on
    the index's own last close on or before `when` and start on its close a
    calendar span earlier. On 7 Nov the R2 index file was still weekly and
    ended on an earlier day than the Nifty 500; comparing each series to its
    own last close mixed two windows (Microcap 250 read +7.0 pts, +3.7 on
    the same dates)."""
    s, b = close.dropna(), bench.dropna()
    t1 = _on_or_before(s.index, when)
    if t1 is None:
        return None
    t0 = _on_or_before(s.index, t1 - pd.DateOffset(months=months))
    if t0 is None:
        return None
    b1, b0 = _on_or_before(b.index, t1), _on_or_before(b.index, t0)
    if b1 is None or b0 is None or (t1 - b1).days > 4 or (t0 - b0).days > 4:
        return None
    return (float(s.loc[t1] / s.loc[t0]) - float(b.loc[b1] / b.loc[b0])) * 100


def leaders_answer(prices: pd.DataFrame, industry: pd.Series, bench: pd.Series,
                   size_closes: dict[str, pd.Series] | None, min_stocks: int = 5,
                   market_name: str = "the Nifty 500") -> Leaders | None:
    """Industries by their equal-weighted return less the equal-weighted
    market's (every ranked stock) over six months and one month: ahead on
    both, gaining (ahead over the month only), fading (ahead over six months
    only), behind on both. The cap-weighted size indices are read against the
    Nifty 500, cap against cap; the market against the Nifty 500 is size
    leadership. One construction per comparison (S147, src/engine/peer_index)."""
    if prices is None or prices.empty or bench is None or bench.dropna().empty:
        return None
    prices = prices.sort_index()
    when = prices.index[-1]
    b = bench.dropna()
    levels, market, counts = pi.industry_levels(prices, industry, min_stocks=min_stocks)
    rows = []
    for name, level in levels.items():
        rel = {m: pi.relative_points(level, market, when - pd.DateOffset(months=m), when) for m in (6, 1)}
        if rel[6] is None or rel[1] is None:
            continue
        group = ("ahead on both" if rel[6] > 0 and rel[1] > 0 else
                 "gaining" if rel[1] > 0 else "fading" if rel[6] > 0 else "behind on both")
        rows.append({"Industry": name, "Stocks": counts[name], "rel_6m": rel[6], "rel_1m": rel[1], "group": group})
    sectors = pd.DataFrame(rows, columns=["Industry", "Stocks", "rel_6m", "rel_1m", "group"])
    sectors = sectors.sort_values("rel_6m", ascending=False).reset_index(drop=True)
    gap = tuple(pi.size_gap(market, b, when - pd.DateOffset(months=m), when) for m in (6, 1))

    size = []
    for name, s in (size_closes or {}).items():
        size.append((name, _rel(s, b, when, 6), _rel(s, b, when, 1)))

    both = sectors[sectors["group"] == "ahead on both"]
    lead_names = both["Industry"].head(3).tolist()
    best_size = max((x for x in size if x[1] is not None), key=lambda x: x[1], default=None)
    bits = []
    if best_size is not None:
        bits.append(f"{best_size[0]} lead{'s' if not best_size[0].endswith('s') else ''} the sizes over six months "
                    f"({best_size[1]:+.1f} pts against {market_name})".replace("-", "−"))
    if len(sectors):
        bits.append(f"{len(both)} of {len(sectors)} sectors are ahead over both six months and one month"
                    + (f", led by {', '.join(lead_names)}" if lead_names else ""))
    sentence = ("; ".join(bits) + ".") if bits else "Not enough history to say."
    return Leaders(sentence, size, sectors, when, gap)


# ── Shared ──────────────────────────────────────────────────────────────────

# The weighted vote's two cut-offs: at an end from END_AT either way, leaning from LEAN_AT. One place, read by
# `word_for` and by the Market page's note (S203 mk.q.8).
END_AT, LEAN_AT = 0.6, 0.25


def word_for(score: float | None, words: tuple[str, ...]) -> str:
    """Five bands of the weighted vote: at an end (|score| >= END_AT), leaning
    (>= LEAN_AT), else the middle word."""
    if score is None:
        return "Not enough data"
    lo2, lo1, mid, hi1, hi2 = words
    if score >= END_AT:
        return hi2
    if score >= LEAN_AT:
        return hi1
    if score <= -END_AT:
        return lo2
    if score <= -LEAN_AT:
        return lo1
    return mid


def _answer(question, ms, words, sentence) -> Answer:
    s_now, s_m, s_y = _score(ms, "now"), _score(ms, "month_ago"), _score(ms, "year_ago")
    word = word_for(s_now, words)
    return Answer(question, word, sentence(word, ms), s_now if s_now is not None else 0.0,
                  s_m, s_y, ms, words)


# ── What changed, and what would change the answer ─────────────────────────

def changes(a: Answer) -> list[tuple[Measure, float, float]]:
    """Each measure's move over the month (month ago, now), largest first,
    measured against the width of its own cut-off band so a share and a count
    compare fairly."""
    out = []
    for m in a.measures:
        if m.now is None or m.month_ago is None:
            continue
        width = abs(m.up_at - m.down_at) or 1.0
        out.append((m, m.month_ago, m.now, abs(m.now - m.month_ago) / width))
    out.sort(key=lambda t: -t[3])
    return [(m, then, now) for m, then, now, _ in out]


def _replace_vote(ms: list[Measure], i: int, value: float) -> list[Measure]:
    m = ms[i]
    moved = Measure(m.name, m.unit, value, m.month_ago, m.year_ago,
                    _vote(value, m.up_at, m.down_at), m.rule, m.up_at, m.down_at, m.primary)
    return ms[:i] + [moved] + ms[i + 1:]


def what_would_change(a: Answer) -> dict[str, list[tuple[Measure, float]]]:
    """The single measures whose next step would change the verdict word, each
    with the cut-off it would have to cross: {"higher": [...], "lower": [...]},
    nearest first. A step is one vote: down -> between (past the lower
    cut-off), between -> up (at the upper one), and the same way down."""
    eps = 1e-9
    out: dict[str, list[tuple[Measure, float]]] = {"higher": [], "lower": []}
    for i, m in enumerate(a.measures or []):
        if m.now is None:
            continue
        steps = []
        if m.vote == DOWN:
            steps.append(("higher", m.down_at, m.down_at + eps))
        elif m.vote == MID:
            steps += [("higher", m.up_at, m.up_at), ("lower", m.down_at, m.down_at)]
        if m.vote == UP:
            steps.append(("lower", m.up_at, m.up_at - eps))
        for side, cutoff, value in steps:
            moved = _replace_vote(a.measures, i, value)
            if word_for(_score(moved, "now"), a.words) != a.verdict:
                out[side].append((m, cutoff))
    for side in out:
        out[side].sort(key=lambda t: abs(t[1] - t[0].now))
    return out


# ── Industry runs: month by month against the Nifty 500 ────────────────────

def industry_months(prices: pd.DataFrame, industry: pd.Series, bench: pd.Series,
                    months: int = 12, min_stocks: int = 5) -> pd.DataFrame:
    """Each industry's equal-weighted return less the equal-weighted market's,
    per calendar month, for the last `months` completed months and the month
    to date (points; S147, src/engine/peer_index). Columns are month labels
    ("Nov 2025" … "Nov so far"), plus "run" (completed months in a row
    ahead, +n, or behind, -n, ending with the last completed month) and
    "total" (the completed months' points summed), sorted by total. `bench`
    is kept for the caller's signature; the comparison no longer reads it."""
    if prices is None or prices.empty or bench is None or bench.dropna().empty:
        return pd.DataFrame()
    px = prices.sort_index()
    last = px.index[-1]
    month_ends = px.groupby(px.index.to_period("M")).apply(lambda f: f.index[-1])
    cur = last.to_period("M")
    done = [p for p in month_ends.index if p < cur][-(months + 1):]   # +1 for the opening close
    if len(done) < 2:
        return pd.DataFrame()
    periods = done[1:] + [cur]
    ends = [month_ends[p] for p in done] + [last]
    levels, market, _ = pi.industry_levels(px, industry, min_stocks=min_stocks)
    rows = {}
    for name, level in levels.items():
        vals = [pi.relative_points(level, market, t0, t1) for t0, t1 in zip(ends[:-1], ends[1:])]
        rows[name] = [np.nan if v is None else v for v in vals]
    labels = [p.strftime("%b %Y") for p in periods[:-1]] + [periods[-1].strftime("%b") + " so far"]   # glossary 9
    out = pd.DataFrame.from_dict(rows, orient="index", columns=labels)
    complete = out.iloc[:, :-1]

    def run(row) -> int:
        n, sign = 0, 0
        for v in reversed(row.tolist()):
            if not np.isfinite(v) or v == 0:
                break
            s = 1 if v > 0 else -1
            if sign and s != sign:
                break
            sign, n = s, n + 1
        return sign * n

    out["run"] = complete.apply(run, axis=1)
    out["total"] = complete.sum(axis=1, min_count=1)
    return out.sort_values("total", ascending=False)


def nearest_switches(sectors: pd.DataFrame, k: int = 3) -> dict[str, list[tuple[str, float]]]:
    """Industries nearest to changing group: behind over six months but within
    reach of ahead (entrants), and ahead but near to falling behind (exits),
    by their six-month figure."""
    if sectors is None or sectors.empty:
        return {"entrants": [], "exits": []}
    s = sectors.dropna(subset=["rel_6m"])
    ent = s[s["rel_6m"] <= 0].sort_values("rel_6m", ascending=False).head(k)
    ext = s[s["rel_6m"] > 0].sort_values("rel_6m").head(k)
    return {"entrants": list(zip(ent["Industry"], ent["rel_6m"])),
            "exits": list(zip(ext["Industry"], ext["rel_6m"]))}
