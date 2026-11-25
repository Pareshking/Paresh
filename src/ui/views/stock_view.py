"""The stock page (S182; mock-up v2 approved by the owner, 23 Nov 2026: "Stock v2 approved").

A route of the Screener (`/?stock=SYMBOL`, `ranking_view.py`), for every system.
It answers what a reader comes with (docs/STOCK_REQUIREMENTS.md):

  Head      kicker, a serif title answering rank / filters / held, a lede, four tiles
  1 Rank    3M ago · 1M ago · now: the rank of the universe and the place among the qualified
  2 Filters and sell rules: the ladder, each rule's line and the fall that reaches it,
            the model book's holding (Portfolio's own function), the calendar before the check
  3 Returns and falls: line bars on one scale against Nifty Total Market over the same sessions
  4 Price   today's Lightweight Charts chart, restyled: price and the ranking's 50D EMA,
            Volume, RS against Nifty Total Market; 6M · 12M · 3Y as chips in the chart, opening on 12M,
            the heading's relative-strength words following the chip (S193 H2); one-line readout
  5 Sector    the eight best-ranked, qualified places filled; the rest on the Screener
  6 Data    the checks in plain sight; corporate actions from NSE's own list
  Foot      Data to <date> · NSE

The words and figures are worked out in src/ui/stock_lines.py (pure functions, tested);
this module draws them. No stop loss and no chandelier exit (owner, 22 Nov 2026: "we
don't have exit or SL so remove it"); the Factsheet window that showed them is gone.
"""

from __future__ import annotations

import html
from urllib.parse import quote

import pandas as pd
import streamlit as st

from src.ui import formats
from src.ui import stock_lines as sl
from src.ui import watchlist_lines as wl
from src.ui.components import gap_count, render_data_quality_footer

e = html.escape

INDEX_NAMES = {   # NSE indices by their full names in the kicker (glossary 3)
    "N50": "Nifty 50", "NN50": "Nifty Next 50", "MID150": "Nifty Midcap 150",
    "SMALL250": "Nifty Smallcap 250", "MICRO250": "Nifty Microcap 250",
    "NANO250": "Nano Cap", "NANO": "> ₹2,000 Cr",   # S175 / S194: our own groups, not NSE indices
}

