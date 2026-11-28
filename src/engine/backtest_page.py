"""The Backtest page's figures, from one run of `run_backtest` (S174, mock-up v1 approved 21 Nov 2026).

Pure functions: no Streamlit, no files. The view (src/ui/views/backtest_view.py)
and the weekly reference (scripts/build_backtest_reference.py) both read them,
so the page and the stored cost and tax tests are worked out the same way.

Conventions (docs/BACKTEST_REQUIREMENTS.md, owner's decisions of 21 Nov 2026):
- "a year" is compounded over calendar time (365.25-day years), as the engine;
- a lead is a difference of two returns, in points;
- every fall from a peak is `metrics.drawdown` / `metrics.max_drawdown`;
- both sides are price returns (the long file keeps only dividends of 10% or more).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from src.engine.metrics import drawdown, max_drawdown
from src.loaders.app_pack import resolve as _pack

# The run the page opens on, and the one the weekly reference re-runs: the record's
# rules on the Nifty 500 as it stood, from 2010, with the six-monthly reset applied
# throughout (owner, 21 Nov 2026, decision G).
DEFAULT_INDEX = "nifty_500"
DEFAULT_START = pd.Period("2010-01", "M")
DEFAULT_RULE = "live"

# Each universe's own NSE index, shown beside the Nifty 500 "for this universe"
# (owner, 21 Nov 2026, decision A). The Nifty 500 itself is the headline.
UNIVERSE_INDEX = {
    "nifty_50": ("nifty_50", "Nifty 50"),
    "nifty_100": ("nifty_100", "Nifty 100"),
    "nifty_midcap_150": ("nifty_midcap_150", "Nifty Midcap 150"),
    "nifty_smallcap_250": ("nifty_smallcap_250", "Nifty Smallcap 250"),
    "nifty_microcap_250": ("nifty_microcap_250", "Nifty Microcap 250"),
    "nifty_total_market": ("nifty_total_market", "Nifty Total Market"),
}
TOTAL_MARKET = "nifty_total_market"
TOTAL_MARKET_FROM = 2022            # its first whole calendar year (live 14 Oct 2021)
MOMENTUM_INDEX = "nifty200_momentum_30"
HISTORICAL_INDUSTRIES = Path(__file__).resolve().parents[2] / "data" / "reference" / "historical_industries.csv"


def frame_for(close: pd.DataFrame, columns, end: pd.Period, to_latest: bool) -> pd.DataFrame:
    """The price frame a run reads: the index's members ever, to the first session after
    the end month (the engine reports the completed months before its last session), or
    to the file's last session when the run ends at the latest completed month."""
    after = close.index[close.index >= (end + 1).start_time]
    cut = close.index[-1] if to_latest or not len(after) else after[0]
    cols = sorted(set(columns) & set(close.columns))
    return close.loc[:cut, cols].astype("float64")


def industry_map(columns, current: dict[str, str]) -> tuple[dict[str, str], int]:
    """The industry each stock is capped under, and how many no list places.

    The current lists (`current`), then TradingView mapped to NSE's names, then
    data/reference/historical_industries.csv (NSE's sector for the names that left
    before today's lists, looked up 3 Oct 2026). A stock nothing places is its own
    group, not one shared "Other" the cap would squeeze. The page and the weekly
    reference use this one map, so their "as tested" figures are the same run.
    """
    from src.loaders import former_members

    cols = list(columns)
    sec = dict(current)
    sec.update(former_members.industry_for([c for c in cols if c not in sec]))
    try:
        past_frame = pd.read_csv(HISTORICAL_INDUSTRIES)
        past = dict(zip(past_frame["NSE_SYMBOL"], past_frame["SECTOR"]))
    except (OSError, ValueError, KeyError):
        past = {}
    sec.update({c: past[c] for c in cols if sec.get(c, "Other") == "Other" and c in past})
    unlabelled = [c for c in cols if sec.get(c, "Other") == "Other"]
    sec.update({c: f"Unlabelled · {c}" for c in unlabelled})
    return sec, len(unlabelled)


