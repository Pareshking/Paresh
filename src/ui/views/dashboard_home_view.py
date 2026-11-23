"""The home page, rebuilt from the approved mock-up (owner, 20 Nov 2026, S149).

Verdict first, then the sections in the order an owner asks: my book this
month, what happens at the next rebalance, is momentum working, money flows,
size, where the book is strong and weak, where leadership is moving; an
"At a glance" band keeps the reference figures the main sections left out.

Every inference comes from src/engine/dashboard_insights.py; this module only
gathers inputs (the same functions Portfolio, Actions, Sectors and RRG use)
and formats. The market is Nifty Total Market; the track record's frozen
months stay against the Nifty 500 and are compared beside, never rewritten.
"""
from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

from src.ui import formats as _fmt

from src.core.market_time import ist_now
from src.engine import dashboard_insights as di
from src.engine.extra_universe import SYSTEM_750, UNIVERSE_SHORT
from src.engine.exit_watch import SELL, UNKNOWN, WATCH, Rules, assess, least_room, nearest_rule
from src.engine.track_record import TRACK_RECORD_CONFIG
from src.loaders import benchmark_indices as bi
from src.ui import dash_charts as dc
from src.ui.system_param import page_href, stock_href

ROOT = Path(__file__).resolve().parents[3]
FILES = {
    "spreads": ROOT / "data" / "momentum_health.csv",
    "latest_q": ROOT / "data" / "momentum_health_latest.json",
    "nsdl": ROOT / "data" / "nsdl_fpi_daily.csv",
    "nse_flows": ROOT / "data" / "fii_dii_flows.csv",
    "nse_dii": ROOT / "data" / "nse_dii.csv",
    "bench": ROOT / "data" / "benchmarks.csv",
    "tests": ROOT / "data" / "signal_tests.json",
    "mcap": ROOT / "data" / "nse_market_caps.csv",
    "lists": ROOT / "data" / "indices",
}
# NSE's size lists, today's members (data/indices); Nifty 100 = Nifty 50 + Next 50.
SIZE_LISTS = {"Nifty 100": ("ind_nifty50list.csv", "ind_niftynext50list.csv"),
              "Nifty Midcap 150": ("ind_niftymidcap150list.csv",), "Nifty Smallcap 250": ("ind_niftysmallcap250list.csv",),
              "Nifty Microcap 250": ("ind_niftymicrocap250_list.csv",)}
MOMENTUM_NAMES = {
    "midcap150_mom50": "Nifty Midcap150 Momentum 50",
    "smallcap250_mq100": "Nifty Smallcap250 Momentum Quality 100",
    "nifty200_mom30": "Nifty200 Momentum 30",
    "total_market_mq50": "Nifty Total Market Momentum Quality 50",
    "nifty500_mom50": "Nifty500 Momentum 50",
}
SIZE_LABELS = {"nifty100": "Nifty 100", "nifty200": "Nifty 200", "midcap150": "Nifty Midcap 150", "smallcap250": "Nifty Smallcap 250",
               "microcap250": "Nifty Microcap 250", "nifty200_mom30": "Nifty200 Momentum 30",
               "midcap150_mom50": "Nifty Midcap150 Momentum 50", "smallcap250_mq100": "Nifty Smallcap250 Momentum Quality 100"}
AT_RISK_ROWS = 8
from src.ui.industry_names import INDUSTRY_SHORT as SHORT  # noqa: E402  one map for every page
TONE = {"up": "dh-up", "down": "dh-down", "watch": "dh-watch", "flat": "dh-muted", "for": "dh-up",
        "against": "dh-down", "neutral": "dh-muted"}

e = html.escape


# ── Parts: a section is HTML with charts between (S151, v8) ─────────────────
# A chart is its own frame (src/ui/dash_charts.py), so a section is a list of
# HTML strings and charts, drawn in order; Cols puts two lists side by side.


@dataclass
class Chart:
    kind: str
    spec: dict
    fill: dict = field(default_factory=dict)


@dataclass
class Cols:
    left: list
    right: list
    ratio: tuple = (2, 1)


def html_of(parts) -> str:
    """The HTML in a list of parts, charts left out (for tests and the requirements check)."""
    out = []
    for p in parts:
        if isinstance(p, str):
            out.append(p)
        elif isinstance(p, Cols):
            out.append(html_of(p.left) + html_of(p.right))
    return "".join(out)


_NOTE = re.compile(r'<p class="dh-note">(.*?)</p>', re.S)


def _long_notes(html_text: str) -> str:
    """A note long enough to run five lines or more flows in two columns on a wide screen: short lines, no empty
    right half (owner, 21 Nov 2026: "Why paragraph and title are having blank space?")."""
    return _NOTE.sub(lambda m: (f'<p class="dh-note dh-note-long">{m.group(1)}</p>'
                                if len(re.sub(r"<[^>]+>", "", m.group(1))) > 380 else m.group(0)), html_text)


def emit(parts) -> None:
    buf: list[str] = []

    def flush():
        if buf:
            st.html(f'<div class="dh">{_long_notes("".join(buf))}</div>')
            buf.clear()
    for p in parts:
        if isinstance(p, str):
            buf.append(p)
        elif isinstance(p, Chart):
            flush()
            dc.render(p.kind, p.spec, **p.fill)
        elif isinstance(p, Cols):
            flush()
            a, b = st.columns(list(p.ratio), gap="medium")
            with a:
                emit(p.left)
            with b:
                emit(p.right)
    flush()


END = '<div class="dh-end"></div>'


def how(what: str, read: str, head: list[str], rows: list[list[str]]) -> str:
    """Under every chart: what it is, how to read it, and its table (agreed 20 Nov, tipsheet pattern)."""
    from src.ui.formats import date as _date

    def cell(c):
        t = _date(c)                                   # "2026-11-13" -> "13 Nov 2026" (S173 rule 3)
        return t.replace("-", "−", 1) if t.startswith("-") else t

    def _td(c):
        t = cell(c)
        # A date stays on one line: "20 Nov 2026" wrapped to three at 412 px (S173 rule 3 keeps the year:
        # these tables span years, so "20 Nov" alone would be ambiguous).
        return f'<td style="white-space:nowrap">{e(t)}</td>' if t != str(c) and _date(c) == t else f"<td>{e(t)}</td>"
    table = ('<table class="dh-tab dh-tab-s"><thead><tr>' + "".join(f'<th scope="col">{e(h)}</th>' for h in head)
             + "</tr></thead><tbody>" + "".join("<tr>" + "".join(_td(c) for c in r) + "</tr>" for r in rows)
             + "</tbody></table>")
    body = f'<p><b>What it is</b>{e(what)}</p><p><b>How to read it</b>{e(read)}</p>'
    return (f'<div class="dh-how"><div class="dh-how-b dh-how-wide">{body}</div>'
            f'<details class="dh-how-narrow"><summary>What it is · how to read it</summary><div class="dh-how-b">{body}</div></details>'
            f'<details><summary>Show the table</summary><div class="dh-scroll dh-how-t">{table}</div></details></div>')


def _read_csv(path: Path, **kw) -> pd.DataFrame | None:
    try:
        return pd.read_csv(path, **kw)
    except (OSError, ValueError):
        return None


def sg(v: float | None, digits: int = 1, unit: str = "") -> str:
    if v is None or (isinstance(v, float) and not np.isfinite(v)):
        return "–"
    return f"{_fmt.signed(float(v), digits)}{unit}"   # half away from zero (glossary 12)


def cr(v: float | None) -> str:
    """₹ crore in Indian words: ₹1.15 lakh Cr, ₹38,000 Cr. The lakh-crore form stays (owner, 22 Nov 2026: the
    whole-crore "₹1,15,000 Cr" was "completely opposite to what I asked")."""
    if v is None:
        return "–"
    sign = "+" if v > 0 else "−" if v < 0 else ""
    a = abs(float(v))
    if a >= 100000:
        return f"{sign}₹{a / 100000:.2f} lakh Cr"
    if a >= 1000:
        return f"{sign}₹{round(a / 1000) * 1000:,.0f} Cr"
    return f"{sign}₹{a:,.0f} Cr"


def tone(v: float | None) -> str:
    return "" if v is None else ("dh-up" if v > 0 else "dh-down" if v < 0 else "")


# ── Inputs (cached on the price frame's fingerprint) ────────────────────────


@st.cache_data(show_spinner=False, ttl=3600)
def _history_inputs(key: str, _adj_close: pd.DataFrame, _rank_df: pd.DataFrame, symbols: tuple,
                    pit: bool = True) -> dict:
    """The costly reads: breadth series and rank snapshots."""
    from src.engine import market_questions as mq
    from src.engine.rank_history import snapshots

    px = _adj_close.sort_index()
    as_of = px.index[-1]
    dates = {k: di.on_or_before(px.index, d) for k, d in di.trail_dates(as_of).items()}
    ranked = [s for s in _rank_df["Symbol"] if s in px.columns]
    out: dict = {"dates": dates}
    from src.engine import pit_breadth
    # The members-of-the-day history is the 750's (data/breadth_history.csv): joined only under
    # the 750's own live line, never under another system's universe (S194 L4, 23 Nov 2026).
    past = pit_breadth.load("total_market") if pit else None
    for span in (50, 200):
        out[f"above_{span}"] = pit_breadth.splice(mq._share_above_ema(px[ranked], span), past, f"above_{span}")
    snap = snapshots(px, [d for d in dates.values() if d is not None])
    key_of = {d: k for k, d in dates.items() if d is not None}
    from src.engine.exit_watch import qualified_ranks
    qnow = qualified_ranks(_rank_df)       # today: the ranking the plan trades on (S154)
    out["rank_table"] = (snap.assign(when=snap["date"].map(key_of))
                         .pivot_table(index="symbol", columns="when", values="rank", aggfunc="first"))
    if "now" in out["rank_table"]:
        out["rank_table"]["now"] = out["rank_table"].index.map(lambda s: qnow.get(s))
    # The same trail Portfolio and Actions show: one function, one definition (S151, S154).
    out["ranks"] = di.rank_trails(px, symbols, snap, now=qnow)[1]
    return out


# ── Sections ────────────────────────────────────────────────────────────────


def _kicker(n: str, text: str) -> str:
    return f'<p class="dh-kick">{e(n)} · {e(text)}</p>'


def _kpis(items: list[tuple[str, str, str, str, str, str]]) -> str:
    """(label, value, value tone, status, status tone, sub)."""
    cells = "".join(
        f'<div class="dh-kpi"><span class="dh-k-l">{e(l)}</span><span class="dh-k-v {vt}">{e(v)}</span>'
        f'<span class="dh-k-s {st_}">{e(s)}</span><span class="dh-k-sub">{e(sub)}</span></div>'
        for l, v, vt, s, st_, sub in items)
    return f'<div class="dh-kpis">{cells}</div>'


def _bars(rows: list[tuple[str, float, str, bool]], scale: float) -> str:
    out = []
    for name, v, cls, bold in rows:
        w = max(0.0, min(100.0, v / scale * 100)) if scale else 0
        b = " dh-b" if bold else ""
        out.append(f'<div class="dh-bar"><span class="dh-bar-n{b}">{e(name)}</span>'
                   f'<span class="dh-bar-t"><span class="dh-bar-f {cls}" style="width:{w:.0f}%"></span></span>'
                   f'<span class="dh-bar-v{b}">{e(sg(v, unit="%"))}</span></div>')
    return "".join(out)


