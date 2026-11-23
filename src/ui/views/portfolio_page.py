"""Portfolio, rebuilt from the approved mock-up v3 (owner, 20 Nov 2026: "Approved,
add the uninvested line and build it"; S151, requirements docs/PORTFOLIO_REQUIREMENTS.md).

Holdings first, as a broker shows a portfolio; plain section names; then
industry and size (now, against the 750, and at every rebalance), returns by
period, equity, drawdown and risk, calendar returns that last for years, day by
day against the market, trades with one hidden history, and the three systems
over the same window.

Figures come from src/ui/book_series.py (the book's daily value, the series every
page reads), src/engine/portfolio_report.py (periods, drawdown, risk, calendar),
src/engine/book_exposure.py (industry and size kept at each rebalance) and
dashboard_insights.rank_trails (the rank trail the Dashboard shows). This module
gathers and formats.
"""
from __future__ import annotations

import html
import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

from src.ui import formats as _fmt

from src.engine import book_exposure as bx
from src.engine import dashboard_insights as di
from src.engine import portfolio_report as pr
from src.loaders import benchmark_indices as bi
from src.ui.views.dashboard_home_view import (END, HOME_CSS, SHORT, Chart, emit, how, html_of, sg, size_class)

e = html.escape
ROOT = Path(__file__).resolve().parents[3]
SIZE_INDEX = {"Large": "nifty50", "Mid": "midcap150", "Small": "smallcap250", "Micro": "microcap250"}
YTD_ROWS = (("microcap250", "Nifty Microcap 250"), ("mix", "Mix in the book’s size split"), ("smallcap250", "Nifty Smallcap 250"),
            ("nifty500_mom50", "Nifty500 Momentum 50"), ("midcap150", "Nifty Midcap 150"),
            (bi.TOTAL_MARKET, "Nifty Total Market"), ("nifty50", "Nifty 50"))
EXIT_NAMES = (("Trend Breakdown", "Trend breakdown", "closed below its 50D EMA"),
              ("Rank Dropped", "Rank dropped", "fell out of the top {cut}"),
              ("52W", "Off its high", "more than {hc}% below the 52W high"))
MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def short(name: str) -> str:
    return SHORT.get(name, name)


def tone(v) -> str:
    return "" if v is None or not np.isfinite(v) else ("dh-up" if v > 0 else "dh-down" if v < 0 else "")


def pct(v, d: int = 1) -> str:
    return sg(v, d, "%")


def inr(v, plus: bool = False) -> str:
    from src.ui import formats as f
    return f.inr(v, plus=plus)


def dshort(t) -> str:
    t = pd.Timestamp(t)
    return f"{t.day} {MON[t.month - 1]}"


def _kpis(cells, cls: str = "") -> str:
    """(label, value, value tone, status, status tone, sub)."""
    out = "".join(f'<div class="dh-kpi"><span class="dh-k-l">{e(a)}</span><span class="dh-k-v {vt}">{e(v)}</span>'
                  f'<span class="dh-k-s {stt}">{e(s)}</span><span class="dh-k-sub">{e(sub)}</span></div>'
                  for a, v, vt, s, stt, sub in cells)
    return f'<div class="dh-kpis pf-kpis {cls}">{out}</div>'


def _head(anchor: str, title: str, sub: str) -> str:
    return (f'<div class="pf-shead" id="{anchor}"><h2 class="pf-h2">{e(title)}</h2>'
            f'<span class="pf-sc">{e(sub)}</span></div>')


def _sec(parts: list) -> list:
    return ['<section class="dh-sec pf-sec">'] + parts + ["</section>", END]


# ── Inputs ──────────────────────────────────────────────────────────────────


@dataclass
class Page:
    as_of: pd.Timestamp
    capital: float
    value: float
    holdings: float
    equity: pd.Series
    market: pd.Series
    mom: pd.Series
    table: pd.DataFrame
    history: dict
    meta: dict
    record: dict
    ledger: dict
    rank_df: pd.DataFrame
    prices: pd.DataFrame
    cfg: dict
    trails: dict
    industry_state: dict
    sizes: dict
    exposure: pd.DataFrame
    market_weights: dict
    indices: dict
    systems: list = field(default_factory=list)
    correlation: float | None = None
    system: str = "750"


def gather(series, record: dict, ledger: dict, rank_df: pd.DataFrame, system: str, benchmark_close) -> Page:
    from src.engine import market_questions as mq
    from src.engine.model_record import record_sector_map
    from src.engine.track_record import TRACK_RECORD_CONFIG
    from src.ui.views.qualified_view import correlation

    meta = (record or {}).get("live_meta") or {}
    as_of = series.as_of or pd.Timestamp(series.equity.index[-1])
    frame = bi.read()
    idx = {k: bi.series(k, frame=frame).loc[:as_of] for k in bi.SERIES}
    # An index not yet published for the book's session: Nifty Total Market keeps its history (the note
    # under Returns says it is a session behind); the comparison indices read "–" rather than a stale close (S148).
    end = idx[bi.TOTAL_MARKET].dropna().index.max() if len(idx[bi.TOTAL_MARKET].dropna()) else as_of
    idx = {k: (v if k in (bi.TOTAL_MARKET, "nifty500_mom50") else di.as_of(v, end)) for k, v in idx.items()}
    market, mom = idx[bi.TOTAL_MARKET], idx["nifty500_mom50"]
    table = series.table
    syms = table["Symbol"].astype(str).tolist()
    from src.engine.exit_watch import qualified_ranks
    _, trails = di.rank_trails(series.prices, syms, now=qualified_ranks(rank_df))   # now: the plan's rank (S154)
    industry = rank_df.set_index("Symbol")["Industry"] if "Industry" in rank_df else pd.Series(dtype=str)
    n500 = _n500()
    leaders = mq.leaders_answer(series.prices, industry, n500, None)
    state = {}
    if leaders is not None:
        for _, r in leaders.sectors.iterrows():
            state[str(r["Industry"])] = di.industry_bucket(float(r["rel_6m"]), float(r["rel_1m"]))
    membership = json.loads((ROOT / "data" / "membership_history.json").read_text())
    sizes = bx.size_of(syms, as_of, membership)
    tb = record.get("tradebook")
    # data/book_exposure.csv is the 750's record (scripts/update_track_record.py writes it);
    # another system's history comes from its own tradebook, never merged under the 750's
    # dates (S194 L3, 23 Nov 2026: Nano Cap, Combined and Nifty 1000 showed the 750's sizes).
    from src.engine.extra_universe import SYSTEM_750
    exposure = bx.load() if system == SYSTEM_750 else pd.DataFrame(columns=bx.FIELDS)
    if isinstance(tb, pd.DataFrame) and len(tb):
        live = bx.exposure(tb, record_sector_map(sorted(set(tb["Symbol"].astype(str))), system), membership)
        exposure = bx.merge(exposure, live)
    mw = _market_weights(rank_df)
    corr = correlation(series.prices, syms)[1]
    systems = _systems(series.prices, benchmark_close, system, market, as_of)
    # The money put in, not the equity's first point: with no frozen month that point is today's
    # value, so the Nifty 1000 read "Started with ₹1,05,50,323" and a gain of ₹0 (S193 A2).
    from src.core.config import MODEL_BOOK_CAPITAL
    return Page(as_of=as_of, capital=float(MODEL_BOOK_CAPITAL),
                value=series.value, holdings=series.holdings, equity=series.equity, market=market, mom=mom,
                table=table, history=series.history, meta=meta, record=record, ledger=ledger, rank_df=rank_df,
                prices=series.prices, cfg=dict(TRACK_RECORD_CONFIG), trails=trails, industry_state=state,
                sizes=sizes, exposure=exposure, market_weights=mw, indices=idx, systems=systems,
                correlation=corr, system=system)


def _n500() -> pd.Series:
    try:
        b = pd.read_csv(ROOT / "data" / "benchmarks.csv", parse_dates=["date"]).set_index("date").sort_index()
        return pd.to_numeric(b["nifty500"], errors="coerce").dropna()
    except (OSError, KeyError, ValueError):
        return pd.Series(dtype=float)


def _market_weights(rank_df: pd.DataFrame) -> dict[str, float]:
    """Each industry's share of the system's ranked stocks by market value: NSE's market caps, then
    the > ₹2,000 Cr list's own month-end figures for the stocks NSE's file lacks (S193 C)."""
    from src.loaders.extra_universe_loader import system_market_caps

    r = rank_df.drop_duplicates("Symbol").set_index("Symbol")
    mc = system_market_caps(r.index, str(ROOT / "data" / "nse_market_caps.csv"))
    if mc.empty:
        return {}
    w = pd.to_numeric(mc.reindex(r.index), errors="coerce").groupby(r["Industry"]).sum()
    return (w / w.sum() * 100).to_dict() if w.sum() > 0 else {}


_NUMBER_WORDS = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six"}


def waiting_for(start: pd.Period, this: pd.Period, frozen: set | None) -> pd.Period | None:
    """The first month from `start` to last month that the ledger has not frozen, or None."""
    if frozen is None:
        return None
    m = start
    while m < this:
        if m not in frozen:
            return m
        m += 1
    return None


def common_window(starts: dict[str, pd.Period], this: pd.Period,
                  frozen: dict[str, set] | None = None) -> tuple[pd.Period | None, set[str]]:
    """The window the systems are compared over, and the systems in it.

    A system joins only after its first full month (owner, 22 Nov 2026: "first full month"): one that
    started this month has a partial month only, so it would shrink every other system's window to a
    few weeks. With `frozen` ({system: frozen months}), a full month means a FROZEN month: a system
    whose ledger lacks a month from its start to last month waits (S194 F5: a refused Nifty 1000
    November would otherwise join in December with December only, on a window from 1 Nov).
    The window starts at the latest start among the systems that have joined."""
    joined = {sid for sid, start in starts.items() if start < this
              and waiting_for(start, this, (frozen or {}).get(sid) if frozen is not None else None) is None}
    if not joined:
        return None, set()
    return max(starts[sid] for sid in joined), joined