def index_file_industries() -> dict[str, str]:
    """Today's Total Market list's industries (the Screener's rows carry the same)."""
    from src.loaders import former_members

    idx = pd.read_csv(_pack(former_members.INDEX_FILE))
    idx.columns = [str(c).strip() for c in idx.columns]
    return dict(zip(idx["Symbol"].astype(str), idx["Industry"].astype(str)))


def calendar_years(curve: pd.Series) -> float:
    curve = curve.dropna()
    return (pd.Timestamp(curve.index[-1]) - pd.Timestamp(curve.index[0])).days / 365.25


def a_year(curve: pd.Series) -> float | None:
    """Compounded a year over calendar time; None under a year (the site does not scale a part-year up)."""
    curve = curve.dropna()
    if len(curve) < 2:
        return None
    yrs = calendar_years(curve)
    if yrs < 1 or curve.iloc[0] <= 0:
        return None
    return float((curve.iloc[-1] / curve.iloc[0]) ** (1 / yrs) - 1)


def on_calendar(series: pd.Series, index: pd.Index) -> pd.Series:
    s = pd.to_numeric(series, errors="coerce").dropna().sort_index()
    s.index = pd.DatetimeIndex(s.index)
    return s.reindex(s.index.union(pd.DatetimeIndex(index))).ffill().reindex(index)


def months(curve: pd.Series, bench: pd.Series) -> pd.DataFrame:
    """Calendar-month returns of the curve and the benchmark (the first from the first fill)."""
    curve = curve.dropna()
    b = on_calendar(bench, curve.index)
    me, mb = curve.resample("ME").last(), b.resample("ME").last()
    s = pd.concat([curve.iloc[:1], me]).pct_change().dropna()
    t = pd.concat([b.iloc[:1], mb]).pct_change().dropna()
    out = pd.DataFrame({"rule": s, "bench": t}).dropna()
    return out[~out.index.duplicated(keep="last")]


@dataclass
class Summary:
    first: pd.Timestamp
    last: pd.Timestamp
    years: float
    a_year: float | None
    bench_a_year: float | None
    lead: float | None              # pts a year, as a fraction (0.085 = 8.5 pts)
    total: float
    bench_total: float
    months: int
    ahead: int
    up: int
    lead_first_half: float | None   # mean monthly lead, first half of the months
    lead_second_half: float | None
    split: pd.Timestamp | None
    median_lead: float | None


def summary(curve: pd.Series, bench: pd.Series) -> Summary:
    curve = curve.dropna()
    b = on_calendar(bench, curve.index)
    ay, by = a_year(curve), a_year(b)
    m = months(curve, bench)
    lead_m = m["rule"] - m["bench"]
    half = len(m) // 2
    split = m.index[half] if half else None
    return Summary(
        first=pd.Timestamp(curve.index[0]), last=pd.Timestamp(curve.index[-1]), years=calendar_years(curve),
        a_year=ay, bench_a_year=by, lead=None if ay is None or by is None else ay - by,
        total=float(curve.iloc[-1] / curve.iloc[0] - 1), bench_total=float(b.iloc[-1] / b.iloc[0] - 1),
        months=len(m), ahead=int((lead_m > 0).sum()), up=int((m["rule"] > 0).sum()),
        lead_first_half=float(lead_m.iloc[:half].mean()) if half else None,
        lead_second_half=float(lead_m.iloc[half:].mean()) if half else None,
        split=split, median_lead=float(lead_m.median()) if len(lead_m) else None)


@dataclass
class Fall:
    depth: float
    peak: pd.Timestamp
    low: pd.Timestamp
    recovered: pd.Timestamp | None
    days: int                       # calendar days from the peak to the day it was regained (or to the last day)


def falls(curve: pd.Series, n: int = 3) -> list[Fall]:
    """The n deepest separate falls from a peak, each ending when the peak is regained."""
    curve = curve.dropna()
    dd = drawdown(curve)
    under = dd < 0
    if not bool(under.any()):
        return []
    runs = (under != under.shift(fill_value=False)).cumsum()
    out = []
    idx = curve.index
    for _, seg in dd[under].groupby(runs[under]):
        start = idx.get_loc(seg.index[0])
        peak = idx[start - 1] if start > 0 else seg.index[0]
        end = idx.get_loc(seg.index[-1])
        rec = idx[end + 1] if end + 1 < len(idx) else None
        out.append(Fall(float(seg.min()), pd.Timestamp(peak), pd.Timestamp(seg.idxmin()),
                        None if rec is None else pd.Timestamp(rec),
                        int(((rec if rec is not None else idx[-1]) - peak).days)))
    return sorted(out, key=lambda f: f.depth)[:n]