def section_book(bm: di.BookMonth, since: float | None, since_mkt: float | None, as_of: pd.Timestamp,
                 prev: dict | None = None, begun: pd.Timestamp | None = None) -> list:
    """`prev`: {"label", "market", "book", "momentum": {key: %}} for the last finished month."""
    gap = None if bm.book_mtd is None or bm.market_mtd is None else bm.book_mtd - bm.market_mtd
    mom = bm.momentum_mtd
    lo, hi = (min(mom.values()), max(mom.values())) if mom else (None, None)
    style_lag = gap is not None and gap < 0 and hi is not None and bm.book_mtd >= hi - 0.05
    month = f"{as_of:%B}"
    if style_lag:
        title = f'{month}’s lag is <span class="dh-down">momentum’s</span>, not <span class="dh-up">this book’s</span>.'
    elif gap is not None and gap >= 0:
        title = f'The book is <span class="dh-up">{e(sg(gap))} points ahead</span> of Nifty Total Market so far in {month}.'
    else:
        title = f'The book is <span class="dh-down">{e(sg(gap))} points behind</span> Nifty Total Market so far in {month}.'
    up = lambda v: f"{'up' if v >= 0 else 'down'} {abs(v):.1f}%"  # noqa: E731
    lede = ""
    if mom and bm.market_mtd is not None and bm.book_mtd is not None:
        n = {5: "All five", 4: "All four"}.get(len(mom), f"All {len(mom)}")
        lede = f"Nifty Total Market is {up(bm.market_mtd)}. {n} NSE momentum indices are up {lo:.1f} to {hi:.1f}%; the book, {up(bm.book_mtd)}, "
        lede += "is level with the best of them." if bm.book_mtd >= hi - 0.05 else ("is ahead of them." if bm.book_mtd > hi else "is within their range.")
        if style_lag:
            lede += " What lagged is the style, not the stock picking."
    level = bm.level_with_momentum
    kp = _kpis([
        (f"The book, month so far · {as_of:%b}", sg(bm.book_mtd, unit="%"), "",
         f"{_fmt.fixed(abs(gap), 1)} pts {'behind' if gap < 0 else 'ahead of'} Nifty Total Market" if gap is not None else "",
         "dh-down" if gap is not None and gap < 0 else "dh-up", f"Nifty Total Market {sg(bm.market_mtd, unit='%')}"),
        ("Momentum indices matched or beaten", f"{bm.ahead_of_momentum + level} of {len(mom)}",
         "dh-up" if (bm.ahead_of_momentum + level) * 2 > len(mom) else "",
         f"Ahead of {bm.ahead_of_momentum}" + (f", level with {level}" if level else ""), "dh-up",
         f"They rose {lo:.1f} to {hi:.1f}%" if mom else ""),
        (f"{_fmt.since(begun)}, after costs" if begun is not None else "The record, after costs", sg(since, unit="%"), tone(since),
         f"{sg(since - since_mkt)} pts on Nifty Total Market" if since is not None and since_mkt is not None else "",
         tone(None if since is None or since_mkt is None else since - since_mkt),
         f"Nifty Total Market {sg(since_mkt, unit='%')}"),
        ("Months ahead of Nifty Total Market", f"{bm.months_ahead} of {bm.months}", "dh-up" if bm.months_ahead * 2 > bm.months else "",
         "Behind in " + ", ".join(bm.behind_months) if bm.behind_months else "Ahead every month", "dh-muted",
         "The month in progress counts as it stands"),
    ])
    order = sorted(mom, key=lambda k: -mom[k])
    rows = [{"name": "Nifty Total Market", "sub": "NSE, about 750 stocks"}, {"name": "The book", "sub": "After costs", "bold": True}]
    rows += [{"name": MOMENTUM_NAMES[k], "sub": "NSE"} for k in order]
    cur = [bm.market_mtd, bm.book_mtd] + [mom[k] for k in order]
    periods, values = [{"key": "cur", "label": f"{month} so far"}], {"cur": [_r2(v) for v in cur]}
    if prev:
        periods.append({"key": "prev", "label": prev["label"]})
        values["prev"] = [_r2(prev.get("market")), _r2(prev.get("book"))] + [_r2(prev["momentum"].get(k)) for k in order]
    every = [v for vs in values.values() for v in vs if v is not None] + [0.0]
    step = 0.25
    lo_s, hi_s = np.floor(min(every)) - 0.5, np.ceil(max(every)) + 0.5
    n = int(round((hi_s - lo_s) / step))
    axis = [t for t in range(int(np.ceil(lo_s)), int(np.floor(hi_s)) + 1) if t % 2 == 0]
    spec = {"periods": periods, "values": values, "rows": rows, "lo": float(lo_s), "hi": float(hi_s), "step": step,
            "axis": axis, "market": 0, "book": 1}
    table_rows = [[r["name"]] + [("–" if values[p["key"]][i] is None else f'{sg(values[p["key"]][i])}%') for p in periods]
                  for i, r in enumerate(rows)]
    return [
        f'<div class="dh-sec">{_kicker("1", f"The book, month so far · {as_of:%b}")}<h1 id="s-month" class="dh-h1">{title}</h1>'
        f'<p class="dh-lede">{e(lede)}</p>{kp}<div class="dh-cap"><b>The month</b><span>to {as_of:%-d %b}, price return</span></div></div>',
        Chart("month", spec, {"note": "Each line is 0.25%; filled lines right of the dark zero line are a gain, left a fall.", "n": n}),
        how("Each row is a return for the month: Nifty Total Market (about 750 stocks), the model book, "
            "and NSE’s momentum indices. Switch to the last finished month to compare.",
            "Right of the zero line is a gain, left a fall. The book against the momentum rows tells whether the picking or the "
            "style lagged; against the Nifty Total Market row, how far momentum is behind.",
            [""] + [p["label"] for p in periods], table_rows),
        f'<p class="dh-note">{_fmt.PTS_NOTE} The yardstick is Nifty Total Market, about 750 stocks. January to October stay as recorded '
        'against the Nifty 500; the Nifty Total Market comparison is worked out beside them. The book is after costs; indices are '
        'price returns. The book’s month-by-month record is on Portfolio.</p>' + END]


def _r2(v):
    return None if v is None or not np.isfinite(v) else round(float(v), 2)


def _turnover_html(t: di.Turnover | None, industry: pd.Series) -> str:
    if t is None or not t.climbers:
        return ""
    ind = lambda s: e(SHORT.get(str(industry.get(s, "")), str(industry.get(s, ""))))  # noqa: E731
    rk = lambda v, cls="dh-muted": f'<td class="dh-num {cls}">{"–" if v is None else f"#{v}"}</td>'  # noqa: E731
    rows = "".join(f'<tr><th scope="row">{e(s)}<span class="dh-sub">{ind(s)}</span></th>{rk(a)}{rk(b)}{rk(c, "dh-b dh-up")}</tr>'
                   for s, a, b, c in t.climbers)
    if t.fallers:
        rows += '<tr><th scope="row" colspan="4" class="dh-sub dh-tr-g">Fell out</th></tr>'
        rows += "".join(f'<tr><th scope="row">{e(s)}<span class="dh-sub">{ind(s)}</span></th><td></td>{rk(b)}'
                        f'<td class="dh-num dh-b dh-down">{"Out" if c is None else f"#{c}"}</td></tr>' for s, b, c in t.fallers)
    say = []
    up_ind = pd.Series([industry.get(s) for s, *_ in t.climbers]).value_counts()
    if len(up_ind) and up_ind.iloc[0] >= 2:
        say.append(f"{SHORT.get(up_ind.index[0], up_ind.index[0])} are climbing in, {up_ind.iloc[0]} of the {len(t.climbers)}")
    dn_ind = pd.Series([industry.get(s) for s, *_ in t.fallers]).value_counts()
    if len(dn_ind) and dn_ind.iloc[0] >= 2:
        say.append(f"{dn_ind.iloc[0]} of the {len(t.fallers)} falling out are {SHORT.get(dn_ind.index[0], dn_ind.index[0])} names")
    line = f'<p class="dh-lede-s">{e("; ".join(say))}.</p>' if say else ""
    return (f'<div><div class="dh-lab">Leadership turnover · {t.new} of today’s top {t.top} were not there a month ago</div>'
            '<table class="dh-tab dh-tab-s"><thead><tr><th scope="col">Rising in</th><th scope="col" class="dh-num">3M ago</th>'
            f'<th scope="col" class="dh-num">1M ago</th><th scope="col" class="dh-num">Now</th></tr></thead><tbody>{rows}</tbody></table>{line}</div>')


def _rank_trail_svg(t: list[int | None], cut: int) -> str:
    """Three ranks as a small line, higher a better rank; the cut-off dashed; "Out" hollow at the floor."""
    W, H = 88, 30
    y = lambda r: H - 3 if r is None else 3 + (min(r, 90) - 1) / 89 * (H - 8)  # noqa: E731
    x = lambda i: 6 + i * (W - 12) / 2  # noqa: E731
    now, before = t[2], t[1]
    c = ("var(--c-down)" if now is None or now > cut else "var(--c-up)" if before is None or now < before
         else "var(--c-caution)")
    pts = [(x(i), y(r)) for i, r in enumerate(t)]
    dots = "".join(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="{3.5 if i == 2 else 2.5}" '
                   f'style="fill:{"var(--c-white)" if t[i] is None else c};stroke:{c};stroke-width:1.5"></circle>' for i, (px, py) in enumerate(pts))
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">'
           f'<line x1="2" x2="{W - 2}" y1="{y(cut):.1f}" y2="{y(cut):.1f}" style="stroke:var(--c-muted);stroke-dasharray:2 3"></line>'
           f'<polyline points="{" ".join(f"{px:.1f},{py:.1f}" for px, py in pts)}" '
           f'style="fill:none;stroke:{c};stroke-width:2;stroke-linejoin:round"></polyline>{dots}</svg>')
    # st.html's cleaner drops inline SVG, so the trail is an image with the theme's colours written in.
    from urllib.parse import quote

    from src.ui.tokens import resolve
    words = " → ".join("Out" if r is None else f"#{r}" for r in t)
    return (f'<img class="dh-trail" width="{W}" height="{H}" alt="Rank trail {words}" '
            f'src="data:image/svg+xml,{quote(resolve(svg))}">')


def section_rebalance(a: pd.DataFrame, plan, ranks: dict, ind_state: dict, check, fill, n_sess: int,
                      rules: Rules, n_hold: int, churn: str, results_line: str, turnover: str = "",
                      dates: dict | None = None) -> list:
    rows = a[a["status"] != UNKNOWN].copy()
    rows["room"] = rows.apply(lambda r: least_room(r, rules), axis=1)
    rows = rows.sort_values("room", na_position="first").head(AT_RISK_ROWS)
    sells, watch = len(plan.sells), int(a[a["Symbol"].isin(plan.holds)]["status"].eq(WATCH).sum())
    worst = None
    for sym in rows["Symbol"]:
        t = ranks.get(sym, [None, None, None])
        if t[1] is not None and t[2] is not None and t[2] - t[1] >= 15 and t[2] <= rules.buffer_n:
            worst = (sym, t[1], t[2])
            break
    head = (f'<span class="dh-down">{sells} sell{"s" if sells != 1 else ""}</span>, '
            f'<span class="dh-up">{len(plan.buys)} buy{"s" if len(plan.buys) != 1 else ""}</span>'
            + (f', <span class="dh-watch">{watch} on the edge</span>' if watch else "")
            + f", {n_sess} session{'s' if n_sess != 1 else ''} away.")
    if worst:
        head += (f' <span class="dh-watch">{e(worst[0])} fell from #{worst[1]} to #{worst[2]} in a month</span>, '
                 f'{rules.buffer_n - worst[2]} places from the cut-off.')
    sold = a[a["Symbol"].isin(plan.sells)]
    shared_ind = [i for i, n in sold["Industry"].value_counts().items() if n >= 2] if "Industry" in sold else []
    for ind in shared_ind:
        n_ind = int((a["Industry"] == ind).sum())
        if n_ind == int((sold["Industry"] == ind).sum()) and ind_state.get(str(ind), ("",))[0] == "behind on both":
            word = "both" if n_ind == 2 else f"all {n_ind}"
            head = head[:-1] + f'; <span class="dh-down">{word} {e(str(ind))} holdings go</span> as their sector slides.'
            break
    body = []
    for _, r in rows.iterrows():
        sym = r["Symbol"]
        status = "Sell" if sym in plan.sells else ("Watch" if r["status"] == WATCH else "Clear")
        stc = {"Sell": "dh-down", "Watch": "dh-watch", "Clear": "dh-up"}[status]
        t = ranks.get(sym, [None, None, None])
        word, wt = di.rank_trail_word(t, rules.buffer_n)
        rk = "".join(f'<span class="dh-num dh-rk{" dh-muted" if x is None else ""}">{"Out" if x is None else f"#{x}"}</span>' for x in t)
        ind = str(r.get("Industry") or "")
        state, st_tone = ind_state.get(ind, ("", ""))
        body.append(
            f'<div class="dh-hold"><div><a class="dh-mono dh-b dh-sym" href="{e(stock_href(str(sym)))}" target="_self">{e(sym)}</a><span class="dh-sub">{e(ind)}'
            + (f' · <span class="{st_tone}">{e(state)}</span>' if state else "") + '</span></div>'
            f'<div class="{"dh-muted" if status == "Clear" else ""}">{e(str(r["why"]) if r["status"] == SELL else nearest_rule(r, rules))}'
            f'<span class="dh-sub dh-b {TONE[wt]}">{e(word)}</span></div>{rk}{_rank_trail_svg(t, rules.buffer_n)}'
            f'<span class="dh-badge {stc}">{status}</span></div>')
    buys = "".join(f'<span class="dh-chip">{e(s)}</span>' for s in plan.buys) or '<span class="dh-muted">None</span>'
    nxt = " · ".join(e(s) for s in plan.next_in_line) or "–"
    others = n_hold - len(rows)
    last = str(rows["Symbol"].iloc[-1]) if len(rows) else ""
    d3, d1 = (dates or {}).get("3m"), (dates or {}).get("1m")
    when = f" (3M ago is {d3:%-d %b}, 1M ago {d1:%-d %b})" if d3 is not None and d1 is not None else ""
    return [(f'<div class="dh-sec">{_kicker("2", f"What happens on {check:%-d %b}")}'
            f'<h2 id="s-next" class="dh-h2">{head}</h2><div class="dh-cols"><div class="dh-col2">'
            '<div class="dh-hold dh-hold-h"><span>Holding, least room first</span><span>Nearest rule · rank trend</span>'
            '<span class="dh-num">Rank 3M ago</span><span class="dh-num">1M ago</span><span class="dh-num">Now</span>'
            '<span>Rank trail</span><span class="dh-num">If unchanged</span></div>' + "".join(body)
            + f'<p class="dh-note">Checked at the {check:%a %-d %b} close, filled {fill:%a %-d %b}.'
            + (f' The other {others} holdings have more room than {e(last)}.' if others > 0 and last else "")
            + f' Rank: how today’s rule ranks the stock on that day{when}, among the stocks passing the filters then, on '
            'today’s clean prices; it can differ by a place or two from what the site showed that day. “Out”: it did not '
            f'pass the filters. The trail: higher is a better rank, the dashed line is the cut-off at #{rules.buffer_n}, a '
            'hollow point is “Out”. Under each name, its sector against all ranked stocks.</p></div>'
            f'<div class="dh-col1"><div class="dh-lab">Would be bought</div><div class="dh-chips">{buys}</div>'
            f'<p class="dh-sub">Next in line: <span class="dh-mono">{nxt}</span></p>'
            f'<div class="dh-callout">{e(churn)} {e(results_line)}</div>{turnover}'
            f'<a class="dh-link" href="{e(page_href("actions"))}" target="_self">The plan, share by share, on Actions →</a>'
            '</div></div></div>' + END)]


def _month_end_count(passed: list[dict], average) -> str:
    """", at the last month-end, which the tests read, 3 and 2": said only when
    the month-end readings give a different count from today's (staleness
    audit, 21 Nov 2026)."""
    if average is None or not passed:
        return ""
    now = sum(x["like"] >= average for x in passed if x["like"] is not None)
    me = [x.get("like_me") for x in passed]
    if any(v is None for v in me):
        return ""
    good = sum(v >= average for v in me)
    if good == now:
        return ""
    return f"; at the last month-end, which the tests read, {good} and {len(me) - good}"


def _trail_cell(vals: list[float | None], fmt) -> list[str]:
    """Three cells: 3 months ago, 1 month ago, now."""
    return ["–" if v is None else fmt(v) for v in vals]


