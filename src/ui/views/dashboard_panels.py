"""Two Dashboard panels from S91 (owner, 7 Nov 2026: "build it").

Momentum health reads data/momentum_health.csv (scripts/build_momentum_health.py,
monthly; method and the IIMA check in docs/MOMENTUM_HEALTH.md). Flows reads
data/fii_dii_flows.csv (scripts/collect_fii_dii.py, each trading evening). Both
files are written and checked by scheduled jobs on the failure alert; a panel
whose file is missing or too thin says so instead of drawing.
"""
from __future__ import annotations

import base64
import html
from pathlib import Path

import pandas as pd
import streamlit as st

from src.engine.momentum_health import health, long_only
from src.ui import formats as fmt
from src.ui.tokens import C

ROOT = Path(__file__).resolve().parents[3]
MOMENTUM_FILE = ROOT / "data" / "momentum_health.csv"
FLOWS_FILE = ROOT / "data" / "fii_dii_flows.csv"
NSDL_FILE = ROOT / "data" / "nsdl_fpi_daily.csv"
IIMA_CHECK = "correlation 0.83 with IIM Ahmedabad's momentum factor, Feb 2010 to Dec 2025"


@st.cache_data(show_spinner=False, ttl=3600)
def _read(path: str, stamp: float) -> pd.DataFrame | None:
    try:
        return pd.read_csv(path)
    except Exception:  # noqa: BLE001
        return None


def _load(path: Path) -> pd.DataFrame | None:
    return _read(str(path), path.stat().st_mtime) if path.exists() else None


def ordinal(n: int) -> str:
    """1st, 2nd, 3rd, 4th, 11th, 12th, 13th, 21st, 42nd."""
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def percentile_word(p: float) -> str:
    return ("weak" if p < 20 else "below usual" if p < 40 else "about usual" if p < 60
            else "above usual" if p < 80 else "strong")


def _bars_svg(values: list[float], width: int = 300, height: int = 64) -> str:
    """Monthly spreads as diverging bars, as a data-URI image (st.html strips inline SVG)."""
    if not values:
        return ""
    top = max(max(abs(v) for v in values), 1e-9)
    mid = height / 2
    w = width / len(values)
    bars = []
    for i, v in enumerate(values):
        h = abs(v) / top * (mid - 2)
        y = mid - h if v >= 0 else mid
        bars.append(f'<rect x="{i * w + 1:.1f}" y="{y:.1f}" width="{max(w - 2, 1):.1f}" height="{max(h, 0.5):.1f}" '
                    f'fill="{C.up if v >= 0 else C.down}"/>')
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
           f'<line x1="0" x2="{width}" y1="{mid}" y2="{mid}" stroke="{C.rule}" stroke-width="1"/>{"".join(bars)}</svg>')
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()


def momentum_health_html(spreads: pd.DataFrame | None) -> str | None:
    h = health(spreads) if spreads is not None else None
    if h is None:
        return None
    month = pd.Period(h["month"], freq="M")
    t12, last = h["trailing_12m"], h["month_spread"]
    word = percentile_word(h["percentile"])
    lede = (f"Over the last 12 months the top fifth of our ranking beat the bottom fifth by "
            f"{fmt.signed(t12)} points: {word} ({ordinal(round(h['percentile']))} percentile since 2010). "
            f"{month:%B}: {fmt.signed(last)} points.")
    if t12 < 0:
        lede = (f"Over the last 12 months the top fifth of our ranking trailed the bottom fifth by "
                f"{fmt.signed(abs(t12), plus=False)} points: {word} ({ordinal(round(h['percentile']))} percentile "
                f"since 2010). {month:%B}: {fmt.signed(last)} points.")
    crash = (f'<p class="db-flag">{month:%B} was in the worst 10% of months since 2010: momentum '
             "stocks fell well behind the laggards.</p>") if h["crash"] else ""
    recent = spreads.tail(24)["spread"].astype(float).tolist()
    img = _bars_svg(recent)
    alt = (f"Monthly spread, top fifth minus bottom fifth, last {len(recent)} months: from "
           f"{fmt.signed(min(recent))} to {fmt.signed(max(recent))} points.")
    tone = "up" if t12 > 0 else "down" if t12 < 0 else ""
    return (f'<div class="db-mh"><div class="db-big {tone}">{fmt.signed(t12)}<span> pts, 12 months</span></div>'
            f'<p class="db-lede">{html.escape(lede)}</p>{crash}'
            f'<img src="{img}" alt="{html.escape(alt)}" width="300" height="64" style="max-width:100%"></div>')


