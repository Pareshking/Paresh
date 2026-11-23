"""The Sectors page's figures (S174), approved by the owner on 21 Nov 2026 (mock-up v2,
docs/SECTORS_REQUIREMENTS.md "Owner's decisions").

A sector is NSE's: the "Industry" column of NSE's index lists, which NSE's own
classification calls the sector level (22 groups). Every sector figure is the
equal-weighted, daily-rebalanced index of its ranked stocks (src/engine/peer_index, S147),
read against the same construction over all ranked stocks, "the 750". NSE's sector
indices come from the app's copy of NSE's daily index files (src/engine/indices_page),
each placed under one sector by data/reference/nse_sector_index_map.csv.

With a TradingView grouping chosen, every figure built from the ranked stocks regroups;
the NSE index figures are not computed, since NSE's indices match NSE's sectors only.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from src.engine import indices_page as ip
from src.engine import market_questions as mq
from src.engine import peer_index as pi

MAP_FILE = Path(__file__).resolve().parents[2] / "data" / "reference" / "nse_sector_index_map.csv"
MIN_STOCKS = 5                  # one count for every section: five or more ranked stocks
WINDOWS = ip.WINDOWS            # 1, 3, 6, 9, 12 months, as on Indices
GROUPS = ("ahead on both", "gaining", "fading", "behind on both")
EMA_SPANS = (20, 50, 100, 200)
MAP_PERIODS = (1, 3)


def sector_map(path: Path | None = None) -> pd.DataFrame:
    """The approved sector -> NSE sector index map: sector, index_key, role (headline | finer), reason."""
    return pd.read_csv(path or MAP_FILE, dtype=str).fillna("")


def headline_of(m: pd.DataFrame) -> dict[str, str]:
    h = m[m["role"] == "headline"]
    return dict(zip(h["sector"], h["index_key"]))


def on_or_before(idx: pd.DatetimeIndex, day: pd.Timestamp) -> pd.Timestamp:
    return pd.Timestamp(idx[max(0, idx.searchsorted(day, side="right") - 1)])


def ew_return(level: pd.Series, months: int, end: pd.Timestamp) -> float | None:
    """An equal-weighted level's return in %, with the Indices page's date rule."""
    v = pi.window_return(level, end - pd.DateOffset(months=months), end)
    return None if v is None else v * 100


def from_high(s: pd.Series, end: pd.Timestamp) -> float | None:
    """% below the highest close of the last year; None when the series is younger than a year."""
    s = s.dropna()
    s = s[s.index <= end]
    if s.empty or s.index[0] > end - pd.DateOffset(months=12):
        return None
    # Opens on the last session on or before the date a year back, as every 52-week high (S211).
    from src.engine.calendar_momentum import year_window_start
    year = s.iloc[year_window_start(s.index, len(s) - 1):]
    return float(s.iloc[-1] / year.max() - 1) * 100


def clean_groups(groups: pd.Series, columns) -> pd.Series:
    g = groups.dropna().astype(str).str.strip()
    return g[(g != "") & (g.str.lower() != "nan") & g.index.isin(columns)]


# ── Which sectors lead ────────────────────────────────────────────────────────

@dataclass
class Lead:
    name: str
    stocks: int
    lead6_3m: float | None      # the six-month lead over the 750, read 3 months ago
    lead6_1m: float | None      # ... a month ago
    lead6: float                # ... now
    lead1: float                # the one-month lead now
    lead3: float | None
    group: str
    returns: dict[int, float | None] = field(default_factory=dict)
    from_high: float | None = None


@dataclass
class Leads:
    when: pd.Timestamp
    d1: pd.Timestamp
    d3: pd.Timestamp
    rows: list[Lead]
    levels: dict[str, pd.Series]
    market: pd.Series
    counts: dict[str, int]
    market_ret: dict[int, float | None]
    gap: dict[str, float | None]          # the 750 less Nifty Total Market, pts: "1", "3", "6", "6_1m", "6_3m"
    left_out: dict[str, int]               # groups with fewer than MIN_STOCKS, and their counts


def group_of(l6: float, l1: float) -> str:
    return ("ahead on both" if l6 > 0 and l1 > 0 else "gaining" if l1 > 0
            else "fading" if l6 > 0 else "behind on both")


def leads(prices: pd.DataFrame, groups: pd.Series, total_market: pd.Series | None) -> Leads | None:
    """Each group's lead over the 750, both equal-weighted (the construction of
    market_questions.leaders_answer, read on three dates)."""
    if prices is None or prices.empty:
        return None
    px = prices.sort_index()
    g = clean_groups(groups, px.columns)
    if g.empty:
        return None
    when = pd.Timestamp(px.index[-1])
    d1, d3 = on_or_before(px.index, when - pd.DateOffset(months=1)), on_or_before(px.index, when - pd.DateOffset(months=3))
    levels, market, counts = pi.industry_levels(px, g, min_stocks=MIN_STOCKS)

    def lead(level, months, end):
        return pi.relative_points(level, market, end - pd.DateOffset(months=months), end)

    rows = []
    for name, level in levels.items():
        l6, l1 = lead(level, 6, when), lead(level, 1, when)
        if l6 is None or l1 is None:
            continue
        rows.append(Lead(name, counts[name], lead(level, 6, d3), lead(level, 6, d1), l6, l1, lead(level, 3, when),
                         group_of(l6, l1), {m: ew_return(level, m, when) for m in WINDOWS}, from_high(level, when)))
    rows.sort(key=lambda r: -r.lead6)
    gap: dict[str, float | None] = {}
    tm = None if total_market is None else pd.to_numeric(total_market, errors="coerce").dropna().sort_index()
    if tm is not None and len(tm):
        tm = tm[tm.index <= when]
        for m in (1, 3, 6):
            gap[str(m)] = pi.size_gap(market, tm, when - pd.DateOffset(months=m), when)
        gap["6_3m"] = pi.size_gap(market, tm, d3 - pd.DateOffset(months=6), d3)
        gap["6_1m"] = pi.size_gap(market, tm, d1 - pd.DateOffset(months=6), d1)
    sizes = g.value_counts()
    left = {str(k): int(v) for k, v in sizes.items() if v < MIN_STOCKS}
    return Leads(when, d1, d3, rows, levels, market, counts, {m: ew_return(market, m, when) for m in WINDOWS}, gap, left)


def nearest_switches(ld: Leads, k: int = 3) -> dict[str, list[tuple[str, float]]]:
    frame = pd.DataFrame([{"Industry": r.name, "rel_6m": r.lead6} for r in ld.rows])
    return mq.nearest_switches(frame, k)


# ── NSE's sector indices beside each sector ────────────────────────────────────

@dataclass
class IndexLine:
    key: str
    name: str
    headline: bool
    live: pd.Timestamp
    returns: dict[int, float | None]
    from_high: float | None
    pe: float | None

    @property
    def young(self) -> bool:
        return self.returns.get(12) is None


@dataclass
class SectorGroup:
    sector: str
    stocks: int
    ours: Lead | None
    indices: list[IndexLine]


def sector_indices(f: ip.Frames, ld: Leads, smap: pd.DataFrame, all_counts: dict[str, int]) -> list[SectorGroup]:
    """Every "Sector" index under the sector the map places it in, in the order of the lead table;
    the headline index first, then the rest by 1-year return, those younger than a year last."""
    rows = {x.key: x for x in ip.every_index(f, families=("Sector",))["Sector"]}
    by_sector: dict[str, list[IndexLine]] = {}
    for r in smap.itertuples():
        x = rows.get(r.index_key)
        if x is None:
            continue
        by_sector.setdefault(r.sector, []).append(
            IndexLine(x.key, x.name, r.role == "headline", x.live, x.returns, x.from_high, x.pe))
    ours = {r.name: r for r in ld.rows}
    order = [r.name for r in ld.rows] + sorted(s for s in by_sector if s not in ours)
    out = []
    for name in order:
        ix = sorted(by_sector.get(name, []), key=lambda x: (not x.headline, x.young,
                                                            -(x.returns.get(12) or -1e9) if not x.young else x.live.value))
        out.append(SectorGroup(name, int(all_counts.get(name, 0)), ours.get(name), ix))
    return out


@dataclass
class Gap:
    sector: str
    index: str
    live: pd.Timestamp
    ours3: float
    nse3: float
    gap3: float
    ours1: float
    nse1: float
    gap1: float


def broad_or_narrow(f: ip.Frames, ld: Leads, smap: pd.DataFrame) -> list[Gap]:
    """Each sector's ranked stocks against its headline index over 3M and 1M, narrowest first."""
    out = []
    ours = {r.name: r for r in ld.rows}
    for sector, key in headline_of(smap).items():
        r = ours.get(sector)
        if r is None or key not in f.close:
            continue
        s = f.close[key].dropna()
        n3, n1 = ip.ret(s, 3, ld.when), ip.ret(s, 1, ld.when)
        o3, o1 = r.returns.get(3), r.returns.get(1)
        if None in (n3, n1, o3, o1):
            continue
        out.append(Gap(sector, f.names.get(key, key), pd.Timestamp(s.index[0]), o3, n3, o3 - n3, o1, n1, o1 - n1))
    out.sort(key=lambda g: g.gap3)
    return out