SP_CSS = """
.sp-head{display:flex;flex-direction:column;gap:10px;padding-top:8px;padding-bottom:16px;border-bottom:1px solid var(--c-rule)}
.dh .sp-head .dh-h1{max-width:24ch}
.sp-tiles{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));margin-top:12px;border-top:1px solid var(--c-rule)}
.sp-tiles.n3{grid-template-columns:repeat(3,minmax(0,1fr))}
.sp-tile{padding:14px 16px 0 0;display:flex;flex-direction:column;gap:2px;min-width:0}
.sp-tile+.sp-tile{padding-left:16px;border-left:1px solid var(--c-rule)}
.sp-tile .k{font-size:var(--fs-12);color:var(--c-muted)}
.sp-tile .v{font-family:var(--font-serif);font-size:var(--fs-30);font-weight:400;line-height:1.2;font-variant-numeric:tabular-nums lining-nums;white-space:nowrap}
.sp-tile .s{font-size:var(--fs-13);color:var(--c-text_2)}
.sp-sec{border-bottom:1px solid var(--c-rule);padding-bottom:16px}
.dh .dh-h2 .up{color:var(--c-up)}.dh .dh-h2 .down{color:var(--c-down)}.dh .dh-h2 .watch{color:var(--c-caution)}
.sp-tbox{overflow-x:auto;-webkit-overflow-scrolling:touch}
table.sp-t{border-collapse:collapse;width:100%;font-size:var(--fs-13)}
.sp-t th,.sp-t td{padding:9px 10px;border-bottom:1px solid var(--c-rule);vertical-align:top;text-align:left}
.sp-t thead th{font-size:var(--fs-12);font-weight:500;color:var(--c-muted);border-bottom:1px solid var(--c-rule_strong);vertical-align:bottom}
.sp-t thead th.n{text-align:right}
.sp-t tbody th{font-weight:500;white-space:nowrap}
.sp-t .sub{display:block;font-size:var(--fs-12);color:var(--c-muted);font-weight:400}
.sp-t td.n{text-align:right;font-family:var(--font-mono);font-variant-numeric:tabular-nums;white-space:nowrap}
.sp-t td.past{color:var(--c-muted)}
.sp-t td.up{color:var(--c-up)}.sp-t td.down{color:var(--c-down)}.sp-t td.watch{color:var(--c-caution)}
.sp-t tr.me th b,.sp-t tr.me td{font-weight:600}
.sp-t tr.me{background:var(--c-subtle)}
.sp-t th:first-child,.sp-t td:first-child{padding-left:0}
.sp-t th:last-child,.sp-t td:last-child{padding-right:0}
.sp-t a{color:var(--c-ink);text-decoration:none}
.sp-t a:hover{text-decoration:underline}
.sp-trail{display:grid;grid-template-columns:minmax(0,1fr) 220px;gap:24px;align-items:start}
.sp-trail svg{width:220px;height:170px;display:block}
.sp-trail text{fill:var(--c-muted);font-family:var(--font-ui);font-size:var(--fs-12)}
.sp-trail .cap{font-size:var(--fs-12);color:var(--c-muted);margin-top:4px}
.sp-ladder{max-width:640px}
.sp-ladder .track{position:relative;height:22px;margin:0 8px}
.sp-ladder .track::before{content:"";position:absolute;left:0;right:0;top:9px;height:4px;background:var(--c-rule);border-radius:2px}
.sp-ladder .seg{position:absolute;top:9px;height:4px;background:var(--c-ink);border-radius:2px}
.sp-ladder .dot{position:absolute;top:5px;width:12px;height:12px;margin-left:-6px;border-radius:50%;background:var(--c-white);border:2px solid var(--c-ink)}
.sp-ladder .dot.now{background:var(--c-ink)}
.sp-ladder .dot.line{border-color:var(--c-muted);border-style:dashed}
.sp-ladder .labels{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin-top:8px;font-size:var(--fs-12);color:var(--c-muted)}
.sp-ladder .labels div:nth-child(n+2){text-align:center}.sp-ladder .labels div:last-child{text-align:right}
.sp-ladder .labels b{display:block;font-family:var(--font-mono);font-variant-numeric:tabular-nums;font-size:var(--fs-13);font-weight:500;color:var(--c-ink)}
.sp-grid2{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:32px;align-items:start}
.sp-grid2 .dh-note+.dh-note{margin-top:12px}
.dh-note b{color:var(--c-ink);font-weight:600}
a.sp-go{color:var(--c-up);text-decoration:none;font-weight:500}
a.sp-go:hover{text-decoration:underline}
.sp-key{display:flex;flex-wrap:wrap;gap:4px 16px;font-size:var(--fs-12);color:var(--c-muted)}
.sp-key .tri{display:inline-block;width:0;height:0;border-left:4px solid transparent;border-right:4px solid transparent;border-bottom:6px solid var(--c-muted);margin-right:4px}
.sp-key .ln{display:inline-block;width:4px;height:12px;background:var(--c-ink);margin-right:4px;vertical-align:-1px}
.sp-ret{--pitch:8px;--lw:4px}
.lb{position:relative;display:inline-block;vertical-align:middle;height:18px;width:calc(var(--n) * var(--pitch))}
.lb::before{content:"";position:absolute;inset:0;background:repeating-linear-gradient(to right,var(--c-rule) 0 var(--lw),transparent var(--lw) var(--pitch))}
.lb i{position:absolute;top:0;bottom:0}
.lb .f{left:calc(var(--s) * var(--pitch));width:calc(var(--f) * var(--pitch));background:repeating-linear-gradient(to right,var(--c-ink) 0 var(--lw),transparent var(--lw) var(--pitch))}
.lb .p{left:calc(var(--pa) * var(--pitch));width:var(--lw);top:auto;height:calc(var(--part) * 18px);background:var(--c-ink)}
.lb .z{left:calc(var(--z) * var(--pitch) - 3px);width:2px;top:-3px;bottom:-3px;background:var(--c-ink)}
.lb .m{left:calc(var(--m) * var(--pitch) - 4px);top:auto;bottom:-9px;width:0;height:0;border-left:4px solid transparent;border-right:4px solid transparent;border-bottom:6px solid var(--c-muted)}
.sp-t td.bar{padding-top:11px;padding-bottom:13px}
.sp-checks{list-style:none;padding:0;margin:0;columns:2 26em;column-gap:32px;font-size:var(--fs-13)}
.sp-checks li{padding:7px 0 7px 22px;border-bottom:1px solid var(--c-rule);position:relative;break-inside:avoid}
.sp-checks li::before{content:"✓";position:absolute;left:0;color:var(--c-up)}
.sp-checks li.bad::before{content:"!";color:var(--c-caution);font-weight:700}
.sp-cap{display:flex;flex-wrap:wrap;justify-content:space-between;gap:6px;font-size:var(--fs-13);color:var(--c-muted)}
.sp-cap b{color:var(--c-ink)}
.sp-phone{display:none;font-size:var(--fs-12);color:var(--c-muted)}
.dh-note.sp-cols{max-width:none;columns:2 34em;column-gap:32px}
@media (max-width:900px){.sp-grid2{grid-template-columns:minmax(0,1fr);gap:16px}}
@media (max-width:640px){
 .sp-tiles,.sp-tiles.n3{grid-template-columns:repeat(2,minmax(0,1fr))}
 .sp-tile:nth-child(3){padding-left:0;border-left:0}
 .sp-tile:nth-child(n+3){border-top:1px solid var(--c-rule);margin-top:12px}
 .sp-tiles.n3 .sp-tile:last-child{grid-column:1/-1}
 .sp-tile .v{font-size:var(--fs-24)}
 .sp-trail{grid-template-columns:minmax(0,1fr);gap:12px}
 .sp-ret{--pitch:3px;--lw:2px}
 .sp-t th,.sp-t td{padding-left:6px;padding-right:6px}
 .sp-wide,.sp-pline{display:none!important}
 .sp-phone{display:block}
}
"""


def _emit(parts: list) -> None:
    from src.ui.views.dashboard_home_view import emit
    emit(parts)


def _peers_note(shown: pd.DataFrame, in_ind: pd.DataFrame, sym: str) -> str:
    """"The 8 best-ranked of the sector's 26, with this stock", or, when the stock is below them,
    "The 7 best-ranked of the sector's 26, and this stock (14th)" (S193 B: it read "eight" over seven;
    S203 st.ind.2 and rule 11: a count in a sentence is a figure)."""
    order = [str(s) for s in in_ind["Symbol"]]
    top = [str(s) for s in shown["Symbol"]]
    if sym in order and sym in top and order.index(sym) >= len(top):   # shown after the best, below them in the sector
        return (f"The {len(top) - 1:,} best-ranked of the sector’s {len(in_ind):,}, and this stock "
                f"({_ordinal(order.index(sym) + 1)})")
    return f"The {len(top):,} best-ranked of the sector’s {len(in_ind):,}, with this stock"


def _ordinal(n: int) -> str:
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def _kick(text: str) -> str:
    # "kicker" is the class the requirements check reads (rows 22, 41).
    return f'<p class="dh-kick kicker">{e(text)}</p>'