def long_only_html(spreads: pd.DataFrame | None) -> str | None:
    """Momentum health led by what a long-only book earns: winners against the
    Nifty 500 (owner, 8 Nov 2026), with winners against losers kept as one row."""
    lo = long_only(spreads)
    if lo is None:
        return None
    month = pd.Period(lo["month"], freq="M")
    t12 = lo["lead_12m"]
    word = percentile_word(lo["percentile"])
    verb = "beat" if t12 >= 0 else "trailed"
    lede = (f"Over the last 12 months the top fifth of our ranking {verb} the Nifty 500 by "
            f"{abs(t12):.1f} points: {word} ({ordinal(round(lo['percentile']))} percentile since {lo['since']}). "
            f"{month:%B}: {fmt.signed(lo['month_lead'])} points.")
    rows = []

    def row(label: str, v: float | None) -> None:
        if v is None:
            return
        tone = "up" if v > 0 else "down" if v < 0 else ""
        rows.append(f'<tr><td>{html.escape(label)}</td><td class="{tone}">{fmt.signed(v)}</td></tr>')

    row("Winners against the average stock (momentum)", lo["momentum_12m"])
    row("Average stock against the Nifty 500 (breadth)", lo["breadth_12m"])
    row("Winners against losers (the factor, for reference)", lo["wml_12m"])
    table = ('<table class="db-fig"><thead><tr><th scope="col">Last 12 months</th><th scope="col">Points</th>'
             f'</tr></thead><tbody>{"".join(rows)}</tbody></table>') if rows else ""
    recent = lo["recent"]
    img = _bars_svg(recent)
    alt = (f"Monthly lead of the top fifth over the Nifty 500, last {len(recent)} months: from "
           f"{fmt.signed(min(recent))} to {fmt.signed(max(recent))} points.")
    tone = "up" if t12 > 0 else "down" if t12 < 0 else ""
    return (f'<div class="db-mh"><div class="db-big {tone}">{fmt.signed(t12)}<span> pts, 12 months</span></div>'
            f'<p class="db-lede">{html.escape(lede)}</p>{table}'
            f'<img src="{img}" alt="{html.escape(alt)}" width="300" height="64" style="max-width:100%"></div>')


QUARTER_WORDS = ("Few", "Fewer than usual", "More than usual", "Many")


def _qualified_evidence(spreads: pd.DataFrame, d: pd.DataFrame, cuts: list[float]) -> str:
    """Our portfolio's own backtest, when the monthly job has written it (owner,
    8 Nov 2026: evidence must hold for the book, and in most 5-year blocks);
    until then the momentum factor's, said as such."""
    from src.engine.portfolio_history import excess_by_quarter

    pe = excess_by_quarter(spreads, "qualified")
    if pe is not None:
        held = sum(ok for _, ok in pe["blocks"])

        def lead(v: float, name: str) -> str:
            return f"beat {name} by {v:.1f} pts" if v >= 0 else f"trailed {name} by {-v:.1f} pts"

        return (f"In a backtest of the strategy's rules on the Nifty 500 since {pe['since']} (not the live "
                f"record, which trades the 750), after the quarter of month-ends with the fewest "
                f"(at or below {pe['cut'] * 100:.0f}%) the portfolio {lead(pe['low'], 'the Nifty 500')} the next "
                f"month on average; after the other months it {lead(pe['rest'], 'the index')}. The pattern held in "
                f"{held} of {len(pe['blocks'])} five-year blocks.")
    d = d.assign(qtr=pd.qcut(d["qualified"], 4, labels=False))
    g = d.groupby("qtr")["spread"]
    low, high = g.get_group(0), g.get_group(3)
    return (f"In the quarter of month-ends with the fewest (below {cuts[0] * 100:.0f}%), the momentum factor's next "
            f"month (top fifth minus bottom fifth) averaged {fmt.signed(float(low.mean()))} pts and fell in "
            f"{float((low < 0).mean()) * 100:.0f}% of them; in the quarter with the most, "
            f"{fmt.signed(float(high.mean()))} pts and {float((high < 0).mean()) * 100:.0f}%.")