def _systems(prices, benchmark_close, system, market, as_of) -> list[tuple]:
    """("common", "1 Oct", systems in the window), then (name, this month %, since the common start %,
    since its own start %, started) for each live system, then the market."""
    from src.engine.extra_universe import SYSTEM_NAMES, SYSTEMS
    from src.engine.systems import inception, ledger_path
    from src.engine.track_record import load_ledger
    from src.ui.views.track_record_view import _comparison_price_frame, _record_mtd
    names = {sid: (n, "this book" if sid == system else "") for sid, n in SYSTEM_NAMES.items()}   # S193 B9
    got = {}
    for sid in SYSTEMS:
        try:
            led = load_ledger(ledger_path(sid), inception(sid))
        except (ValueError, OSError):
            continue
        try:
            lm = _record_mtd(_comparison_price_frame(sid, system, prices), benchmark_close, sid) if prices is not None else {}
        except (ValueError, KeyError, TypeError, IndexError):
            lm = {}
        months = {pd.Period(k, "M"): float(v["strategy"]) * 100 for k, v in (led.get("months") or {}).items()
                  if v.get("strategy") is not None}
        if lm.get("mtd_period") and lm.get("strategy_mtd") is not None:
            months[pd.Period(lm["mtd_period"], "M")] = float(lm["strategy_mtd"]) * 100
        if months:
            got[sid] = (inception(sid), months, {pd.Period(k, "M") for k in (led.get("months") or {})})
    if not got:
        return []
    this = pd.Period(as_of, "M")
    frozen = {sid: fz for sid, (_, _, fz) in got.items()}
    common, joined = common_window({sid: start for sid, (start, _, _) in got.items()}, this, frozen)
    if common is None:
        return []
    rows = []
    for sid, (start, months, fz) in got.items():
        n, sub = names.get(sid, (sid, ""))
        if sid in joined:
            rows.append((n, sub, months.get(this), pr.chain([v for p, v in months.items() if p >= common]),
                         pr.chain(months.values()), start.strftime("%b %Y")))
        else:
            gap = waiting_for(start, this, fz)
            rows.append((n, sub, months.get(this), None, pr.chain(months.values()),
                         f"{start:%b %Y} · joins once {gap:%B} is frozen" if gap is not None
                         else f"{start:%b %Y} · joins from {(pd.Period(start, 'M') + 1).to_timestamp():%b}"))
    rows.append(("Nifty Total Market", "", pr.ret(market, (this - 1).to_timestamp(how="end").normalize(), as_of),
                 pr.ret(market, (common - 1).to_timestamp(how="end").normalize(), as_of), None, ""))
    return [("common", f"{common.to_timestamp():%-d %b}", len(joined))] + rows


# ── The page, as parts ──────────────────────────────────────────────────────


def months_of(p: Page) -> dict[str, dict]:
    """Each series by month: the book as recorded (and the month so far), the market, momentum, the Nifty 500 as recorded."""
    g = p.history.get("monthly_grid")
    book, n5 = {}, {}
    if isinstance(g, pd.DataFrame) and len(g):
        for _, r in g.iterrows():
            per = pd.Period(str(r["Period"]), "M")
            if pd.notna(r["Strategy Net"]):
                book[per] = float(r["Strategy Net"]) * 100
            if pd.notna(r["Benchmark"]):
                n5[per] = float(r["Benchmark"]) * 100
    ps = sorted(book)
    mkt = pr.month_returns(p.market, ps, p.as_of)
    mom = pr.month_returns(p.mom, ps, p.as_of)
    # The system's first month starts at its first fill for every series, as the book and
    # the recorded Nifty 500 do (S193 A12, owner 23 Nov 2026); calendar_html footnotes it.
    first, fill = first_fill(p)
    if fill is not None and first in book:
        end = min(first.to_timestamp(how="end").normalize(), p.as_of)
        mkt[first], mom[first] = pr.ret(p.market, fill, end), pr.ret(p.mom, fill, end)
    lead = {k: (book[k] - mkt[k]) if mkt.get(k) is not None else None for k in ps}
    return {"book": book, "market": mkt, "lead": lead, "mom": mom, "n500": n5}


def first_fill(p: Page) -> tuple[pd.Period, pd.Timestamp | None]:
    """The system's first month and its first fill (the month's first session)."""
    from src.engine.dashboard_insights import first_fill as _first_fill
    from src.engine.systems import inception

    first = inception(p.system)
    return first, _first_fill(p.market, first)


def _frozen_note(p: Page) -> str:
    """The frozen-months note, only for a system that has frozen months (S193 B: the 1000 had none)."""
    if not ((p.ledger or {}).get("months")):
        return ""
    return ("Frozen months stay as recorded against the Nifty 500, the benchmark when they were frozen; Nifty Total Market is "
            "worked out beside them (the Nifty 500 row shows what each was frozen against). ")


def _provenance(p: Page) -> str:
    """How the record's months were made, when not all were struck month by month (S193 B)."""
    months = (p.ledger or {}).get("months") or {}
    back = sorted(k for k, v in months.items() if (v or {}).get("origin") == "backfill")
    if back:
        on = (months[back[-1]] or {}).get("finalized_on")
        a, b = pd.Period(back[0], "M"), pd.Period(back[-1], "M")
        span = f"{a:%b}" if a == b else f"{a:%b} to {b:%b}"
        return (f" {span} {a.year} were worked out from the rules" + (f" on {pd.Timestamp(on):%-d %b %Y}" if on else "")
                + "; later months were recorded as they happened.")
    from src.engine.extra_universe import SYSTEM_1000
    if p.system == SYSTEM_1000 and not months:
        # THREE_SYSTEMS.md: the Nifty 1000's November is reconstructed from a list NSE published on 16 Nov.
        return " November is reconstructed: its 30 Oct book uses a list NSE first published on 16 Nov."
    return ""


def header(p: Page) -> list:
    t = p.history
    since = t.get("strategy_total_return")
    since = float(since) * 100 if since is not None and np.isfinite(since) else None
    # From the close before the system's first month, not the equity's first point: with no
    # frozen month that point is the live month's end (S175: Nifty 1000 read 5.5 points ahead
    # on its Portfolio and 4.3 behind on its Dashboard). For the 750 the two are the same day.
    from src.engine.extra_universe import SYSTEM_NAMES
    from src.engine.systems import inception
    begun = inception(p.system).start_time
    # The market from the first fill's close, where the book starts (owner, 23 Nov 2026: "2: from the fill").
    fill = first_fill(p)[1]
    mkt_since = pr.ret(p.market, fill if fill is not None else begun - pd.Timedelta(days=1), p.as_of)
    # The book's own latest day; the market's only when its index has that session (S148: one date for both).
    eq = p.equity.dropna()
    mk = p.market.dropna()
    # The live month's point can carry the month-end date (30 Nov on 20 Nov); the day is the price date.
    last = min(pd.Timestamp(eq.index[-1]), pd.Timestamp(p.as_of)) if len(eq) else pd.Timestamp(p.as_of)
    day = {"book": float(eq.iloc[-1] / eq.iloc[-2] - 1) * 100 if len(eq) > 1 else None,
           "market": float(mk.iloc[-1] / mk.iloc[-2] - 1) * 100 if len(mk) > 1 and mk.index[-1] >= last else None}
    tab = p.table
    dayr = float(pd.to_numeric(tab["Day P&L (₹)"], errors="coerce").sum())
    m = months_of(p)
    this = pd.Period(p.as_of, "M")
    mtd, mmtd = m["book"].get(this), m["market"].get(this)
    gap = None if mtd is None or mmtd is None else mtd - mmtd
    f = pr.falls(p.equity)
    cells = [("Portfolio value", inr(p.value), "", f"Started with {inr(p.capital)}", "dh-muted",
              f"{inr(p.value - p.holdings)} not invested"),
             (f"{_fmt.since(begun)}, after costs", pct(since), tone(since), inr(p.value - p.capital, plus=True), tone(since),
              f"Nifty Total Market {pct(mkt_since)}"),
             ("Day P&L", pct(day["book"]), tone(day["book"]), inr(dayr, plus=True), tone(dayr),
              f"Nifty Total Market {pct(day['market'])}" if day["market"] is not None
              else f"Nifty Total Market for {dshort(last)} not in yet"),
             (f"Month so far · {this:%b}", pct(mtd), tone(mtd),
              "" if gap is None else f"{_fmt.fixed(abs(gap), 1)} pts {'ahead of' if gap >= 0 else 'behind'} Nifty Total Market", tone(gap),
              f"Nifty Total Market {pct(mmtd)}"),
             ("Below its peak today", pct(f.now) if f else "–", "dh-watch" if f and f.now < 0 else "",
              f"Peak {dshort(f.peak_now)}" if f else "", "", f"Max drawdown {pct(f.worst)}" if f else "")]
    nav = "".join(f'<a class="dh-pill" href="#{a}">{e(t)}</a>' for a, t in NAV)
    # Each system's own start and rules: the 750 from 1 Jan 2026, the others from their
    # inception (Nifty 1000 1 Nov, > ₹2,000 Cr and Combined 1 Oct 2026).
    sub = (f"The model book: ₹1 Cr put in on {begun:%-d %B %Y}, run by the "
           f"{SYSTEM_NAMES.get(p.system, 'Nifty 750')} rules, {len(tab)} stocks. Returns are after costs.{_provenance(p)}")
    lead = None if since is None or mkt_since is None else since - mkt_since
    answer = ("The model book" if since is None else
              f"The book is {'up' if since >= 0 else 'down'} {abs(since):.1f}% since {begun:%-d %B}" + ("" if lead is None else
              f", {_fmt.fixed(abs(lead), 1)} points {'ahead of' if lead >= 0 else 'behind'} Nifty Total Market") + ".")
    # The title answers the reader's first question; the page's name is the kicker (tipsheet benchmark, 21 Nov 2026).
    return [f'<div class="pf-head"><p class="pf-kick">Portfolio</p><h1 class="pf-title">{e(answer)}</h1><p class="pf-sub">{e(sub)}</p>',
            _kpis(cells, "pf-five"), f'<div class="dh-pills pf-nav" role="navigation" aria-label="On this page">{nav}</div></div>']