def _h2(plain_a: str, coloured: str = "", plain_b: str = "", tone: str = "up") -> str:
    mid = f'<span class="{tone}">{e(coloured)}</span>' if coloured else ""
    return f'<h2 class="dh-h2">{e(plain_a)}{mid}{e(plain_b)}</h2>'


def _num_cls(v) -> str:
    return "" if v is None or round(v, 3) == 0 else ("up" if v > 0 else "down")


# ── Data the page reads from the app's own functions ─────────────────────────

def _market() -> pd.Series | None:
    """Nifty Total Market's closes (S165), the file the Dashboard and Portfolio read."""
    try:
        from src.loaders import benchmark_indices as bi
        s = bi.series(bi.TOTAL_MARKET)
        return None if s.empty else s
    except Exception:  # noqa: BLE001 -- a missing index costs the market column, never the page
        return None


@st.cache_data(show_spinner=False, ttl=3600)
def _nse_action_list() -> tuple[pd.DataFrame | None, pd.Timestamp | None]:
    """NSE's own split/bonus/rights/demerger list (data/nse_prices/actions.parquet) and its first date."""
    from src.loaders.nse_prices import DIR
    try:
        a = pd.read_parquet(DIR / "actions.parquet")
    except (OSError, ValueError):
        return None, None
    first = pd.to_datetime(a["ex_date"], errors="coerce").min() if "ex_date" in a else None
    return a, (None if first is None or pd.isna(first) else pd.Timestamp(first))


def _holding(sym: str, prices: pd.DataFrame, rank_df: pd.DataFrame, system: str) -> sl.Holding | None:
    """The holding as Portfolio shows it: Portfolio's own table (`book_series` ->
    `build_portfolio_tracker`) at Portfolio's starting capital (PAGE_DESIGN §5.4)."""
    try:
        from src.engine.systems import inception, ledger_path
        from src.engine.track_record import load_ledger
        from src.loaders.price_loader import fetch_benchmark_history
        from src.ui.book_series import book_series
        from src.ui.canonical_book import current_book
        from src.ui.views.portfolio_view import PORTFOLIO_STARTING_CAPITAL
        bench = fetch_benchmark_history(period="5y")
        book, record = current_book(prices, bench, system)
        if book is None or book.empty:
            return None
        ledger = load_ledger(ledger_path(system), inception(system))
        series = book_series(book, record, ledger, rank_df, prices, bench, PORTFOLIO_STARTING_CAPITAL)
        return sl.holding_from_table(series.table if series is not None else None, sym)
    except Exception:  # noqa: BLE001 -- the holding's detail is a sentence, never a reason to fail
        return None


def _calendar(sym: str, as_of: pd.Timestamp, until: pd.Timestamp) -> tuple[list, pd.Timestamp | None]:
    """Board meetings and ex-dates from the day after the data to the fill (Actions' `_events`, the same window;
    S203 st.rule.4, owner 24 Nov 2026),
    and the stock's last results meeting this season (`results_calendar.for_book`)."""
    try:
        from src.engine import results_calendar as rc
        from src.ui.views.actions_page import _events
        events, _note = _events([sym], set(), set(), as_of, until)
        cal = rc.load()
        rep = rc.for_book(cal, [sym], [], as_of + pd.Timedelta(days=1)) if cal is not None else None
        last = None
        if rep is not None and len(rep.reported):
            last = pd.Timestamp(rep.reported["date"].max())
        return events, last
    except Exception:  # noqa: BLE001
        return [], None


# ── Toolbar ──────────────────────────────────────────────────────────────────

def _share_url(sym: str) -> str:
    """The short, public link `/?stock=SYMBOL` (owner, 20 Nov 2026: the URL stays as it is)."""
    from urllib.parse import urlsplit
    try:
        parts = urlsplit(str(st.context.url or ""))
        base = f"{parts.scheme}://{parts.netloc}" if parts.scheme and parts.netloc else ""
    except Exception:  # noqa: BLE001
        base = ""
    return f"{base}/?stock={quote(sym, safe='')}"


def _render_actions(sym: str, on_back=None) -> None:
    from src.ui import page_kit as kit
    from src.ui import watchlist_store

    on_list = sym.upper() in watchlist_store.symbols()
    with st.container(key="sp_actions", horizontal=True, vertical_alignment="center", gap="small"):
        if on_back:
            on_back()
        st.space("stretch")
        st.button("In watchlist" if on_list else "Add to watchlist",
                  icon=":material/star:" if on_list else ":material/star_border:",
                  key="sp_watch", type="secondary", on_click=watchlist_store.toggle, args=(sym,),
                  help=("Remove from your watchlist" if on_list else "Save to your watchlist, kept in this browser"))
        with st.popover("Share", icon=":material/link:", key="sp_share"):
            st.caption("Link to this stock's page. Use the copy button on the right.")
            st.code(_share_url(sym), language=None, wrap_lines=True)
        st.link_button("Chart on TradingView", kit.tradingview_url(sym), icon=":material/open_in_new:",
                       help="Opens this stock on TradingView in a new tab")


# ── Sections ─────────────────────────────────────────────────────────────────

def head_html(row, uni: sl.Universe, held: bool, as_of, market12, q, n_q, ln, holding, hits=(), late=False) -> list:
    kick = " · ".join(sl.kicker(row, INDEX_NAMES))
    ts = sl.tiles(row, uni, q, n_q, as_of, ln, holding if held else None)
    tiles = "".join(f'<div class="sp-tile"><span class="k">{e(t.label)}</span><span class="v">{e(t.value)}</span>'
                    f'<span class="s">{e(t.sub)}</span></div>' for t in ts)
    return ['<div class="sp-head">', _kick(kick), f'<h1 class="dh-h1">{e(sl.title(row, uni, held))}</h1>',
            f'<p class="dh-lede">{e(sl.lede(row, as_of, market12, late))}</p>',
            *([f'<p class="dh-lede">It also ranks {e(wl.ranks_elsewhere_words(list(hits)))}. '
               f'{_elsewhere_links(str(row["Symbol"]), list(hits))}</p>'] if hits else []),
            f'<div class="sp-tiles{" n3" if len(ts) == 3 else ""}">{tiles}</div></div>']