def qualified_html(spreads: pd.DataFrame | None) -> str | None:
    """How many stocks qualify? (TODO S110, item 2): the month-end share of the
    Nifty 500 passing the strategy's own gates, from data/momentum_health.csv."""
    from src.ui import page_kit as kit

    if spreads is None or "qualified" not in spreads.columns:
        return None
    d = spreads.assign(qualified=pd.to_numeric(spreads["qualified"], errors="coerce"),
                       spread=pd.to_numeric(spreads["spread"], errors="coerce")).dropna(subset=["qualified"])
    if len(d) < 24:
        return None
    last = d.iloc[-1]
    q = d["qualified"]
    cuts = q.quantile([0.25, 0.5, 0.75]).tolist()
    quarter = sum(float(last["qualified"]) > c for c in cuts)
    share_below = float((q < float(last["qualified"])).mean())
    when = pd.Timestamp(last["date"])
    share_above = float((q > float(last["qualified"])).mean())
    since = f"{pd.Timestamp(d['date'].iloc[0]):%Y}"
    rank = (f"fewer than in {share_above * 100:.0f}% of month-ends since {since}" if share_above > share_below
            else f"more than in {share_below * 100:.0f}% of month-ends since {since}")
    lede = (f"At the end of {when:%B %Y}, {float(last['qualified']) * 100:.0f}% of the Nifty 500 passed the strategy's "
            f"own filters (above the 50-day EMA, within 20% of the 52-week high): {rank}.")
    ev = _qualified_evidence(spreads, d, cuts)
    spark = kit.spark_img(d["qualified"].tail(24).tolist(), 120, 28, last=None)
    tone = "down" if quarter == 0 else ""
    return (f'<div class="db-big {tone}">{float(last["qualified"]) * 100:.0f}%<span>{QUARTER_WORDS[quarter]}</span></div>'
            f'<p class="db-lede">{html.escape(lede)}</p>{spark}'
            f'<p class="db-note">{html.escape(ev)}</p>')


TREND_MIN, TREND_WINDOW = 5, 20


def _pair_bars_svg(fii: list[float], dii: list[float], width: int = 300, height: int = 76) -> str:
    """Daily net flows as two rows of bars on one scale (FII above, DII below)."""
    top = max([abs(v) for v in fii + dii] + [1e-9])
    row, w = height / 2, width / max(len(fii), 1)
    parts = []
    for r, vals in enumerate((fii, dii)):
        mid = row * r + row / 2
        parts.append(f'<line x1="0" x2="{width}" y1="{mid}" y2="{mid}" stroke="{C.rule}" stroke-width="1"/>')
        for i, v in enumerate(vals):
            h = abs(v) / top * (row / 2 - 2)
            y = mid - h if v >= 0 else mid
            parts.append(f'<rect x="{i * w + 1:.1f}" y="{y:.1f}" width="{max(w - 2, 1):.1f}" height="{max(h, 0.5):.1f}" '
                         f'fill="{C.up if v >= 0 else C.down}"/>')
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
           f'viewBox="0 0 {width} {height}">{"".join(parts)}</svg>')
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()