NAV = (("pf-book", "Current book"), ("pf-exp", "Sector & size"), ("pf-ret", "Returns"), ("pf-eq", "Equity, drawdown & risk"),
       ("pf-cal", "Calendar returns"), ("pf-day", "Day by day"), ("pf-trades", "Trades"), ("pf-sys", "Systems side by side"))


def holdings_spec(p: Page) -> dict:
    t = p.table
    r = p.rank_df.drop_duplicates("Symbol").set_index("Symbol")
    hc = int(round((1 - float(p.cfg.get("high_pct", 0.8))) * 100))
    cut = int(p.cfg.get("buffer_n", 40))
    word = {"strong": ("Strong", "up"), "turning": ("Turning", "watch"), "weak": ("Weak", "down")}
    rows = []
    for _, h in t.iterrows():
        s = str(h["Symbol"])
        ind = str(h.get("Sector / Industry") or "–")
        st_, tn = word.get(p.industry_state.get(ind, ""), ("", ""))
        tr = p.trails.get(s, [None, None, None])
        ema = pd.to_numeric(r["% 50 EMA"].get(s) if "% 50 EMA" in r else np.nan, errors="coerce")
        hi = pd.to_numeric(r["% High"].get(s) if "% High" in r else np.nan, errors="coerce")
        co = str(h.get("Company") or s)
        rows.append({"s": s, "co": co, "co_short": co.removesuffix(" Ltd.").removesuffix(" Limited").removesuffix(" Ltd"),
                     "ind": short(ind), "status": st_, "tone": tn, "size": _fmt.size(p.sizes.get(s, "")) if p.sizes.get(s) else "",
                     "since": f"{pd.Timestamp(h['Entry Date']):%Y-%m-%d}", "days": int(h.get("Holding Days") or 0),
                     # Unrounded: the page rounds once, half up (S193 A13). Rounded here to 2 dp first,
                     # 188.549 became 188.55 and then +188.6% against Actions' +188.5%.
                     "q": int(h["Shares"]), "ep": float(h["Entry Price"]), "px": float(h["Current Price"]),
                     "val": round(float(h["Current Value (₹)"])), "w": float(h["Weight %"]),
                     "dayp": float(h.get("Day P&L %") or 0), "pnl": round(float(h["P&L since Rebalance (₹)"])),
                     "ret": float(h["Return since Entry %"]),
                     "ema": None if pd.isna(ema) else round(float(ema), 1), "hi": None if pd.isna(hi) else round(float(hi), 1),
                     "r3": tr[0], "r1": tr[1], "rn": tr[2]})
    val = sum(x["val"] for x in rows)
    prev = float(pd.to_numeric(t["Previous Value (₹)"], errors="coerce").sum())
    rebal = float(pd.to_numeric(t["Value at Rebalance (₹)"], errors="coerce").sum())
    dayr = float(pd.to_numeric(t["Day P&L (₹)"], errors="coerce").sum())
    foot = {"val": val, "w": float(sum(x["w"] for x in rows)), "day": (val / prev - 1) * 100 if prev else 0.0, "dayr": dayr,
            "pnl": float(sum(x["pnl"] for x in rows)), "since_fill": (val / rebal - 1) * 100 if rebal else 0.0,
            "below_ema": sum(1 for x in rows if x["ema"] is not None and x["ema"] < 0),
            "past_high": sum(1 for x in rows if x["hi"] is not None and x["hi"] <= -hc),
            "past_rank": sum(1 for x in rows if x["rn"] is None or x["rn"] > cut)}
    fill = pd.to_datetime(p.meta.get("fill_date"), errors="coerce")
    fill_s = dshort(fill) if pd.notna(fill) else "the fill"
    # Labels from here, not the kit, so the page's words are in the page (and in the CI check without a browser).
    cols = [["s", "Stock", 0], ["ind", "Sector · size", 0], ["since", "Entry date", 0], ["q", "Qty", 1], ["ep", "Entry price", 1],
            ["px", "Price", 1], ["val", "Value", 1], ["w", "Weight", 1], ["dayp", "Today", 1], ["pnl", f"P&L from {fill_s}", 1],
            ["ret", "Since entry", 1], ["ema", "vs 50D EMA", 1], ["hi", "From 52W high", 1], ["rn", "Rank 3M · 1M · now", 0]]
    text = {"holdings": f"{len(rows)} holdings", "before": "before costs", "below": "below", "past_high": f"past −{hc}%",
            "past_rank": f"past #{cut}"}
    return {"rows": rows, "foot": foot, "high_cut": hc, "rank_cut": cut, "fill": fill_s, "cols": cols, "text": text}


def section_book(p: Page) -> list:
    spec = holdings_spec(p)
    hc, cut = spec["high_cut"], spec["rank_cut"]
    # The sessions the ranks are read on (20 Oct 2026 was a holiday: the rank is the 19 Oct one), as
    # Actions and the Dashboard print them (S193 A4).
    px = p.prices.index if len(p.prices.index) else pd.DatetimeIndex([p.as_of])
    dates = [di.on_or_before(px, d) or d for d in di.trail_dates(p.as_of).values()]
    note = (f"Entry price and since entry are from the day the stock was first bought. P&L in rupees starts at the {spec['fill']} "
            "fill, where today’s share counts were set: the record keeps returns and weights, so rupee figures are a mark, not "
            f"a cost. Holdings {inr(p.holdings)} + {inr(p.value - p.holdings)} not invested = portfolio value {inr(p.value)}. "
            f"Sell rules, checked at each month-end: below its 50D EMA (trend breakdown), more than {hc}% below its 52-week high, "
            f"or out of the top {cut} by rank. Rank: where today’s rule puts the stock on {', '.join(dshort(d) for d in dates)} "
            "among the stocks that pass its filters; “Out” means it does not pass them. The plan for the next rebalance is on Actions.")
    return _sec([_head("pf-book", "Current book", f"{len(spec['rows'])} holdings · tap a column to sort · red: past a sell "
                                                  "rule’s line today (the rules are checked at month-end)"),
                 Chart("holdings", spec, {"label": "The book's holdings"}),
                 f'<p class="dh-note">{e(note)}</p>'])


def section_exposure(p: Page) -> list:
    t = p.table
    now = (t.groupby("Sector / Industry")["Weight %"].sum()).to_dict()
    held = t.groupby("Sector / Industry")["Symbol"].count().to_dict()
    names = list(dict.fromkeys(list(now) + [k for k, v in p.market_weights.items() if v >= 4 and k not in now]))
    rows = sorted(((n, float(now.get(n, 0.0)), float(p.market_weights.get(n, 0.0))) for n in names), key=lambda r: (-r[1], -r[2]))
    top = max([r[1] for r in rows] + [r[2] for r in rows] + [10.0]) * 1.05
    word = {"strong": ("Strong", "dh-up"), "turning": ("Turning", "dh-watch"), "weak": ("Weak", "dh-down")}
    from src.engine.extra_universe import UNIVERSE_SHORT
    uni = e(UNIVERSE_SHORT.get(p.system, "750"))
    head = (f'<div class="pf-ihead"><span>Sector</span><span></span><span class="dh-num">Book</span><span class="dh-num">The {uni}</span>'
            '<span class="dh-num">Over / under</span><span>Status</span></div>')
    body = ""
    for n, v, m in rows:
        k = held.get(n, 0)
        st_, c = word.get(p.industry_state.get(n, ""), ("", "")) if v else ("Not held", "dh-muted")
        d = v - m
        body += (f'<div class="pf-irow"><span class="pf-nm">{e(short(n))}<small>{f"{k} holding" + ("s" if k > 1 else "") if k else "none held"}</small></span>'
                 f'<span class="pf-ibar"><i style="width:{v / top * 100:.1f}%"></i><b style="left:{m / top * 100:.1f}%"></b></span>'
                 f'<span class="dh-num dh-b">{f"{v:.1f}%" if v else "–"}</span><span class="dh-num dh-muted">{m:.1f}%</span>'
                 f'<span class="dh-num {tone(d)}">{sg(d)}</span><span class="{c}">{e(st_)}</span></div>')
    ex = p.exposure
    size = ex[ex["kind"] == "size"].pivot_table(index="date", columns="name", values="weight").sort_index() if len(ex) else pd.DataFrame()
    srows = ""
    # Nano Cap (the Nifty 1000's other 250), Ultra Nano Cap (outside the 1000) and Other (outside the four
    # lists before the 1000's history) are drawn only when a book held them.
    drawn = [k for k in bx.SIZES if k in ("Large", "Mid", "Small", "Micro") or (k in size and size[k].fillna(0).gt(0).any())]
    for d, r in size.iterrows():
        segs = "".join(f'<i class="{size_class(k)}" style="width:{float(r.get(k, 0)):.1f}%" title="{_fmt.size(k)} {float(r.get(k, 0)):.0f}%">'
                       f'{f"{float(r.get(k, 0)):.0f}" if float(r.get(k, 0)) >= 15 else ""}</i>' for k in drawn)
        srows += f'<div class="pf-srow"><span class="dh-mono">{MON[d.month - 1]}</span><div class="dh-sizebar pf-thin">{segs}</div></div>'
    key = '<div class="pf-key">' + "".join(f'<span><i class="{size_class(k)}"></i>{_fmt.size(k)}</span>' for k in drawn) + '</div>'
    ind = ex[ex["kind"] == "industry"].pivot_table(index="name", columns="date", values="weight").fillna(0) if len(ex) else pd.DataFrame()
    heat = ""
    if len(ind):
        # Every industry the book has held, largest weight at any rebalance first
        # (owner, 21 Nov 2026: "We might be missing other sectors despite we have space"; it listed only those ever at 15%).
        held = ind[(ind > 0).any(axis=1)]          # every industry the book has held
        big = held.loc[held.max(axis=1).sort_values(ascending=False).index]
        heat = ('<table class="dh-tab pf-heat"><thead><tr><th scope="col">Sector</th>'
                + "".join(f'<th scope="col" class="dh-num">{MON[c.month - 1]}</th>' for c in big.columns) + "</tr></thead><tbody>"
                + "".join(f'<tr><th scope="row">{e(short(n))}</th>' + "".join(
                    f'<td class="dh-num pf-hc" style="background:color-mix(in srgb,var(--c-ink) {min(100, v * 1.6):.0f}%,var(--c-white));'
                    f'color:{"var(--c-white)" if v >= 30 else "var(--c-ink)"}">{f"{v:.0f}" if v else ""}</td>' for v in r.values) + "</tr>"
                    for n, r in big.iterrows()) + "</tbody></table>")
    first = size.iloc[0] if len(size) else None
    last = size.iloc[-1] if len(size) else None
    shift = ""
    if first is not None:
        # A system whose record starts after January (Nano Cap, Combined, Nifty 1000) names its first rebalance;
        # "small and micro" takes in Nano Cap and Ultra Nano Cap when the book holds them (S194 L3, 23 Nov 2026).
        began = "began the year" if size.index[0].month == 1 else f"began {MON[size.index[0].month - 1]} {size.index[0].year}"
        # Only the groups the book holds now (S193 B: the list read "Small Cap, Micro Cap, Nano Cap and Ultra
        # Nano Cap" while 40% Nano Cap and 60% Ultra Nano Cap).
        held = [(k, n) for k, n in (("Small", "Small Cap"), ("Micro", "Micro Cap"), ("Nano Cap", "Nano Cap"),
                                    ("Ultra Nano Cap", "Ultra Nano Cap")) if float(last.get(k, 0) or 0) > 0]
        held = held or [("Small", "Small Cap"), ("Micro", "Micro Cap")]
        small = sum(float(last.get(k, 0) or 0) for k, _ in held)
        names = [n for _, n in held]
        words = names[0] if len(names) == 1 else ", ".join(names[:-1]) + f" and {names[-1]}"
        shift = (f"The book {began} {first.get('Large', 0) + first.get('Mid', 0):.0f}% in Large Cap and Mid Cap and is now "
                 f"{small:.0f}% {words}. ")
    note = (shift + "Each rebalance’s sector and size weights are worked out from that month’s book and kept, so the history "
            "stays as it was when later lists change. Size is by NSE’s index lists on each date; sectors are the record’s own.")
    since = f"since {_fmt.date(_start(p))}"
    # _head escapes its own text; `uni` is already escaped for the HTML below (S193 B6: "&gt;" showed).
    return _sec([_head("pf-exp", "Sector & size", f"now, against the {UNIVERSE_SHORT.get(p.system, '750')}, and at every rebalance {since}"),
                 f'<div class="dh-cap"><b>Sector exposure now</b><span>bar: the book’s weight · mark: the sector’s weight in the {uni} '
                 'by market value</span></div>', '<div class="pf-ilist">' + head + body + '</div>',
                 '<div class="dh-pair"><div><div class="dh-cap"><b>The book by size, each rebalance</b>'
                 f'<span>{e(" · ".join(_fmt.size(k) for k in drawn))}</span></div>'
                 + srows + key + f'<p class="dh-note pf-gap">{e(note)}</p></div><div><div class="dh-cap"><b>Sectors, each rebalance</b>'
                 '<span>% of the book, the largest at any rebalance first</span></div>'
                 f'<div class="dh-scroll">{heat}</div></div></div>'])