def below_peak_now(curve: pd.Series) -> float:
    return float(drawdown(curve.dropna()).iloc[-1])


def years_table(curve: pd.Series, others: dict[str, pd.Series], first_year: dict[str, int] | None = None) -> pd.DataFrame:
    """One row per calendar year: the rule and each index over the same span (the first
    year from the first fill, the last to the curve's last day). An index with no close
    at the start of a year, or before its first whole year, reads NaN."""
    curve = curve.dropna()
    first_year = first_year or {}
    rows = []
    years = sorted(set(curve.index.year))
    for y in years:
        seg = curve[curve.index.year == y]
        prior = curve[curve.index.year < y]
        start = prior.index[-1] if len(prior) else seg.index[0]
        end = seg.index[-1]
        row = {"year": y, "months": len(set(seg.index.month)), "first_month": int(seg.index[0].month) if not len(prior) else 1,
               "last_month": int(end.month), "rule": float(seg.iloc[-1] / curve.loc[start] - 1)}
        for name, s in others.items():
            s = pd.to_numeric(s, errors="coerce").dropna()
            s.index = pd.DatetimeIndex(s.index)
            a, b = s.loc[:start], s.loc[:end]
            ok = len(a) and len(b) and (start - a.index[-1]).days <= 7 and y >= first_year.get(name, 0)
            row[name] = float(b.iloc[-1] / a.iloc[-1] - 1) if ok else np.nan
        rows.append(row)
    return pd.DataFrame(rows)


def window(curve: pd.Series, others: dict[str, pd.Series], start) -> dict:
    """A year and the largest fall from `start` (the first session on or after it) for
    the rule and each index, over the same days."""
    e = curve.dropna().loc[pd.Timestamp(start):]
    if len(e) < 2:
        return {}
    out = {"from": pd.Timestamp(e.index[0]), "to": pd.Timestamp(e.index[-1]), "years": calendar_years(e),
           "rule": (a_year(e), max_drawdown(e))}
    for name, s in others.items():
        s = on_calendar(s, e.index)
        out[name] = (a_year(s), max_drawdown(s)) if s.notna().all() else (None, None)
    return out


def weekly_chart(curve: pd.Series, others: dict[str, pd.Series]) -> dict:
    """Friday closes (and the last day) re-based to 100 at the first fill, with each
    one's fall from its own peak on daily closes; an index with no close yet is None."""
    curve = curve.dropna()
    frame = pd.DataFrame({"rule": curve})
    for name, s in others.items():
        frame[name] = on_calendar(s, curve.index)
    keep = frame.resample("W-FRI").last().index
    picks = sorted(set(frame.index[frame.index.searchsorted(k, side="right") - 1] for k in keep
                       if frame.index.searchsorted(k, side="right") > 0) | {frame.index[-1]})
    out = {"dates": [f"{d:%Y-%m-%d}" for d in picks], "series": {}, "dd": {}}
    for col in frame.columns:
        s = frame[col]
        valid = s.dropna()
        base = valid.iloc[0] if len(valid) else np.nan
        rel = s / base * 100
        dd = pd.Series(np.nan, index=s.index)
        if len(valid):
            dd.loc[valid.index] = drawdown(valid) * 100
        out["series"][col] = [None if pd.isna(rel.loc[d]) else round(float(rel.loc[d]), 2) for d in picks]
        out["dd"][col] = [None if pd.isna(dd.loc[d]) else round(float(dd.loc[d]), 2) for d in picks]
    return out