def _lag_note(lag) -> str:
    """How long this ranking's momentum can lag, from its own record (owner, 21 Nov 2026, from the Indices review):
    NSE's momentum indices are large and mid caps, the book mostly small and micro."""
    if lag is None:
        return ""
    txt = f"Against the Nifty 500 the top 100 is {abs(lag.now):.1f}% below its {lag.best:%B %Y} best (month-ends to {lag.as_of:%B %Y})."
    if lag.episodes:
        d = lag.episodes[0]
        txt += (f" Its deepest fall since 2010 was {abs(d.depth):.1f}%, {d.peak:%B %Y} to {d.low:%B %Y}, "
                + ("not yet made back" if d.recovered is None else f"made back by {d.recovered:%B %Y}"))
        prev = next((x for x in lag.episodes[1:] if x.months_to_recover is not None), None)
        if prev is not None:
            txt += (f"; the one before, {abs(prev.depth):.1f}% in {prev.peak.year + (prev.peak.month == 12)}–{str(prev.low.year)[2:]}, "
                    f"took {prev.months_to_recover} months from its peak to recover")
        txt += "."
    txt += " A description, not a forecast: the recovery time rests on one earlier fall. "
    return (f'<p class="dh-note">{e(txt)}<a class="dh-link" href="{e(page_href("indices"))}" target="_self">'
            "NSE’s momentum indices, style by style, on Indices →</a></p>")


def section_momentum(lead, streak: int, signals: list[dict], average: float | None, lead_bars: dict | None = None,
                     lag: di.MomentumLag | None = None) -> list:
    tested = [x for x in signals if x["test"] is not None]
    passed = [x for x in tested if x["test"]["passed"]]
    better = sum(x["like"] is not None and average is not None and x["like"] >= average for x in passed)
    long_ok = lead and lead[0][1] is not None and lead[0][1] > 0
    head = ("Ahead over a year" if long_ok else "Behind over a year")
    head += (f', but <span class="dh-down">{streak} losing month{"s" if streak != 1 else ""} in a row</span>.'
             if streak >= 2 else ".")
    if tested:
        head += (f' We tested each signal on our own record since 2010: <span class="dh-up">{len(passed)} pass</span>, '
                 f'<span class="dh-muted">{len(tested) - len(passed)} {"is" if len(tested) - len(passed) == 1 else "are"} not confirmed</span>'
                 + (', one of them a reading the page used to count for momentum. ' if any(
                     x["key"] == "participation_jump" and x["test"] and not x["test"]["passed"] for x in signals) else '. ')
                 + f'On today\'s readings <span class="dh-up">{better} point{"s" if better == 1 else ""} to a stronger month</span>, '
                 f'<span class="dh-down">{len(passed) - better} to a weaker one</span>'
                 + _month_end_count([x for x in passed if x["like"] is not None], average) + '.')
    tiles = []
    for when, v, note in lead:
        pos = 0 if v is None or v <= 0 else min(v / 13 * 100, 100)
        neg = 0 if v is None or v >= 0 else min(-v / 13 * 100, 100)
        tiles.append(f'<div class="dh-tile"><span class="dh-sub">{e(when)}</span><span class="dh-big {tone(v)}">{e(sg(v))}</span>'
                     f'<span class="dh-dbar"><span><i class="dh-f-neg" style="width:{neg:.0f}%"></i></span>'
                     f'<span><i class="dh-f-pos" style="width:{pos:.0f}%"></i></span></span><span class="dh-sub">{e(note)}</span></div>')
    rows = []
    for x in signals:
        t, like = x["test"], x["like"]
        d = None if like is None or average is None else like - average
        w = 0 if d is None else min(abs(d) / 1.5 * 100, 100)
        cls = "dh-muted" if d is None else ("dh-up" if d >= 0 else "dh-down")
        reads = "Not used" if d is None else ("Better than usual" if d >= 0 else "Worse than usual")
        if t is None:
            badge, why = '<span class="dh-ev dh-ev-c">Not tested</span>', ""
        elif t["passed"]:
            badge = '<span class="dh-ev dh-ev-t">Pass</span>'
            why = f'{sg(t["on"])} on vs {sg(t["off"])} off; both halves; on in {t["n_on"]} of {t["n"]} months'
        else:
            badge = '<span class="dh-ev dh-ev-c">Not confirmed</span>'
            why = f'{sg(t["on"])} on vs {sg(t["off"])} off, {t["n_on"]} of {t["n"]} months; ' + (
                "the halves disagree" if t["halves"][0] * t["halves"][1] < 0 else "under the 1-point bar")
        rows.append(
            f'<tr class="{"dh-faint" if d is None else ""}"><th scope="row">{e(x["name"])}<span class="dh-sub">{e(x["sub"])}</span></th>'
            + "".join(f'<td class="dh-num{" dh-muted" if k < 2 else " dh-b"}">{e(v)}</td>' for k, v in enumerate(x["cells"]))
            + f'<td class="dh-hist">{e(x.get("hist", ""))}</td>'
            + f'<td class="dh-num dh-b {cls}">{"–" if like is None else e(sg(like))}</td>'
            f'<td><span class="dh-dbar"><span><i class="dh-f-neg" style="width:{w if d is not None and d < 0 else 0:.0f}%"></i></span>'
            f'<span><i class="dh-f-pos" style="width:{w if d is not None and d >= 0 else 0:.0f}%"></i></span></span>'
            f'<span class="dh-sub dh-b {cls}">{reads}</span></td>'
            f'<td>{badge}<span class="dh-sub">{e(why)}</span></td><td>{e(x["flip"]) if d is not None else ""}</td></tr>')
    avg = "–" if average is None else sg(average)
    parts = [f'<div class="dh-sec">{_kicker("3", "Is momentum still working?")}<h2 id="s-mom" class="dh-h2">{head}</h2>'
             '<div class="dh-sub">This ranking’s top 100 against the Nifty 500, points, longest window first</div>'
             f'<div class="dh-tiles">{"".join(tiles)}</div>'
             '<p class="dh-note">Tiles: the top 100 of this site’s ranking against the Nifty 500, the history’s benchmark, '
             'over 12 months, the last 3 months and the last finished month; the month so far is NSE’s Nifty500 Momentum 50 '
             'against Nifty Total Market.</p>'
             + ('<div class="dh-cap"><b>Momentum’s lead, every month</b><span>top 100 less the Nifty 500, points</span></div>'
                if lead_bars else '')
             + (f'<p class="dh-note dh-band-note">{e(lead_bars["band_note"])}</p>' if lead_bars and lead_bars.get("band_note") else '')
             + _lag_note(lag) + '</div>']
    if lead_bars:
        parts += [Chart("bars", lead_bars, {"label": "Momentum’s lead over the Nifty 500 by month"}),
                  how("Each month, the return of the 100 best-ranked stocks less the Nifty 500’s, in points. The last bar is the "
                      "month so far, from Nifty500 Momentum 50 against Nifty Total Market.",
                      "Bars above the line are months momentum led. A run below it is momentum out of favour; whether the "
                      "year-long lead holds matters more than one month.",
                      ["Month", "Lead, pts"], [[m, sg(v)] for m, v in zip(lead_bars["full"][::-1], lead_bars["values"][::-1])])]
    parts.append(
        f'<div class="dh-sec dh-sec-cont"><div class="dh-cap"><b>What today’s readings have meant for next month</b><span>Momentum’s next-month lead after '
        f'months like this, points · all months since 2010 average {e(avg)}</span></div>'
        '<div class="dh-scroll"><table class="dh-tab dh-tab-sig"><thead><tr><th scope="col">Signal · when it is on</th>'
        '<th scope="col" class="dh-num">3M ago</th><th scope="col" class="dh-num">1M ago</th><th scope="col" class="dh-num">Now</th>'
        '<th scope="col">In its own history</th>'
        f'<th scope="col" class="dh-num">Months like this</th><th scope="col" class="dh-w-bar">Against the {e(avg)} average</th>'
        '<th scope="col">Our test</th><th scope="col">What would flip it</th></tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table></div>'
        '<p class="dh-note"><b>The test, fixed before looking:</b> a signal passes if momentum’s next-month lead (the '
        'top 100 of this ranking less the Nifty 500) differs by at least 1 point between months when it is on and off, '
        'in the direction it claims, and in both halves of the record. Failures stay on the page. The signals overlap, '
        'so their bars are not added into one score. Breadth and participation count the Nifty 500’s members on each '
        'date, leavers included. In-sample: the thresholds were set on the record they are tested on. '
        'Describing is not forecasting; the live rules stay fully invested whatever this says.</p></div>' + END)
    return parts


def section_flows(f: di.Flows, ev: di.FlowEvidence | None, dii, share: tuple[float, float] | None = None,
                  bars: dict | None = None, compare: tuple[float, float, int] | None = None,
                  universe: str = "750") -> list:
    rec = f.month_rank == 1
    head = (f'Foreign investors have bought <span class="dh-up">{e(cr(f.mtd).lstrip("+"))} so far in {f.as_of:%B}'
            + (f', the most in any month since {f.months_in_record and e(_first_year(f))}</span>' if rec else '</span>')
            + (f', after selling {e(cr(-f.before).lstrip("+"))} over the 11 months before.' if f.before < 0 else '.'))
    if dii and dii[2] < 0:
        head += ' <span class="dh-down">Domestic institutions are selling into it.</span>'
    kp = [(f"Foreign, month so far · {f.as_of:%b}", cr(f.mtd), tone(f.mtd),
           "Record: largest month since " + _first_year(f) if rec else f"Rank {f.month_rank} of {f.months_in_record} months",
           "dh-up" if rec else "dh-muted",
           f"Previous high {cr(f.prior_record[1]).lstrip('+')}, {f.prior_record[0]}" if f.prior_record and rec else ""),
          ("Foreign, last 20 sessions", cr(f.last20), tone(f.last20),
           "Highest 20-day total since " + _first_year(f) if f.last20_is_record else "", "dh-up",
           f"{f.streak} sessions of net buying in a row" if f.streak >= 3 else ""),
          ("Foreign, the 11 months before", cr(f.before), tone(f.before),
           f"Net sellers in {f.before_selling_months} of 11 months", "dh-down" if f.before_selling_months > 5 else "dh-muted",
           f"{f.as_of:%B} so far has bought back {_fmt.fixed(f.mtd / -f.before * 100, 0)}%" if f.before < 0 and f.mtd > 0 else "")]
    if share is not None:
        kp.insert(1, (f"Against the {universe}’s market value", sg(share[0], 1, "%"), tone(share[0]),
                      f"Bought so far in {f.as_of:%B}" if share[0] > 0 else f"Sold so far in {f.as_of:%B}", tone(share[0]),
                      f"The 11 months before: {'sold' if share[1] < 0 else 'bought'} {abs(share[1]):.1f}% of it"))
    if dii:
        kp.append((f"Domestic institutions, {dii[0]:%-d} to {dii[1]:%-d %b}, {dii[5] if len(dii) > 5 else 'on NSE'}", cr(dii[2]), tone(dii[2]),
                   f"Net sellers on {dii[4]} of {dii[3]} sessions", "dh-down" if dii[4] * 2 > dii[3] else "dh-muted",
                   "Taking the other side of foreign buying" if dii[2] < 0 and f.mtd > 0 else ""))
    evid = ""
    if ev is not None:
        halves = "; ".join(f"{p.replace('-', ' to ')}: {sg(h)} vs {sg(r)}" for p, h, r in ev.halves)
        held = all(h > r for _, h, r in ev.halves)
        evid = (f'<div class="dh-ev-box dh-ev-up"><b class="dh-up">{"Better" if ev.after_heavy > ev.after_rest else "No better"} months for momentum next.</b> '
                f'After the quarter of months with the most foreign buying (₹{ev.threshold:,.0f} Cr or more), momentum beat the '
                f'Nifty 500 the next month by {ev.after_heavy:.1f} points on average, against {ev.after_rest:.1f} after the rest; ahead '
                f'{ev.hit_heavy:.0f}% of the time against {ev.hit_rest:.0f}%. '
                + (f'It held in both halves ({halves}).' if held else f'It did not hold in both halves ({halves}).')
                + f'<span class="dh-ev dh-ev-t">Tested here · {ev.months} months, {ev.heavy_months} heavy, in-sample</span></div>'
                f'<div class="dh-ev-box"><b>No forecast for the Nifty 500.</b> Flows move with the Nifty 500 in the same month '
                f'(correlation {sg(ev.corr_same, 2)}) and say nothing about the next ({sg(ev.corr_next, 2)}).</div>'
                f'<div class="dh-ev-box"><b>{"Not a large-cap story" if ev.large_minus_broad <= 0 else "A large-cap tilt"}.</b> '
                f'In those heavy-buying months the Nifty 50 {"trailed" if ev.large_minus_broad <= 0 else "beat"} the Nifty 500 '
                f'by {abs(ev.large_minus_broad):.1f} points on average.</div>')
    head_html = (f'<div class="dh-sec">{_kicker("4", "Money flows")}<h2 id="s-flow" class="dh-h2">{head}</h2>{_kpis(kp)}</div>')
    left = []
    if bars:
        thr = f", dashed line: a heavy-buying month, ₹{ev.threshold:,.0f} Cr or more" if ev is not None else ""
        left = [f'<div class="dh-cap"><b>Foreign investors, net, each month</b><span>₹ thousand Cr{e(thr)}; teal: domestic institutions on NSE, '
                f'stacked on the same bar (a sale runs down from zero)</span></div>',
                Chart("bars", bars, {"label": "Foreign portfolio investors’ net equity flows by month"}),
                f'<p class="dh-note dh-band-note">{e(bars["band_note"])}</p>' if bars.get("band_note") else "",
                how("Foreign portfolio investors’ net purchases of Indian equity each month, exchange and primary market; in teal, "
                    "domestic institutions’ net purchases on NSE (banks, insurers, mutual funds, pension funds).",
                    "Above the line is net buying. The dashed line starts the top quarter of months since 2016; after such months "
                    "momentum has led the Nifty 500 by more the next month than after the rest.",
                    ["Month", "FPI net, ₹ Cr", "DII net, ₹ Cr"],
                    [[m, f"{v:,.0f}", "–" if not a else f"{a[1]:,.0f}"] for m, v, a in
                     zip(bars["full"][::-1], bars["values"][::-1], (bars.get("also") or [None] * len(bars["values"]))[::-1])])]
    right = (f'<div class="dh-col1"><div class="dh-sub"><b>What heavy foreign buying has meant</b> · {e(ev.first) if ev else ""} to '
             f'{e(ev.last) if ev else ""}</div>{evid}</div>')
    return [head_html, Cols(left, [right], (2, 1)),
            '<p class="dh-note">Foreign: confirmed FPI equity figures, exchange and primary market. Domestic institutions: '
            'trades on NSE to October 2026 (the total for banks, insurers, mutual funds, pension funds and other financial '
            'institutions); from November all exchanges, provisional, once a month is collected from its first session; '
            'a month in progress on NSE alone is banks, insurers and mutual funds to the latest day published.</p>' + END]