def rank_html(row, uni, q, n_q, ln, tr: sl.Trail) -> list:
    a, b, c = sl.rank_heading(row, uni, q, n_q, ln)
    heads = "".join(f'<th scope="col" class="n">{lab}<span class="sub">{e(wl.fmt_day(d)) if d is not None else formats.DASH}</span></th>'
                    for lab, d in zip(("3M ago", "1M ago", "Now"), tr.dates))
    rk = "".join(f'<td class="n{" past" if i < 2 else ""}">{"–" if r is None else r}</td>' for i, r in enumerate(tr.ranks))
    pl = "".join(f'<td class="n{" past" if i < 2 else (" up" if p is not None and p <= ln.buy else "")}">{e(sl.place_text(p))}</td>'
                 for i, p in enumerate(tr.places))
    ys = sl.trail_points(tr.places, ln.keep)
    xs = (35, 115, 195)
    pts = " ".join(f"{x},{y}" for x, y in zip(xs, ys))
    dots = "".join(f'<circle cx="{x}" cy="{y}" r="{5 if i == 2 else 4}" style="fill:var(--c-{"ink" if i == 2 else "white"})" '
                   f'stroke="var(--c-ink)" stroke-width="2"/>' for i, (x, y) in enumerate(zip(xs, ys)))
    label = ("Place among the qualified: " + ", ".join(sl.place_text(p) for p in tr.places)
             + f"; buy line {wl.fmt_ordinal(ln.buy)}, keep line {wl.fmt_ordinal(ln.keep)}")
    t = 'style="fill:var(--c-muted);font-family:IBM Plex Sans,system-ui,sans-serif;font-size:var(--fs-12)"'
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="220" height="170" viewBox="0 0 220 170">'
           '<line x1="20" x2="210" y1="52" y2="52" stroke="var(--c-muted)" stroke-dasharray="4 4"/>'
           '<line x1="20" x2="210" y1="110" y2="110" stroke="var(--c-muted)" stroke-dasharray="2 4"/>'
           f'<text x="210" y="66" text-anchor="end" {t}>Buy line, {wl.fmt_ordinal(ln.buy)}</text>'
           f'<text x="210" y="124" text-anchor="end" {t}>Keep line, {wl.fmt_ordinal(ln.keep)}</text>'
           f'<polyline points="{pts}" fill="none" stroke="var(--c-ink)" stroke-width="2"/>{dots}'
           f'<text x="35" y="166" text-anchor="middle" {t}>3M</text><text x="115" y="166" text-anchor="middle" {t}>1M</text>'
           f'<text x="195" y="166" text-anchor="middle" {t}>Now</text></svg>')
    # st.html's cleaner drops inline SVG, so the trail is an image with the theme's colours
    # written in, as the Dashboard's rank trail is.
    from src.ui.tokens import resolve
    img = (f'<img width="220" height="170" alt="{e(label)}" '
           f'src="data:image/svg+xml,{quote(resolve(svg))}">')
    return ['<section class="dh-sec sp-sec">', _kick("1 · Rank"), _h2(a, b, c, "up" if q is not None and q <= ln.keep else "down"),
            '<div class="sp-trail"><div><div class="sp-tbox"><table class="sp-t"><thead><tr><th scope="col"></th>'
            f'{heads}</tr></thead><tbody><tr><th scope="row">{e(uni.rank_label)}</th>{rk}</tr>'
            f'<tr><th scope="row">Place among the qualified</th>{pl}</tr></tbody></table></div>'
            f'<p class="dh-note" style="margin-top:12px">{e(sl.rank_note(row, uni, ln))}</p></div>'
            f'<div>{img}<div class="cap">Place among the qualified; higher is better.</div></div></div>', "</section>"]