def section_returns(p: Page) -> list:
    rows = pr.periods(p.equity, p.market, p.mom, p.as_of, first_fill(p)[1])
    begun = _start(p)
    label = {"1 year": "12 months", "Since start": _fmt.since(begun), "Month so far": f"Month so far · {p.as_of:%b}"}
    shown = [(label.get(lab, lab.replace(", since start", f", since {_fmt.date(begun)}")), *v) for lab, *v in rows]
    per = "".join(f'<tr{" class=pf-hl" if lab.startswith("This year") else ""}><th scope="row">{e(lab)}</th>'
                  f'<td class="dh-num dh-b {tone(b)}">{pct(b)}</td><td class="dh-num">{pct(m)}</td>'
                  f'<td class="dh-num {tone(None if b is None or m is None else b - m)}">{sg(None if b is None or m is None else b - m)}</td>'
                  f'<td class="dh-num dh-muted">{pct(mo)}</td></tr>' for lab, b, m, mo in shown)
    start = p.equity.index[0]
    # One window for the book and the indices: a book begun after 31 Dec is set against the
    # indices from its own start, and the table says so (S193 A3: the book since 1 Oct stood
    # against indices since 31 Dec).
    year_start = pd.Timestamp(year=p.as_of.year - 1, month=12, day=31)
    ytd_start = max(pd.Timestamp(start), year_start)
    young = ytd_start > year_start
    book_ytd = pr.ret(p.equity, ytd_start, p.as_of)
    # A young book's indices start at its first fill, as the header's (owner, 23 Nov 2026: "2: from the
    # fill"); the book from the money put in. The table read +8.5% from 30 Sep beside +9.6% (S193 B8).
    fill = first_fill(p)[1] if young else None
    idx_start = fill if fill is not None else ytd_start
    vals = {k: pr.ret(p.indices[k], idx_start, p.as_of) for k, _ in YTD_ROWS if k in p.indices}
    ex_since = p.exposure[pd.to_datetime(p.exposure["date"]) > ytd_start] if len(p.exposure) else p.exposure
    vals["mix"] = pr.size_mix(ex_since, {k: p.indices[v] for k, v in SIZE_INDEX.items()}, p.as_of)
    ytd = (f'<tr class="pf-hl"><th scope="row">The book, after costs</th><td class="dh-num dh-b {tone(book_ytd)}">{pct(book_ytd)}</td><td></td></tr>'
           + "".join(f'<tr{" class=pf-hl" if k == "mix" else ""}><th scope="row">{e(n)}</th><td class="dh-num dh-b {tone(vals.get(k))}">{pct(vals.get(k))}</td>'
                     f'<td class="dh-num {tone(None if vals.get(k) is None or book_ytd is None else book_ytd - vals[k])}">'
                     f'{sg(None if vals.get(k) is None or book_ytd is None else book_ytd - vals[k])}</td></tr>' for k, n in YTD_ROWS))
    grows = (f"From the record’s second year the table adds 12 months, 3 years, 5 years and a yearly rate since {_fmt.date(begun)} "
             "by itself; nothing is annualised before then." if not any(r[0] == "1 year" for r in rows) else
             f"A yearly rate since {_fmt.date(begun)} compounds the whole record to a return per 12 months.")
    mlast = p.market.dropna().index.max() if len(p.market.dropna()) else None
    if mlast is not None and mlast < p.as_of:
        grows = (f"Nifty Total Market and Momentum 50 to {dshort(mlast)}: NSE’s closes for {dshort(p.as_of)} are not in yet, "
                 "so Today shows no Nifty Total Market figure and the longer windows end a session early on the index side. " + grows)
    return _sec([_head("pf-ret", "Returns", "the book after costs · indices are price returns"),
                 '<div class="dh-pair"><div><div class="dh-cap"><b>By period</b><span>to ' + f"{p.as_of:%-d %b}" + '</span></div>'
                 '<div class="dh-scroll"><table class="dh-tab dh-tab-s"><thead><tr><th scope="col">Period</th><th scope="col" class="dh-num">The book</th>'
                 '<th scope="col" class="dh-num">Nifty Total Market</th><th scope="col" class="dh-num">Lead, pts</th><th scope="col" class="dh-num">Momentum 50</th>'
                 f'</tr></thead><tbody>{per}</tbody></table></div><p class="dh-note">{e(grows)}</p></div>'
                 f'<div><div class="dh-cap"><b>{_fmt.since(begun) if young else "This year"} against other indices</b><span>{"to " + f"{p.as_of:%-d %b}" if young else f"since {ytd_start:%-d %b %Y}"}</span></div>'
                 '<div class="dh-scroll"><table class="dh-tab dh-tab-s"><thead><tr><th scope="col">Index</th>'
                 f'<th scope="col" class="dh-num">{_fmt.since(begun) if young else "This year"}</th>'
                 f'<th scope="col" class="dh-num">The book’s lead, pts</th></tr></thead><tbody>{ytd}</tbody></table></div>'
                 f'<p class="dh-note">The book is mostly {e(book_size_words(p))}, so Nifty Total Market is not its only fair yardstick. '
                 + ('The mix holds the four NSE size indices in the book’s own size split, reset at each rebalance (see Sector &amp; size). '
                    if vals.get("mix") is not None else
                    'A mix of NSE’s size indices cannot be built for it: Nano Cap and Ultra Nano Cap have no NSE index. ')
                 + f'{_fmt.PTS_NOTE}</p></div></div>'])


def book_size_words(p: Page) -> str:
    """The two size groups holding most of the book today ("Small Cap and Micro Cap" on the 750;
    "Nano Cap and Ultra Nano Cap" on the > ₹2,000 Cr list), from its own size split (S193 C)."""
    ex = p.exposure
    if ex is None or not len(ex):
        return "Small Cap and Micro Cap"
    size = ex[ex["kind"] == "size"]
    if size.empty:
        return "Small Cap and Micro Cap"
    last = size[size["date"] == size["date"].max()].groupby("name")["weight"].sum().sort_values(ascending=False)
    top = [_fmt.size(k) for k, v in last.items() if v > 0][:2]
    return " and ".join(top) if top else "Small Cap and Micro Cap"


def growth_spec(p: Page) -> dict:
    eq = pr._clean(p.equity)
    base = float(eq.iloc[0])
    m = pr._clean(p.market).reindex(eq.index).ffill()
    mo = pr._clean(p.mom).reindex(eq.index).ffill()

    def norm(s):
        s0 = s.dropna()
        b = float(s0.iloc[0]) if len(s0) else np.nan
        return [None if pd.isna(v) else round(float(v) / b * 100, 2) for v in s]
    dd = pr.drawdown_series(eq)
    ddm = pr.drawdown_series(m.dropna()).reindex(eq.index)
    return {"dates": [f"{d:%Y-%m-%d}" for d in eq.index], "book": [round(float(v) / base * 100, 2) for v in eq],
            "market": norm(m), "mom": norm(mo), "dd": [round(float(v), 2) for v in dd],
            "ddm": [None if pd.isna(v) else round(float(v), 2) for v in ddm]}