def pair_series(f: ip.Frames, ld: Leads, smap: pd.DataFrame) -> dict[str, dict]:
    """A year of each sector and its headline index, both 100 on the first session they share inside the year."""
    out = {}
    start = ld.when - pd.DateOffset(months=12)
    for sector, key in headline_of(smap).items():
        if sector not in ld.levels or key not in f.close:
            continue
        j = pd.concat([ld.levels[sector].rename("ours"), f.close[key].dropna().rename("nse")], axis=1, join="inner").dropna()
        j = j[(j.index >= start) & (j.index <= ld.when)]
        if len(j) < 2:
            continue
        j = 100 * j / j.iloc[0]
        out[sector] = {"index": f.names.get(key, key), "dates": [f"{d:%Y-%m-%d}" for d in j.index],
                       "ours": [round(float(v), 2) for v in j["ours"]], "nse": [round(float(v), 2) for v in j["nse"]]}
    return out


# ── Inside each sector ───────────────────────────────────────────────────────

@dataclass
class Share:
    name: str
    stocks: int
    b3: float | None
    b1: float | None
    now: float | None


def ema_shares(prices: pd.DataFrame, groups: pd.Series, ld: Leads, span: int = 200) -> list[Share]:
    """The share of each group's ranked stocks above their own EMA, 3M ago, 1M ago and now (today's members),
    and the same for all of them first."""
    px = prices.sort_index()
    g = clean_groups(groups, px.columns)
    ema = px.ewm(span=span, min_periods=max(int(span * 0.8), 5)).mean()

    def share(members, d):
        p, e = px.loc[d, members], ema.loc[d, members]
        obs = p.notna() & e.notna()
        return None if not obs.any() else float(((p > e) & obs).sum() / obs.sum() * 100)
    out = [Share("All ranked stocks", len(g), *(share(list(g.index), d) for d in (ld.d3, ld.d1, ld.when)))]
    for name in ld.levels:
        members = list(g.index[g == name])
        out.append(Share(name, len(members), *(share(members, d) for d in (ld.d3, ld.d1, ld.when))))
    return out