def rules_html(row, a: dict | None, q, ln, high_pct, ladder: sl.Ladder, held, holding, check, events, last_res,
               fill=None) -> list:
    from src.ui.system_param import page_href
    from src.engine.exit_watch import SELL, WATCH
    ca, cb = sl.rules_heading(a, check, high_pct, bool(held))
    status = (a or {}).get("status")
    tone = "down" if status == SELL else "watch" if status == WATCH else "up"
    at_high = ladder.close is not None and ladder.high is not None and round(ladder.close) >= round(ladder.high)
    seg_from = ladder.x(ladder.ema) if ladder.ema is not None else 0.0
    now_x = ladder.x(ladder.close)
    dots = (f'<span class="seg" style="left:{min(seg_from, now_x)}%;width:{abs(now_x - seg_from)}%"></span>'
            f'<span class="dot" style="left:0%"></span><span class="dot line" style="left:{ladder.x(ladder.line)}%"></span>'
            f'<span class="dot" style="left:{ladder.x(ladder.ema)}%"></span>'
            + ('' if at_high else '<span class="dot" style="left:100%"></span>')
            + f'<span class="dot now" style="left:{now_x}%"></span>')
    hi_label = "52W high · close" if at_high else "52W high"
    labels = (f'<div>52W low<b>{formats.price(ladder.low)}</b>{e(formats.date(ladder.low_date)) if ladder.low_date is not None else ""}</div>'
              f'<div>−{round((1 - high_pct) * 100)}% line<b>{formats.price(ladder.line)}</b>filter line</div>'
              f'<div>50D EMA<b>{formats.price(ladder.ema)}</b>trend line</div>'
              f'<div>{hi_label}<b>{formats.price(ladder.high)}</b>{e(formats.date(ladder.high_date)) if ladder.high_date is not None else ""}</div>')
    aria = (f"52W low {formats.price(ladder.low)}, −20% line {formats.price(ladder.line)}, 50D EMA "
            f"{formats.price(ladder.ema)}, 52W high {formats.price(ladder.high)}, close {formats.price(ladder.close)}")
    rows = "".join(
        f'<tr><th scope="row">{e(r.name)}<span class="sub">{e(r.kind)}</span></th><td class="n sp-pline">{e(r.line)}</td>'
        f'<td class="n">{e(r.fall)}</td><td class="n {"up" if r.ok else "down"}">{e(r.today)}</td></tr>'
        for r in sl.rules(row, a, q, ln, high_pct))
    lead, rest = sl.holding_sentence(held, holding)
    book = (f'<p class="dh-note"><b>{e(lead)}</b>{e(rest)} {e(sl.calendar_sentence(check, events, last_res, fill))} '
            f'<a class="sp-go" href="{e(page_href("actions"))}" target="_self">The plan, share by share, on Actions →</a></p>')
    return ['<section class="dh-sec sp-sec">', _kick("2 · Filters and sell rules"), _h2("", ca, cb, tone),
            f'<div class="sp-ladder" role="img" aria-label="{e(aria)}"><div class="track">{dots}</div>'
            f'<div class="labels">{labels}</div></div>',
            '<div class="sp-grid2"><div class="sp-tbox"><table class="sp-t"><thead><tr><th scope="col">Rule</th>'
            '<th scope="col" class="n sp-pline">Line</th><th scope="col" class="n">Fall to reach it</th>'
            f'<th scope="col" class="n">Today</th></tr></thead><tbody>{rows}</tbody></table></div>'
            f'<div>{book}<p class="dh-note">{e(sl.highs_note(row))}</p></div></div>', "</section>"]


def returns_html(ws: list[sl.Window], as_of, uni, late: bool = False) -> list:
    step = sl.line_step(ws)
    bs = sl.bars(ws, step)
    a, b, c = sl.returns_heading(ws)
    body = []
    for w, bar in zip(ws, bs):
        style = (f"--n:{bar.n};--z:{bar.zero};--s:{bar.start};--f:{bar.filled};--part:{bar.part};"
                 f"--pa:{bar.part_at if bar.part_at is not None else 0};--m:{bar.market if bar.market is not None else 0}")
        inner = ('<i class="f"></i>' + ('<i class="p"></i>' if bar.part_at is not None else "") + '<i class="z"></i>'
                 + ('<i class="m"></i>' if bar.market is not None else ""))
        aria = f"{formats.pct(w.ret)} against {formats.pct(w.market)} for {sl.MARKET}"
        start = f'<span class="sub sp-wide">from {e(formats.date(w.start))}</span>' if w.start is not None else ""
        body.append(
            f'<tr><th scope="row">{w.months}M{start}</th>'
            f'<td class="bar"><span class="lb" role="img" aria-label="{e(aria)}" style="{style}">{inner}</span></td>'
            f'<td class="n {_num_cls(w.ret)}">{formats.pct(w.ret)}</td><td class="n">{formats.pct(w.market)}</td>'
            f'<td class="n sp-wide {_num_cls(w.lead)}">{formats.pts(w.lead)}</td>'
            f'<td class="n sp-wide">{formats.pct(w.typical)}</td>'
            f'<td class="n">{formats.pct(w.fall, fraction=False)}</td>'
            f'<td class="n sp-wide">{formats.pct(w.typical_fall, fraction=False)}</td>'
            f'<td class="n sp-wide">{formats.signed(w.sharpe, 2, plus=False) if w.sharpe is not None else formats.DASH}</td>'
            f'<td class="n sp-wide">{wl.fmt_ordinal(w.place) if w.place is not None else formats.DASH}</td></tr>')
    return ['<section class="dh-sec sp-sec">', _kick("3 · Returns and falls"), _h2(a, b, c, sl.returns_tone(ws)),
            f'<div class="sp-key"><span><i class="ln"></i>One line is {step}% of return, one scale for every row</span>'
            f'<span><i class="tri"></i>{sl.MARKET}, same sessions</span></div>',
            '<div class="sp-tbox sp-ret"><table class="sp-t"><thead><tr><th scope="col">Window</th><th scope="col">Return</th>'
            '<th scope="col" class="n">Stock</th><th scope="col" class="n">Nifty Total Market</th><th scope="col" class="n sp-wide">Lead, pts</th>'
            '<th scope="col" class="n sp-wide">Typical stock</th><th scope="col" class="n">Max DD</th>'
            '<th scope="col" class="n sp-wide">Typical max DD</th><th scope="col" class="n sp-wide">Sharpe</th>'
            f'<th scope="col" class="n sp-wide">Rank by return</th></tr></thead><tbody>{"".join(body)}</tbody></table></div>',
            '<p class="sp-phone">On a wider screen: each window’s first day, the lead in pts, the typical stock’s '
            'return and fall, Sharpe, and rank by return.</p>',
            f'<p class="dh-note sp-cols">{e(sl.returns_note(as_of, uni))}'
            + (f" {e(formats.closes_not_in([sl.MARKET], as_of))}" if late else "") + '</p>', "</section>"]