def _start(p: Page) -> pd.Timestamp:
    """The first day of the system's record (the 750: 1 Jan 2026)."""
    from src.engine.systems import inception
    return inception(p.system).start_time


def section_equity(p: Page) -> list:
    spec = growth_spec(p)
    f, fm = pr.falls(p.equity), pr.falls(pr._clean(p.market).loc[p.equity.index[0]:p.as_of])
    m = months_of(p)
    wme = pr.worst_month_end(list(m["book"].values()))
    wme_m = list(m["book"])[wme[1]] if wme and wme[1] >= 0 else None
    risks = pr.risk(p.equity, p.market)
    cap = pr.capture(p.equity, p.market)
    rk = risks[0] if risks else None
    mday = pr.daily_gaps(p.equity, p.market, first_fill(p)[1])
    mkt_on = float(mday["market"].get(f.worst_day_on, np.nan)) if f else np.nan
    falls = [("Below its peak today", pct(f.now), "dh-watch" if f.now < 0 else "", f"Peak {dshort(f.peak_now)}", "",
              ("" if not fm else f"Nifty Total Market is at a new high ({dshort(fm.peak_now)})" if fm.now > -0.05
               else f"Nifty Total Market {pct(fm.now)}, below its {dshort(fm.peak_now)} peak")),
             ("Max drawdown", pct(f.worst), "dh-down",
              f"{dshort(f.peak)} → {dshort(f.low)}" + (f", recovered {dshort(f.recovered)}" if f.recovered is not None else ", not yet recovered"), "",
              (f"Nifty Total Market {pct(fm.worst)} ({dshort(fm.peak)} → {dshort(fm.low)})"
               + ("" if fm.recovered is not None else ", not yet recovered")) if fm else ""),
             ("Worst day", pct(f.worst_day), "dh-down", dshort(f.worst_day_on), "", f"Nifty Total Market {pct(mkt_on)} that day"),
             ("Worst month-end", pct(wme[0]) if wme else "–", "dh-down" if wme and wme[0] < 0 else "",
              f"{wme_m:%B}" if wme_m is not None else "", "", "Counting month-end values only")] if f else []
    risk_cells = []
    if rk:
        risk_cells = [("Volatility, a year", f"{rk.vol:.1f}%", "", f"Nifty Total Market {rk.market_vol:.1f}%", "",
                       f"Swings about {rk.vol / rk.market_vol:.1f} times as much as the index"),
                      ("Beta", f"{rk.beta:.1f}", "", "How much it moves with Nifty Total Market", "",
                       f"On average, a 1% day for the index is a {rk.beta:.1f}% book day"),
                      ("Tracking error", f"{rk.tracking:.1f}%", "", "How far it strays from Nifty Total Market", "",
                       f"About {rk.tracking / np.sqrt(pr.YEAR):.1f} pt on a typical day"),
                      ("Up / down capture, 60 sessions", f"{cap[0]:.0f}% / {cap[1]:.0f}%" if cap else "–", "",
                       "Falls less on bad days" if cap and cap[1] < 100 else "Falls more on bad days", "dh-up" if cap and cap[1] < 100 else "dh-down",
                       "Rises less on good days" if cap and cap[0] < 100 else "Rises more on good days"),
                      ("How they move together, 90 sessions", "–" if p.correlation is None else f"{p.correlation:.2f}", "",
                       "Average correlation of the holdings", "", "Low: the list is well spread" if p.correlation is not None and p.correlation < 0.3 else "")]
    windows = " · ".join(f"{r.label}, {r.sessions} sessions" for r in risks[:1])
    # A year of the book: from its first fill (the 1000: 2 Nov 2026), not the money-put-in point before it.
    began = first_fill(p)[1]
    second = (began if began is not None else p.equity.index[0] + pd.Timedelta(days=1)) + pd.DateOffset(years=1)
    more = ("" if len(risks) > 1 else f" · from {second:%B %Y} also the last 12 months and each year")
    rtable = ""
    if len(risks) > 1:
        rtable = ('<div class="dh-scroll"><table class="dh-tab dh-tab-s"><thead><tr><th scope="col">Window</th><th scope="col" class="dh-num">Sessions</th>'
                  '<th scope="col" class="dh-num">Volatility</th><th scope="col" class="dh-num">Nifty Total Market</th><th scope="col" class="dh-num">Beta</th>'
                  '<th scope="col" class="dh-num">Tracking error</th></tr></thead><tbody>'
                  + "".join(f'<tr><th scope="row">{e(r.label)}</th><td class="dh-num">{r.sessions}</td><td class="dh-num">{r.vol:.1f}%</td>'
                            f'<td class="dh-num">{r.market_vol:.1f}%</td><td class="dh-num">{r.beta:.2f}</td><td class="dh-num">{r.tracking:.1f}%</td></tr>'
                            for r in risks) + "</tbody></table></div>")
    te = rk.tracking if rk else 0
    ex_hi, ex_lo = 10 + te, 10 - te
    return _sec([_head("pf-eq", "Equity, drawdown & risk", f"₹100 on {_start(p):%-d %b}, daily"),
                 (Chart("growth", spec, {"label": "Growth of ₹100: the book, Nifty500 Momentum 50 and Nifty Total Market"})
                  if len(spec["dates"]) > 1 else   # a system's first days (Nifty 1000, Nov 2026): one point draws no line
                  f'<p class="dh-note">The growth chart starts once the book has two sessions; it has {len(spec["dates"])}.</p>'),
                 how(f"Top: what ₹100 put in on {_start(p):%-d %b %Y} has grown to, the book after costs against NSE’s Nifty500 Momentum 50 "
                     "and Nifty Total Market. Bottom: drawdown, how far each sat below its own highest close so far, every day.",
                     "A drawdown is today’s value against the highest value before it: (value ÷ peak) − 1. The max drawdown is the "
                     "deepest point; the worst day is a different measure, the biggest drop from one close to the "
                     "next; the worst month-end counts month-end values only.",
                     ["Date", "The book", "Momentum 50", "Nifty Total Market", "Book below peak", "Nifty Total Market below peak"],
                     [[d, f"{b:.1f}", "–" if mo is None else f"{mo:.1f}", "–" if mk is None else f"{mk:.1f}", f"{dd:.1f}%",
                       "–" if dm is None else f"{dm:.1f}%"]
                      for d, b, mo, mk, dd, dm in list(zip(spec["dates"], spec["book"], spec["mom"], spec["market"], spec["dd"], spec["ddm"]))[::-5]]),
                 _kpis(falls, "pf-four"),
                 f'<div class="dh-cap"><b>Risk</b><span>{e(windows + more)}</span></div>', _kpis(risk_cells, "pf-five"), rtable,
                 how("Volatility: how much the book’s daily returns swing, scaled to a year. Beta: how much the book moves, on average, for a 1% "
                     "move in Nifty Total Market. Tracking error: how much the book’s return differs from Nifty Total Market’s, scaled to a year "
                     "(the spread of the daily gaps). Capture: on Nifty Total Market’s up days and down days, the book’s average move as a share "
                     "of the index’s.",
                     ((f"Worked out from {rk.sessions} sessions, so a rough guide until the book has a year. "
                       if rk and rk.sessions < 250 else "")   # S193 B: the list's 22.9% rested on 34 sessions
                      + f"Tracking error {te:.1f}% means: over 12 months in which Nifty Total Market makes +10%, a book like this one would usually end between about "
                     f"{_fmt.signed(ex_lo, 0)}% and {_fmt.signed(ex_hi, 0)}% (10 ± {te:.1f}, two years in three), and outside that range one year in three. On a "
                     f"typical day the book and Nifty Total Market differ by about {te / np.sqrt(pr.YEAR):.1f} point (tracking error ÷ √250). An "
                     "index fund aims for well under 1%; a 20-stock small-company momentum book cannot be close to Nifty Total Market, and that "
                     "distance is where its lead comes from.")
                     if rk else "No risk figures yet: they need more sessions of the book than it has.",   # S193 B7: read 0.0%
                     ["Measure", "The book", "Nifty Total Market"],
                     [["Volatility, a year", f"{rk.vol:.1f}%", f"{rk.market_vol:.1f}%"], ["Beta", f"{rk.beta:.2f}", "1.00"],
                      ["Tracking error", f"{rk.tracking:.1f}%", "–"], ["Sessions", str(rk.sessions), str(rk.sessions)]] if rk else [])])


