"""Three questions the Dashboard answers about the market, from data the app
already holds (owner, 7 Nov: tipsheet's question pages as the model, our own
sources as the data).

* Are most stocks taking part?  (breadth of the ranked universe)
* Is the market in an uptrend?  (Nifty 500 and the size indices against their
  averages and highs)
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
    pos = index.searchsorted(when, side="right") - 1
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


def _measure(name, unit, values, up_at, down_at, rule, primary=False, history=None) -> Measure:
    now, month, year = values
    return Measure(name, unit, now, month, year, _vote(now, up_at, down_at), rule,
                   up_at, down_at, primary, history_stats(history, now))


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


def _share_above_ema(prices: pd.DataFrame, span: int) -> pd.Series:
    ema = prices.ewm(span=span, min_periods=max(int(span * 0.8), 5)).mean()
    observed = prices.notna() & ema.notna()
    share = (prices > ema).where(observed).astype(float).mean(axis=1) * 100
    return share.where(_enough(observed.sum(axis=1)))


def _net_new_highs(prices: pd.DataFrame, days: int = 5) -> pd.Series:
    """Net new 52-week highs as a share of the stocks that can make one, summed
    over the last `days` rows (a week). The 52 weeks are a calendar window, not
    252 rows: the deep price history holds fewer rows a year in its early
    years, and a row count read those years as too short (no reading at all)."""
    hi = prices.rolling("365D", min_periods=20).max()
    lo = prices.rolling("365D", min_periods=20).min()
    # a stock needs most of a year of prices before it can set a 52W extreme
    first = prices.apply(lambda c: c.first_valid_index())
    old_enough = pd.DataFrame({c: prices.index >= (first[c] + pd.Timedelta(days=330)) if pd.notna(first[c])
                               else np.zeros(len(prices), bool) for c in prices.columns}, index=prices.index)
    tol = prices * 0.001
    can = prices.notna() & hi.notna() & lo.notna() & old_enough
    net = ((prices >= hi - tol) & can).sum(axis=1) - ((prices <= lo + tol) & can).sum(axis=1)
    counts = can.sum(axis=1)
    n = counts.replace(0, np.nan)
    return ((net.rolling(days, min_periods=1).sum() / n) * 100).where(_enough(counts))


def _beat_series(prices: pd.DataFrame, bench: pd.Series) -> tuple[pd.Series, pd.Series]:
    """The two year-long measures at each month end: share of stocks ahead of
    the Nifty 500 over the year, and the median stock less the index (pts)."""
    ends = prices.groupby(prices.index.to_period("M")).apply(lambda f: f.index[-1]).tolist()
    share, gap = {}, {}
    for t in ends:
        a, b = _beat_index_12m(prices, bench, t)
        if a is not None:
            share[t], gap[t] = a, b
    return pd.Series(share, dtype=float), pd.Series(gap, dtype=float)


def _beat_index_12m(prices: pd.DataFrame, bench: pd.Series, when: pd.Timestamp | None) -> tuple[float | None, float | None]:
    """Share of stocks ahead of the Nifty 500 over the year to `when`, and the
    median stock's return less the index's (points)."""
    if when is None:
        return None, None
    start = _on_or_before(prices.index, when - pd.DateOffset(years=1))
    if start is None:
        return None, None
    b = bench.dropna()
    b0, b1 = _on_or_before(b.index, start), _on_or_before(b.index, when)
    if b0 is None or b1 is None:
        return None, None
    rb = float(b.loc[b1] / b.loc[b0] - 1)
    # Each stock's last price in the week to each date: the history holds
    # dates on which few or no stocks have a price (4 Nov 2024 has none).
    week = pd.Timedelta(days=7)
    p1 = prices.loc[when - week:when].ffill().iloc[-1]
    p0 = prices.loc[start - week:start].ffill().iloc[-1]
    r = (p1 / p0 - 1).dropna()
    if len(r) < max(min(100, 0.5 * prices.shape[1]), 0.2 * prices.shape[1]):
        return None, None
    return float((r > rb).mean() * 100), float((r.median() - rb) * 100)


def breadth_answer(prices: pd.DataFrame, bench: pd.Series) -> Answer | None:
    if prices is None or prices.empty or bench is None or bench.dropna().empty:
        return None
    prices = prices.sort_index()
    d = anchor_dates(prices.index)
    a200, a50, nnh = _share_above_ema(prices, 200), _share_above_ema(prices, 50), _net_new_highs(prices)

    def at(s: pd.Series, key):
        t = d[key]
        return None if t is None else _f(s.get(t))

    beat = {k: _beat_index_12m(prices, bench, d[k]) for k in d}
    beat_share, beat_gap = _beat_series(prices, bench)
    ms = [
        _measure("Stocks above their 200D EMA", "pct", [at(a200, k) for k in d], 60, 40,
                 "60% or more is broad, 40% or less is narrow", primary=True, history=a200.iloc[200:]),
        _measure("Stocks ahead of the Nifty 500 over a year", "pct", [beat[k][0] for k in d], 55, 45,
                 "55% or more is broad, 45% or less is narrow", primary=True, history=beat_share),
        _measure("Stocks above their 50D EMA", "pct", [at(a50, k) for k in d], 60, 40,
                 "60% or more is broad, 40% or less is narrow", history=a50.iloc[50:]),
        _measure("Net new 52W highs this week, share of stocks", "pts", [at(nnh, k) for k in d], 5, -5,
                 "+5 or more is broad, −5 or less is narrow", history=nnh),
        _measure("Median stock less the Nifty 500, a year", "pts", [beat[k][1] for k in d], 3, -3,
                 "+3 pts or more is broad, −3 or less is narrow", history=beat_gap),
    ]
    return _answer("Are most stocks taking part?", ms,
                   ("Very narrow", "Narrow", "About usual", "Broad", "Very broad"),
                   lambda word, m: _breadth_sentence(word, ms))


def _breadth_sentence(word: str, ms: list[Measure]) -> str:
    a200, beat = ms[0].now, ms[1].now
    parts = []
    if a200 is not None:
        parts.append(f"{a200:.0f}% of the ranked stocks are above their 200D EMA")
    if beat is not None:
        parts.append(f"{beat:.0f}% beat the Nifty 500 over the year")
    text = " and ".join(parts) + "."
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
    s = s.loc[s.index > s.index[-1] - pd.DateOffset(years=1)] if len(s) else s
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


def _from_high_series(close: pd.Series) -> pd.Series:
    s = close.dropna()
    return ((s / s.rolling(252, min_periods=200).max() - 1) * 100).dropna()


def trend_answer(bench: pd.Series, size_closes: dict[str, pd.Series] | None,
                 share_above_200: pd.Series | None) -> Answer | None:
    if bench is None or bench.dropna().empty:
        return None
    b = bench.dropna().sort_index()
    d = anchor_dates(b.index)
    keys = list(d)
    ms = [
        _measure("Nifty 500 against its 10-month average", "pts", [ten_month_gap(b, d[k]) for k in keys],
                 0.0001, -0.0001, "above is up, below is down", primary=True, history=_ten_month_series(b)),
        _measure("Nifty 500 against its 200D EMA", "pts", [ema_gap(b, d[k]) for k in keys],
                 0.0001, -0.0001, "above is up, below is down", primary=True, history=_ema_gap_series(b)),
        _measure("Nifty 500 from its 52W high", "pts", [from_high(b, d[k]) for k in keys],
                 -5, -15, "within 5% is up, 15% or more below is down", history=_from_high_series(b)),
    ]
    for name, s in (size_closes or {}).items():
        s = s.dropna().sort_index()
        if len(s) < 200:
            continue
        ms.append(_measure(f"{name} against its 10-month average", "pts",
                           [ten_month_gap(s, d[k]) for k in keys], 0.0001, -0.0001,
                           "above is up, below is down", history=_ten_month_series(s)))
    if share_above_200 is not None and not share_above_200.dropna().empty:
        s = share_above_200.dropna()
        ms.append(_measure("Stocks above their 200D EMA", "pct",
                           [_f(s.get(_on_or_before(s.index, d[k]))) if d[k] is not None and
                            _on_or_before(s.index, d[k]) is not None else None for k in keys],
                           60, 40, "60% or more is up, 40% or less is down", history=s.iloc[200:]))
    return _answer("Is the market in an uptrend?", ms,
                   ("Strong downtrend", "Downtrend", "No clear trend", "Uptrend", "Strong uptrend"),
                   lambda word, m: _trend_sentence(word, ms))


def _trend_sentence(word: str, ms: list[Measure]) -> str:
    ups = sum(m.vote == UP for m in ms)
    downs = sum(m.vote == DOWN for m in ms)
    return f"{ups} of {len(ms)} measures say up, {downs} say down."


# ── What is leading? ────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Leaders:
    sentence: str
    size: list[tuple[str, float | None, float | None]]          # name, 6M rel, 1M rel (pts)
    sectors: pd.DataFrame                                         # Industry, Stocks, rel_6m, rel_1m, group
    as_of: pd.Timestamp


def _rel(close: pd.Series, bench: pd.Series, when: pd.Timestamp, months: int) -> float | None:
    s, b = close.dropna(), bench.dropna()
    t1s, t1b = _on_or_before(s.index, when), _on_or_before(b.index, when)
    start = when - pd.DateOffset(months=months)
    t0s, t0b = _on_or_before(s.index, start), _on_or_before(b.index, start)
    if None in (t1s, t1b, t0s, t0b):
        return None
    return (float(s.loc[t1s] / s.loc[t0s]) - float(b.loc[t1b] / b.loc[t0b])) * 100


def leaders_answer(prices: pd.DataFrame, industry: pd.Series, bench: pd.Series,
                   size_closes: dict[str, pd.Series] | None, min_stocks: int = 5) -> Leaders | None:
    """Industries by the median stock's return less the Nifty 500 over six
    months and one month: ahead on both, gaining (ahead over the month only),
    fading (ahead over six months only), behind on both. Size indices the same way."""
    if prices is None or prices.empty or bench is None or bench.dropna().empty:
        return None
    prices = prices.sort_index()
    when = prices.index[-1]
    b = bench.dropna()
    rows = []
    groups = industry.dropna().astype(str)
    groups = groups[groups.index.isin(prices.columns)]
    for name, syms in groups.groupby(groups).groups.items():
        syms = list(syms)
        if len(syms) < min_stocks:
            continue
        rel = {}
        for m in (6, 1):
            t0 = _on_or_before(prices.index, when - pd.DateOffset(months=m))
            b0, b1 = _on_or_before(b.index, when - pd.DateOffset(months=m)), _on_or_before(b.index, when)
            if t0 is None or b0 is None or b1 is None:
                rel[m] = None
                continue
            r = (prices.loc[when, syms] / prices.loc[t0, syms] - 1).dropna()
            rel[m] = None if r.empty else (float(r.median()) - float(b.loc[b1] / b.loc[b0] - 1)) * 100
        if rel[6] is None or rel[1] is None:
            continue
        group = ("ahead on both" if rel[6] > 0 and rel[1] > 0 else
                 "gaining" if rel[1] > 0 else "fading" if rel[6] > 0 else "behind on both")
        rows.append({"Industry": name, "Stocks": len(syms), "rel_6m": rel[6], "rel_1m": rel[1], "group": group})
    sectors = pd.DataFrame(rows, columns=["Industry", "Stocks", "rel_6m", "rel_1m", "group"])
    sectors = sectors.sort_values("rel_6m", ascending=False).reset_index(drop=True)

    size = []
    for name, s in (size_closes or {}).items():
        size.append((name, _rel(s, b, when, 6), _rel(s, b, when, 1)))

    both = sectors[sectors["group"] == "ahead on both"]
    lead_names = both["Industry"].head(3).tolist()
    best_size = max((x for x in size if x[1] is not None), key=lambda x: x[1], default=None)
    bits = []
    if best_size is not None:
        bits.append(f"{best_size[0]} lead{'s' if not best_size[0].endswith('s') else ''} the sizes over six months "
                    f"({best_size[1]:+.1f} pts against the Nifty 500)".replace("-", "−"))
    if len(sectors):
        bits.append(f"{len(both)} of {len(sectors)} industries are ahead over both six months and one month"
                    + (f", led by {', '.join(lead_names)}" if lead_names else ""))
    sentence = ("; ".join(bits) + ".") if bits else "Not enough history to say."
    return Leaders(sentence, size, sectors, when)


# ── Shared ──────────────────────────────────────────────────────────────────

def word_for(score: float | None, words: tuple[str, ...]) -> str:
    """Five bands of the weighted vote: at an end (|score| >= 0.6), leaning
    (>= 0.25), else the middle word."""
    if score is None:
        return "Not enough data"
    lo2, lo1, mid, hi1, hi2 = words
    if score >= 0.6:
        return hi2
    if score >= 0.25:
        return hi1
    if score <= -0.6:
        return lo2
    if score <= -0.25:
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
    """Each industry's median stock return less the Nifty 500's, per calendar
    month, for the last `months` completed months and the month to date
    (points). Columns are month labels ("Nov 2025" … "Nov 2026 MTD"), plus
    "run" (completed months in a row ahead, +n, or behind, -n, ending with the
    last completed month) and "total" (the completed months' points summed),
    sorted by total."""
    if prices is None or prices.empty or bench is None or bench.dropna().empty:
        return pd.DataFrame()
    px = prices.sort_index()
    b = bench.dropna().sort_index()
    last = px.index[-1]
    month_ends = px.groupby(px.index.to_period("M")).apply(lambda f: f.index[-1])
    cur = last.to_period("M")
    done = [p for p in month_ends.index if p < cur][-(months + 1):]   # +1 for the opening close
    if len(done) < 2:
        return pd.DataFrame()
    periods = done[1:] + [cur]
    ends = [month_ends[p] for p in done] + [last]
    groups = industry.dropna().astype(str)
    groups = groups[groups.index.isin(px.columns)]
    rows = {}
    for name, syms in groups.groupby(groups).groups.items():
        syms = list(syms)
        if len(syms) < min_stocks:
            continue
        vals = []
        for t0, t1 in zip(ends[:-1], ends[1:]):
            r = (px.loc[t1, syms] / px.loc[t0, syms] - 1).dropna()
            b0, b1 = _on_or_before(b.index, t0), _on_or_before(b.index, t1)
            if r.empty or b0 is None or b1 is None:
                vals.append(np.nan)
            else:
                vals.append((float(r.median()) - float(b.loc[b1] / b.loc[b0] - 1)) * 100)
        rows[name] = vals
    labels = [p.strftime("%b %Y") for p in periods[:-1]] + [periods[-1].strftime("%b") + " MTD"]
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
