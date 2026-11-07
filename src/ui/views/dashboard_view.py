"""The home page: is anything in the book at risk, and what happens next.

Owner, 7 Nov 2026: a dashboard as the home page, drawn in "Paper B · Ledger",
with tipsheet's ideas taken from their original sources. Every figure here
comes from something another page already computes, from the same function:
the model book and its month from the Track Record replay (as Portfolio), the
rules and the rebalance plan from Actions, the industry board from Sectors.
The one new input is NSE's index levels (src/loaders/index_levels.py), shown
only when their Nifty 50 matches NSE's own daily closes.

The market line (regime, breadth) is in the header on every page, so it is
not repeated here.
"""
from __future__ import annotations

import html

import pandas as pd
import streamlit as st

from src.core.market_time import ist_now
from src.engine import size_leadership as sl
from src.engine.actions import plan_rebalance
from src.engine.exit_watch import (
    SELL,
    STATUS_LABEL,
    UNKNOWN,
    WATCH,
    RANK_SCALE,
    Rules,
    assess,
    least_room,
    nearest_rule,
)
from src.engine.track_record import TRACK_RECORD_CONFIG
from src.loaders.index_levels import fetch_index_levels, nse_benchmarks
from src.ui import page_kit as kit
from src.ui.canonical_book import current_book
from src.ui.components import gap_count, render_data_quality_footer
from src.ui.system_param import stock_href
from src.ui.views.actions_view import _day, _sessions_between, next_rebalance
from src.ui.views.sector_view import industry_board

AT_RISK_ROWS = 8


def _pct(v, signed: bool = True) -> str:
    if v is None or pd.isna(v):
        return "—"
    v = round(float(v) * 100, 1)
    sign = ("+" if v > 0 else "−" if v < 0 else "") if signed else ("−" if v < 0 else "")
    return f"{sign}{abs(v):.1f}%"


def _tone(v) -> str:
    return "" if v is None or pd.isna(v) or round(float(v), 4) == 0 else ("up" if v > 0 else "down")


def _link(sym: str) -> str:
    return f'<a href="{stock_href(sym)}" target="_self">{html.escape(sym)}</a>'


def answer_line(mtd, bench_mtd, n_watch: int, n_sell: int, check: pd.Timestamp) -> str:
    """The page's one sentence. Built from the same figures shown below it."""
    parts = []
    if mtd is not None and pd.notna(mtd):
        parts.append(f"The book is {_pct(mtd)} this month"
                     + (f" against {_pct(bench_mtd)} for the Nifty 500" if pd.notna(bench_mtd) else ""))
    risk = []
    if n_sell:
        risk.append(f"{n_sell} would be sold if the month ended today")
    if n_watch:
        risk.append(f"{n_watch} {'is' if n_watch == 1 else 'are'} close to a rule")
    parts.append("; ".join(risk) if risk else "no holding is close to a rule")
    parts.append(f"next rebalance {_day(check, weekday=True)}")
    return "; ".join(parts) + "."


def _at_risk_html(a: pd.DataFrame, rules: Rules) -> str:
    rows = a[a["status"] != UNKNOWN].copy()
    rows["_room"] = [least_room(r, rules) for _, r in rows.iterrows()]
    rows = rows.sort_values("_room", na_position="last").head(AT_RISK_ROWS)
    out = []
    for _, r in rows.iterrows():
        room = r["_room"]
        w = 0.0 if room is None or pd.isna(room) else max(2.0, min(100.0, room / RANK_SCALE * 100))
        status = r["status"]
        rule = r["why"] if status == SELL else nearest_rule(r, rules)
        out.append(
            f'<div class="db-risk-row {status}" role="row"><span class="db-sym" role="rowheader">{_link(str(r["Symbol"]))}'
            f'<small>{html.escape(str(r.get("Industry") or ""))}</small></span>'
            f'<span class="db-status" role="cell">{html.escape(STATUS_LABEL[status])}</span>'
            f'<span class="db-rule" role="cell">{html.escape(rule)}</span>'
            f'<span class="db-bar" aria-hidden="true"><i style="width:{w:.0f}%"></i></span></div>')
    head = ('<div class="db-risk-row db-head" role="row"><span role="columnheader">Holding</span>'
            '<span role="columnheader">At rebalance</span>'
            '<span role="columnheader">Nearest rule · room</span><span aria-hidden="true">Room</span></div>')
    return f'<div class="db-risk" role="table" aria-label="Book at risk">{head}{"".join(out)}</div>'


def _names(symbols) -> str:
    return ", ".join(_link(s) for s in symbols) if symbols else "none"


def _size_html(res: sl.SizeLeadership) -> str:
    cols = [w for w in sl.WINDOWS if w in res.starts]
    head = "".join(f"<th>{w}M<small>from {res.starts[w]:%d %b}</small></th>" for w in cols)
    body = []
    for name in [n for _, n in sl.INDICES] + ["Nifty 500"]:
        r = res.table.loc[name]
        cells = []
        for w in cols:
            if name == "Nifty 500":
                cells.append(f'<td class="{_tone(r[f"{w}M"])}">{_pct(r[f"{w}M"])}</td>')
            else:
                rel, ab = r[f"{w}M vs 500"], r[f"{w}M"]
                cells.append(f'<td><b class="{_tone(rel)}">{_pct(rel)}</b><small>{_pct(ab)}</small></td>')
        cls = ' class="db-base"' if name == "Nifty 500" else ""
        body.append(f"<tr{cls}><th>{html.escape(name)}</th>{''.join(cells)}</tr>")
    return (f'<table class="db-size"><thead><tr><th>Against the Nifty 500</th>{head}</tr></thead>'
            f'<tbody>{"".join(body)}</tbody></table>')