def calendar_html(p: Page, show: str = "All") -> tuple[str, str, str]:
    m = months_of(p)
    cal = pr.calendar(m)
    names = {"book": "The book", "market": "Nifty Total Market", "lead": "Lead, pts", "mom": "Momentum 50", "n500": "Nifty 500, as recorded"}
    pick = {"All": list(names), "The book": ["book"], "Nifty Total Market": ["market"], "Lead": ["lead"], "Momentum 50": ["mom"]}.get(show, list(names))

    first, fill = first_fill(p)
    mark_month = first.month - 1 if fill is not None and first in m["book"] else None

    def cell(v, b=False, q=False, mark=False):
        cls = "dh-num" + (" pf-q" if q else "") + (f" dh-b {tone(v)}" if b else "")
        sup = '<sup class="dh-muted">*</sup>' if mark and v is not None else ""
        return f'<td class="{cls}">{"–" if v is None else sg(v)}{sup}</td>'
    head = ('<thead><tr><th scope="col">%</th>' + "".join(f'<th scope="col" class="dh-num">{x}</th>' for x in MON)
            + "".join(f'<th scope="col" class="dh-num{" pf-q" if i == 0 else ""}">{q}</th>' for i, (q, _) in enumerate(pr.QUARTERS))
            + '<th scope="col" class="dh-num pf-q">Year</th></tr></thead>')
    body = ""
    this = pd.Period(p.as_of, "M")
    for y, row in cal.items():
        note = f" · {this:%b} so far" if y == this.year else ""
        body += f'<tr class="pf-yr"><th scope="rowgroup" colspan="18">{y}<span class="dh-muted">{e(note)}</span></th></tr>'
        for k in pick:
            r = row.get(k)
            if r is None:
                continue
            b = k in ("book", "lead")
            qs = r["quarters"] if k != "n500" else [None] * 4
            yr = r["year"]
            if k == "lead":
                bk, mk = row["book"], row["market"]
                qs = [None if a is None or c is None else a - c for a, c in zip(bk["quarters"], mk["quarters"])]
                yr = None if bk["year"] is None or mk["year"] is None else bk["year"] - mk["year"]
            body += (f'<tr class="{"dh-muted" if k == "n500" else ""}"><th scope="row">{names[k]}</th>'
                     + "".join(cell(v, b, mark=(y == first.year and i == mark_month)) for i, v in enumerate(r["months"])) + "".join(cell(v, b, i == 0) for i, v in enumerate(qs)) + cell(yr, b, True) + "</tr>")
    body += (f'<tr class="pf-yr pf-ghost"><th scope="rowgroup" colspan="18">{this.year + 1}<span class="dh-muted"> · from January, a row group '
             'like the one above; each year adds its own</span></th></tr>') if len(cal) == 1 else ""
    foot = (f'<p class="dh-note">* {first:%b %Y}, the first month: from the fill, {fill:%-d %b}. A system\u2019s first month has '
            'no book before it, so the book and every index start at its first fill.</p>' if mark_month is not None else "")
    grid = f'<div class="dh-scroll"><table class="dh-tab pf-grid pf-nw">{head}<tbody>{body}</tbody></table></div>{foot}'
    # Calendar and financial years
    ys = ""
    for y, row in cal.items():
        sl = p.equity[(p.equity.index.year == y) | (p.equity.index == pd.Timestamp(year=y - 1, month=12, day=31))]
        fy = pr.falls(sl)
        ml = pr._clean(p.market)
        fm = pr.falls(ml[(ml.index.year == y) | (ml.index == ml.loc[:pd.Timestamp(year=y - 1, month=12, day=31)].index.max())])
        bk, mk = row["book"], row["market"]
        ahead = sum(1 for a, c in zip(bk["months"], mk["months"]) if a is not None and c is not None and a > c)
        nmon = sum(1 for a in bk["months"] if a is not None)
        lead = None if bk["year"] is None or mk["year"] is None else bk["year"] - mk["year"]
        ys += (f'<tr><th scope="row">{y}{", so far" if y == this.year else ""}</th><td class="dh-num dh-b {tone(bk["year"])}">{pct(bk["year"])}</td>'
               f'<td class="dh-num">{pct(mk["year"])}</td><td class="dh-num dh-b {tone(lead)}">{sg(lead)}</td><td class="dh-num">{pct(row["mom"]["year"])}</td>'
               f'<td class="dh-num">{ahead} of {nmon}</td><td class="dh-num dh-down">{pct(fy.worst) if fy else "–"}'
               f'<span class="dh-sub">Nifty Total Market {pct(fm.worst) if fm else "–"}</span></td></tr>')
    years = ('<div class="dh-scroll"><table class="dh-tab dh-tab-s pf-nw"><thead><tr><th scope="col">Year</th><th scope="col" class="dh-num">Book</th>'
             '<th scope="col" class="dh-num">Nifty Total Market</th><th scope="col" class="dh-num">Lead, pts</th><th scope="col" class="dh-num">Momentum 50</th>'
             f'<th scope="col" class="dh-num">Months ahead</th><th scope="col" class="dh-num">Max drawdown</th></tr></thead><tbody>{ys}</tbody></table></div>')
    fys = ""
    first = min(m["book"]) if m["book"] else this
    for lab, vals, ps in pr.financial_years({k: m[k] for k in ("book", "market", "mom")}):
        part = " so far" if this <= pd.Period(f"{lab[3:7]}-04", "M") + 11 and this >= pd.Period(f"{lab[3:7]}-04", "M") else ""
        partial = f"{MON[ps[0].month - 1]}–{MON[ps[-1].month - 1]} only, from the start" if ps and ps[0] == first and ps[0].month != 4 else ""
        lead = None if vals["book"] is None or vals["market"] is None else vals["book"] - vals["market"]
        fys += (f'<tr><th scope="row">{e(lab)}{"," + part if part else ""}<span class="dh-sub">{e(partial)}</span></th>'
                f'<td class="dh-num dh-b {tone(vals["book"])}">{pct(vals["book"])}</td><td class="dh-num">{pct(vals["market"])}</td>'
                f'<td class="dh-num dh-b {tone(lead)}">{sg(lead)}</td><td class="dh-num">{pct(vals["mom"])}</td></tr>')
    fyt = ('<div class="dh-scroll"><table class="dh-tab dh-tab-s pf-nw"><thead><tr><th scope="col">Year</th><th scope="col" class="dh-num">Book</th>'
           '<th scope="col" class="dh-num">Nifty Total Market</th><th scope="col" class="dh-num">Lead, pts</th><th scope="col" class="dh-num">Momentum 50</th>'
           f'</tr></thead><tbody>{fys}</tbody></table></div>')
    return grid, years, fyt


def month_bars_spec(p: Page) -> dict:
    m = months_of(p)
    ps = sorted(m["book"])[-12:]
    this = pd.Period(p.as_of, "M")
    return {"values": [round(m["lead"][k], 1) if m["lead"][k] is not None else 0.0 for k in ps],
            "labels": [f"{k:%b}" for k in ps], "full": [f"{k:%B %Y}" + (", so far" if k == this else "") for k in ps],
            "unit": "pts against Nifty Total Market", "xn": 12, "valueLabels": True, "vdp": 1, "height": 170}


def day_section(p: Page) -> list:
    g = pr.daily_gaps(p.equity, p.market, first_fill(p)[1])
    if len(g) < 6:
        # A system's first week (Nifty 1000 from Nov 2026, S175): five sessions back is not there yet.
        return _sec([_head("pf-day", "Day by day against Nifty Total Market", "Day P&L in context"),
                     f'<p class="dh-note">Day by day starts once the book has six sessions; it has {len(g)}.</p>'])
    last = g.tail(20)
    five = (pr.ret(p.equity, g.index[-6], g.index[-1]), pr.ret(pr._clean(p.market).reindex(p.equity.index).ffill(), g.index[-6], g.index[-1]))
    t = g.iloc[-1]
    beat20, beat = int((last["gap"] > 0).sum()), int((g["gap"] > 0).sum())
    cells = [("Today", sg(t["gap"], 1, " pts"), tone(t["gap"]), f"Book {pct(t['book'])}, Nifty Total Market {pct(t['market'])}", "", ""),
             ("Last 5 sessions", sg(five[0] - five[1], 1, " pts") if None not in five else "–", tone(None if None in five else five[0] - five[1]),
              f"Book {pct(five[0])}, Nifty Total Market {pct(five[1])}", "", ""),
             ("Last 20 sessions", f"{beat20} of {len(last)}", "dh-up" if beat20 > len(last) / 2 else "dh-watch", "Sessions the book beat Nifty Total Market", "", ""),
             (f"Since {dshort(g.index[0])}", f"{beat} of {len(g)}", "dh-up" if beat > len(g) / 2 else "dh-watch",
              f"Sessions the book beat Nifty Total Market, {_fmt.fixed(beat / len(g) * 100, 0)}%", "", "")]
    spec = {"values": [round(float(v), 2) for v in last["gap"]], "labels": [dshort(d) for d in last.index],
            "full": [f"{d:%-d %b %Y}" for d in last.index], "unit": "pts against Nifty Total Market", "dp": 1, "xn": 5,
            "lastLabel": "Today", "height": 170}
    return _sec([_head("pf-day", "Day by day against Nifty Total Market", "Day P&L in context"), _kpis(cells, "pf-four"),
                 '<div class="dh-cap"><b>The book against Nifty Total Market, last 20 sessions</b><span>points</span></div>',
                 Chart("bars", spec, {"label": "The book's daily lead over Nifty Total Market, last 20 sessions"}),
                 how("Each session, the book’s day less Nifty Total Market’s day, in points.",
                     f"One day is mostly noise; a run of bars on one side is not. The book beat Nifty Total Market on {beat} of {len(g)} sessions.",
                     ["Session", "Book", "Nifty Total Market", "Lead, pts"],
                     [[f"{d:%-d %b %Y}", pct(r.book), pct(r.market), sg(r.gap)] for d, r in last.iloc[::-1].iterrows()])])


def trade_stats(p: Page) -> dict:
    t = p.history.get("trades")
    if not isinstance(t, pd.DataFrame) or t.empty:
        return {}
    closed = t[(t["Status"] == "Closed") & t["Return %"].notna()].copy()
    closed["r"] = closed["Return %"].astype(float) * 100
    win, loss = closed[closed.r > 0], closed[closed.r <= 0]
    hold = pd.to_numeric(closed["Holding (Days)"], errors="coerce")
    exits = []
    hc = int(round((1 - float(p.cfg.get("high_pct", 0.8))) * 100))
    cut = int(p.cfg.get("buffer_n", 40))
    for key, name, sub in EXIT_NAMES:
        g = closed[closed["Reason for Exit"].astype(str).str.contains(key, case=False)]
        if len(g):
            exits.append((name, sub.format(cut=cut, hc=hc), len(g), float(g.r.mean()), float(g.r.median())))
    tb = p.history.get("tradebook")
    bought = []
    if isinstance(tb, pd.DataFrame) and len(tb):
        for per, g in tb.groupby("Period", sort=False):
            start = pd.to_datetime(str(per).split("→")[0].strip(), errors="coerce")
            bought.append((start, int(g["Action"].str.contains("BUY").sum()), int(g["Action"].str.contains("SELL").sum()),
                           int(g["Action"].str.contains("HOLD").sum())))
    bought.sort()
    return {"closed": len(closed), "open": int((t["Status"] == "Open").sum()), "wins": len(win),
            "avg_win": float(win.r.mean()) if len(win) else None, "med_win": float(win.r.median()) if len(win) else None,
            "avg_loss": float(loss.r.mean()) if len(loss) else None, "med_loss": float(loss.r.median()) if len(loss) else None,
            "hold": float(hold.median()), "hold_win": float(pd.to_numeric(win["Holding (Days)"]).median()) if len(win) else None,
            "hold_loss": float(pd.to_numeric(loss["Holding (Days)"]).median()) if len(loss) else None,
            "exits": exits, "best": closed.nlargest(3, "r"), "worst": closed.nsmallest(3, "r"), "rebal": bought}


