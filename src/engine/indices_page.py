"""The Indices page's figures (S170), from the app's copy of NSE's daily index files.

Approved 21 Nov 2026 (docs/INDICES_REQUIREMENTS.md, mock-up v4). Every figure is a
price figure: NSE's total-return series cannot be reached (decision A). "N months
ago" is the last session on or before the same date N months back, the Dashboard's
rule (S154). Returns come from closes, never from NSE's points change (13 Mar 2023's
file measures it from the wrong day).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from src.engine import metrics

# On this day NSE's P/E basis changed (Nifty 50 40.43 -> 33.20 with the price flat);
# a percentile counts only from here (DATA_CORRECTNESS section 5, S168).
PE_FROM = pd.Timestamp("2021-03-31")

VALUATION_KEYS = ("nifty_50", "nifty_500", "nifty_total_market", "nifty_midcap_150",
                  "nifty_smallcap_250", "nifty_microcap_250")

# (style, the style index, its parent); decision C: Nifty500 Value 50.
STYLES = (("Momentum", "nifty200_momentum_30", "nifty_200"),
          ("Quality", "nifty200_quality_30", "nifty_200"),
          ("Value", "nifty500_value_50", "nifty_500"),
          ("Low volatility", "nifty100_low_volatility_30", "nifty_100"),
          ("Alpha", "nifty100_alpha_30", "nifty_100"),
          ("Equal weight", "nifty50_equal_weight", "nifty_50"))

# The size indices the rest of the site uses (owner, 21 Nov 2026), from 2017 for all:
# NSE's file lists Midcap 150 and Smallcap 250 from Apr 2016.
SIZES = (("Large", "nifty_100"), ("Mid", "nifty_midcap_150"), ("Small", "nifty_smallcap_250"),
         ("Micro", "nifty_microcap_250"))
SIZE_FROM_YEAR = 2017

WINDOWS = (1, 3, 6, 9, 12)            # months, the every-index table (owner, 21 Nov 2026)
PAGE_FAMILIES = ("Broad market", "Theme", "Strategy")   # sector indices are on Sectors


@dataclass
class Frames:
    """The store as wide frames, one column per index."""
    close: pd.DataFrame
    pe: pd.DataFrame
    pb: pd.DataFrame
    dy: pd.DataFrame
    names: dict[str, str] = field(default_factory=dict)
    groups: dict[str, str] = field(default_factory=dict)

    @property
    def as_of(self) -> pd.Timestamp:
        return pd.Timestamp(self.close.index[-1])

    def until(self, day: pd.Timestamp) -> "Frames":
        """The same frames cut at `day`, so a figure reads on another page's session."""
        cut = lambda x: x[x.index <= pd.Timestamp(day)]  # noqa: E731
        return Frames(cut(self.close), cut(self.pe), cut(self.pb), cut(self.dy), self.names, self.groups)


def frames(store: pd.DataFrame, groups: pd.DataFrame | None = None) -> Frames:
    def wide(col):
        return store.pivot(index="date", columns="key", values=col).sort_index()
    names = dict(zip(groups["key"], groups["name"])) if groups is not None else {}
    grp = dict(zip(groups["key"], groups["group"])) if groups is not None else {}
    return Frames(wide("close"), wide("pe"), wide("pb"), wide("div_yield"), names, grp)


def on_or_before(s: pd.Series, day: pd.Timestamp) -> pd.Timestamp | None:
    s = s.dropna()
    s = s[s.index <= day]
    return None if s.empty else pd.Timestamp(s.index[-1])


def months_back(day: pd.Timestamp, months: int) -> pd.Timestamp:
    return pd.Timestamp(day) - pd.DateOffset(months=months)


def ret(s: pd.Series, months: int, end: pd.Timestamp) -> float | None:
    """Price return in %, from the session on or before `months` back to `end`;
    None when the index is younger than the window."""
    s = s.dropna()
    s = s[s.index <= end]
    if s.empty:
        return None
    a = on_or_before(s, months_back(s.index[-1], months))
    if a is None:
        return None
    return float(s.iloc[-1] / s[a] - 1) * 100


def percentile(history: pd.Series, value: float) -> float:
    """Share of `history` strictly below `value`, in %."""
    h = history.dropna()
    return float((h < value).mean() * 100) if len(h) else float("nan")


# ── Valuation ────────────────────────────────────────────────────────────────

@dataclass
class Valuation:
    key: str
    name: str
    pe_3m: float
    pe_1m: float
    pe_now: float
    pct_3m: float
    pct_1m: float
    pct_now: float
    since: pd.Timestamp
    pb_now: float
    dy_now: float


def valuation(f: Frames, keys=VALUATION_KEYS) -> list[Valuation]:
    out = []
    for k in keys:
        if k not in f.pe:
            continue
        pe = f.pe[k].dropna()
        reg = pe[pe.index >= PE_FROM]
        if reg.empty:
            continue
        now = f.as_of
        d1, d3 = on_or_before(pe, months_back(now, 1)), on_or_before(pe, months_back(now, 3))
        at = lambda d: (float(pe[d]), percentile(reg[reg.index <= d], float(pe[d])))  # noqa: E731
        (p3, c3), (p1, c1) = at(d3), at(d1)
        out.append(Valuation(k, f.names.get(k, k), p3, p1, float(pe.iloc[-1]), c3, c1,
                             percentile(reg, float(pe.iloc[-1])), pd.Timestamp(reg.index[0]),
                             float(f.pb[k].dropna().iloc[-1]), float(f.dy[k].dropna().iloc[-1])))
    return out


def weekly(s: pd.Series) -> pd.Series:
    return s.dropna().resample("W-FRI").last().dropna()