def flows_html(flows: pd.DataFrame | None) -> str | None:
    """The trend in FII and DII net buying, never one day on its own (owner,
    8 Nov: one day's flow is misleading). Under TREND_MIN sessions the panel
    says how many are in and lists them small; from TREND_MIN it leads with
    the total over the last TREND_WINDOW sessions (or all, while fewer) and
    draws each day as a bar."""
    if flows is None or flows.empty:
        return None
    f = flows.copy()
    f["date"] = pd.to_datetime(f["date"])
    wide = f.pivot_table(index="date", columns="category", values="net", aggfunc="last").sort_index()
    fii = wide.get("FII/FPI", pd.Series(0.0, index=wide.index)).fillna(0.0)
    dii = wide.get("DII", pd.Series(0.0, index=wide.index)).fillna(0.0)
    days, first = len(wide), wide.index[0]
    if days < TREND_MIN:
        listed = "".join(f"<li>{d:%-d %b}: FII/FPI {fmt.inr(fii[d], plus=True)} Cr, DII {fmt.inr(dii[d], plus=True)} Cr</li>"
                         for d in wide.index)
        return (f'<p class="db-lede">Collecting: {days} session{"s" if days != 1 else ""} since {first:%-d %b %Y}. '
                f'One day\'s flow swings widely and says little on its own, so the trend shows from '
                f'{TREND_MIN} sessions.</p><ul class="db-note">{listed}</ul>')
    n = min(days, TREND_WINDOW)
    f_n, d_n = fii.tail(n), dii.tail(n)

    def side(label: str, total: float) -> str:
        word, tone = ("bought", "up") if total > 0 else ("sold", "down")
        return f'<dt>{label}</dt><dd><b class="{tone}">{fmt.inr(abs(total))} Cr</b> net {word}</dd>'

    img = _pair_bars_svg(f_n.tolist(), d_n.tolist())
    alt = (f"Daily net flows, last {n} sessions: FII/FPI from {fmt.inr(f_n.min())} to {fmt.inr(f_n.max())} Cr; "
           f"DII from {fmt.inr(d_n.min())} to {fmt.inr(d_n.max())} Cr.")
    since = ""
    if days > n:
        since = (f'<p class="db-note">Since {first:%-d %b %Y} ({days} sessions): FII/FPI '
                 f'{fmt.inr(fii.sum(), plus=True)} Cr, DII {fmt.inr(dii.sum(), plus=True)} Cr.</p>')
    return (f'<p class="db-lede">Cash market, last {n} sessions to {wide.index[-1]:%-d %b %Y} (provisional).</p>'
            f'<dl class="db-kv">{side("FII/FPI", float(f_n.sum()))}{side("DII", float(d_n.sum()))}</dl>'
            f'<img src="{img}" alt="{html.escape(alt)}" width="300" height="76" style="max-width:100%;margin-top:8px">'
            f'<p class="db-note">Bars: each session, FII/FPI above, DII below.</p>{since}')


def _month_bars_svg(values: list[float], width: int = 300, height: int = 64) -> str:
    return _bars_svg(values, width, height)


def nsdl_flows_html(nsdl: pd.DataFrame | None, nse: pd.DataFrame | None) -> str | None:
    """Foreign flows from NSDL's confirmed record: the last 20 reporting days'
    equity net, the last 12 months as bars; domestic (DII) from our NSE
    collection once it has TREND_MIN sessions (NSDL reports only foreign)."""
    if nsdl is None or len(nsdl) < TREND_MIN:
        return None
    n = nsdl.copy()
    n["date"] = pd.to_datetime(n["date"])
    n = n.sort_values("date")
    last = n["date"].iloc[-1]
    k = min(len(n), TREND_WINDOW)
    recent = float(n["equity_net"].tail(k).sum())
    months = n.set_index("date")["equity_net"].resample("ME").sum().tail(12)
    word, tone = ("bought", "up") if recent > 0 else ("sold", "down")
    rows = (f'<dt>FII/FPI</dt><dd><b class="{tone}">{fmt.inr(abs(recent))} Cr</b> net {word}, '
            f'last {k} reporting days</dd>')
    year = float(months.sum())
    rows += (f'<dt>12 months</dt><dd><b class="{"up" if year > 0 else "down"}">{fmt.inr(year, plus=True)} Cr</b> '
             f'since {months.index[0]:%b %Y}</dd>')
    dii_line = ""
    if nse is not None and not nse.empty:
        f = nse.copy()
        f["date"] = pd.to_datetime(f["date"])
        d = f[f["category"] == "DII"].sort_values("date")
        if len(d) >= TREND_MIN:
            m = min(len(d), TREND_WINDOW)
            tot = float(d["net"].tail(m).sum())
            rows += (f'<dt>DII</dt><dd><b class="{"up" if tot > 0 else "down"}">{fmt.inr(abs(tot))} Cr</b> net '
                     f'{"bought" if tot > 0 else "sold"}, last {m} sessions (NSE)</dd>')
        else:
            dii_line = (f'<p class="db-note">DII: {len(d)} session{"s" if len(d) != 1 else ""} collected from NSE '
                        f'since {d["date"].min():%-d %b} (NSDL reports foreign investors only); the DII trend appears once '
                        f'{TREND_MIN} sessions are collected.</p>' if len(d) else "")
    img = _month_bars_svg(months.tolist())
    alt = (f"FPI equity net per month, {months.index[0]:%b %Y} to {months.index[-1]:%b %Y}: from "
           f"{fmt.inr(months.min())} to {fmt.inr(months.max())} Cr.")
    # NSDL dates a row by its reporting day, which covers the session before
    # (audit, 8 Nov 2026: "to 6 Nov" read as trades to 6 Nov).
    return (f'<p class="db-lede">Foreign portfolio investors in equity, NSDL, reported to {last:%-d %b %Y} '
            f'(each report covers the session before).</p>'
            f'<dl class="db-kv">{rows}</dl>'
            f'<img src="{img}" alt="{html.escape(alt)}" width="300" height="64" style="max-width:100%;margin-top:8px">'
            f'<p class="db-note">Bars: net per month, last 12 months.</p>{dii_line}')