def _days(v) -> str:
    """A median holding period, or a dash when there is none to take."""
    return "–" if v is None or pd.isna(v) else f"{v:.0f}"


def section_trades_top(p: Page, s: dict) -> list:
    if not s:
        return _sec([_head("pf-trades", "Trades", "no trades yet")])
    if not s.get("closed"):
        # A system's first month (Nifty 1000 from Nov 2026, S175): trades are open, none closed.
        # Left open like the full section below: render() closes it.
        return ['<section class="dh-sec pf-sec">',
                _head("pf-trades", "Trades", f"0 closed · {s.get('open', 0)} open · {len(s.get('rebal') or [])} rebalances"),
                '<p class="dh-note">No trade has closed yet; these figures start with the first exit.</p>']
    reb = s["rebal"]
    after = [b for _, b, _, _ in reb[1:]]
    avg = sum(after) / len(after) if after else None
    lo = min(reb[1:], key=lambda r: r[1]) if len(reb) > 1 else None
    cells = [("Trades won", f"{s['wins'] / s['closed'] * 100:.0f}%", "dh-watch" if s["wins"] / s["closed"] < 0.5 else "dh-up",
              f"{s['wins']} of {s['closed']} closed", "", ""),
             ("Average win", pct(s["avg_win"]), "dh-up", f"Median {pct(s['med_win'])}", "", "A few large winners carry it"
              if s["avg_win"] and s["med_win"] and s["avg_win"] > 2 * s["med_win"] else ""),
             ("Average loss", pct(s["avg_loss"]), "dh-down", f"Median {pct(s['med_loss'])}", "", ""),
             # A side with no closed trade has no median (Combined, 21 Nov 2026: no closed loser yet).
             ("Held, median", _days(s["hold"]) + " days", "", f"Winners {_days(s['hold_win'])} · losers {_days(s['hold_loss'])}", "", ""),
             ("Changed at a rebalance", f"{avg:.0f} of 20" if avg else "–", "", f"On average, from {reb[1][0]:%B}" if len(reb) > 1 else "", "",
              f"{reb[-1][0]:%B} {reb[-1][1]}, {lo[0]:%B} {lo[1]}" if lo else "")]
    ex = "".join(f'<tr><th scope="row">{e(n)}<span class="dh-sub">{e(sub)}</span></th><td class="dh-num">{k}</td>'
                 f'<td class="dh-num {tone(a)}">{pct(a)}</td><td class="dh-num {tone(md)}">{pct(md)}</td></tr>' for n, sub, k, a, md in s["exits"])

    def held(r):
        a = pd.to_datetime(r["Entry Date"], errors="coerce")
        b = pd.to_datetime(str(r["Exit Date"])[:11], errors="coerce")
        return f"{dshort(a)} → {dshort(b)}" if pd.notna(a) and pd.notna(b) else ""
    bw = "".join(f'<tr><th scope="row">{e(str(r.Symbol))}</th><td>{held(r)}</td><td class="dh-num {tone(r.r)}">{pct(r.r)}</td></tr>'
                 for df in (s["best"], s["worst"]) for _, r in df.iterrows())
    return ['<section class="dh-sec pf-sec">', _head("pf-trades", "Trades", f"{s['closed']} closed · {s['open']} open · {len(reb)} rebalances"),
            _kpis(cells, "pf-five"),
            '<div class="dh-pair"><div><div class="dh-cap"><b>Which rule closed each trade</b><span>' + f"{s['closed']} closed" + '</span></div>'
            '<div class="dh-scroll"><table class="dh-tab dh-tab-s"><thead><tr><th scope="col">Sell rule</th><th scope="col" class="dh-num">Trades</th>'
            f'<th scope="col" class="dh-num">Average</th><th scope="col" class="dh-num">Median</th></tr></thead><tbody>{ex}</tbody></table></div></div>'
            '<div><div class="dh-cap"><b>Best trades and worst trades</b><span>closed</span></div><div class="dh-scroll"><table class="dh-tab dh-tab-s">'
            '<thead><tr><th scope="col">Stock</th><th scope="col">Held</th><th scope="col" class="dh-num">Return</th></tr></thead>'
            f'<tbody>{bw}</tbody></table></div></div></div>']


HISTORY_NOTE = ("A trade is one stock from the day it was bought to the day it was sold. A rebalance line is one stock’s action in one "
                "month (bought, sold or kept), so a stock held five months has five lines and one trade. Signal is the close the rule read; "
                "the fill is the next session. Prices are NSE’s closes, so each trade can be checked against NSE’s own files.")


def history_spec(trades: pd.DataFrame, tb: pd.DataFrame | None, rebal: list) -> dict:
    def iso(v):
        return None if v is None or pd.isna(v) else f"{pd.Timestamp(v):%Y-%m-%d}"

    def num(v):
        return None if v is None or pd.isna(v) else float(v)
    # Prices and returns unrounded: the page rounds once, half up (S193 A13).
    rows = [[r["Symbol"], r["Industry"], iso(r["Entry signal date"]), iso(r["Entry date"]), float(r["Entry price"]),
             None if pd.isna(r["Entry rank"]) else int(r["Entry rank"]), num(r["Entry weight %"]), iso(r["Exit signal date"]),
             iso(r["Exit date"]), num(r["Exit price"]),
             None if pd.isna(r["Exit rank"]) else int(r["Exit rank"]), float(r["Return %"]), int(r["Days held"]),
             str(r["Exit rule"]).replace(" (< 50 EMA)", ""), r["Status"]] for _, r in trades.iterrows()]
    lines = []
    if isinstance(tb, pd.DataFrame) and len(tb):
        for _, r in tb.iloc[::-1].iterrows():
            a = str(r["Action"])
            start = pd.to_datetime(str(r["Period"]).split("→")[0].strip(), errors="coerce")
            lines.append([f"{start:%b %Y}" if pd.notna(start) else "", "BUY" if "BUY" in a else "SELL" if "SELL" in a else "HOLD",
                          str(r["Symbol"]), num(r.get("Price")), num(r.get("Weight %")), str(r.get("Reason / Signal", ""))])
    return {"trades": rows, "lines": lines, "rebal": [[f"{d:%b}", b, sl, k, f"{d:%-d %b %Y}"] for d, b, sl, k in rebal],
            "views": [["trades", "Trades", "Trades, entry to exit: all, winners, losers or open"],
                      ["lines", "Rebalance lines", "Rebalance lines, month by month: all, buy, sell or hold"]],
            "filters": {"trades": [["all", "All"], ["win", "Winners"], ["loss", "Losers"], ["open", "Open"]],
                        "lines": [["all", "All"], ["BUY", "Buy"], ["SELL", "Sell"], ["HOLD", "Hold"]]}}


def _and(names: list[str]) -> str:
    names = [f"the {n}" for n in names]
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + f" and {names[-1]}" if names else "all of them"


def section_systems(p: Page) -> list:
    if not p.systems:
        return []
    _, common, k = p.systems[0]
    total = len(p.systems) - 2                   # less the "common" entry and the market row
    word = _NUMBER_WORDS.get(k, str(k))
    rows = "".join(
        f'<tr class="{"dh-muted" if not started else ""}"><th scope="row">{e(n)}{f"<span class=dh-sub>{e(sub)}</span>" if sub else ""}</th>'
        f'<td class="dh-num {tone(m)}">{pct(m)}</td><td class="dh-num {tone(c)}">{pct(c)}</td><td class="dh-num {tone(o)}">{pct(o)}</td><td>{e(started)}</td></tr>'
        for n, sub, m, c, o, started in p.systems[1:])
    from src.engine.track_record import SHADOWS
    shadows = ", ".join(f"{b.name.replace(' (shadow)', '')} (from {b.inception.strftime('%b %Y')})" for b in SHADOWS.values())
    return _sec([_head("pf-sys", f"{_NUMBER_WORDS.get(total, str(total)).capitalize()} systems, side by side",
                       "compared over the same window"),
                 f'<div class="dh-scroll"><table class="dh-tab dh-tab-s pf-sys"><thead><tr><th scope="col">System</th><th scope="col" class="dh-num">Month so far · {p.as_of:%b}</th>'
                 f'<th scope="col" class="dh-num">Since {e(common)}, all {word}</th><th scope="col" class="dh-num">Since it started</th><th scope="col">Started</th>'
                 f'</tr></thead><tbody>{rows}</tbody></table></div>',
                 f'<p class="dh-note">“Since {e(common)}” is the window {e(_and([r[0] for r in p.systems[1:-1] if r[3] is not None]))} have all traded, '
                 'so it is the fair comparison; it grows as the systems age. '
                 'A new system joins it after its first full month. '
                 f'<b>Shadow systems</b>, recorded but not traded: {e(shadows)}.</p>'])