# ── Styles ───────────────────────────────────────────────────────────────────

@dataclass
class Style:
    style: str
    key: str
    parent: str
    name: str
    parent_name: str
    live: pd.Timestamp
    lead_3m: float | None
    lead_1m: float | None
    lead_now: float | None
    dy_gap: float
    years: dict[int, float]
    rel: pd.Series            # style / parent, 100 at launch
    from_peak: pd.Series      # % below the relative line's best so far
    worst: float
    worst_peak: pd.Timestamp
    worst_low: pd.Timestamp
    recovered: pd.Timestamp | None


def lead_12m(f: Frames, key: str, parent: str, day: pd.Timestamp) -> float | None:
    a, b = ret(f.close[key], 12, day), ret(f.close[parent], 12, day)
    return None if a is None or b is None else a - b


def calendar_lead(fs: pd.Series, ps: pd.Series, year: int, as_of: pd.Timestamp) -> float | None:
    a0, b0 = pd.Timestamp(f"{year - 1}-12-31"), min(pd.Timestamp(f"{year}-12-31"), as_of)
    fa, fb, pa, pb = on_or_before(fs, a0), on_or_before(fs, b0), on_or_before(ps, a0), on_or_before(ps, b0)
    if None in (fa, fb, pa, pb):
        return None
    return float(fs[fb] / fs[fa] - ps[pb] / ps[pa]) * 100


def styles(f: Frames, pairs=STYLES) -> list[Style]:
    out = []
    now = f.as_of
    for lab, k, p in pairs:
        if k not in f.close or p not in f.close:
            continue
        fs, ps = f.close[k].dropna(), f.close[p].dropna()
        live = pd.Timestamp(fs.index[0])
        j = pd.concat([fs, ps], axis=1, join="inner").dropna()
        rel = j.iloc[:, 0] / j.iloc[:, 1]
        rel = 100 * rel / rel.iloc[0]
        from_peak = metrics.drawdown(rel) * 100
        low = pd.Timestamp(from_peak.idxmin())
        peak = pd.Timestamp(rel[:low].idxmax())
        after = rel[low:]
        back = after[after >= rel[peak]]
        years = {}
        for y in range(live.year + 1, now.year + 1):
            v = calendar_lead(fs, ps, y, now)
            if v is not None:
                years[y] = v
        out.append(Style(lab, k, p, f.names.get(k, k), f.names.get(p, p), live,
                         lead_12m(f, k, p, months_back(now, 3)), lead_12m(f, k, p, months_back(now, 1)),
                         lead_12m(f, k, p, now),
                         float(f.dy[k].dropna().iloc[-1] - f.dy[p].dropna().iloc[-1]),
                         years, rel, from_peak, float(from_peak.min()), peak, low,
                         pd.Timestamp(back.index[0]) if len(back) else None))
    return out


def years_led(s: Style) -> tuple[int, int]:
    return sum(v > 0 for v in s.years.values()), len(s.years)


# ── Size by year ─────────────────────────────────────────────────────────────

@dataclass
class SizeYears:
    size: str
    key: str
    name: str
    years: dict[int, tuple[float, float]]      # year: (return %, worst fall within the year %)
    median_fall: float                          # whole years only


def size_years(f: Frames, sizes=SIZES, from_year: int = SIZE_FROM_YEAR) -> list[SizeYears]:
    out = []
    now = f.as_of
    for lab, k in sizes:
        if k not in f.close:
            continue
        s = f.close[k].dropna()
        rows = {}
        for y in range(max(from_year, s.index[0].year + 1), now.year + 1):
            a = on_or_before(s, pd.Timestamp(f"{y - 1}-12-31"))
            if a is None:
                continue
            yy = s[(s.index > a) & (s.index <= pd.Timestamp(f"{y}-12-31"))]
            if yy.empty:
                continue
            path = pd.concat([s[[a]], yy])
            rows[y] = (float(yy.iloc[-1] / s[a] - 1) * 100, metrics.max_drawdown(path) * 100)
        whole = [v[1] for y, v in rows.items() if y < now.year]
        out.append(SizeYears(lab, k, f.names.get(k, k), rows, float(np.median(whole)) if whole else float("nan")))
    return out


# ── Every index ──────────────────────────────────────────────────────────────

@dataclass
class IndexRow:
    key: str
    name: str
    group: str
    live: pd.Timestamp
    returns: dict[int, float | None]     # months: %
    from_high: float | None              # % below the 1-year high of closes; None if younger than a year
    pe: float | None


def every_index(f: Frames, families=PAGE_FAMILIES) -> dict[str, list[IndexRow]]:
    """{family: rows}, each sorted by 1-year return, indices younger than a year last
    (oldest launch first)."""
    now = f.as_of
    out: dict[str, list[IndexRow]] = {g: [] for g in families}
    for k in f.close.columns:
        g = f.groups.get(k)
        if g not in out:
            continue
        s = f.close[k].dropna()
        if s.empty or s.index[-1] != now:
            continue                      # discontinued, or not published today
        r = {m: ret(s, m, now) for m in WINDOWS}
        year = s[s.index > months_back(now, 12)]
        hi = None if r[12] is None else float(s.iloc[-1] / year.max() - 1) * 100
        pe = f.pe[k].dropna()
        out[g].append(IndexRow(k, f.names.get(k, k), g, pd.Timestamp(s.index[0]), r, hi,
                               float(pe.iloc[-1]) if len(pe) and pe.index[-1] == now else None))
    for g in out:
        full = sorted((x for x in out[g] if x.returns[12] is not None), key=lambda x: -x.returns[12])
        young = sorted((x for x in out[g] if x.returns[12] is None), key=lambda x: x.live)
        out[g] = full + young
    return out