def stale_exits(closed_trades: pd.DataFrame | None, close: pd.DataFrame, sessions: int = 5) -> list[dict]:
    """Sales struck on a price carried from `sessions` or more sessions before (a stock that
    had stopped trading: a takeover, a delisting, a suspension)."""
    out = []
    if closed_trades is None or closed_trades.empty:
        return out
    done = closed_trades[closed_trades["Status"] == "Closed"]
    for _, r in done.iterrows():
        s = r["Symbol"]
        d = pd.to_datetime(r["Exit Date"], errors="coerce")
        if pd.isna(d) or s not in close.columns:
            continue
        col = close[s].loc[:d].dropna()
        if col.empty:
            continue
        gap = int(((close.index > col.index[-1]) & (close.index <= d)).sum())
        if gap >= sessions:
            out.append({"symbol": s, "exit": pd.Timestamp(d), "last_print": pd.Timestamp(col.index[-1]), "sessions": gap})
    return out


def short_books(monthly: pd.DataFrame | None, top_n: int) -> list[tuple[pd.Timestamp, int]]:
    """Rebalances that found fewer stocks passing the rules than the book holds: the rest sat in cash."""
    if monthly is None or monthly.empty or "Holdings" not in monthly:
        return []
    short = monthly[monthly["Holdings"] < top_n]
    return [(pd.Timestamp(d), int(h)) for d, h in zip(short["Period Start"], short["Holdings"])]


PERIOD_COLS = ("Period Start", "Period End", "Strategy Net", "Benchmark", "Alpha vs Benchmark", "Turnover %",
               "Cost Drag %", "Buys", "Sells", "Holdings")
PERIOD_KEYS = ("from", "to", "rule", "n500", "lead", "turnover", "costs", "buys", "sells", "holdings")


def periods(monthly: pd.DataFrame | None) -> pd.DataFrame:
    """Each rebalance period, fill to fill, newest first: the rule's return after costs and the Nifty 500's, turnover,
    costs, buys, sells and holdings (S239 item 7; "Rebalance periods" dropped 22 Nov, restored on "Restore the 9",
    28 Nov). Returns are fractions; turnover and costs are in percent, as the engine writes them."""
    names = dict(zip(PERIOD_COLS, PERIOD_KEYS))
    if monthly is None or monthly.empty or "Period Start" not in monthly:
        return pd.DataFrame(columns=list(PERIOD_KEYS))
    m = monthly[[c for c in PERIOD_COLS if c in monthly]].rename(columns=names)
    for c in ("from", "to"):
        if c in m:
            m[c] = pd.to_datetime(m[c])
    return m.sort_values("from", ascending=False).reset_index(drop=True)


def trade_stats(closed_trades: pd.DataFrame | None) -> dict:
    """Closed trades: count, share won, median days held, median return, and the profit
    factor weighted by each trade's size at entry (gains in ₹ terms over losses)."""
    if closed_trades is None or closed_trades.empty:
        return {}
    ct = closed_trades
    done = ct[(ct["Status"] == "Closed") & ct["Return %"].notna()]
    if done.empty:
        return {"closed": 0, "open": int((ct["Status"] == "Open").sum())}
    r = done["Return %"].astype(float)
    w = pd.to_numeric(done.get("Entry Weight %"), errors="coerce").fillna(0.0) if "Entry Weight %" in done else pd.Series(1.0, index=done.index)
    pnl = r * w
    gains, losses = float(pnl[pnl > 0].sum()), float(-pnl[pnl < 0].sum())
    return {"closed": len(done), "open": int((ct["Status"] == "Open").sum()), "won": float((r > 0).mean()),
            "median_days": float(pd.to_numeric(done["Holding (Days)"], errors="coerce").median()),
            "median_return": float(r.median()), "mean_return": float(r.mean()),
            "profit_factor": gains / losses if losses > 0 else None,
            # The average win and loss, the best and the worst (S239 item 8; dropped 22 Nov, restored on the owner's
            # "Restore the 9", 28 Nov). Each trade counted once, as the share won is.
            "avg_win": float(r[r > 0].mean()) if (r > 0).any() else None,
            "avg_loss": float(r[r < 0].mean()) if (r < 0).any() else None,
            "best": float(r.max()), "worst": float(r.min()),
            "best_sym": str(done.loc[r.idxmax(), "Symbol"]) if "Symbol" in done else None,
            "worst_sym": str(done.loc[r.idxmin(), "Symbol"]) if "Symbol" in done else None}