def render_dashboard_view(rank_df: pd.DataFrame, adj_close: pd.DataFrame,
                          benchmark_close: pd.Series | None, system: str = "750") -> None:
    cfg = TRACK_RECORD_CONFIG
    rules = Rules(buffer_n=int(cfg["buffer_n"]), high_pct=float(cfg["high_pct"]))
    as_of = (pd.Timestamp(adj_close.index[-1]) if adj_close is not None and len(adj_close)
             else pd.Timestamp(ist_now().date()))
    check, fill = next_rebalance(as_of)

    with st.spinner("Loading the model book…"):
        book, record = current_book(adj_close, benchmark_close, system)
    symbols = [] if book is None or book.empty else book["Symbol"].tolist()
    meta = (record or {}).get("live_meta") or {}
    mtd = pd.to_numeric(meta.get("strategy_mtd"), errors="coerce")
    bench_mtd = pd.to_numeric(meta.get("benchmark_mtd"), errors="coerce")

    if not symbols:
        kit.page_head("Dashboard", f"Closes of {as_of:%d %b %Y}.")
        kit.note("No model book yet.", "The book forms once the strategy has its price history.")
        return

    a = assess(rank_df, symbols, rules)
    plan = plan_rebalance(rank_df, symbols, top_n=int(cfg["top_n"]), buffer_n=rules.buffer_n,
                          stock_cap=float(cfg["stock_cap"]), sector_cap=float(cfg["sector_cap"]))
    held = a[a["Symbol"].isin(plan.holds)]
    n_watch = int(held["status"].eq(WATCH).sum())

    kit.page_head("Dashboard", answer_line(mtd, bench_mtd, n_watch, len(plan.sells), check))

    # Two columns, each a stack, so a short block never leaves a hole beside
    # a long one (owner, 7 Nov: "unnecessary white spaces and large gaps").
    # Left: the book's risk, then the next rebalance; right: sector leaders,
    # then size leadership. A phone shows the left stack first, which is the
    # order of importance.
    page = st.container(key="db_page")
    left, right = page.columns([1.45, 1], gap="large")
    top_l, top_r = left, left
    low_l, low_r = right, right

    with top_l, kit.card("Book at risk", "db_risk", "least room first"):
        st.html(_at_risk_html(a, rules))
        kit.caption(f"Room is how far the price can fall, or the rank slip, before a rule is "
                    f"broken; a full rank buffer ({rules.buffer_n} places) counts as a "
                    f"{RANK_SCALE:.0%} fall. All {len(symbols)} holdings are on Actions.")

    n_sess = _sessions_between(as_of, check)
    with top_r, kit.card("Next rebalance", "db_next", "if the month ended today"):
        st.html(
            '<dl class="db-kv">'
            f'<dt>Check</dt><dd>{_day(check, weekday=True)} close, {n_sess} '
            f'session{"s" if n_sess != 1 else ""} away</dd>'
            f'<dt>Fill</dt><dd>{_day(fill, weekday=True)}</dd>'
            f'<dt>Sell</dt><dd>{_names(plan.sells)}</dd>'
            f'<dt>Buy</dt><dd>{_names(plan.buys)}</dd>'
            f'<dt>Next in line</dt><dd>{_names(plan.next_in_line)}</dd>'
            '</dl>')
        kit.caption("The same plan as Actions, from today's ranking and the model book's rules.")

    with low_r, kit.card("Sector leaders", "db_sectors", "median 3M return"):
        board, _ = industry_board(rank_df)
        top = (board.sort_values("3M Return", ascending=False).head(5)
               if not board.empty else board)
        rows = "".join(
            f'<tr><th>{html.escape(str(r["Industry"]))}</th>'
            f'<td class="{_tone(r["3M Return"])}">{_pct(r["3M Return"])}</td>'
            f'<td class="db-n">{int(r["Top 50"]) if pd.notna(r.get("Top 50")) else "—"} in the top 50</td></tr>'
            for _, r in top.iterrows())
        st.html(f'<table class="db-sectors"><tbody>{rows}</tbody></table>')
        kit.caption("As ranked on Sectors (3M median); the full board is there.")

    levels, bench = fetch_index_levels(), nse_benchmarks()
    with low_l, kit.card("Size leadership", "db_size", "price return, NSE index closes"):
        res = None
        if levels is None or bench is None or "nifty500" not in bench or "nifty50" not in bench:
            kit.caption("Index levels are not available right now, so this table is left out.")
        else:
            ok, why = sl.cross_check(levels, bench["nifty50"])
            res = sl.size_leadership(levels, bench["nifty500"]) if ok else None
            if not ok:
                kit.caption(f"Left out: the index file failed its check ({why}).")
            elif res is None:
                kit.caption("Left out: the index file does not cover every size index yet.")
        if res is not None:
            line = sl.headline(res)
            if line:
                st.html(f'<p class="db-lede">{html.escape(line)}</p>')
            st.html(_size_html(res))
            stale = (as_of - res.end).days > 7
            kit.caption(f"To {res.end:%d %b %Y}"
                        + (" (older than the latest prices)" if stale else "")
                        + "; bold figures are against the Nifty 500, small ones the index's own move. "
                        + f"{why}. Source: " + ", ".join(res.sources) + ".")

    render_data_quality_footer(
        total_stocks=len(rank_df),
        gap_count=gap_count(rank_df),
        short_count=int((rank_df.get("Short History", pd.Series()) == "Yes").sum()),
    )