PF_CSS = """
.pf-head{padding:18px 0 14px;display:flex;flex-direction:column;gap:12px;border-bottom:1px solid var(--c-rule)}
.dh .pf-title{margin:0!important;padding:0!important;font-family:var(--font-serif)!important;font-weight:400!important;font-size:var(--fs-44)!important;line-height:1.1!important;max-width:36ch}
.pf-kick{margin:0;font-size:var(--fs-12);font-weight:600;letter-spacing:.06em;text-transform:uppercase;color:var(--c-muted)}
.pf-sub{margin:0;font-size:var(--fs-17);color:var(--c-text_2);max-width:80ch}
.pf-nav{border-top:1px solid var(--c-rule_soft);padding-top:10px}
.pf-sec{padding-top:26px;gap:16px}
.pf-shead{display:flex;flex-wrap:wrap;align-items:baseline;gap:4px 14px;scroll-margin-top:64px}
.dh .pf-h2{margin:0!important;padding:0!important;font-family:var(--font-serif)!important;font-size:var(--fs-30)!important;font-weight:400!important;letter-spacing:0!important;line-height:1.15!important}
.pf-sc{font-size:var(--fs-13);color:var(--c-muted)}
.pf-five{grid-template-columns:repeat(auto-fit,minmax(min(100%,180px),1fr))}
.pf-four{grid-template-columns:repeat(auto-fit,minmax(min(100%,200px),1fr))}
.pf-ihead,.pf-irow{display:grid;grid-template-columns:minmax(150px,230px) minmax(0,340px) 64px 64px 84px 76px;justify-content:start;gap:6px 16px;align-items:center}
.pf-ihead{font-size:var(--fs-12);color:var(--c-muted);border-bottom:1px solid var(--c-ink);padding:4px 0}
.pf-ihead .dh-num{font-family:var(--font-ui)}
.pf-irow{padding:5px 0;border-bottom:1px solid var(--c-rule_soft);font-size:var(--fs-13)}
.pf-nm{font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.pf-nm small{font-weight:400;font-size:var(--fs-12);color:var(--c-muted);margin-left:6px}
.pf-ibar{position:relative;height:14px;background:var(--c-rule_soft);border-radius:2px;display:block}
.pf-ibar i{position:absolute;left:0;top:0;bottom:0;background:var(--c-ink);border-radius:2px}
.pf-ibar b{position:absolute;top:-4px;bottom:-4px;width:0;border-left:2px dashed var(--c-caution)}
.pf-srow{display:grid;grid-template-columns:34px 1fr;gap:10px;align-items:center;margin-bottom:5px;font-size:var(--fs-13)}
.pf-thin{height:20px}.pf-thin i{font-size:11px;padding-left:5px}.dh-sz-large,.dh-sz-mid{color:var(--c-white)}
.pf-gap{margin-top:14px}
.pf-key{display:flex;flex-wrap:wrap;gap:6px 16px;font-size:var(--fs-12);color:var(--c-muted);margin-top:6px}
.pf-key span{display:flex;align-items:center;gap:6px}.pf-key i{width:12px;height:12px;border-radius:3px;display:inline-block}
.dh-tab.pf-heat{min-width:560px}.pf-heat th,.pf-heat td{padding:3px 6px!important;line-height:1.3}.pf-heat thead th.dh-num{text-align:center!important}.pf-hc{text-align:center!important;font-size:var(--fs-12);border:1px solid var(--c-white)}
.pf-hl th,.pf-hl td{background:var(--c-fill_soft)}
.dh-tab.pf-grid{min-width:1060px}.pf-grid th,.pf-grid td{padding:7px 10px 7px 0}.pf-q{border-left:1px solid var(--c-rule)}
.pf-yr th{font-weight:700;padding-top:12px!important;border-bottom:1px solid var(--c-rule)!important}.pf-ghost th{font-weight:400}
.pf-tall{max-height:380px;overflow:auto;border:1px solid var(--c-rule_soft);border-radius:4px}
.dh-tab.pf-log{min-width:860px;font-size:var(--fs-12)}.pf-log th,.pf-log td{padding:5px 10px;white-space:nowrap;width:1%}
.pf-log td:last-child,.pf-log th:last-child{width:auto;white-space:normal}
.pf-log thead th{position:sticky;top:0;background:var(--c-white);z-index:1}
.dh-tab.pf-sys{width:auto}.pf-sys th,.pf-sys td{padding-right:24px}
.pf-sec .dh-tab tbody th,.pf-nw tbody th{white-space:nowrap}.pf-sec .dh-tab thead th.dh-num{white-space:normal;vertical-align:bottom}
@media (max-width:640px){.pf-four{grid-template-columns:1fr 1fr}.pf-head .pf-five .dh-kpi:last-child{grid-column:auto}.pf-head .pf-five .dh-kpi:first-child{grid-column:1/-1}.pf-sec .pf-five .dh-kpi:last-child:nth-child(odd){grid-column:1/-1}.dh .pf-h2{font-size:var(--fs-24)!important}.dh .pf-title{font-size:var(--fs-36)!important}
.pf-ihead,.pf-irow{grid-template-columns:minmax(0,1fr) 84px 48px 50px;gap:4px 10px}.pf-nm small{display:block;margin:0}
.pf-ihead>span:nth-child(4),.pf-ihead>span:nth-child(6),.pf-irow>span:nth-child(4),.pf-irow>span:nth-child(6){display:none}}
"""


def page_parts(p: Page) -> list:
    """Everything but the widgets, in order (for tests and the requirements check)."""
    s = trade_stats(p)
    grid, years, fys = calendar_html(p)
    parts = header(p) + section_book(p) + section_exposure(p) + section_returns(p) + section_equity(p)
    parts += ['<section class="dh-sec pf-sec">', _head("pf-cal", "Calendar returns", "every month, quarter and year; each new year adds a row"),
              '<div class="dh-cap"><b>Month by month</b><span>the book’s lead over Nifty Total Market, points</span></div>',
              Chart("bars", month_bars_spec(p), {"label": "The book's lead over Nifty Total Market by month"}),
              '<div class="dh-cap"><b>Months and quarters</b></div>', grid,
              f'<div class="dh-pair"><div><div class="dh-cap"><b>Calendar years</b><span>January to December</span></div>{years}</div>'
              f'<div><div class="dh-cap"><b>Financial years</b><span>April to March</span></div>{fys}</div></div>',
              f'<p class="dh-note">{_frozen_note(p)}Momentum 50 is NSE’s Nifty500 Momentum 50, a '
              'momentum index to judge the strategy by.</p></section>', END]
    parts += day_section(p) + section_trades_top(p, s) + ["</section>"]
    parts += section_systems(p) + [f'<p class="dh-foot">{_fmt.data_to(p.as_of)}.</p>']
    return parts


def render(prices: pd.DataFrame, rank_df: pd.DataFrame) -> None:
    from src.engine.extra_universe import SYSTEM_750
    from src.engine.systems import inception, ledger_path
    from src.engine.track_record import load_ledger
    from src.loaders.price_loader import fetch_benchmark_history
    from src.ui import page_kit as kit
    from src.ui import system_param
    from src.ui.book_series import book_series
    from src.ui.canonical_book import current_book
    from src.ui.views.portfolio_view import PORTFOLIO_STARTING_CAPITAL

    system = system_param.current() or SYSTEM_750
    prices = prices if prices is not None else pd.DataFrame()
    benchmark_close = fetch_benchmark_history(period="5y")
    try:
        book, record = current_book(prices, benchmark_close, system)
    except (ValueError, KeyError) as exc:
        st.error(f"Canonical Track Record book is invalid: {exc}")
        return
    if book.empty:
        kit.empty("No current model book", "for this system yet.")
        return
    from src.ui.canonical_book import unpriced_note
    if (note := unpriced_note(record)) is not None:
        kit.note(*note)
    try:
        ledger = load_ledger(ledger_path(system), inception(system))
    except (ValueError, OSError) as exc:
        st.error(f"Portfolio Track Record could not be read: {exc}")
        return
    series = book_series(book, record, ledger, rank_df, prices, benchmark_close, PORTFOLIO_STARTING_CAPITAL)
    if series is None:
        kit.empty("The model book could not be sized.")
        return
    with st.spinner("Reading the record…"):
        p = gather(series, record, ledger, rank_df, system, benchmark_close)
    st.html(f"<style>{HOME_CSS}{PF_CSS}</style>")
    s = trade_stats(p)
    emit(header(p) + section_book(p) + section_exposure(p) + section_returns(p) + section_equity(p))

    # Calendar returns: the series switch is a widget, so the section is drawn in pieces.
    emit(['<section class="dh-sec pf-sec">', _head("pf-cal", "Calendar returns", "every month, quarter and year; each new year adds a row"),
          '<div class="dh-cap"><b>Month by month</b><span>the book’s lead over Nifty Total Market, points</span></div>',
          Chart("bars", month_bars_spec(p), {"label": "The book's lead over Nifty Total Market by month"})])
    show = st.pills("Show", ["All", "The book", "Nifty Total Market", "Lead", "Momentum 50"], default="All", key="pf_cal_show",
                    label_visibility="collapsed") or "All"
    grid, years, fys = calendar_html(p, show)
    emit(['<div class="dh-cap"><b>Months and quarters</b></div>', grid,
          f'<div class="dh-pair"><div><div class="dh-cap"><b>Calendar years</b><span>January to December</span></div>{years}</div>'
          f'<div><div class="dh-cap"><b>Financial years</b><span>April to March</span></div>{fys}</div></div>',
          f'<p class="dh-note">{_frozen_note(p)}Momentum 50 is NSE’s Nifty500 Momentum 50, a '
          'momentum index to judge the strategy by.</p></section>', END])
    emit(day_section(p) + section_trades_top(p, s) + ["</section>"])

    # The history, hidden until opened (owner, 20 Nov: "Can't it be one and hidden?").
    tb = p.history.get("tradebook")
    trades = pr.trades_table(p.history.get("trades"), tb, p.prices.index,
                             p.rank_df.drop_duplicates("Symbol").set_index("Symbol")["Industry"].to_dict()
                             if "Industry" in p.rank_df else None)
    n_lines = 0 if not isinstance(tb, pd.DataFrame) else len(tb)
    with st.expander("Trade history: every trade and every rebalance line, with CSV to check them", expanded=False):
        emit([Chart("history", history_spec(trades, tb, s.get("rebal") or []), {"label": "Every trade and every rebalance line", "note": HISTORY_NOTE})])
        a, b = st.columns(2)
        with a:
            st.download_button(f"Export CSV · {len(trades)} trades, {len(pr.TRADE_FIELDS)} fields", trades.to_csv(index=False).encode(),
                               f"model_book_trades_{p.as_of:%Y%m%d}.csv", "text/csv", key="pf_dl_trades")
        with b:
            st.download_button(f"Export CSV · {n_lines} lines", tb.to_csv(index=False).encode() if n_lines else b"",
                               f"model_book_rebalances_{p.as_of:%Y%m%d}.csv", "text/csv", key="pf_dl_lines")
    emit([END] + section_systems(p) + [f'<p class="dh-foot">{_fmt.data_to(p.as_of)}.</p>'])


__all__ = ["render", "gather", "page_parts", "html_of", "Page"]