def results_html(res) -> list:
    """5 · Results (owner, 25 Nov 2026: "one table showing last 8-10 quarter key numbers and % growth"): the
    company's last eight reported quarters, each against the same quarter a year earlier."""
    from src.engine.earnings_review import Results
    if not isinstance(res, Results) or not res.quarters:
        return []
    q0 = res.quarters[0]
    g = q0.growth
    lead = "Profit before tax" if res.lender else "Operating profit"
    sales = "Revenue" if res.lender else "Sales"
    if g.get("net_profit") is not None:
        verb = "rose" if g["net_profit"] >= 0 else "fell"
        tail = f" on {sales.lower()} {'up' if (g.get('sales') or 0) >= 0 else 'down'} {abs(g['sales']):.1f}%." \
            if g.get("sales") is not None else "."
        head = _h2(f"In {q0.label} net profit {verb} ", formats.pct(abs(g["net_profit"]), signed_=False, fraction=False),
                   f" from a year earlier{tail}", "up" if g["net_profit"] >= 0 else "down")
    else:
        head = _h2(f"{sales} and profit in the last {len(res.quarters)} quarters.")

    def cr(v):
        return formats.DASH if v is None else ("−" if v < 0 else "") + formats.indian_group(round(abs(v)))

    def eps(v):
        return formats.DASH if v is None else formats.signed(v, 2, plus=False)

    def yoy(v, wide=""):
        return f'<td class="n {wide} {_num_cls(v)}">{formats.pct(v, fraction=False)}</td>'

    body = []
    for q in res.quarters:
        v, gr = q.values, q.growth
        body.append(f'<tr><th scope="row">{e(q.label)}</th>'
                    f'<td class="n">{cr(v["sales"])}</td>{yoy(gr["sales"])}'
                    f'<td class="n sp-wide">{cr(v["profit"])}</td>{yoy(gr["profit"], "sp-wide")}'
                    f'<td class="n">{cr(v["net_profit"])}</td>{yoy(gr["net_profit"])}'
                    f'<td class="n sp-wide">{eps(v["eps"])}</td>{yoy(gr["eps"], "sp-wide")}</tr>')
    dash = any(x is None for q in res.quarters for x in q.growth.values())
    note = (f"The company's reported results, {res.basis}, in ₹ crore (EPS in ₹), each quarter against the same quarter "
            f"a year earlier; last updated {formats.date(res.read)}."
            + (" Growth reads – where the year-earlier figure is nil or a loss." if dash else "")
            + (" For a bank or lender, profit before tax stands in for operating profit." if res.lender else ""))
    return ['<section class="dh-sec sp-sec">', _kick("5 · Results"), head,
            '<div class="sp-tbox"><table class="sp-t"><thead><tr><th scope="col">Quarter</th>'
            f'<th scope="col" class="n">{sales}, Cr</th><th scope="col" class="n">YoY</th>'
            f'<th scope="col" class="n sp-wide">{lead}, Cr</th><th scope="col" class="n sp-wide">YoY</th>'
            '<th scope="col" class="n">Net profit, Cr</th><th scope="col" class="n">YoY</th>'
            '<th scope="col" class="n sp-wide">EPS, ₹</th><th scope="col" class="n sp-wide">YoY</th>'
            f'</tr></thead><tbody>{"".join(body)}</tbody></table></div>',
            f'<p class="sp-phone">On a wider screen: {lead.lower()} and EPS, with their growth.</p>',
            f'<p class="dh-note">{e(note)}</p>', "</section>"]


def industry_html(row, shown: pd.DataFrame, in_ind: pd.DataFrame, as_of) -> list:
    from src.ui.industry_names import short_industry
    from src.ui.system_param import stock_href, suffix
    sym = str(row["Symbol"])
    body = []
    for _, r in shown.iterrows():
        s = str(r["Symbol"])
        me = s == sym
        q = sl.num(r.get("Qualified Rank"))
        name = sl.short_name(r.get("Company Name"), s) + (" · this stock" if me else "")
        cells = "".join(f'<td class="n {_num_cls(sl.num(r.get(f"{m}M Return")))}">{formats.pct(sl.num(r.get(f"{m}M Return")))}</td>'
                        for m in (1, 3, 6, 12))
        ema = sl.num(r.get("% 50 EMA"))
        body.append(
            f'<tr class="{"me" if me else ""}"><td class="n">{int(r["Rank"])}</td>'
            f'<td class="n">{e(sl.place_text(None if q is None else int(q)))}</td>'
            f'<th scope="row"><a href="{e(stock_href(s))}" target="_self"><b>{e(s)}</b></a><span class="sub">{e(name)}</span></th>'
            f'<td class="n">{formats.price(r.get("CMP"))}</td>{cells}'
            f'<td class="n">{e(sl.from_high(r, as_of))}</td>'
            f'<td class="n {_num_cls(ema)}">{formats.pct(ema, fraction=False)}</td></tr>')
    ind_full = str(row.get("Industry") or "")
    ind = short_industry(ind_full)
    href = f"screener?ind={quote(ind_full, safe='')}{suffix()}"
    return ['<section class="dh-sec sp-sec">', _kick("6 · Sector"), _h2(sl.industry_heading(row, in_ind)),
            '<div class="sp-tbox"><table class="sp-t"><thead><tr><th scope="col" class="n">Rank</th>'
            '<th scope="col" class="n">Qualified</th><th scope="col">Stock</th><th scope="col" class="n">Price</th>'
            '<th scope="col" class="n">1M</th><th scope="col" class="n">3M</th><th scope="col" class="n">6M</th>'
            '<th scope="col" class="n">12M</th><th scope="col" class="n">From 52W high</th>'
            f'<th scope="col" class="n">vs 50D EMA</th></tr></thead><tbody>{"".join(body)}</tbody></table></div>',
            f'<p class="dh-note">{e(_peers_note(shown, in_ind, str(row.get("Symbol"))))}; returns in %. '
            f'<a class="sp-go" href="{e(href)}" target="_self">All {len(in_ind)} {e(ind)} stocks on the Screener →</a></p>',
            "</section>"]