def _first_year(f: di.Flows) -> str:
    return f"{f.since:%Y}"


def _shared_html(by_size, typical, book_sizes: dict[str, float] | None = None, universe: str = "750",
                 month: str = "the month") -> tuple[str, str]:
    """(the two tables, a phrase for the heading). The Dashboard draws the left one as a chart (_shared_parts)."""
    phrase, left, right = "", "", ""
    if by_size:
        now = {n: v[2] for n, v in by_size if v[2] is not None}
        hi = max(now, key=now.get) if now else None
        lo = min(now, key=now.get) if now else None
        body = "".join(
            f'<tr><th scope="row">{e(n)}</th>'
            + "".join(f'<td class="dh-num dh-muted">{"–" if x is None else f"{x:.0f}%"}</td>' for x in v[:2])
            + f'<td class="dh-num dh-b{" dh-up" if n == hi else " dh-down" if n == lo else ""}">'
            f'{"–" if v[2] is None else f"{v[2]:.0f}%"}</td></tr>' for n, v in by_size)
        left = ('<div><div class="dh-cap"><b>Is the rally shared?</b><span>Share above the 200D EMA, by NSE size list</span></div>'
                '<table class="dh-tab dh-tab-s"><thead><tr><th scope="col">Size</th><th scope="col" class="dh-num">3M ago</th>'
                f'<th scope="col" class="dh-num">1M ago</th><th scope="col" class="dh-num">Now</th></tr></thead><tbody>{body}</tbody></table>'
                + (f'<p class="dh-lede-s">Now <b class="dh-up">{e(hi)}</b> is the broadest and <b class="dh-down">{e(lo)}</b> the narrowest'
                   + (f', where {held:.0f}% of the book sits.' if (held := (book_sizes or {}).get(BREADTH_TIER.get(lo, ""), 0)) >= 20 else '.')
                   + '</p>' if hi and lo and hi != lo else "") + '</div>')
        if hi == "Nifty 100":
            phrase = ', even as <span class="dh-up">the Nifty 100 is now the broadest of NSE’s size lists</span>'
    if typical:
        f1 = lambda v: "–" if v is None else sg(v)  # noqa: E731
        pc = lambda v: "–" if v is None else f"{v:.0f}%"  # noqa: E731
        lines = [("Nifty Total Market", typical["market"], f1, None), (f"Equal-weighted {universe}", typical["equal_weight"], f1, None),
                 ("Median stock", typical["median"], f1, None), ("Share beating Nifty Total Market", typical["beat_share"], pc, 50)]
        body = "".join(f'<tr><th scope="row">{e(n)}</th>' + "".join(
            f'<td class="dh-num{" dh-b dh-down" if cut is not None and v is not None and v < 30 else ""}">{e(fmt(v))}</td>' for v in vals)
            + '</tr>' for n, vals, fmt, cut in lines)
        b1, ew12, mk12, med12 = (typical["beat_share"][0], typical["equal_weight"][-1], typical["market"][-1], typical["median"][-1])
        say = ""
        if b1 is not None:
            say = (f"Only {b1:.0f}% of the {universe} beat Nifty Total Market over the past month." if b1 < 40
                   else f"{b1:.0f}% of the {universe} beat Nifty Total Market over the past month.")
        if None not in (ew12, mk12, med12) and ew12 > mk12 and med12 < 0:
            say += (f" Over 12 months the equal-weighted {universe} beat it by {ew12 - mk12:.1f} points while <b>the median stock fell "
                    f"{abs(med12):.1f}%</b>: a few big winners lift the average, the field a momentum book picks from.")
        right = (f'<div><div class="dh-cap"><b>The typical stock against Nifty Total Market</b><span>The {e(universe)}, three ways · %</span></div>'
                 '<table class="dh-tab dh-tab-s"><thead><tr><th scope="col"></th>'
                 + "".join(f'<th scope="col" class="dh-num">{m}M</th>' for m in (1, 3, 6, 12))
                 + f'</tr></thead><tbody>{body}</tbody></table><p class="dh-lede-s">{say}</p></div>')
    if not left and not right:
        return "", phrase
    return f'<div class="dh-pair">{left}{right}</div>', phrase


def _shared_parts(by_size, typical, book_sizes, universe: str = "750", month: str = "the month") -> list:
    """Is the rally shared (a chart with its readings) beside the typical stock (a table)."""
    _, phrase = _shared_html(by_size, typical, book_sizes, universe, month)
    right = _shared_html(None, typical, book_sizes, universe, month)[0]
    if not by_size:
        return [right] if right else []
    rows = [[n, None if v[0] is None else round(v[0]), None if v[1] is None else round(v[1]), round(v[2])]
            for n, v in by_size if v[2] is not None]
    now = {r[0]: r[3] for r in rows}
    hi, lo = max(now, key=now.get), min(now, key=now.get)
    month_ago = {r[0]: r[2] for r in rows if r[2] is not None}
    was_best = max(month_ago, key=month_ago.get) if month_ago else None
    held = (book_sizes or {}).get(BREADTH_TIER.get(lo, ""), 0)
    say = ((f"A month ago the {e(was_best)} held up best; now " if was_best and was_best != hi else "Now ")
           + f'<b class="dh-up">{e(hi)} is the broadest</b> and <b class="dh-down">{e(lo)} the narrowest</b>'
           + (f", where {held:.0f}% of the book sits." if held >= 20 else "."))
    left = ['<div class="dh-cap"><b>Is the rally shared?</b><span>share above the 200D EMA, by NSE size list</span></div>',
            Chart("shared", {"rows": rows, "step": 2}, {"step": "2"})]
    # The sentence and explanation sit under the right-hand table, so neither column runs on alone (owner, 20 Nov: no extra white space).
    right_more = [f'<p class="dh-lede-s"><b>Is the rally shared?</b> {say}</p>',
            how("The share of each NSE size list trading above its own 200D EMA.",
                "Above 60% the rally is broad there, below 40% narrow. The triangle marks a month ago.",
                ["Size", "3M ago", "1M ago", "Now"], [[r[0]] + ["–" if x is None else f"{x}%" for x in r[1:]] for r in rows])]
    return [Cols(left, [right] + right_more, (1, 1))]


def section_size(rows, book_sizes: dict[str, float], by_size=None, typical=None, universe: str = "750",
                 month: str = "the month") -> list:
    shared, phrase = _shared_html(by_size, typical, book_sizes, universe, month)
    large = next((p for s, _, p in rows if s == "Large"), [None] * 3)
    midsmall = [x for s, _, p in rows if s in ("Mid", "Small") for x in p if x is not None]
    fail_large = all(x is not None and x <= -3 for x in large)
    level = midsmall and all(abs(x) < 2.5 for x in midsmall)
    ms = book_sizes.get("Mid", 0) + book_sizes.get("Small", 0)
    head = ""
    if fail_large:
        head += (f'<span class="dh-down">Large Cap momentum is failing</span>: {min(-x for x in large):.0f} to '
                 f'{max(-x for x in large):.0f} points behind the Nifty 200 over every window{phrase}. ')
    if level:
        head += f'<span class="dh-up">In Mid Cap and Small Cap it keeps level with its index</span>; that is {ms:.0f}% of this book.'
    head = head or "Momentum within each size, against its own index."
    parents = {sz: p for sz, p, _, _ in di.SIZES}
    moms = {sz: m for sz, _, m, _ in di.SIZES}
    mom_parents = {sz: mp for sz, _, _, mp in di.SIZES}

    def cell(v):
        if v is None:
            return '<td class="dh-num dh-muted">–</td>'
        strong = abs(v) >= 3
        return f'<td class="dh-num {tone(v)}{" dh-hl" if strong else ""}">{e(sg(v))}</td>'

    body = "".join(
        f'<tr><th scope="row">{e(_fmt.size(s))}<span class="dh-sub">{e(SIZE_LABELS[parents[s]])} · '
        f'{e(SIZE_LABELS[moms[s]]) if moms[s] else "no momentum index"}'
        f'{" against the " + e(SIZE_LABELS[mom_parents[s]]) if moms[s] and mom_parents[s] != parents[s] else ""}</span></th>'
        f'<td class="dh-num{" dh-b dh-watch" if book_sizes.get(s, 0) >= 20 else " dh-muted"}">{book_sizes.get(s, 0):.0f}%</td>'
        + "".join(cell(v) for v in vs) + '<td></td>' + "".join(cell(v) for v in prem) + "</tr>" for s, vs, prem in rows)
    strip = "".join(f'<i class="{size_class(k)}" style="width:{v:.0f}%">{e(_fmt.size(k)) + " " + f"{v:.0f}%" if v >= 20 else ""}</i>'
                    for k, v in book_sizes.items())
    return [(f'<div class="dh-sec">{_kicker("5", "Size, and where momentum works")}'
            f'<h2 id="s-size" class="dh-h2">{head}</h2><div class="dh-sub">The book by size, NSE index lists'
            f'{"; Nano Cap and Ultra Nano Cap are our own groups, with no NSE index" if set(book_sizes) - {"Large", "Mid", "Small", "Micro"} else ""}</div>'
            f'<div class="dh-sizebar" role="img" aria-label="The book by size">{strip}</div>'
            '<div class="dh-scroll"><table class="dh-tab"><thead><tr><th scope="col" rowspan="2">Size · its index · its momentum index</th>'
            '<th scope="col" rowspan="2" class="dh-num">Book</th><th scope="colgroup" colspan="3">Size against Nifty Total Market</th><th></th>'
            '<th scope="colgroup" colspan="3">Momentum against its size index</th></tr><tr>'
            + "".join(f'<th scope="col" class="dh-num">{m}M</th>' for m in di.WINDOWS) + '<th></th>'
            + "".join(f'<th scope="col" class="dh-num">{m}M</th>' for m in di.WINDOWS)
            + f'</tr></thead><tbody>{body}</tbody></table></div></div>')] + _shared_parts(by_size, typical, book_sizes, universe, month) + [
            '<p class="dh-note">Size lists and members are NSE’s as of today, so older readings leave out stocks that have '
            'since left them. Points, price returns. Size against Nifty Total Market. Nifty Smallcap250 Momentum Quality 100 also screens '
            'for quality; NSE has no microcap momentum index.</p>' + END]


def section_strong_weak(weights: pd.DataFrame, sectors: pd.DataFrame) -> list:
    """The book's weight by industry status, Sectors' measures only (RRG removed, owner 21 Nov 2026)."""
    s = sectors.set_index("Industry")
    rows = []
    for _, r in weights.iterrows():
        ind = r["Industry"]
        if ind not in s.index:
            continue
        a, b = float(s.loc[ind, "rel_6m"]), float(s.loc[ind, "rel_1m"])
        rows.append((ind, int(r["Holdings"]), float(r["Weight"]), a, b, di.industry_bucket(a, b)))
    tot = {k: sum(x[2] for x in rows if x[5] == k) for k in ("strong", "turning", "weak")}
    weak_names = [x[0] for x in rows if x[5] == "weak"]
    head = (f'<span class="dh-up">{tot["strong"]:.0f}% sits in sectors beating all ranked stocks.</span> '
            f'<span class="dh-down">{tot["weak"]:.0f}% sits in {len(weak_names)} that lag</span>')
    head += "."
    order = {"strong": 0, "turning": 1, "weak": 2}
    srt = sorted(rows, key=lambda x: (order[x[5]], -x[2]))
    segs = [[SHORT.get(x[0], x[0]), x[1], round(x[2], 1), round(x[3], 1), round(x[4], 1), "", x[5]] for x in srt]
    turning = [x for x in srt if x[5] == "turning"]
    desc = {
        "strong": "Ahead of all ranked stocks over six months and one month.",
        "turning": "Ahead on one window only" + (": " + ", ".join(
            f"{SHORT.get(x[0], x[0])} over {'the month' if x[4] > 0 else 'six months'}" for x in turning) + "." if turning else "."),
        "weak": "Behind all ranked stocks on both windows.",
    }
    cards = []
    for k, title, cls in (("strong", "Strong", "up"), ("turning", "Turning", "watch"), ("weak", "Weak", "down")):
        items = [x for x in srt if x[5] == k]
        if not items:
            continue
        body = "".join(
            f'<div class="dh-gc-r"><div class="dh-gc-1"><span><b>{e(SHORT.get(x[0], x[0]))}</b> <span class="dh-muted">· {x[1]} '
            f'holding{"s" if x[1] > 1 else ""}</span></span><b class="dh-mono">{x[2]:.1f}%</b></div>'
            f'<div class="dh-gc-2"><span class="dh-muted">6M · 1M <span class="dh-mono {tone(x[3])}">{e(sg(x[3]))}</span> · '
            f'<span class="dh-mono {tone(x[4])}">{e(sg(x[4]))}</span></span></div>'
            + '</div>' for x in items)
        cards.append(f'<div class="dh-gcard dh-g-{cls}"><div class="dh-gc-h"><h3 class="dh-{cls}">{title}</h3>'
                     f'<b class="dh-{cls} dh-mono">{tot[k]:.1f}%</b></div><p>{e(desc[k])}</p>{body}</div>')
    return [f'<div class="dh-sec">{_kicker("6", "Where the book is strong and weak")}<h2 id="s-book" class="dh-h2">{head}</h2></div>',
            Chart("segbar", {"segs": segs, "totals": {k: round(v, 1) for k, v in tot.items()}}, {"label": "The book by sector status"}),
            how("The book’s weight in each sector, coloured by how that sector stands against all ranked stocks over six "
                "months and one month.", "Blue is ahead on both, amber ahead on one, rust behind on both. The cards give each "
                "sector’s figures.", ["Sector", "Weight", "Status"],
                [[x[0], f"{x[2]:.1f}%", x[6].capitalize()] for x in sorted(segs, key=lambda x: -x[2])]),
            f'<div class="dh-gcards">{"".join(cards)}</div>'
            '<p class="dh-note">Each sector’s stocks, equal-weighted, against all ranked stocks built the same way: 6M · 1M in '
            'points, as on Sectors.</p>' + END]