def render(kit, left, right) -> None:
    """The two cards, momentum health on the left, flows on the right."""
    spreads = _load(MOMENTUM_FILE)
    lo_out = long_only_html(spreads)
    with left, kit.card("Momentum health", "db_mh",
                        "top fifth against the Nifty 500" if lo_out else "top fifth minus bottom fifth"):
        out = lo_out or momentum_health_html(spreads)
        if out is None:
            kit.caption("Momentum health is not available right now: its monthly file is missing or "
                        "shorter than two years.")
        elif lo_out:
            st.html(out)
            kit.caption("Each month-end the Nifty 500's members are ranked by this site's score; the "
                        "figure is the next month's return of the top fifth, equal weight, less the Nifty "
                        "500's: what a long-only momentum book earns over the index. Since 2010 its 12-month "
                        "sum moved with our book's lead over the index (correlation 0.81; winners minus "
                        "losers 0.44). Breadth carries the small-stock effect. Bars: the last 24 months. "
                        f"Winners minus losers checked: {IIMA_CHECK}. A reading, not a forecast.")
        else:
            st.html(out)
            kit.caption("Each month-end the Nifty 500's members are ranked by this site's score; the "
                        "spread is the next month's return of the top fifth minus the bottom fifth. "
                        f"Bars: the last 24 months. Checked: {IIMA_CHECK}. How momentum has been "
                        "paying, not a forecast.")
    with right, kit.card("How many stocks qualify?", "db_qual", "the strategy's own filters, month-ends"):
        out = qualified_html(spreads)
        if out is None:
            kit.caption("Not available yet: the monthly momentum file has no qualified share until its "
                        "next build.")
        else:
            st.html(out)
            kit.caption("Each month-end, the share of the Nifty 500's members (as they stood then) passing the "
                        "same filters the model applies. Line: the last 24 month-ends. The backtest is the record's "
                        "configuration on NSE's adjusted closes over the Nifty 500 as it stood (Backtest's History "
                        "from 2010), rebuilt each month; a reading, not a forecast.")
    with right, kit.card("Flows", "db_flows", "foreign and domestic institutions"):
        nse = _load(FLOWS_FILE)
        out = nsdl_flows_html(_load(NSDL_FILE), nse)
        if out is not None:
            st.html(out)
            kit.caption("NSDL's confirmed FPI figures (custodians' reports, a reporting date covers the "
                        "previous trading day), equity, stock exchange and primary market. DII from NSE's "
                        "provisional daily figures, collected each evening from 6 Nov 2026.")
            return
        out = flows_html(nse)
        if out is None:
            kit.caption("Flows are not available right now.")
        else:
            st.html(out)
            kit.caption("NSE's provisional figures, collected each trading evening. NSE and MSEI publish "
                        "only the latest day, so this history starts on 6 Nov 2026 and grows by one "
                        "session a day; NSDL's longer record is being tried as a source.")