def data_html(dc: sl.DataChecks) -> list:
    items = [(ok, text) for ok, text in dc.items] + [(True, sl.action_line(a)) for a in dc.actions]
    lis = "".join(f'<li class="{"" if ok else "bad"}">{e(text)}</li>' for ok, text in items)
    note = ('<p class="dh-note">Corporate actions are read from NSE’s own lists; the prices before an ex-date are '
            'scaled by its factor, so the step is not counted as a gain or a fall in the ranking or the record.</p>'
            if dc.actions else "")
    return ['<section class="dh-sec sp-sec">', _kick("7 · Data"), _h2(sl.data_heading(dc)),
            f'<ul class="sp-checks">{lis}</ul>', note, "</section>"]


# ── Not in the ranking (row 20) ──────────────────────────────────────────────

def _render_not_ranked(symbol: str, rank_df: pd.DataFrame, uni: sl.Universe, as_of, on_back,
                       members=(), other_rankings=None) -> None:
    from src.ui.views.watchlist_view import _nse_lists
    try:
        changes, listed = _nse_lists()
    except Exception:  # noqa: BLE001
        changes, listed = None, set()
    # The same pointers as the Watchlist (S193 item A #1): without the other systems'
    # rankings a stock ranked in the 750 read "in none of the systems' lists" under Nano.
    others = _other_ranks(other_rankings)
    rows = wl.not_ranked([symbol], rank_df, universe=uni.short, members=members or (),
                         changes=changes, listed=listed, others=others)
    why = f"{rows[0].why} {rows[0].where if rows[0].where != wl.MISSING else ''}".strip() if rows else ""
    new = rows[0].replace_with if rows else ""
    hits = wl.ranks_elsewhere(symbol, others) if rows and rows[0].kind == wl.ELSEWHERE else []
    if hits:
        go = " " + _elsewhere_links(symbol, hits)
    elif new:
        from src.ui.system_param import stock_href
        go = f' <a class="sp-go" href="{e(stock_href(new))}" target="_self">{e(new)}’s page →</a>'
    else:   # S203 st.nr.1: a link, as the other ways on are
        from src.ui.system_param import page_href
        go = f' <a class="sp-go" href="{e(page_href("screener"))}" target="_self">Back to the Screener →</a>'
    _render_actions(symbol, on_back)
    _emit(['<div class="sp-head">', _kick(f"Stock · {symbol}"),
           f'<h1 class="dh-h1">{e(symbol)} is not in the current ranking of {e(uni.the)}.</h1>',
           f'<p class="dh-lede">{e(why)}{go}</p></div>',
           f'<p class="dh-foot">{e(sl.foot(as_of))}</p>'])


def _elsewhere_links(symbol: str, hits: list) -> str:
    """' See it in the Nifty 750 → · See it in the Nifty 1000 →' for each other system ranking it."""
    from src.ui.system_param import suffix
    keys = {v: k for k, v in _system_names().items()}
    links = []
    for name, _r, _n in hits:
        key = keys.get(name)
        if key:
            href = f"screener?stock={quote(symbol, safe='')}{suffix(key)}"
            links.append(f'<a class="sp-go" href="{e(href)}" target="_self">See it in {e(wl.fmt_system(name))} →</a>')
    return " · ".join(links)


def _other_ranks(other_rankings) -> dict:
    try:
        return other_rankings() if callable(other_rankings) else (other_rankings or {})
    except Exception:  # noqa: BLE001 -- another system's ranking is a pointer, never a reason to fail
        return {}


def _system_names() -> dict:
    from src.engine.extra_universe import SYSTEM_NAMES
    return dict(SYSTEM_NAMES)


# ── Main entry ───────────────────────────────────────────────────────────────