def _and(names: list[str]) -> str:
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def section_glance(blocks: list[tuple[str, str, list[tuple[str, str, str]]]], breadth: dict | None = None,
                   universe: str = "750", pit: bool = True) -> list:
    cells = "".join(
        f'<div class="dh-gl"><div class="dh-gl-h"><b>{e(t)}</b><a href="{e(href)}" target="_self">{e(lbl)} →</a></div>'
        + "".join(f'<div class="dh-gl-r"><span>{e(k)}</span><span class="dh-mono {c}">{e(v)}</span></div>' for k, v, c in rows)
        + "</div>" for t, (href, lbl), rows in blocks)
    parts = ['<div class="dh-sec"><div class="dh-gl-top"><h2 id="s-glance" class="dh-h3">At a glance</h2>'
             '<span class="dh-sub">Reference figures; the full readings are a page away</span></div></div>']
    if breadth:
        counted = ("counted over the members of each date, leavers included." if pit else
                   "counted over today's members (no members-of-the-day history for this universe).")
        parts += [Chart("breadth", breadth, {"note": "The index and how many stocks carry it",
                                             "label": f"Nifty 500 and the share of the {universe} above their 200D EMA"}),
                  how(f"Top: the Nifty 500. Bottom: the share of the {universe} above their own 200D EMA, {counted}", "When the top line rises while the bottom one falls, fewer stocks are carrying the index.",
                      ["Date", "Nifty 500", "Above 200D EMA"],
                      [[d, f"{n:,.1f}", "–" if a is None else f"{a:.0f}%"] for d, n, a in list(zip(breadth["dates"], breadth["n500"], breadth["a200"]))[::-5]])]
    return parts + [f'<div class="dh-gls">{cells}</div>']


# ── The page ────────────────────────────────────────────────────────────────


def render_home_view(rank_df: pd.DataFrame, adj_close: pd.DataFrame, benchmark_close: pd.Series | None,
                     system: str = "750", volume: pd.DataFrame | None = None) -> None:
    from src.core.config import MODEL_BOOK_CAPITAL
    from src.engine import market_questions as mq
    from src.engine.pipeline import price_fingerprint
    from src.engine.systems import inception, ledger_path
    from src.engine.track_record import load_ledger
    from src.ui import page_kit as kit
    from src.ui.canonical_book import current_book
    from src.ui.views.actions_view import _sessions_between, next_rebalance
    from src.ui.views.portfolio_view import build_portfolio_history

    cfg = TRACK_RECORD_CONFIG
    rules = Rules(buffer_n=int(cfg["buffer_n"]), high_pct=float(cfg["high_pct"]))
    as_of = pd.Timestamp(adj_close.index[-1]) if adj_close is not None and len(adj_close) else pd.Timestamp(ist_now().date())
    st.html(f"<style>{HOME_CSS}</style>")

    with st.spinner("Loading the model book…"):
        book, record = current_book(adj_close, benchmark_close, system)
    symbols = [] if book is None or book.empty else book["Symbol"].tolist()
    if not symbols:
        kit.page_head("Dashboard", f"{_fmt.data_to(as_of)}.")
        kit.note("No model book yet.", "The book forms once the strategy has its price history.")
        return
    meta = (record or {}).get("live_meta") or {}
    ledger = load_ledger(ledger_path(system), inception(system))
    history = build_portfolio_history(record, MODEL_BOOK_CAPITAL, ledger, meta)
    book_mtd = history.get("strategy_mtd")
    book_mtd = None if book_mtd is None or not np.isfinite(book_mtd) else float(book_mtd) * 100
    since = history.get("strategy_total_return")
    since = None if since is None or not np.isfinite(since) else float(since) * 100

    frame = bi.read()
    closes = {k: bi.series(k, frame=frame) for k in bi.SERIES}
    closes["nifty100"] = _nse_close("nifty_100")      # Large = Nifty 100 (owner, 21 Nov 2026), from NSE's daily files
    market = closes[bi.TOTAL_MARKET]
    # Index figures end on one session: the last both prices and indices have. An index
    # without a close for that session reads "–", never the session before (S148).
    idx_end = min(as_of, market.index[-1]) if len(market) else as_of
    closes = {k: di.as_of(v, idx_end) for k, v in closes.items()}
    market = closes[bi.TOTAL_MARKET]
    momentum = {k: closes[k] for k in MOMENTUM_NAMES}
    bm = di.book_month(ledger.get("months", {}), book_mtd, market, momentum, idx_end)
    inc = pd.Period(str(ledger.get("inception", "2026-01")), freq="M").to_timestamp() - pd.Timedelta(days=1)
    since_mkt = di.window_return(market, inc, idx_end)

    a = assess(rank_df, symbols, rules)
    check, fill = next_rebalance(as_of)
    from src.ui.model_plan import model_plan
    plan = model_plan(book, record, rank_df, adj_close, benchmark_close, system, check)   # the same plan as Actions (S154)
    n_sess = _sessions_between(as_of, check)

    key = f"{price_fingerprint(adj_close)}"
    with st.spinner("Reading the trails…"):
        hist = _history_inputs(key, adj_close, rank_df, tuple(symbols), system == SYSTEM_750)
    bench = _read_csv(FILES["bench"], parse_dates=["date"])
    bench = bench.set_index("date").sort_index() if bench is not None else None
    n500 = (pd.to_numeric(bench["nifty500"], errors="coerce").dropna() if bench is not None
            else pd.Series(dtype=float))
    industry = rank_df.set_index("Symbol")["Industry"] if "Industry" in rank_df else pd.Series(dtype=str)
    leaders = mq.leaders_answer(adj_close, industry, n500, None)
    sectors = leaders.sectors if leaders is not None else pd.DataFrame(columns=["Industry", "rel_6m", "rel_1m"])
    ind_state = {}
    for _, r in sectors.iterrows():
        b = di.industry_bucket(float(r["rel_6m"]), float(r["rel_1m"]))
        word = {"strong": "ahead on both", "weak": "behind on both"}.get(
            b, "gaining" if float(r["rel_1m"]) > 0 else "fading")
        ind_state[str(r["Industry"])] = (word, {"strong": "dh-up", "weak": "dh-down"}.get(b, "dh-up" if word == "gaining" else "dh-watch"))

    # 2. churn and results
    from src.engine import results_calendar as rc
    books = (record or {}).get("month_books") or {}
    bought = [int((b["Action"] == "Bought").sum()) for k, b in sorted(books.items())[1:]
              if hasattr(b, "columns") and "Action" in b.columns]
    churn = f"{len(plan.buys)} of {len(symbols)} would change."
    if bought:
        avg = sum(bought) / len(bought)
        churn = (("A light month. " if len(plan.buys) < avg * 0.75 else "")
                 + f"{len(plan.buys)} of {len(symbols)} would change; {avg:.0f} in an average month.")
    bc = rc.for_book(rc.load(), symbols, list(plan.buys), pd.Timestamp(ist_now().date()), fetched=rc.fetched_on())
    results_line = ""
    if bc is not None:
        due = bc.upcoming[pd.to_datetime(bc.upcoming["date"]) <= check] if len(bc.upcoming) else bc.upcoming
        results_line = ("No results are due from the holdings or the buys before the check."
                        if due.empty else f"Results due before the check: {', '.join(due['symbol'].astype(str).unique())}.")

    turnover = _turnover_html(di.leadership_turnover(hist.get("rank_table")), industry)

    # 3. signals, each with its test (S150)
    spreads = _read_csv(FILES["spreads"])
    lead = di.momentum_lead(spreads, closes["nifty500_mom50"], market, idx_end) if spreads is not None else []
    streak = di.losing_streak(spreads, lead[-1][1] if lead else None) if spreads is not None else 0
    nsdl = _read_csv(FILES["nsdl"])
    flows = di.flows_summary(nsdl)
    ev = di.flow_evidence(nsdl, spreads, bench) if flows is not None else None
    dii = _dii_now(_read_csv(FILES["nse_dii"], dtype={"period": str}))
    tests = _load_tests()
    signals = _signals(spreads, n500, idx_end, flows, nifty500_breadth(adj_close, as_of), tests,
                       qualify_now=_qualify_today(adj_close, idx_end))
    average = tests.get("average")

    # 4. flows against the 750's market value
    share = None
    mcap = _read_csv(FILES["mcap"])
    if flows is not None and mcap is not None and {"Symbol", "MarketCap"} <= set(mcap.columns):
        ranked = set(rank_df["Symbol"])
        value_cr = float(pd.to_numeric(mcap[mcap["Symbol"].isin(ranked)]["MarketCap"], errors="coerce").sum()) / 1e7
        share = di.fpi_share_of_value(flows, value_cr)
    # 5. size
    sizes = di.size_table(closes, market, idx_end)
    lists = {}
    for name, files in SIZE_LISTS.items():
        syms = []
        for fn in files:
            f = _read_csv(FILES["lists"] / fn)
            if f is not None and "Symbol" in f:
                syms += f["Symbol"].astype(str).tolist()
        if syms:
            lists[name] = syms
    # The Nifty 1000's other 250 (S194 L3): shown when the system prices nearly all of them
    # (the Nifty 1000), not on a universe that holds a few (the 750 holds none).
    f1000 = _read_csv(FILES["lists"] / "ind_nifty1000_list.csv")
    if f1000 is not None and "Symbol" in f1000:
        nse = {x for v in lists.values() for x in v}
        extra = [x for x in f1000["Symbol"].astype(str) if x not in nse]
        if extra and sum(x in adj_close.columns for x in extra) >= 0.9 * len(extra):
            lists["Nano Cap"] = extra
    by_size = di.size_breadth(adj_close, lists, as_of) if lists else None
    ranked_px = adj_close[[c for c in rank_df["Symbol"] if c in adj_close.columns]]
    typical = di.typical_stock(ranked_px, market, idx_end)
    from src.engine import book_risk as br
    from src.ui.book_series import book_series
    # The book's daily value to today, the series Portfolio draws (S154): the
    # backtest replay alone ends at the last month-end and read −8.1% below the
    # peak on 19 Nov when the book was −3.1%.
    series = book_series(book, record, ledger, rank_df, adj_close, benchmark_close, MODEL_BOOK_CAPITAL)
    eq = series.equity if series is not None else None
    # Exit time on the book's value today, as the Actions basket (it used the ₹1 crore start).
    # Today's weights, Portfolio's Weight column, so "the book by size" is the same "now" as Portfolio and Actions (S154).
    w_now = (series.table.set_index("Symbol")["Weight %"] if series is not None and "Weight %" in series.table
             else book.set_index("Symbol")["Weight %"])
    risk = br.book_risk(w_now, adj_close, n500, eq, volume,
                        float(series.value) if series is not None else MODEL_BOOK_CAPITAL)
    # Volatility and beta as Portfolio shows them: the book's daily series against Nifty Total Market,
    # the same function (S154; the card showed 16.7% and 0.77 from today's weights against the Nifty 500
    # while Portfolio showed 22.7% and 1.0 under the same label, found 21 Nov 2026).
    from src.engine import portfolio_report as pr
    record_risk = (pr.risk(eq, market) or [None])[0] if eq is not None else None
    book_sizes = _book_sizes(risk)

    # 6, 7. industries
    # Today's weights from Portfolio's own table, so the two pages cannot differ.
    tracker = series.table if series is not None else None
    if tracker is not None and not tracker.empty and "Weight %" in tracker:
        book = book.assign(**{"Weight %": book["Symbol"].map(tracker.set_index("Symbol")["Weight %"])})
    weights = (book.assign(Industry=book["Symbol"].map(industry).fillna("–"))
               .groupby("Industry").agg(Weight=("Weight %", "sum"), Holdings=("Symbol", "count"))
               .sort_values("Weight", ascending=False).reset_index())

    # v8 chart inputs (S151)
    prev = _last_month(ledger, market, momentum, idx_end)
    lead_bars = _lead_bars(spreads, lead)
    fpi_bars = _fpi_bars(nsdl, ev, flows, _read_csv(FILES["nse_dii"], dtype={"period": str}))
    compare = _flow_compare(_read_csv(FILES["nse_flows"]), nsdl)
    breadth = _breadth_spec(n500, hist.get("above_200"), idx_end)

    uni = UNIVERSE_SHORT.get(system, "750")
    parts = [_brief(bm, len(plan.sells), check, signals, average, typical, flows, f"{idx_end:%B}", uni)]
    parts += section_book(bm, since, since_mkt, idx_end, prev, inc + pd.Timedelta(days=1))
    parts += section_rebalance(a, plan, hist["ranks"], ind_state, check, fill, n_sess, rules, len(symbols), churn,
                               results_line, turnover, hist.get("dates"))
    parts += section_momentum(lead, streak, signals, average, lead_bars, di.momentum_lag(spreads) if spreads is not None else None)
    if flows is not None:
        parts += section_flows(flows, ev, dii, share, fpi_bars, compare, uni)
    parts += section_size(sizes, book_sizes, by_size, typical, UNIVERSE_SHORT.get(system, "750"), f"{idx_end:%B}")
    parts += section_strong_weak(weights, sectors)
    parts += section_glance(_glance(closes, idx_end, hist, risk, n500, record_risk) + _indices_glance(idx_end), breadth,
                            UNIVERSE_SHORT.get(system, "750"), system == SYSTEM_750)
    # Owner, 20 Nov 2026: the data date only; sources are not shown on the page.
    parts.append(f'<p class="dh-foot">{_fmt.data_to(idx_end)}.</p>')
    emit(parts)


# ── v8 chart inputs ─────────────────────────────────────────────────────────


def _last_month(ledger: dict, market: pd.Series, momentum: dict, as_of: pd.Timestamp) -> dict | None:
    """The last finished month: the market, the book (as recorded) and each momentum index."""
    p = as_of.to_period("M") - 1
    start, end = (p - 1).to_timestamp(how="end").normalize(), p.to_timestamp(how="end").normalize()
    rec = (ledger.get("months") or {}).get(str(p)) or {}
    book = rec.get("strategy")
    out = {"label": f"{p:%B}", "market": di.window_return(market, start, end),
           "book": None if book is None else float(book) * 100,
           "momentum": {k: di.window_return(v, start, end) for k, v in momentum.items()}}
    return out if out["market"] is not None else None