# ── The leadership map ──────────────────────────────────────────────────────

def leadership_views(prices: pd.DataFrame, groups: pd.Series, bench: pd.Series) -> dict[str, list[dict]]:
    """The live page's map (sector_breadth.sector_leadership) for every EMA and period, with five or more
    stocks a group, keyed "<span>-<months>"."""
    from src.engine.sector_breadth import sector_leadership
    out = {}
    for span in EMA_SPANS:
        for months in MAP_PERIODS:
            b = sector_leadership(prices, groups, bench, span, min_stocks=MIN_STOCKS, months=months)
            if b.empty:
                continue
            out[f"{span}-{months}"] = [{
                "name": r.Sector, "stocks": int(r.Stocks), "then": f"{pd.Timestamp(r.Then):%-d %b}", "now": f"{pd.Timestamp(r.Now):%-d %b}",
                "x0": _r(r.x_then * 100), "x1": _r(r.x_now * 100), "y0": _r(r.y_then * 100), "y1": _r(r.y_now * 100),
                "a0": int(r.above_then), "o0": int(r.obs_then), "a1": int(r.above_now), "o1": int(r.obs_now),
                "ret": _r(r.ret_now * 100, 2), "bench": _r(r.bench_now * 100, 2),
                "leaders": [[str(s), _r(v * 100)] for s, v in r.Leaders]} for r in b.itertuples()]
    return out


def _r(v, nd: int = 1):
    if v is None or (isinstance(v, float) and not np.isfinite(v)):
        return None
    return round(float(v), nd)