def render_stock_view(
    symbol: str,
    rank_df: pd.DataFrame,
    adj_close: pd.DataFrame,
    high_prices: pd.DataFrame | None = None,
    low_prices: pd.DataFrame | None = None,
    volume_data: pd.DataFrame | None = None,
    open_prices: pd.DataFrame | None = None,
    *,
    on_back=None,
    book_symbols=None,
    history_prices: pd.DataFrame | None = None,
    system: str | None = None,
    members=(),
    other_rankings=None,
) -> None:
    """Render the page for one symbol. members (this system's list) and other_rankings
    ({system name: ranking}, or a callable giving it) explain a stock this system does not rank."""
    from src.engine.exit_watch import assess, qualified_ranks
    from src.engine.track_record import TRACK_RECORD_CONFIG
    from src.ui import system_param
    from src.ui.stock_chart import (DEFAULT_RANGE, RANGE_WORDS, RANGES, ranking_ema, relative_strength,
                                    render_price_chart, window)
    from src.ui.views.dashboard_home_view import HOME_CSS
    from src.ui.views.ranking_view import _month_ago, with_book_columns

    system = system or system_param.current()
    uni = sl.universe(system, len(rank_df))
    # The session the header shows, not the frame's last row (S193 E).
    as_of = (formats.session_of(adj_close) if adj_close is not None and len(adj_close.index)
             else pd.Timestamp.today().normalize())
    st.html(f"<style>{HOME_CSS}{SP_CSS}</style>")

    match = rank_df[rank_df["Symbol"].astype(str).str.upper() == str(symbol).upper()]
    if match.empty:
        _render_not_ranked(str(symbol).upper(), rank_df, uni, as_of, on_back,
                           members=members, other_rankings=other_rankings)
        return
    row = match.iloc[0]
    sym = str(row["Symbol"])
    prices = history_prices if history_prices is not None else adj_close
    ln = wl.lines()
    high_pct = float(TRACK_RECORD_CONFIG["high_pct"])
    held = sym in set(book_symbols or ())

    qmap = qualified_ranks(rank_df)
    q = int(qmap[sym]) if sym in qmap.index else None
    n_q = len(qmap)
    full = with_book_columns(rank_df, book_symbols, prices)
    me = full[full["Symbol"].astype(str) == sym]
    past = ([me.iloc[0].get("Qualified (-3M)"), me.iloc[0].get("Qualified (-1M)")]
            if not me.empty and "Qualified (-3M)" in me.columns else [None, None])
    tr = sl.trail(row, [_month_ago(adj_close, 3), _month_ago(adj_close, 1), as_of], past, q)

    # Closes in the 52-week window, for a recent listing's "too new to have a 52-week high: 70 of 126 sessions".
    if sym in adj_close.columns:
        from src.engine.calendar_momentum import year_window_start
        _s = adj_close[sym].loc[:as_of]
        n_win = int(_s.iloc[year_window_start(_s.index, len(_s) - 1):].notna().sum()) if len(_s) else 0
    else:
        n_win = None
    a = assess(rank_df, [sym], sessions=None if n_win is None else {sym: n_win})
    a_row = a.iloc[0].to_dict() if not a.empty else None
    from src.ui.views.actions_view import next_rebalance
    check, fill = next_rebalance(as_of)
    events, last_res = _calendar(sym, as_of, fill if fill is not None else check)
    holding = _holding(sym, prices, rank_df, system) if held else None

    market = _market()
    if market is not None:
        market = market[market.index <= as_of]     # one session for the whole page (S148)
    # A late close is "–", never a session-early figure read as today's (S148; S203 st.ret.3). The Dashboard
    # and Portfolio already do this.
    late = market is not None and (market.dropna().empty or market.dropna().index[-1] < pd.Timestamp(as_of))
    ws = sl.windows(row, rank_df, adj_close.index, None if late else market)
    m12 = next((w.market for w in ws if w.months == 12), None)

    closes = adj_close[sym] if sym in adj_close.columns else None
    # The chart and its 50D EMA on daily closes over the whole range (S193 B): the ranking frame, its
    # weekly years filled from NSE's long file. The deep store is weekly before mid-2025, which put the
    # EMA a year back at Rs 1,448 for RELIANCE against Rs 1,454 on NSE's daily closes.
    from src.ui import daily_history
    chart_close = daily_history.stock_close(sym, adj_close)
    if chart_close.empty:
        chart_close = (history_prices[sym].dropna() if history_prices is not None and sym in history_prices.columns
                       else closes.dropna() if closes is not None else pd.Series(dtype=float))
    chart_close = chart_close[chart_close.index <= as_of]

    _render_actions(sym, on_back)
    hits = wl.ranks_elsewhere(sym, _other_ranks(other_rankings))
    _emit(head_html(row, uni, held, as_of, m12, q, n_q, ln, holding, hits, late)
          + rank_html(row, uni, q, n_q, ln, tr)
          + rules_html(row, a_row, q, ln, high_pct, sl.ladder(row, closes, high_pct), held, holding, check,
                       events, last_res, fill)
          + returns_html(ws, as_of, uni, late))

    # 4 · Price: the chart is a widget (the range control), so the section is drawn in pieces.
    ema = ranking_ema(chart_close) if not chart_close.empty else pd.Series(dtype=float)
    above, of = sl.sessions_above(chart_close, ema)
    # The heading's relative strength over the range the chart shows: each chip rewrites it (S193 H2; at 3Y the
    # pane read 85.4 while the heading read the 12M figure, item H C16).
    heads = {}
    for lab, months in RANGES.items():
        rs = relative_strength(window(chart_close, months), market)
        pa, pb, pc = sl.price_heading(above, of, float(rs.iloc[-1]) if len(rs) else None)
        heads[lab] = _h2(pa, pb, pc.replace(RANGE_WORDS[DEFAULT_RANGE], RANGE_WORDS[lab]))
    head = heads[DEFAULT_RANGE].replace('<h2 class="dh-h2">', '<h2 class="dh-h2 sp-price-h">', 1)
    follow = {"sel": "h2.sp-price-h", "html": {k: v[len('<h2 class="dh-h2">'):-len("</h2>")] for k, v in heads.items()}}
    _emit(['<section class="dh-sec sp-sec" style="padding-bottom:0;border-bottom:0">', _kick("4 · Price"), head,
           f'<div class="sp-cap"><b>Price and relative strength</b><span>against {sl.MARKET}</span></div>', "</section>"])
    vol = volume_data[sym] if volume_data is not None and sym in volume_data.columns else None
    if not chart_close.empty:
        render_price_chart(sym, chart_close, vol, market, follow=follow)
    _emit([f'<div class="sp-sec"><p class="dh-note">{e(sl.PRICE_NOTE)}</p></div>'])

    shown, in_ind = sl.peers(full, row)
    actions_df, actions_from = _nse_action_list()
    dc = sl.data_checks(row, as_of, sl.nse_actions(actions_df, sym), actions_from)
    from src.engine.earnings_review import company
    _emit(results_html(company(sym)) + (industry_html(row, shown, in_ind, as_of) if len(in_ind) else [])
          + data_html(dc) + [f'<p class="dh-foot">{e(sl.foot(as_of))}</p>'])
    render_data_quality_footer(
        total_stocks=len(rank_df),
        gap_count=gap_count(rank_df),
        short_count=int((rank_df.get("Short History", pd.Series(dtype=str)) == "Yes").sum()),
        # No `as_of`: the page's own foot line carries "Data to <date> · NSE" (S173 rule 7).
    )