def _lead_bars(spreads: pd.DataFrame | None, lead) -> dict | None:
    """Momentum's lead each completed month since January 2024: the top 100 of the ranking less
    the Nifty 500, one pair for every bar. The month so far was a different pair (Nifty500 Momentum 50
    less Nifty Total Market) and is left to the table above (S193, owner 23 Nov 2026)."""
    if spreads is None or not {"month", "top", "nifty500"} <= set(spreads.columns):
        return None
    sp = spreads[spreads["month"] >= "2024-01"]
    months = [pd.Period(m, "M") for m in sp["month"]]
    vals = [round(float(t) - float(n), 2) for t, n in zip(sp["top"], sp["nifty500"])]
    if len(vals) < 6:
        return None
    allv = (pd.to_numeric(spreads["top"], errors="coerce") - pd.to_numeric(spreads["nifty500"], errors="coerce")).dropna()
    q1, q3 = float(allv.quantile(0.25)), float(allv.quantile(0.75))
    # The middle half of every month since the history starts: the usual range (tipsheet benchmark, 21 Nov 2026).
    band = [q1, q3, ""]
    band_note = f"shaded: the usual range since {str(spreads['month'].iloc[0])[:4]}, {sg(q1)} to {sg(q3)} pts (the middle half of all months)"
    return {"values": vals, "labels": [f"{m:%b} ’{m:%y}" for m in months], "full": [f"{m:%b %Y}" for m in months],
            "unit": "pts, momentum’s lead", "dp": 1, "lastLabel": f"{months[-1]:%b}", "lastNote": "", "xn": 6, "height": 200,
            "band": band, "band_note": band_note}


def _dii_months(nse: pd.DataFrame | None) -> dict:
    """{month: (net ₹ crore, first day, last day, sessions, selling sessions, whole)} for domestic institutions'
    trades on NSE (data/nse_dii.csv, scripts/collect_nse_dii.py; S153, 21 Nov 2026). A finished month is NSE's
    total for domestic institutions; the month in progress is banks, insurers and mutual funds, the categories
    the daily figures list, to the latest day published (whole=False)."""
    if nse is None or nse.empty or "kind" not in nse:
        return {}
    nse = nse.assign(period=nse["period"].astype(str), net=pd.to_numeric(nse["net"], errors="coerce"))
    out: dict = {}
    for _, r in nse[nse["kind"] == "month"].iterrows():
        p = pd.Period(r["period"], "M")
        out[p] = (float(r["net"]), p.start_time, p.end_time, None, None, True)
    days = nse[nse["kind"] == "day"].assign(date=lambda d: pd.to_datetime(d["period"]))
    for p, g in days.groupby(days["date"].dt.to_period("M")):
        if p in out:
            continue
        out[p] = (float(g["net"].sum()), g["date"].min(), g["date"].max(), len(g), int((g["net"] < 0).sum()), False)
    # All exchanges (NSE's provisional report, collected each evening since 6 Nov 2026) for a month it covers from
    # its first session: BSE and MSEI are about a tenth of the market and not in NSE's own files (S153, 21 Nov 2026).
    allx = _all_exchange_months()
    for p, v in allx.items():
        out[p] = v
    return out


def _all_exchange_months() -> dict:
    """{month: (net, first, last, sessions, selling sessions, whole)} from data/fii_dii_flows.csv, for months whose
    first session is in the file and with no session missing up to the last one collected."""
    from src.loaders.nse_calendar import published_holidays
    f = _read_csv(FILES["nse_flows"])
    if f is None or f.empty or "category" not in f:
        return {}
    x = f[f["category"].astype(str).str.upper() == "DII"].assign(date=lambda d: pd.to_datetime(d["date"]),
                                                                  net=lambda d: pd.to_numeric(d["net"], errors="coerce"))
    cal = pd.offsets.CustomBusinessDay(holidays=published_holidays())
    out = {}
    for p, g in x.groupby(x["date"].dt.to_period("M")):
        want = pd.date_range(p.start_time, g["date"].max(), freq=cal)
        if len(want) and set(want) <= set(g["date"]):
            whole = g["date"].max() >= pd.date_range(p.start_time, p.end_time, freq=cal)[-1]
            out[p] = (float(g["net"].sum()), g["date"].min(), g["date"].max(), len(g), int((g["net"] < 0).sum()), bool(whole))
            out[p] = out[p] + ("all exchanges",)
    return out


def _dii_now(nse: pd.DataFrame | None):
    """The tile: (from, to, net, sessions, selling sessions) for the month in progress, or None."""
    months = _dii_months(nse)
    live = [(p, v) for p, v in months.items() if not v[5]]
    if not live:
        return None
    p, v = max(live)
    return v[1], v[2], v[0], v[3], v[4], (v[6] if len(v) > 6 else "on NSE")


def _fpi_bars(nsdl: pd.DataFrame | None, ev, flows, nse: pd.DataFrame | None = None) -> dict | None:
    """The last 12 months of foreign buying, ₹ crore, the heavy-buying line where tested; domestic
    institutions in the readout for the months NSE's daily file covers (owner, 20 Nov: "DII is also big now")."""
    if nsdl is None or flows is None or "equity_net" not in nsdl:
        return None
    s = pd.Series(pd.to_numeric(nsdl["equity_net"], errors="coerce").values, index=pd.to_datetime(nsdl["date"])).dropna()
    allm = s.groupby(s.index.to_period("M")).sum()
    done = allm.iloc[:-1]                       # finished months only: the month so far would pull the range
    q1, q3 = float(done.quantile(0.25)), float(done.quantile(0.75))
    mo = allm.iloc[-12:]
    out = {"values": [round(float(v)) for v in mo.values], "labels": [f"{p:%b}" for p in mo.index],
           "full": [f"{p:%b %Y}" for p in mo.index], "unit": "foreign", "money": True, "axisDiv": 1000,
           "valueLabels": True, "xn": 12, "height": 240, "lastNote": f", to {flows.as_of:%-d %b}",
           "above": "a heavy-buying month", "between": "net buying, below the heavy line", "belowZero": "net selling"}
    if ev is not None:
        out["levels"] = [round(float(ev.threshold))]
    out["band"] = [round(q1), round(q3), ""]
    out["band_note"] = (f"shaded: foreign investors' usual range since {done.index[0]:%Y}, {sg(q1 / 1000, 0)} to {sg(q3 / 1000, 0)} thousand Cr "
                        "(the middle half of all months)")
    dii = _dii_months(nse)
    if dii:
        out["also"] = [None if p not in dii else
                       [("domestic" + (", all exchanges" if len(dii[p]) > 6 else "") if dii[p][5]
                         else f"domestic, {dii[p][1]:%-d}–{dii[p][2]:%-d %b}"
                         + (", all exchanges" if len(dii[p]) > 6 else " (banks, insurers, MFs)")),
                        round(dii[p][0])] for p in mo.index]
    return out


def _flow_compare(nse: pd.DataFrame | None, nsdl: pd.DataFrame | None) -> tuple[float, float, int] | None:
    """(NSE provisional FPI net, NSDL net, sessions) over the sessions NSE's figures cover."""
    if nse is None or nsdl is None or "category" not in nse or "equity_net" not in nsdl:
        return None
    f = nse[nse["category"].astype(str).str.upper().str.startswith("FII")]
    if f.empty:
        return None
    dates = pd.to_datetime(f["date"])
    n = pd.Series(pd.to_numeric(nsdl["equity_net"], errors="coerce").values, index=pd.to_datetime(nsdl["date"]))
    nsdl_sum = float(n[(n.index >= dates.min()) & (n.index <= dates.max())].sum())
    return float(pd.to_numeric(f["net"], errors="coerce").sum()), nsdl_sum, int(dates.nunique())


def _breadth_spec(n500: pd.Series, above_200: pd.Series | None, as_of: pd.Timestamp) -> dict | None:
    """Three years of the Nifty 500 and the share of the 750 above the 200D EMA, on the index's sessions."""
    if n500 is None or n500.empty or above_200 is None:
        return None
    idx = n500[(n500.index > as_of - pd.DateOffset(years=3)) & (n500.index <= as_of)]
    a = above_200.reindex(idx.index, method="ffill")
    return {"dates": [f"{d:%Y-%m-%d}" for d in idx.index], "n500": [round(float(v), 1) for v in idx.values],
            "a200": [None if pd.isna(v) else round(float(v), 1) for v in a.values]}


def _brief(bm: di.BookMonth, n_sells: int, check, signals: list[dict], average, typical, flows=None,
           month: str = "the month", universe: str = "750") -> str:
    bits = []
    if bm.market_mtd is not None and bm.book_mtd is not None and bm.momentum_mtd:
        if bm.book_mtd < bm.market_mtd and bm.book_mtd >= max(bm.momentum_mtd.values()) - 0.05:
            bits.append(f"So far in {month} the book is keeping pace with momentum, and momentum is losing to Nifty Total Market.")
        elif bm.book_mtd >= bm.market_mtd:
            bits.append(f"The book is ahead of Nifty Total Market so far in {month}.")
        else:
            bits.append(f"The book is behind Nifty Total Market and behind momentum so far in {month}.")
    if n_sells:
        bits.append(f'<span class="dh-down">{n_sells} holding{"s" if n_sells != 1 else ""} go on {check:%-d %b}.</span>')
    passed = [x for x in signals if x["like"] is not None and average is not None]
    if passed:
        good = [x for x in passed if x["like"] >= average]
        fpi = any(x["key"] == "fpi" for x in good)
        n = len(passed)
        bits.append(f'Of the {n} signal{"s" if n != 1 else ""} that pass our own test, on today\'s readings '
                    f'<span class="dh-up">{len(good)} point{"s" if len(good) == 1 else ""} to a stronger month for momentum</span>'
                    + ((", record foreign buying among them," if flows is not None and flows.month_rank == 1
                        else ", foreign buying among them,") if fpi else "")
                    + f' and <span class="dh-down">{n - len(good)} to a weaker one</span>'
                    + _month_end_count(passed, average) + '.')
    b1 = typical["beat_share"][0] if typical else None
    if b1 is not None and b1 < 40:
        # The 1M window (from the same date a month back), not the month so far (S193 A8).
        bits.append(f'<span class="dh-watch">The rally is narrow: only {b1:.0f}% of the {universe} beat Nifty Total Market over the past month.</span>')
    nav = "".join(f'<a href="#{a}" class="dh-pill">{e(t)}</a>' for a, t in (
        ("s-month", "1 The book"), ("s-next", "2 Next rebalance"), ("s-mom", "3 Momentum"), ("s-flow", "4 Money flows"),
        ("s-size", "5 Size"), ("s-book", "6 Strong and weak"), ("s-glance", "At a glance")))
    return (f'<section class="dh-brief" aria-label="Today in brief"><p class="dh-verdict">{" ".join(bits)}</p>'
            f'<nav class="dh-pills" aria-label="On this page">{nav}</nav></section>')


def _load_tests() -> dict:
    try:
        return json.loads(FILES["tests"].read_text())
    except (OSError, ValueError):
        return {}


def nifty500_breadth(adj_close: pd.DataFrame, as_of: pd.Timestamp) -> dict[str, pd.Series]:
    """Nifty 500 shares above the 50D and 200D EMA: its members on each date
    from data/breadth_history.csv, today's members after that file ends."""
    from src.engine import market_questions as mq
    from src.engine import membership, pit_breadth
    from src.engine.index_universe import index_history
    h = index_history("nifty_500")
    now = (membership.members_on(h, as_of, canonical=True) or set()) if h else set()
    cols = [c for c in now if c in adj_close.columns]
    past = pit_breadth.load("nifty500")
    out = {}
    for span in (50, 200):
        live = mq._share_above_ema(adj_close[cols], span) if cols else pd.Series(dtype=float)
        out[f"above_{span}"] = pit_breadth.splice(live, past, f"above_{span}")
    return out


def _since_month_end(series: pd.Series, as_of: pd.Timestamp) -> float | None:
    """Change since the last month-end before `as_of`'s month."""
    s = series.dropna()
    s = s[s.index <= as_of]
    prior = s[s.index < as_of.to_period("M").to_timestamp()]
    return None if s.empty or prior.empty else float(s.iloc[-1] - prior.iloc[-1])


@st.cache_data(show_spinner=False, ttl=3600)
def _qualify_cached(key: str, _prices: pd.DataFrame, dates: tuple) -> dict:
    from src.engine import index_universe as iu
    from src.engine.momentum_health import qualified_on
    membership = iu.index_history("nifty_500")
    if not membership:
        return {}
    cols = sorted(iu.ever_members(membership) & set(_prices.columns))
    return qualified_on(_prices[cols].astype("float64"), [pd.Timestamp(d) for d in dates], membership)


def _qualify_today(adj_close: pd.DataFrame | None, as_of: pd.Timestamp) -> dict:
    """{session: share of the Nifty 500 passing the filters} on the rank trail's
    dates, by the monthly job's rule (`momentum_health.qualified_on`), so the
    row's "Now" is today and not the last month-end (staleness audit, 21 Nov 2026)."""
    if adj_close is None or adj_close.empty:
        return {}
    try:
        from src.engine.pipeline import price_fingerprint
        px = adj_close.loc[:as_of]
        dates = tuple(str(di.on_or_before(px.index, d).date()) for d in di.trail_dates(px.index[-1]).values()
                      if di.on_or_before(px.index, d) is not None)
        return _qualify_cached(f"{price_fingerprint(px)}_{dates}", px, dates)
    except Exception:  # noqa: BLE001 -- the row falls back to month-ends, said on the page
        return {}


