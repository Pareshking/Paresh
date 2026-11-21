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

from src.engine import book_exposure as bx
from src.engine import dashboard_insights as di
from src.engine import portfolio_report as pr
from src.loaders import benchmark_indices as bi
from src.ui.views.dashboard_home_view import (END, HOME_CSS, SHORT, Chart, emit, how, html_of, sg)

e = html.escape
ROOT = Path(__file__).resolve().parents[3]
SIZE_INDEX = {"Large": "nifty50", "Mid": "midcap150", "Small": "smallcap250", "Micro": "microcap250"}
YTD_ROWS = (("microcap250", "Microcap 250"), ("mix", "Mix in the book’s size split"), ("smallcap250", "Smallcap 250"),
            ("nifty500_mom50", "Nifty500 Momentum 50"), ("midcap150", "Midcap 150"),
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


def gather(series, record: dict, ledger: dict, rank_df: pd.DataFrame, system: str, benchmark_close) -> Page:
    from src.engine import market_questions as mq
    from src.engine.model_record import record_sector_map
    from src.engine.track_record import TRACK_RECORD_CONFIG
    from src.ui.views.qualified_view import correlation

    meta = (record or {}).get("live_meta") or {}
    as_of = series.as_of or pd.Timestamp(series.equity.index[-1])
    frame = bi.read()
    idx = {k: bi.series(k, frame=frame).loc[:as_of] for k in bi.SERIES}
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
    exposure = bx.load()
    if isinstance(tb, pd.DataFrame) and len(tb):
        live = bx.exposure(tb, record_sector_map(sorted(set(tb["Symbol"].astype(str)))), membership)
        exposure = bx.merge(exposure, live)
    mw = _market_weights(rank_df)
    corr = correlation(series.prices, syms)[1]
    systems = _systems(series.prices, benchmark_close, system, market, as_of)
    return Page(as_of=as_of, capital=float(series.history["equity"].iloc[0]) if len(series.history["equity"]) else 0.0,
                value=series.value, holdings=series.holdings, equity=series.equity, market=market, mom=mom,
                table=table, history=series.history, meta=meta, record=record, ledger=ledger, rank_df=rank_df,
                prices=series.prices, cfg=dict(TRACK_RECORD_CONFIG), trails=trails, industry_state=state,
                sizes=sizes, exposure=exposure, market_weights=mw, indices=idx, systems=systems,
                correlation=corr)


def _n500() -> pd.Series:
    try:
        b = pd.read_csv(ROOT / "data" / "benchmarks.csv", parse_dates=["date"]).set_index("date").sort_index()
        return pd.to_numeric(b["nifty500"], errors="coerce").dropna()
    except (OSError, KeyError, ValueError):
        return pd.Series(dtype=float)


def _market_weights(rank_df: pd.DataFrame) -> dict[str, float]:
    """Each industry's share of the 750 by market value (NSE's market caps)."""
    try:
        mc = pd.read_csv(ROOT / "data" / "nse_market_caps.csv").set_index("Symbol")["MarketCap"]
    except (OSError, KeyError, ValueError):
        return {}
    r = rank_df.drop_duplicates("Symbol").set_index("Symbol")
    w = pd.to_numeric(mc.reindex(r.index), errors="coerce").groupby(r["Industry"]).sum()
    return (w / w.sum() * 100).to_dict() if w.sum() > 0 else {}


def _systems(prices, benchmark_close, system, market, as_of) -> list[tuple]:
    """(name, this month %, since the common start %, since its own start %, started) for each live system."""
    from src.engine.extra_universe import SYSTEMS
    from src.engine.systems import inception, ledger_path
    from src.engine.track_record import load_ledger
    from src.ui.views.track_record_view import _comparison_price_frame, _record_mtd
    names = {"750": ("Nifty 750", "this book"), "nano": ("Nano Cap", ""), "combined": ("Combined", "")}
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
            got[sid] = (inception(sid), months)
    if not got:
        return []
    common = max(p for p, _ in got.values())
    this = pd.Period(as_of, "M")
    rows = []
    for sid, (start, months) in got.items():
        n, sub = names.get(sid, (sid, ""))
        rows.append((n, sub, months.get(this), pr.chain([v for p, v in months.items() if p >= common]),
                     pr.chain(months.values()), start.strftime("%b %Y")))
    rows.append(("Nifty Total Market", "", pr.ret(market, (this - 1).to_timestamp(how="end").normalize(), as_of),
                 pr.ret(market, (common - 1).to_timestamp(how="end").normalize(), as_of), None, ""))
    return [("common", f"{common.to_timestamp():%-d %b}")] + rows


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
    lead = {k: (book[k] - mkt[k]) if mkt.get(k) is not None else None for k in ps}
    return {"book": book, "market": mkt, "lead": lead, "mom": mom, "n500": n5}


def header(p: Page) -> list:
    t = p.history
    since = t.get("strategy_total_return")
    since = float(since) * 100 if since is not None and np.isfinite(since) else None
    mkt_since = pr.ret(p.market, p.equity.index[0], p.as_of)
    # The book's own latest day; the market's only when its index has that session (S148: one date for both).
    eq = p.equity.dropna()
    mk = p.market.dropna()
    day = {"book": float(eq.iloc[-1] / eq.iloc[-2] - 1) * 100 if len(eq) > 1 else None,
           "market": float(mk.iloc[-1] / mk.iloc[-2] - 1) * 100 if len(mk) > 1 and mk.index[-1] >= eq.index[-1] else None}
    tab = p.table
    dayr = float(pd.to_numeric(tab["Day P&L (₹)"], errors="coerce").sum())
    m = months_of(p)
    this = pd.Period(p.as_of, "M")
    mtd, mmtd = m["book"].get(this), m["market"].get(this)
    gap = None if mtd is None or mmtd is None else mtd - mmtd
    f = pr.falls(p.equity)
    cells = [("Portfolio value", inr(p.value), "", f"Started with {inr(p.capital)}", "dh-muted",
              f"{inr(p.value - p.holdings)} not invested"),
             ("Since inception, after costs", pct(since), tone(since), inr(p.value - p.capital, plus=True), tone(since),
              f"Nifty Total Market {pct(mkt_since)}"),
             ("Day P&L", pct(day["book"]), tone(day["book"]), inr(dayr, plus=True), tone(dayr),
              f"Nifty Total Market {pct(day['market'])}" if day["market"] is not None
              else f"Nifty Total Market for {dshort(eq.index[-1])} not in yet"),
             (f"Month so far · {this:%b}", pct(mtd), tone(mtd),
              "" if gap is None else f"{abs(gap):.1f} pts {'ahead of' if gap >= 0 else 'behind'} the market", tone(gap),
              f"Nifty Total Market {pct(mmtd)}"),
             ("Below its peak today", pct(f.now) if f else "—", "dh-watch" if f and f.now < 0 else "",
              f"Peak {dshort(f.peak_now)}" if f else "", "", f"Largest fall from a peak {pct(f.worst)}" if f else "")]
    nav = "".join(f'<a class="dh-pill" href="#{a}">{e(t)}</a>' for a, t in NAV)
    sub = ("The model book: ₹1 crore put in on 1 January 2026, run by the Nifty 750 rules, "
           f"{len(tab)} stocks. Returns are after costs.")
    lead = None if since is None or mkt_since is None else since - mkt_since
    answer = ("The model book" if since is None else
              f"The book is up {since:.1f}% since 1 January" + ("" if lead is None else
              f", {abs(lead):.1f} points {'ahead of' if lead >= 0 else 'behind'} the market") + ".")
    # The title answers the reader's first question; the page's name is the kicker (tipsheet benchmark, 21 Nov 2026).
    return [f'<div class="pf-head"><p class="pf-kick">Portfolio</p><h1 class="pf-title">{e(answer)}</h1><p class="pf-sub">{e(sub)}</p>',
            _kpis(cells, "pf-five"), f'<div class="dh-pills pf-nav" role="navigation" aria-label="On this page">{nav}</div></div>']


NAV = (("pf-book", "Current book"), ("pf-exp", "Industry & size"), ("pf-ret", "Returns"), ("pf-eq", "Equity, drawdown & risk"),
       ("pf-cal", "Calendar returns"), ("pf-day", "Day by day"), ("pf-trades", "Trades"), ("pf-sys", "Three systems"))


def holdings_spec(p: Page) -> dict:
    t = p.table
    r = p.rank_df.drop_duplicates("Symbol").set_index("Symbol")
    hc = int(round((1 - float(p.cfg.get("high_pct", 0.8))) * 100))
    cut = int(p.cfg.get("buffer_n", 40))
    word = {"strong": ("Strong", "up"), "turning": ("Turning", "watch"), "weak": ("Weak", "down")}
    rows = []
    for _, h in t.iterrows():
        s = str(h["Symbol"])
        ind = str(h.get("Sector / Industry") or "—")
        st_, tn = word.get(p.industry_state.get(ind, ""), ("", ""))
        tr = p.trails.get(s, [None, None, None])
        ema = pd.to_numeric(r["% 50 EMA"].get(s) if "% 50 EMA" in r else np.nan, errors="coerce")
        hi = pd.to_numeric(r["% High"].get(s) if "% High" in r else np.nan, errors="coerce")
        co = str(h.get("Company") or s)
        rows.append({"s": s, "co": co, "co_short": co.removesuffix(" Ltd.").removesuffix(" Limited").removesuffix(" Ltd"),
                     "ind": short(ind), "status": st_, "tone": tn, "size": p.sizes.get(s, ""),
                     "since": f"{pd.Timestamp(h['Entry Date']):%Y-%m-%d}", "days": int(h.get("Holding Days") or 0),
                     "q": int(h["Shares"]), "ep": round(float(h["Entry Price"]), 2), "px": round(float(h["Current Price"]), 2),
                     "val": round(float(h["Current Value (₹)"])), "w": round(float(h["Weight %"]), 2),
                     "dayp": round(float(h.get("Day P&L %") or 0), 2), "pnl": round(float(h["P&L since Rebalance (₹)"])),
                     "ret": round(float(h["Return since Entry %"]), 2),
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
    cols = [["s", "Stock", 0], ["ind", "Industry · size", 0], ["since", "Entry date", 0], ["q", "Qty", 1], ["ep", "Entry price", 1],
            ["px", "Price", 1], ["val", "Value", 1], ["w", "Weight", 1], ["dayp", "Today", 1], ["pnl", f"P&L from {fill_s}", 1],
            ["ret", "Since entry", 1], ["ema", "vs 50D EMA", 1], ["hi", "From 52W high", 1], ["rn", "Rank 3M · 1M · now", 0]]
    text = {"holdings": f"{len(rows)} holdings", "before": "before costs", "below": "below", "past_high": f"past −{hc}%",
            "past_rank": f"past #{cut}"}
    return {"rows": rows, "foot": foot, "high_cut": hc, "rank_cut": cut, "fill": fill_s, "cols": cols, "text": text}


def section_book(p: Page) -> list:
    spec = holdings_spec(p)
    hc, cut = spec["high_cut"], spec["rank_cut"]
    dates = list(di.trail_dates(p.as_of).values())
    note = (f"Entry price and since entry are from the day the stock was first bought. P&L in rupees starts at the {spec['fill']} "
            "fill, where today’s share counts were set: the record keeps returns and weights, so rupee figures are a mark, not "
            f"a cost. Holdings {inr(p.holdings)} + {inr(p.value - p.holdings)} not invested = portfolio value {inr(p.value)}. "
            f"Exit rules, checked at each month-end: below its 50D EMA (trend breakdown), more than {hc}% below its 52-week high, "
            f"or out of the top {cut} by rank. Rank: where today’s rule puts the stock on {', '.join(dshort(d) for d in dates)} "
            "among the stocks that pass its filters; “Out” means it does not pass them. The plan for the next rebalance is on Actions.")
    return _sec([_head("pf-book", "Current book", f"{len(spec['rows'])} holdings · tap a column to sort · red: past an exit "
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
    head = ('<div class="pf-ihead"><span>Industry</span><span></span><span class="dh-num">Book</span><span class="dh-num">The 750</span>'
            '<span class="dh-num">Over / under</span><span>Status</span></div>')
    body = ""
    for n, v, m in rows:
        k = held.get(n, 0)
        st_, c = word.get(p.industry_state.get(n, ""), ("", "")) if v else ("Not held", "dh-muted")
        d = v - m
        body += (f'<div class="pf-irow"><span class="pf-nm">{e(short(n))}<small>{f"{k} holding" + ("s" if k > 1 else "") if k else "none held"}</small></span>'
                 f'<span class="pf-ibar"><i style="width:{v / top * 100:.1f}%"></i><b style="left:{m / top * 100:.1f}%"></b></span>'
                 f'<span class="dh-num dh-b">{f"{v:.1f}%" if v else "—"}</span><span class="dh-num dh-muted">{m:.1f}%</span>'
                 f'<span class="dh-num {tone(d)}">{sg(d)}</span><span class="{c}">{e(st_)}</span></div>')
    ex = p.exposure
    size = ex[ex["kind"] == "size"].pivot_table(index="date", columns="name", values="weight").sort_index() if len(ex) else pd.DataFrame()
    srows = ""
    for d, r in size.iterrows():
        segs = "".join(f'<i class="dh-sz-{k.lower()}" style="width:{float(r.get(k, 0)):.1f}%" title="{k} {float(r.get(k, 0)):.0f}%">'
                       f'{f"{float(r.get(k, 0)):.0f}" if float(r.get(k, 0)) >= 15 else ""}</i>' for k in ("Large", "Mid", "Small", "Micro"))
        srows += f'<div class="pf-srow"><span class="dh-mono">{MON[d.month - 1]}</span><div class="dh-sizebar pf-thin">{segs}</div></div>'
    key = ('<div class="pf-key"><span><i class="dh-sz-large"></i>Large</span><span><i class="dh-sz-mid"></i>Mid</span>'
           '<span><i class="dh-sz-small"></i>Small</span><span><i class="dh-sz-micro"></i>Micro</span></div>')
    ind = ex[ex["kind"] == "industry"].pivot_table(index="name", columns="date", values="weight").fillna(0) if len(ex) else pd.DataFrame()
    heat = ""
    if len(ind):
        # Every industry the book has held, largest weight at any rebalance first
        # (owner, 21 Nov 2026: "We might be missing other sectors despite we have space"; it listed only those ever at 15%).
        held = ind[(ind > 0).any(axis=1)]          # every industry the book has held
        big = held.loc[held.max(axis=1).sort_values(ascending=False).index]
        heat = ('<table class="dh-tab pf-heat"><thead><tr><th scope="col">Industry</th>'
                + "".join(f'<th scope="col" class="dh-num">{MON[c.month - 1]}</th>' for c in big.columns) + "</tr></thead><tbody>"
                + "".join(f'<tr><th scope="row">{e(short(n))}</th>' + "".join(
                    f'<td class="dh-num pf-hc" style="background:color-mix(in srgb,var(--c-ink) {min(100, v * 1.6):.0f}%,var(--c-white));'
                    f'color:{"var(--c-white)" if v >= 30 else "var(--c-ink)"}">{f"{v:.0f}" if v else ""}</td>' for v in r.values) + "</tr>"
                    for n, r in big.iterrows()) + "</tbody></table>")
    first = size.iloc[0] if len(size) else None
    last = size.iloc[-1] if len(size) else None
    shift = ""
    if first is not None:
        shift = (f"The book began the year {first.get('Large', 0) + first.get('Mid', 0):.0f}% in large and mid companies and is now "
                 f"{last.get('Small', 0) + last.get('Micro', 0):.0f}% small and micro. ")
    note = (shift + "Each rebalance’s industry and size weights are worked out from that month’s book and kept, so the history "
            "stays as it was when later lists change. Size is by NSE’s index lists on each date; industries are the record’s own.")
    return _sec([_head("pf-exp", "Industry & size", "now, against the 750, and at every rebalance since January"),
                 '<div class="dh-cap"><b>Industry exposure now</b><span>bar: the book’s weight · mark: the industry’s weight in the 750 '
                 'by market value</span></div>', '<div class="pf-ilist">' + head + body + '</div>',
                 '<div class="dh-pair"><div><div class="dh-cap"><b>The book by size, each rebalance</b><span>large · mid · small · micro</span></div>'
                 + srows + key + f'<p class="dh-note pf-gap">{e(note)}</p></div><div><div class="dh-cap"><b>Industries, each rebalance</b>'
                 '<span>% of the book, the largest at any rebalance first</span></div>'
                 f'<div class="dh-scroll">{heat}</div></div></div>'])


def section_returns(p: Page) -> list:
    rows = pr.periods(p.equity, p.market, p.mom, p.as_of)
    per = "".join(f'<tr{" class=pf-hl" if lab.startswith("This year") else ""}><th scope="row">{e(lab)}</th>'
                  f'<td class="dh-num dh-b {tone(b)}">{pct(b)}</td><td class="dh-num">{pct(m)}</td>'
                  f'<td class="dh-num {tone(None if b is None or m is None else b - m)}">{sg(None if b is None or m is None else b - m)}</td>'
                  f'<td class="dh-num dh-muted">{pct(mo)}</td></tr>' for lab, b, m, mo in rows)
    start = p.equity.index[0]
    ytd_start = pd.Timestamp(year=p.as_of.year - 1, month=12, day=31)
    book_ytd = pr.ret(p.equity, max(start, ytd_start), p.as_of)
    vals = {k: pr.ret(p.indices[k], ytd_start, p.as_of) for k, _ in YTD_ROWS if k in p.indices}
    ex_since = p.exposure[pd.to_datetime(p.exposure["date"]) > ytd_start] if len(p.exposure) else p.exposure
    vals["mix"] = pr.size_mix(ex_since, {k: p.indices[v] for k, v in SIZE_INDEX.items()}, p.as_of)
    ytd = (f'<tr class="pf-hl"><th scope="row">The book, after costs</th><td class="dh-num dh-b {tone(book_ytd)}">{pct(book_ytd)}</td><td></td></tr>'
           + "".join(f'<tr{" class=pf-hl" if k == "mix" else ""}><th scope="row">{e(n)}</th><td class="dh-num dh-b {tone(vals.get(k))}">{pct(vals.get(k))}</td>'
                     f'<td class="dh-num {tone(None if vals.get(k) is None or book_ytd is None else book_ytd - vals[k])}">'
                     f'{sg(None if vals.get(k) is None or book_ytd is None else book_ytd - vals[k])}</td></tr>' for k, n in YTD_ROWS))
    grows = ("From the record’s second year the table adds 1 year, 3 years, 5 years and a yearly rate since start by itself; "
             "nothing is annualised before then." if not any(r[0] == "1 year" for r in rows) else
             "A yearly rate since start compounds the whole record to one year’s return.")
    mlast = p.market.dropna().index.max() if len(p.market.dropna()) else None
    if mlast is not None and mlast < p.as_of:
        grows = (f"Nifty Total Market and Momentum 50 to {dshort(mlast)}: NSE’s closes for {dshort(p.as_of)} are not in yet, "
                 "so Today shows no market figure and the longer windows end a session early on the index side. " + grows)
    return _sec([_head("pf-ret", "Returns", "the book after costs · indices are price returns"),
                 '<div class="dh-pair"><div><div class="dh-cap"><b>By period</b><span>to ' + f"{p.as_of:%-d %b}" + '</span></div>'
                 '<div class="dh-scroll"><table class="dh-tab dh-tab-s"><thead><tr><th scope="col">Period</th><th scope="col" class="dh-num">The book</th>'
                 '<th scope="col" class="dh-num">Nifty Total Market</th><th scope="col" class="dh-num">Lead, pts</th><th scope="col" class="dh-num">Momentum 50</th>'
                 f'</tr></thead><tbody>{per}</tbody></table></div><p class="dh-note">{e(grows)}</p></div>'
                 f'<div><div class="dh-cap"><b>This year against other indices</b><span>since {ytd_start:%-d %b %Y}</span></div>'
                 '<div class="dh-scroll"><table class="dh-tab dh-tab-s"><thead><tr><th scope="col">Index</th><th scope="col" class="dh-num">This year</th>'
                 f'<th scope="col" class="dh-num">The book’s lead, pts</th></tr></thead><tbody>{ytd}</tbody></table></div>'
                 '<p class="dh-note">The book is mostly small and micro companies, so the market is not its only fair yardstick. The mix holds the four '
                 'NSE size indices in the book’s own size split, reset at each rebalance (see Industry &amp; size).</p></div></div>'])


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


def section_equity(p: Page) -> list:
    spec = growth_spec(p)
    f, fm = pr.falls(p.equity), pr.falls(pr._clean(p.market).loc[p.equity.index[0]:p.as_of])
    m = months_of(p)
    wme = pr.worst_month_end(list(m["book"].values()))
    wme_m = list(m["book"])[wme[1]] if wme and wme[1] >= 0 else None
    risks = pr.risk(p.equity, p.market)
    cap = pr.capture(p.equity, p.market)
    rk = risks[0] if risks else None
    mday = pr.daily_gaps(p.equity, p.market)
    mkt_on = float(mday["market"].get(f.worst_day_on, np.nan)) if f else np.nan
    falls = [("Below its peak today", pct(f.now), "dh-watch" if f.now < 0 else "", f"Peak {dshort(f.peak_now)}", "",
              ("" if not fm else f"The market is at a new high ({dshort(fm.peak_now)})" if fm.now > -0.05
               else f"The market {pct(fm.now)}, below its {dshort(fm.peak_now)} peak")),
             ("Largest fall from a peak", pct(f.worst), "dh-down",
              f"{dshort(f.peak)} → {dshort(f.low)}" + (f", recovered {dshort(f.recovered)}" if f.recovered is not None else ", not yet recovered"), "",
              (f"The market {pct(fm.worst)} ({dshort(fm.peak)} → {dshort(fm.low)})"
               + ("" if fm.recovered is not None else ", not yet recovered")) if fm else ""),
             ("Worst day", pct(f.worst_day), "dh-down", dshort(f.worst_day_on), "", f"The market {pct(mkt_on)} that day"),
             ("Worst month-end", pct(wme[0]) if wme else "—", "dh-down" if wme and wme[0] < 0 else "",
              f"{wme_m:%B}" if wme_m is not None else "", "", "Counting month-end values only")] if f else []
    risk_cells = []
    if rk:
        risk_cells = [("Volatility, a year", f"{rk.vol:.1f}%", "", f"Market {rk.market_vol:.1f}%", "",
                       f"Swings about {rk.vol / rk.market_vol:.1f} times the market’s"),
                      ("Beta", f"{rk.beta:.1f}", "", "How much it moves with the market", "",
                       f"On average, a 1% market day is a {rk.beta:.1f}% book day"),
                      ("Tracking error", f"{rk.tracking:.1f}%", "", "How far it strays from the market", "",
                       f"About {rk.tracking / np.sqrt(pr.YEAR):.1f} pt on a typical day"),
                      ("Up / down capture, 60 sessions", f"{cap[0]:.0f}% / {cap[1]:.0f}%" if cap else "—", "",
                       "Falls less on bad days" if cap and cap[1] < 100 else "Falls more on bad days", "dh-up" if cap and cap[1] < 100 else "dh-down",
                       "Rises less on good days" if cap and cap[0] < 100 else "Rises more on good days"),
                      ("How they move together, 90 sessions", "—" if p.correlation is None else f"{p.correlation:.2f}", "",
                       "Average correlation of the holdings", "", "Low: the list is well spread" if p.correlation is not None and p.correlation < 0.3 else "")]
    windows = " · ".join(f"{r.label}, {r.sessions} sessions" for r in risks[:1])
    second = (p.equity.index[0] + pd.Timedelta(days=1) + pd.DateOffset(years=1))
    more = ("" if len(risks) > 1 else f" · from {second:%B %Y} also the last 12 months and each year")
    rtable = ""
    if len(risks) > 1:
        rtable = ('<div class="dh-scroll"><table class="dh-tab dh-tab-s"><thead><tr><th scope="col">Window</th><th scope="col" class="dh-num">Sessions</th>'
                  '<th scope="col" class="dh-num">Volatility</th><th scope="col" class="dh-num">Market</th><th scope="col" class="dh-num">Beta</th>'
                  '<th scope="col" class="dh-num">Tracking error</th></tr></thead><tbody>'
                  + "".join(f'<tr><th scope="row">{e(r.label)}</th><td class="dh-num">{r.sessions}</td><td class="dh-num">{r.vol:.1f}%</td>'
                            f'<td class="dh-num">{r.market_vol:.1f}%</td><td class="dh-num">{r.beta:.2f}</td><td class="dh-num">{r.tracking:.1f}%</td></tr>'
                            for r in risks) + "</tbody></table></div>")
    te = rk.tracking if rk else 0
    ex_hi, ex_lo = 10 + te, 10 - te
    return _sec([_head("pf-eq", "Equity, drawdown & risk", "₹100 on 1 Jan, daily"),
                 Chart("growth", spec, {"label": "Growth of ₹100: the book, Nifty500 Momentum 50 and Nifty Total Market"}),
                 how("Top: what ₹100 put in at the start has grown to, the book after costs against NSE’s Nifty500 Momentum 50 and Nifty "
                     "Total Market. Bottom: drawdown, how far each sat below its own highest close so far, every day.",
                     "A drawdown is today’s value against the highest value before it: (value ÷ peak) − 1. The largest fall from a peak "
                     "(maximum drawdown) is the deepest point; the worst day is a different measure, the largest fall from one close to the "
                     "next; the worst month-end counts month-end values only.",
                     ["Date", "The book", "Momentum 50", "Market", "Book below peak", "Market below peak"],
                     [[d, f"{b:.1f}", "—" if mo is None else f"{mo:.1f}", "—" if mk is None else f"{mk:.1f}", f"{dd:.1f}%",
                       "—" if dm is None else f"{dm:.1f}%"]
                      for d, b, mo, mk, dd, dm in list(zip(spec["dates"], spec["book"], spec["mom"], spec["market"], spec["dd"], spec["ddm"]))[::-5]]),
                 _kpis(falls, "pf-four"),
                 f'<div class="dh-cap"><b>Risk</b><span>{e(windows + more)}</span></div>', _kpis(risk_cells, "pf-five"), rtable,
                 how("Volatility: how much the book’s daily returns swing, scaled to a year. Beta: how much the book moves, on average, for a 1% "
                     "move in the market. Tracking error: how much the book’s return differs from the market’s, scaled to a year (the spread "
                     "of the daily gaps). Capture: on the market’s up days and down days, the book’s average move as a share of the market’s.",
                     f"Tracking error {te:.1f}% means: in a year the market makes +10%, a book like this one would usually end between about "
                     f"{ex_lo:+.0f}% and {ex_hi:+.0f}% (10 ± {te:.1f}, two years in three), and outside that range one year in three. On a "
                     f"typical day the book and the market differ by about {te / np.sqrt(pr.YEAR):.1f} point (tracking error ÷ √250). An "
                     "index fund aims for well under 1%; a 20-stock small-company momentum book cannot be close to the market, and that "
                     "distance is where its lead comes from.",
                     ["Measure", "The book", "The market"],
                     [["Volatility, a year", f"{rk.vol:.1f}%", f"{rk.market_vol:.1f}%"], ["Beta", f"{rk.beta:.2f}", "1.00"],
                      ["Tracking error", f"{rk.tracking:.1f}%", "—"], ["Sessions", str(rk.sessions), str(rk.sessions)]] if rk else [])])


def calendar_html(p: Page, show: str = "All") -> tuple[str, str, str]:
    m = months_of(p)
    cal = pr.calendar(m)
    names = {"book": "The book", "market": "Nifty Total Market", "lead": "Lead, pts", "mom": "Momentum 50", "n500": "Nifty 500, as recorded"}
    pick = {"All": list(names), "The book": ["book"], "Market": ["market"], "Lead": ["lead"], "Momentum 50": ["mom"]}.get(show, list(names))

    def cell(v, b=False, q=False):
        cls = "dh-num" + (" pf-q" if q else "") + (f" dh-b {tone(v)}" if b else "")
        return f'<td class="{cls}">{"—" if v is None else sg(v)}</td>'
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
                     + "".join(cell(v, b) for v in r["months"]) + "".join(cell(v, b, i == 0) for i, v in enumerate(qs)) + cell(yr, b, True) + "</tr>")
    body += (f'<tr class="pf-yr pf-ghost"><th scope="rowgroup" colspan="18">{this.year + 1}<span class="dh-muted"> · from January, a row group '
             'like the one above; each year adds its own</span></th></tr>') if len(cal) == 1 else ""
    grid = f'<div class="dh-scroll"><table class="dh-tab pf-grid pf-nw">{head}<tbody>{body}</tbody></table></div>'
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
               f'<td class="dh-num">{ahead} of {nmon}</td><td class="dh-num dh-down">{pct(fy.worst) if fy else "—"}'
               f'<span class="dh-sub">market {pct(fm.worst) if fm else "—"}</span></td></tr>')
    years = ('<div class="dh-scroll"><table class="dh-tab dh-tab-s pf-nw"><thead><tr><th scope="col">Year</th><th scope="col" class="dh-num">Book</th>'
             '<th scope="col" class="dh-num">Market</th><th scope="col" class="dh-num">Lead</th><th scope="col" class="dh-num">Momentum 50</th>'
             f'<th scope="col" class="dh-num">Months ahead</th><th scope="col" class="dh-num">Largest fall</th></tr></thead><tbody>{ys}</tbody></table></div>')
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
           '<th scope="col" class="dh-num">Market</th><th scope="col" class="dh-num">Lead</th><th scope="col" class="dh-num">Momentum 50</th>'
           f'</tr></thead><tbody>{fys}</tbody></table></div>')
    return grid, years, fyt


def month_bars_spec(p: Page) -> dict:
    m = months_of(p)
    ps = sorted(m["book"])[-12:]
    this = pd.Period(p.as_of, "M")
    return {"values": [round(m["lead"][k], 1) if m["lead"][k] is not None else 0.0 for k in ps],
            "labels": [f"{k:%b}" for k in ps], "full": [f"{k:%B %Y}" + (", so far" if k == this else "") for k in ps],
            "unit": "pts against the market", "xn": 12, "valueLabels": True, "vdp": 1, "height": 170}


def day_section(p: Page) -> list:
    g = pr.daily_gaps(p.equity, p.market)
    last = g.tail(20)
    five = (pr.ret(p.equity, g.index[-6], g.index[-1]), pr.ret(pr._clean(p.market).reindex(p.equity.index).ffill(), g.index[-6], g.index[-1]))
    t = g.iloc[-1]
    beat20, beat = int((last["gap"] > 0).sum()), int((g["gap"] > 0).sum())
    cells = [("Today", sg(t["gap"], 1, " pts"), tone(t["gap"]), f"Book {pct(t['book'])}, market {pct(t['market'])}", "", ""),
             ("Last 5 sessions", sg(five[0] - five[1], 1, " pts") if None not in five else "—", tone(None if None in five else five[0] - five[1]),
              f"Book {pct(five[0])}, market {pct(five[1])}", "", ""),
             ("Last 20 sessions", f"{beat20} of {len(last)}", "dh-up" if beat20 > len(last) / 2 else "dh-watch", "Sessions the book beat the market", "", ""),
             (f"Since {dshort(p.equity.index[1])}", f"{beat} of {len(g)}", "dh-up" if beat > len(g) / 2 else "dh-watch",
              f"Sessions the book beat the market, {beat / len(g) * 100:.0f}%", "", "")]
    spec = {"values": [round(float(v), 2) for v in last["gap"]], "labels": [dshort(d) for d in last.index],
            "full": [f"{d:%-d %b %Y}" for d in last.index], "unit": "pts against the market", "dp": 2, "xn": 5,
            "lastLabel": "Today", "height": 170}
    return _sec([_head("pf-day", "Day by day against the market", "Day P&L in context"), _kpis(cells, "pf-four"),
                 '<div class="dh-cap"><b>The book against the market, last 20 sessions</b><span>points</span></div>',
                 Chart("bars", spec, {"label": "The book's daily lead over the market, last 20 sessions"}),
                 how("Each session, the book’s day less Nifty Total Market’s day, in points.",
                     f"One day is mostly noise; a run of bars on one side is not. The book beat the market on {beat} of {len(g)} sessions.",
                     ["Session", "Book", "Market", "Lead, pts"],
                     [[f"{d:%-d %b %Y}", pct(r.book, 2), pct(r.market, 2), sg(r.gap, 2)] for d, r in last.iloc[::-1].iterrows()])])


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


def section_trades_top(p: Page, s: dict) -> list:
    if not s:
        return _sec([_head("pf-trades", "Trades", "no trades yet")])
    reb = s["rebal"]
    after = [b for _, b, _, _ in reb[1:]]
    avg = sum(after) / len(after) if after else None
    lo = min(reb[1:], key=lambda r: r[1]) if len(reb) > 1 else None
    cells = [("Trades won", f"{s['wins'] / s['closed'] * 100:.0f}%", "dh-watch" if s["wins"] / s["closed"] < 0.5 else "dh-up",
              f"{s['wins']} of {s['closed']} closed", "", ""),
             ("Average win", pct(s["avg_win"]), "dh-up", f"Median {pct(s['med_win'])}", "", "A few large winners carry it"
              if s["avg_win"] and s["med_win"] and s["avg_win"] > 2 * s["med_win"] else ""),
             ("Average loss", pct(s["avg_loss"]), "dh-down", f"Median {pct(s['med_loss'])}", "", ""),
             ("Held, median", f"{s['hold']:.0f} days", "", f"Winners {s['hold_win']:.0f} · losers {s['hold_loss']:.0f}", "", ""),
             ("Changed at a rebalance", f"{avg:.0f} of 20" if avg else "—", "", f"On average, from {reb[1][0]:%B}" if len(reb) > 1 else "", "",
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
            '<div class="dh-scroll"><table class="dh-tab dh-tab-s"><thead><tr><th scope="col">Exit rule</th><th scope="col" class="dh-num">Trades</th>'
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
    rows = [[r["Symbol"], r["Industry"], iso(r["Entry signal date"]), iso(r["Entry date"]), round(float(r["Entry price"]), 2),
             None if pd.isna(r["Entry rank"]) else int(r["Entry rank"]), num(r["Entry weight %"]), iso(r["Exit signal date"]),
             iso(r["Exit date"]), None if num(r["Exit price"]) is None else round(num(r["Exit price"]), 2),
             None if pd.isna(r["Exit rank"]) else int(r["Exit rank"]), round(float(r["Return %"]), 2), int(r["Days held"]),
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


def section_systems(p: Page) -> list:
    if not p.systems:
        return []
    _, common = p.systems[0]
    rows = "".join(
        f'<tr class="{"dh-muted" if not started else ""}"><th scope="row">{e(n)}{f"<span class=dh-sub>{e(sub)}</span>" if sub else ""}</th>'
        f'<td class="dh-num {tone(m)}">{pct(m)}</td><td class="dh-num {tone(c)}">{pct(c)}</td><td class="dh-num {tone(o)}">{pct(o)}</td><td>{e(started)}</td></tr>'
        for n, sub, m, c, o, started in p.systems[1:])
    from src.engine.track_record import SHADOWS
    shadows = ", ".join(f"{b.name.replace(' (shadow)', '')} (from {b.inception.strftime('%b %Y')})" for b in SHADOWS.values())
    return _sec([_head("pf-sys", "Three systems, side by side", "compared over the same window"),
                 '<div class="dh-scroll"><table class="dh-tab dh-tab-s pf-sys"><thead><tr><th scope="col">System</th><th scope="col" class="dh-num">This month</th>'
                 f'<th scope="col" class="dh-num">Since {e(common)}, all three</th><th scope="col" class="dh-num">Since its own start</th><th scope="col">Started</th>'
                 f'</tr></thead><tbody>{rows}</tbody></table></div>',
                 f'<p class="dh-note">“Since {e(common)}” is the window all three have traded, so it is the fair comparison; it grows as the systems age. '
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
              '<p class="dh-note">Frozen months stay as recorded against the Nifty 500, the benchmark when they were frozen; Nifty Total Market is '
              'worked out beside them (the Nifty 500 row shows what each was frozen against). Momentum 50 is NSE’s Nifty500 Momentum 50, a '
              'momentum index to judge the strategy by.</p></section>', END]
    parts += day_section(p) + section_trades_top(p, s) + ["</section>"]
    parts += section_systems(p) + [f'<p class="dh-foot">Data to {p.as_of:%-d %b %Y}.</p>']
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
    show = st.pills("Show", ["All", "The book", "Market", "Lead", "Momentum 50"], default="All", key="pf_cal_show",
                    label_visibility="collapsed") or "All"
    grid, years, fys = calendar_html(p, show)
    emit(['<div class="dh-cap"><b>Months and quarters</b></div>', grid,
          f'<div class="dh-pair"><div><div class="dh-cap"><b>Calendar years</b><span>January to December</span></div>{years}</div>'
          f'<div><div class="dh-cap"><b>Financial years</b><span>April to March</span></div>{fys}</div></div>',
          '<p class="dh-note">Frozen months stay as recorded against the Nifty 500, the benchmark when they were frozen; Nifty Total Market is '
          'worked out beside them (the Nifty 500 row shows what each was frozen against). Momentum 50 is NSE’s Nifty500 Momentum 50, a '
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
    emit([END] + section_systems(p) + [f'<p class="dh-foot">Data to {p.as_of:%-d %b %Y}.</p>'])


__all__ = ["render", "gather", "page_parts", "html_of", "Page"]