def _signals(spreads, n500: pd.Series, as_of: pd.Timestamp, flows, n500_breadth: dict, tests: dict,
             qualify_now: dict | None = None) -> list[dict]:
    """One row per signal: today's reading, its state, and its test (data/signal_tests.json).

    Two signals are tested on month-end readings (the 10-month average, the share
    that qualifies). Their row shows today's reading under "Now", and keeps the
    month-end reading, which the test used, in `me_on` and the row's note; the
    sentences count both (staleness audit, 21 Nov 2026)."""
    from src.engine import market_questions as mq
    t = tests.get("tests", {})
    pct = lambda v: "–" if v is None else f"{v:.0f}%"  # noqa: E731
    gap = lambda v: sg(v, unit="%")  # noqa: E731
    out = []

    def row(key, name, sub, cells, on, flip, hist="", me_on="same"):
        test = t.get(key)
        like = like_me = None
        if test and test["passed"] and on is not None:
            like = test["on"] if on else test["off"]
        me = on if me_on == "same" else me_on
        if test and test["passed"] and me is not None:
            like_me = test["on"] if me else test["off"]
        out.append({"key": key, "name": name, "sub": sub, "cells": cells, "on": on, "test": test,
                    "like": like, "like_me": like_me, "flip": flip, "hist": hist})

    def where(series, value, unit="days"):
        """Where today's reading sits in its own history (v6, restored 20 Nov)."""
        p, since = di.percentile_of(series, value)
        if p is None:
            return ""
        yr = since[-4:] if since else ""
        return (f"Higher than {p:.0f}% of {unit} since {yr}" if p >= 50
                else f"Lower than {100 - p:.0f}% of {unit} since {yr}")

    if len(n500):
        gs = mq._ema_gap_series(n500)
        g = di.trail_of(gs, as_of)
        on = g[2] is not None and g[2] > 0
        row("trend_fast", "Nifty 500 vs its 200D EMA", "Above: on", [gap(v) for v in g], on,
            "Back below the EMA" if on else "Back above the EMA", where(gs, g[2]))
    if flows is not None and "fpi" in t:
        fpi = t["fpi"]
        cut = fpi.get("threshold")
        on = cut is not None and flows.mtd >= cut
        row("fpi", "Heavy foreign buying", "FPI net, last 20 sessions, ₹ thousand Cr · top quarter of months: on",
            ["–" if v is None else sg(v / 1000, 0) for v in flows.trail20], on if cut is not None else None,
            "Settled for the month" if on else (f"₹{_fmt.fixed(cut / 1000, 0)} thousand Cr in a month" if cut else ""),
            f"Highest 20-session total since {flows.since:%Y}" if flows.last20_is_record else "")
    if len(n500):
        tr = [mq.ten_month_today(n500, d) for d in di.trail_dates(as_of).values()]
        on = tr[2] is not None and tr[2] > 0
        me, me_at = mq.ten_month_gap(n500, as_of), mq.last_month_end(n500, as_of)
        me_txt = "" if me is None or me_at is None else f" · the test reads month-ends: {me_at:%-d %b} {gap(me)}"
        row("trend_slow", "Nifty 500 vs its 10-month average", "Today's close against ten monthly closes · above: on"
            + me_txt, [gap(v) for v in tr],
            None if tr[2] is None else on, "A month-end below the average" if on else "A month-end above the average",
            where(mq._ten_month_series(n500), tr[2], "month-ends"), me_on=None if me is None else me > 0)
    if spreads is not None and "qualified" in spreads:
        q = pd.Series(pd.to_numeric(spreads["qualified"], errors="coerce").values * 100,
                      index=pd.to_datetime(spreads["date"])).dropna()
        try:
            latest = json.loads(FILES["latest_q"].read_text())
            q.loc[pd.Timestamp(latest["date"])] = float(latest["qualified"]) * 100
        except (OSError, ValueError, KeyError, TypeError):
            pass
        q = q.sort_index()
        me_tr = di.month_end_trail(q, as_of)
        cut = float(q.quantile(0.25))
        me_on = None if me_tr[2] is None else me_tr[2] <= cut
        live = [v * 100 for _, v in sorted((qualify_now or {}).items())]
        tr = live if len(live) == 3 else me_tr
        me_at = q.index[q.index <= as_of][-1] if len(q.index[q.index <= as_of]) else None
        note = ("" if me_at is None or me_tr[2] is None else
                f" · the test reads month-ends: {me_at:%-d %b} {me_tr[2]:.0f}%")
        on = tr[2] is not None and tr[2] <= cut
        row("qualify", "Stocks that qualify", f"Nifty 500 above 50D EMA, near the high · {cut:.0f}% or fewer: on"
            + (note if len(live) == 3 else " · month-ends"),
            [pct(v) for v in tr], None if tr[2] is None else on,
            f"Above {cut:.0f}% at the next month-end" if on else f"{cut:.0f}% or fewer at a month-end",
            where(q, tr[2], "month-ends"), me_on=me_on)
    a200, a50 = n500_breadth.get("above_200"), n500_breadth.get("above_50")
    if a200 is not None and len(a200.dropna()):
        tr = di.trail_of(a200, as_of)
        on = tr[2] is not None and tr[2] <= 40
        row("breadth_thin", "Breadth thin", "Nifty 500 above the 200D EMA · 40% or fewer: on", [pct(v) for v in tr],
            None if tr[2] is None else on, "Above 40%" if on else "Back to 40% or below", where(a200, tr[2]))
    if a50 is not None and len(a50.dropna()):
        tr = di.trail_of(a50, as_of)
        jump = _since_month_end(a50, as_of)
        row("participation_jump", "Participation jump", "Nifty 500 above the 50D EMA · up 15+ pts in a month: on",
            [pct(v) for v in tr], None if jump is None else jump >= 15, "A month without a jump", where(a50, tr[2]))
    if len(n500):
        fh = mq._from_high_series(n500)
        tr = di.trail_of(fh, as_of)
        up = _since_month_end(fh, as_of)
        on = None if up is None or tr[2] is None else (up >= 5 and tr[2] >= -3)
        row("rebound", "Sharp rebound", "Nifty 500 from its 52W high · within 3% after a 5-pt jump: on",
            [gap(v) for v in tr], on, "", where(fh, tr[2]))
    return out


BREADTH_TIER = {"Nifty 100": "Large", "Nifty Midcap 150": "Mid", "Nifty Smallcap 250": "Small", "Nifty Microcap 250": "Micro",
                "Nano Cap": "Nano Cap"}
TIER_SIZE = {"Nifty 100": "Large", "Midcap 150": "Mid", "Smallcap 250": "Small", "Microcap 250": "Micro",
             "Nano Cap": "Nano Cap", "Ultra Nano Cap": "Ultra Nano Cap", "Outside": "Outside"}


def size_class(k: str) -> str:
    """The CSS class of a size segment: dh-sz-large ... dh-sz-ultra-nano-cap."""
    return "dh-sz-" + k.lower().replace(" ", "-")


def _book_sizes(risk) -> dict[str, float]:
    """The book's weight by size list, percent (book_risk's tiers are shares). The four NSE
    lists always; Nano Cap (the Nifty 1000's other 250) and Ultra Nano Cap (outside the 1000)
    only when the book holds them, so the bar adds up to the invested
    share (S194 L3, 23 Nov 2026: a Nifty 1000 book's 250 were dropped from the bar)."""
    m = {"Large": 0.0, "Mid": 0.0, "Small": 0.0, "Micro": 0.0}
    for tier, share in (getattr(risk, "tiers", None) or {}).items():
        if tier in TIER_SIZE and float(share) > 0:
            m[TIER_SIZE[tier]] = m.get(TIER_SIZE[tier], 0.0) + float(share) * 100
    return m


def _ordinal(v: float) -> str:
    n = int(round(v))
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def indices_glance_rows(f) -> list[tuple[str, str, str]]:
    """The Indices page in three lines (S170, requirement 17): the Nifty 500's P/E percentile now with 1M and 3M,
    and the styles leading and trailing their parents over 12 months."""
    from src.engine import indices_page as ip
    rows = []
    v = next((x for x in ip.valuation(f, ("nifty_500",))), None)
    if v is not None:
        rows.append(("Nifty 500 P/E, percentile since 2021",
                     f"{_ordinal(v.pct_now)} · 1M {_ordinal(v.pct_1m)} · 3M {_ordinal(v.pct_3m)}", ""))
    st_ = sorted((s for s in ip.styles(f) if s.lead_now is not None), key=lambda s: -s.lead_now)
    if st_:
        for word, x in (("Leading", st_[0]), ("Trailing", st_[-1])):
            rows.append((f"{word} style: {x.style.lower()}, {x.name.replace('NIFTY', 'Nifty')}",
                         f"{sg(x.lead_now)} pts, 12M", tone(x.lead_now)))
    return rows


def _nse_close(key: str) -> pd.Series:
    """One index's close from the app's copy of NSE's daily index files; empty if absent."""
    try:
        from src.ui import indices_data
        f = indices_data.frames()
        return f.close[key].dropna() if f is not None and key in f.close else pd.Series(dtype=float)
    except Exception:  # noqa: BLE001 -- a missing copy reads "–", it does not stop the Dashboard
        return pd.Series(dtype=float)


def _indices_glance(as_of: pd.Timestamp) -> list:
    """Read on the Dashboard's own session (`as_of`), not the index store's last day."""
    try:
        from src.ui import indices_data
        f = indices_data.frames()
        f = None if f is None else f.until(as_of)
        rows = [] if f is None or f.close.empty else indices_glance_rows(f)
    except Exception:  # noqa: BLE001 -- the Dashboard draws without this card rather than fail
        rows, f = [], None
    return [(f"Valuation and styles, {f.as_of:%-d %b}", (page_href("indices"), "Indices"), rows)] if rows else []


def _glance(closes, as_of, hist, risk, n500, record_risk=None) -> list:
    def day(key):
        s = closes[key].dropna()
        s = s[s.index <= as_of]
        return None if len(s) < 2 else (float(s.iloc[-1]) / float(s.iloc[-2]) - 1) * 100

    idx = [(SIZE_LABELS.get(k, "Nifty Total Market" if k == bi.TOTAL_MARKET else "Nifty 50"), day(k))
           for k in (bi.TOTAL_MARKET, "nifty50", "midcap150", "smallcap250", "microcap250")]
    a50, a200 = hist["above_50"], hist["above_200"]
    t50, t200 = di.trail_of(a50, as_of), di.trail_of(a200, as_of)
    rows_b = [("Above their 200D EMA", f"{t200[2]:.0f}% ({t200[1]:.0f}% a month ago)", ""),
              ("Above their 50D EMA", f"{t50[2]:.0f}% ({t50[1]:.0f}% a month ago)", "")]
    rr = record_risk
    rows_r = [(f"Beta, {rr.label[0].lower()}{rr.label[1:]}" if rr else "Beta", f"{rr.beta:.1f}" if rr else "–", ""),
              ("Volatility, a year", f"{rr.vol:.1f}% vs {rr.market_vol:.1f}%" if rr else "–",
               "dh-watch" if rr and rr.vol > rr.market_vol else "")]
    if risk.exit_days is not None and len(risk.exit_days):
        rows_r.append((f"Slowest exit, {risk.exit_days.index[0]}", f"{float(risk.exit_days.iloc[0]):.2f} days",
                       "dh-up" if float(risk.exit_days.iloc[0]) < 1 else "dh-watch"))
    if risk.drawdown is not None:
        rows_r.append(("Below its peak", sg(risk.drawdown * 100, unit="%"), ""))
    return [
        (f"Indices, {as_of:%-d %b}", (page_href("indices"), "Indices"), [(n, sg(v, unit="%"), tone(v)) for n, v in idx]),
        ("Breadth, ranked stocks", (page_href("market"), "Market"), rows_b),
        ("The book’s risk", (page_href("portfolio"), "Portfolio"), rows_r),
    ]


HOME_CSS = """
.dh{font-family:var(--font-ui);color:var(--c-ink);line-height:1.5}
.dh-brief{padding:20px 0 18px;border-bottom:1px solid var(--c-rule)}
.dh-verdict{margin:0 0 12px;font-family:var(--font-serif);font-size:var(--fs-24);line-height:1.35;max-width:980px}
.dh-pills{display:flex;flex-wrap:wrap;gap:6px 8px}
.dh-pill{font-size:var(--fs-13);text-decoration:none;color:var(--c-ink);border:1px solid var(--c-rule);border-radius:999px;padding:6px 12px;min-height:32px;display:inline-flex;align-items:center}
.dh-sec{padding:32px 0 0;display:flex;flex-direction:column;gap:20px}
.dh-sec-cont{padding-top:8px}
.dh-end{border-bottom:1px solid var(--c-rule);padding-bottom:8px}
.dh-sec-last{border-bottom:0}
.dh-kick{margin:0;font-size:var(--fs-12);font-weight:600;letter-spacing:.08em;text-transform:uppercase;color:var(--c-muted)}
.dh .dh-h1{margin:0!important;padding:0!important;font-family:var(--font-serif)!important;font-weight:400!important;font-size:var(--fs-44)!important;line-height:1.08!important;letter-spacing:-.5px!important;max-width:940px}
.dh .dh-h2{margin:0!important;padding:0!important;font-family:var(--font-serif)!important;font-weight:400!important;font-size:var(--fs-30)!important;line-height:1.15!important;letter-spacing:0!important;max-width:960px}
.dh .dh-h3{margin:0!important;padding:0!important;font-size:var(--fs-15)!important;font-weight:700!important}
.dh-lede{margin:0;font-size:var(--fs-17);color:var(--c-text_2);max-width:80ch}
.dh-note{margin:0;font-size:var(--fs-13);color:var(--c-muted);max-width:80ch}
.dh-band-note{margin-bottom:10px}
@media (min-width:901px){.dh-note.dh-note-long{max-width:none;columns:2 380px;column-gap:40px}}
.dh-foot{margin:24px 0 0;font-size:var(--fs-12);color:var(--c-muted)}
.dh-sub{display:block;font-size:var(--fs-12);color:var(--c-muted);font-weight:400}
.dh-mono{font-family:var(--font-mono)}
.dh-b{font-weight:700}
.dh-up{color:var(--c-up)}.dh-down{color:var(--c-down)}.dh-watch{color:var(--c-caution)}.dh-muted{color:var(--c-muted)}
.dh h3.dh-up{color:var(--c-up)!important}.dh h3.dh-down{color:var(--c-down)!important}.dh h3.dh-watch{color:var(--c-caution)!important}
.dh-kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,200px),1fr));gap:1px;background:var(--c-rule_soft);border:1px solid var(--c-rule_soft)}
.dh-kpi{background:var(--c-white);padding:14px 16px;display:flex;flex-direction:column;gap:2px}
.dh-k-l{font-size:var(--fs-12);color:var(--c-muted)}
.dh-k-v{font-family:var(--font-serif)!important;font-size:var(--fs-30);font-weight:400;font-variant-numeric:tabular-nums;letter-spacing:-.01em;line-height:1.15}
.dh-k-s{font-size:var(--fs-12);font-weight:600}
.dh-k-sub{font-size:var(--fs-12);color:var(--c-muted)}
.dh-fig{margin:0;display:flex;flex-direction:column;gap:6px}
.dh-cap{display:flex;flex-wrap:wrap;justify-content:space-between;gap:6px;font-size:var(--fs-13);color:var(--c-muted)}
.dh-cap b{color:var(--c-ink)}
.dh-key{display:inline-block;width:10px;height:10px;margin:0 4px 0 10px;vertical-align:middle}
.dh-bar{display:grid;grid-template-columns:minmax(0,240px) minmax(0,1fr) 64px;gap:12px;align-items:center;font-size:var(--fs-13)}
.dh-bar-n{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.dh-bar-t{height:14px;background:var(--c-fill_soft);border-radius:2px;display:block}
.dh-bar-f{display:block;height:14px;border-radius:2px}
.dh-bar-v{font-family:var(--font-mono);text-align:right}
.dh-f-mkt{background:var(--c-muted_2)}.dh-f-book{background:var(--c-ink)}.dh-f-mom{background:var(--c-up_line)}
.dh-f-pos{background:var(--c-up)}.dh-f-neg{background:var(--c-down)}
.dh-cols{display:flex;flex-wrap:wrap;gap:28px}
.dh-col2{flex:2 1 460px;min-width:0}.dh-col1{flex:1 1 280px;min-width:0;display:flex;flex-direction:column;gap:14px}
.dh-hold{display:grid;grid-template-columns:minmax(0,1.2fr) minmax(0,1.5fr) 84px 56px 56px 92px 84px;gap:12px;align-items:center;padding:9px 0;border-bottom:1px solid var(--c-rule_soft);font-size:var(--fs-13)}
.dh-hold-h{font-size:var(--fs-12);color:var(--c-muted);border-bottom:1px solid var(--c-ink);padding:0 0 6px}
.dh-sym{color:var(--c-ink);text-decoration:none}
.dh-rk{font-size:var(--fs-13)}
.dh-hold .dh-badge{justify-self:end}
.dh-badge{font-size:var(--fs-12);font-weight:600;border:1px solid currentColor;border-radius:4px;padding:3px 8px;text-align:center;white-space:nowrap}
.dh-lab{font-size:var(--fs-12);color:var(--c-muted);padding-bottom:6px;border-bottom:1px solid var(--c-ink)}
.dh-chips{display:flex;flex-wrap:wrap;gap:8px}
.dh-chip{font-family:var(--font-mono);font-weight:600;font-size:var(--fs-13);color:var(--c-up);background:var(--c-up_tint);border-radius:4px;padding:4px 9px}
.dh-callout{background:var(--c-fill_soft);border-radius:4px;padding:12px 14px;font-size:var(--fs-13)}
.dh-link{font-size:var(--fs-13);font-weight:600;color:var(--c-ink);min-height:44px;display:flex;align-items:center}
.dh-tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:1px;background:var(--c-rule_soft);border:1px solid var(--c-rule_soft)}
.dh-tile{background:var(--c-white);padding:14px 16px;display:flex;flex-direction:column;gap:6px}
.dh-big{font-family:var(--font-serif);font-size:var(--fs-30);font-weight:400;line-height:1.1;font-variant-numeric:tabular-nums}
.dh-dbar{height:6px;background:var(--c-fill_soft);display:grid;grid-template-columns:1fr 1fr}
.dh-dbar span{display:flex}.dh-dbar span:first-child{justify-content:flex-end}.dh-dbar span:last-child{border-left:1px solid var(--c-ink)}
.dh-dbar i{display:block;height:6px}
.dh-scroll{overflow-x:auto}
@media (max-width:640px){.dh-k-v,.dh-big{font-size:var(--fs-24);white-space:nowrap}.dh-kpis{grid-template-columns:1fr 1fr}.dh-kpis>:last-child:nth-child(odd){grid-column:1/-1}}
.dh-tab{width:100%;min-width:900px;border-collapse:collapse;font-size:var(--fs-13)}
.dh-tab th,.dh-tab td{text-align:left;padding:9px 12px 9px 0;border-bottom:1px solid var(--c-rule_soft);vertical-align:top}
.dh-tab thead th{font-size:var(--fs-12);color:var(--c-muted);font-weight:500;border-bottom:1px solid var(--c-ink)}
.dh-tab tbody th{font-weight:600}
.dh-grp-row th{padding-top:16px!important;font-size:var(--fs-13);border-bottom:1px solid var(--c-ink)!important}
.dh-tab-sw{min-width:760px}
.dh-num{text-align:right!important;font-family:var(--font-mono);white-space:nowrap;font-variant-numeric:tabular-nums}
.dh-side{display:block;font-size:var(--fs-12);font-weight:700}
.dh-tab thead th.dh-num,.dh-hold-h .dh-num{font-family:var(--font-ui);font-weight:500}
.dh-hl{font-weight:600}
.dh-trail{display:block}
.dh-hist{font-size:var(--fs-12);color:var(--c-muted);min-width:240px}
.dh-tab.dh-tab-sig{min-width:1080px}
.dh-how{display:flex;flex-wrap:wrap;gap:4px 24px;font-size:var(--fs-13)}
.dh-how details{flex:1 1 280px}.dh-how details[open]:last-child{flex-basis:100%}
.dh-how summary{cursor:pointer;font-weight:600;min-height:32px;display:flex;align-items:center;gap:6px;list-style:none;color:var(--c-ink)}
.dh-how summary::-webkit-details-marker{display:none}
.dh-how summary::before{content:"+";font-family:var(--font-mono);color:var(--c-muted);width:12px}
.dh-how details[open] summary::before{content:"−"}
.dh-how-b{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:8px 24px;color:var(--c-text_2);max-width:1000px}
/* What it is and how to read it: in plain sight on a wide screen, folded on a phone (tipsheet benchmark, 21 Nov 2026). */
.dh-how-wide{display:none}@media (min-width:901px){.dh-how-wide{display:grid;flex-basis:100%;margin-bottom:4px}.dh-how-narrow{display:none}}
.dh-how-b p{margin:0}.dh-how-b b{display:block;color:var(--c-ink)}
.dh-how-t{max-height:280px;overflow:auto;border:1px solid var(--c-rule_soft);border-radius:var(--r-sm)}
.dh-how-t .dh-tab td:not(:first-child),.dh-how-t .dh-tab th:not(:first-child){text-align:right;font-family:var(--font-mono)}
.dh-gcards{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,300px),1fr));gap:20px;align-items:start}
.dh-gcard{border:1px solid var(--c-rule_soft);border-top:3px solid var(--c-rule);border-radius:var(--r-sm);padding:14px 16px;display:flex;flex-direction:column;gap:4px;min-width:0}
.dh-g-up{border-top-color:var(--c-up)}.dh-g-watch{border-top-color:var(--c-caution)}.dh-g-down{border-top-color:var(--c-down)}
.dh-gc-h{display:flex;justify-content:space-between;align-items:baseline}
.dh .dh-gc-h h3{margin:0!important;padding:0!important;font-family:var(--font-ui)!important;font-size:var(--fs-17)!important}
.dh-gc-h b{font-size:var(--fs-24)}
.dh-gcard>p{margin:0 0 4px;font-size:var(--fs-13);color:var(--c-muted)}
.dh-gc-r{border-top:1px solid var(--c-rule_soft);padding:9px 0;display:flex;flex-direction:column;gap:3px;font-size:var(--fs-13)}
.dh-gc-1,.dh-gc-2{display:flex;justify-content:space-between;gap:10px;align-items:baseline}
.dh-gc-3{font-size:var(--fs-12);color:var(--c-muted)}.dh-gc-3 b{color:var(--c-text_2);font-weight:600}
.dh-qb{font-size:var(--fs-12);font-weight:600;border-radius:var(--r-sm);padding:2px 8px;white-space:nowrap}
.dh-qb-up{color:var(--c-up);background:var(--c-up_tint)}.dh-qb-imp{color:var(--c-up);background:var(--c-fill)}
.dh-qb-watch{color:var(--c-caution);background:var(--c-caution_tint)}.dh-qb-down{color:var(--c-down);background:var(--c-down_tint)}
.dh-groups.dh-groups-1{grid-template-columns:1fr;gap:20px}
.dh-groups.dh-groups-2{grid-template-columns:repeat(auto-fit,minmax(min(100%,320px),1fr));gap:20px 40px;margin-top:8px}
.dh-tab.dh-tab-s{min-width:0}
.dh-tab-s th,.dh-tab-s td{padding:6px 10px 6px 0}
.dh-tr-g{padding-top:12px!important;font-weight:500!important}
.dh-faint{opacity:.72}
.dh-w-bar{width:170px}
.dh-pair{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:32px}
.dh-lede-s{margin:6px 0 0;font-size:var(--fs-13)}
.dh-ev{font-size:var(--fs-12);font-weight:600;border-radius:4px;padding:2px 7px;white-space:nowrap;display:inline-block}
.dh-ev-t{color:var(--c-up);background:var(--c-up_tint)}.dh-ev-r{color:var(--c-caution);background:var(--c-caution_tint)}.dh-ev-c{color:var(--c-muted);background:var(--c-fill_soft)}
.dh-ev-box{border-left:3px solid var(--c-rule);padding:2px 0 2px 12px;font-size:var(--fs-13)}
.dh-ev-up{border-left-color:var(--c-up)}
.dh-mbars{display:grid;grid-template-columns:repeat(12,minmax(0,1fr));gap:6px}
.dh-mb{display:flex;flex-direction:column;min-width:0}
.dh-mb-l{height:18px;font-family:var(--font-mono);font-size:var(--fs-12);text-align:center}
.dh-mb-up{height:70px;display:flex;flex-direction:column;justify-content:flex-end;border-bottom:1px solid var(--c-ink)}
.dh-mb-dn{height:70px;display:flex;flex-direction:column}
.dh-mb-up i,.dh-mb-dn i{display:block;width:100%}
.dh-mb-n{font-size:var(--fs-12);text-align:center;color:var(--c-muted)}
.dh-sizebar{display:flex;height:26px;border-radius:3px;overflow:hidden;font-size:var(--fs-12);font-weight:600}
.dh-sizebar i{display:flex;align-items:center;padding-left:8px;font-style:normal;white-space:nowrap;overflow:hidden}
.dh-sz-large{background:var(--c-ink)}.dh-sz-mid{background:var(--c-muted)}.dh-sz-small{background:var(--c-caution);color:var(--c-white)}.dh-sz-micro{background:var(--c-caution_line)}.dh-sz-nano-cap{background:var(--c-caution_tint);color:var(--c-caution_ink)}.dh-sz-ultra-nano-cap,.dh-sz-outside,.dh-sz-other{background:var(--c-rule_strong);color:var(--c-ink)}
.dh-segbar{display:flex;height:40px;border-radius:4px;overflow:hidden;gap:2px}
.dh-segbar i{display:flex;align-items:center;padding-left:6px;font-style:normal;font-size:var(--fs-12);font-weight:600;white-space:nowrap;overflow:hidden;color:var(--c-white)}
.dh-seg-strong{background:var(--c-up)}.dh-seg-slow{background:var(--c-up_line);color:var(--c-ink)!important}.dh-seg-turning{background:var(--c-caution_line);color:var(--c-ink)!important}.dh-seg-weak{background:var(--c-down)}
.dh-cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:20px}
.dh-card{border:1px solid var(--c-rule_soft);border-radius:4px;padding:14px 16px;display:flex;flex-direction:column;gap:4px;min-width:0}
.dh-card-strong{border-top:3px solid var(--c-up)}.dh-card-turning{border-top:3px solid var(--c-caution)}.dh-card-weak{border-top:3px solid var(--c-down)}
.dh-card-h{display:flex;justify-content:space-between;align-items:baseline;gap:8px}
.dh .dh-card-h h3{margin:0!important;padding:0!important;font-size:var(--fs-15)!important}
.dh-ind{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:4px 10px;padding:8px 0;border-top:1px solid var(--c-rule_soft);font-size:var(--fs-13)}
.dh-span{grid-column:1/-1}
.dh-tag{font-size:var(--fs-12);font-weight:600;justify-self:end}
.dh-groups{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:28px}
.dh-grp-h{display:flex;justify-content:space-between;align-items:baseline;padding-bottom:6px;border-bottom:2px solid currentColor}
.dh .dh-grp-h h3{margin:0!important;padding:0!important;font-size:var(--fs-15)!important;color:inherit!important}
.dh-gl-top{display:flex;justify-content:space-between;align-items:baseline;gap:12px;flex-wrap:wrap}
.dh-gls{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:1px;background:var(--c-rule_soft);border:1px solid var(--c-rule_soft)}
.dh-gl{background:var(--c-white);padding:14px 16px}
.dh-gl-h{display:flex;justify-content:space-between;align-items:baseline;gap:8px;margin-bottom:4px;font-size:var(--fs-13)}
.dh-gl-h a{font-size:var(--fs-12);font-weight:600;color:var(--c-ink)}
.dh-gl-r{display:flex;justify-content:space-between;gap:10px;padding:4px 0;border-top:1px solid var(--c-fill_soft);font-size:var(--fs-13)}
@media (max-width:640px){.dh .dh-h1{font-size:var(--fs-36)!important}.dh .dh-h2{font-size:var(--fs-24)!important}.dh-hold{grid-template-columns:minmax(0,1fr) 52px 52px 52px;row-gap:4px}.dh-hold>div:nth-child(2){grid-column:1/-1;grid-row:2}.dh-hold-h{display:none}.dh-hold .dh-badge{grid-column:1/-1;justify-self:start}.dh-bar{grid-template-columns:minmax(0,1fr) 56px;row-gap:4px}.dh-bar-t{grid-column:1/-1;grid-row:2}}
"""
