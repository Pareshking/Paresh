"""
Actions: what the strategy would do at the next rebalance.

Sell the holdings that break a rule, buy the best qualified stocks not already
held to replace them, hold the rest -- worked out with the strategy's own
selection and weighting (src/engine/actions.py) on today's closes. The orders
are struck at the rebalance close (the last session of the month, filled on
the first of the next), so this is a preview: a name can still move in or out
before then. For the model book or for the reader's own holdings.
"""
from __future__ import annotations

import html

import pandas as pd
import streamlit as st

from src.ui.system_param import stock_href
from src.loaders.nse_calendar import published_holidays
from src.engine.exit_watch import (
    STATUS_LABEL,
    UNKNOWN,
    Rules,
    holdings_from_kite_csv,
    nearest_rule,
    parse_holdings,
)
from src.core.config import MODEL_BOOK_CAPITAL
from src.ui import holdings_store
from src.ui.widget_state import resolve
from src.ui import formats as _fmt

SOURCES = ["Model book", "My holdings"]

KITE_CAPITAL_KEY = "ac_kite_capital"
KITE_MIN_CAPITAL = 10_000
KITE_MAX_CAPITAL = 1_000_000_000

# Said once, as the Hold table's heading tooltips, not as a caption on every visit.
CUSHION_HELP = ("Cushion: how far the price can fall from today before it crosses this line, "
                "with the line held where it is today.")
BUFFER_HELP = "Counts only stocks that pass both filters, the same count the strategy uses."


def kite_capital() -> int:
    """The capital the Kite basket is sized on: the reader's, else Portfolio's ₹1 crore."""
    return resolve(KITE_CAPITAL_KEY, int(MODEL_BOOK_CAPITAL), lo=KITE_MIN_CAPITAL, hi=KITE_MAX_CAPITAL)


def fill_due_note(as_of: pd.Timestamp, fill: pd.Timestamp, today: pd.Timestamp) -> str:
    """Why the page still talks about a rebalance that is due today.

    On the first day of a month the latest close is the previous month's last
    one, and the fill the page names is today's: said once, so the dates read
    as consistent rather than stale. Empty on every other day.
    """
    if fill.normalize() == today.normalize() and as_of.to_period("M") < today.to_period("M"):
        return (f" The calendar is now {today:%b %Y}; the latest close is {as_of:%-d %b}. "
                "Today's fill awaits today's closing price.")
    return ""


def _session() -> pd.offsets.CustomBusinessDay:
    # NSE's published holidays (data/reference/nse/holidays.csv, its holiday-master API).
    return pd.offsets.CustomBusinessDay(holidays=published_holidays())


def next_rebalance(as_of: pd.Timestamp) -> tuple[pd.Timestamp, pd.Timestamp]:
    """The check (last NSE session of this month) and the fill (first NSE
    session of the next), skipping weekends and NSE's published holidays."""
    day = _session()
    month_end = (as_of + pd.offsets.MonthEnd(0)).normalize()
    check = day.rollback(month_end)
    if check.normalize() < as_of.normalize():
        check = day.rollback((as_of + pd.offsets.MonthEnd(1)).normalize())
    fill = day.rollforward((check + pd.offsets.MonthBegin(1)).normalize())
    return check, fill


def _day(t: pd.Timestamp, weekday: bool = False) -> str:
    return (f"{t:%a} " if weekday else "") + f"{t:%-d %b}"


def _sessions_between(a: pd.Timestamp, b: pd.Timestamp) -> int:
    """NSE sessions after `a` up to and including `b` (Dussehra, 20 Oct 2026,
    made the weekday count one too many, 13 Oct)."""
    return max(0, len(pd.date_range(a.normalize() + pd.Timedelta(days=1), b.normalize(), freq=_session())))


def _bar(room: float | None, ok: bool, scale: float, label: str) -> str:
    """A cushion bar: full = lots of room, short = close to the line, red = broken."""
    if not ok:
        return (f'<span class="xw-g broken" role="cell"><b>{html.escape(label)}</b>'
                '<i aria-hidden="true"><i style="width:100%"></i></i></span>')
    w = 0.0 if room is None or pd.isna(room) else max(4.0, min(100.0, float(room) / scale * 100))
    tone = "tight" if w < 30 else "ok"
    return (f'<span class="xw-g {tone}" role="cell"><b>{html.escape(label)}</b>'
            f'<i aria-hidden="true"><i style="width:{w:.0f}%"></i></i></span>')


def rows_html(a: pd.DataFrame, since: dict[str, float], rules: Rules) -> str:
    out = []
    for _, r in a.iterrows():
        sym = str(r["Symbol"])
        status = r["status"]
        link = f'<a href="{stock_href(sym)}" target="_self">{html.escape(sym)}</a>'
        if status == UNKNOWN:
            out.append(
                f'<div class="xw-row unknown" role="row"><span class="xw-s" role="rowheader">{link}</span>'
                f'<span class="xw-pill unknown" role="cell">{STATUS_LABEL[UNKNOWN]}</span>'
                '<span class="xw-why" role="cell" aria-colspan="5" style="grid-column: 3 / -1">No rule can be checked.</span></div>')
            continue
        q = r["Qualified rank"]
        room = r["Rank room"]
        if pd.isna(q):
            rank_cell = _bar(None, False, 1, "off the list")
        elif room < 0:
            rank_cell = _bar(None, False, 1, f"#{int(q)} · past {rules.buffer_n}")
        else:
            rank_cell = _bar(room, True, rules.buffer_n, f"#{int(q)} · {int(room)} to go")
        ema_c, hi_c = r["EMA cushion"], r["High cushion"]
        ema_cell = _bar(ema_c, bool(r["EMA ok"]), 0.20,
                        f"{ema_c * 100:.1f}% cushion" if r["EMA ok"] and pd.notna(ema_c)
                        else f"{abs(r['vs 50 EMA %']):.1f}% below" if pd.notna(r["vs 50 EMA %"]) else "below")
        hi_cell = _bar(hi_c, bool(r["High ok"]), 0.20,
                       f"{hi_c * 100:.1f}% cushion" if r["High ok"] and pd.notna(hi_c) else "past the line")
        ret = since.get(sym)
        ret_txt = "–" if ret is None or pd.isna(ret) else f"{'+' if ret >= 0 else '−'}{abs(ret) * 100:.1f}%"
        ret_cls = "" if ret is None or pd.isna(ret) else ("up" if ret >= 0 else "down")
        out.append(
            f'<div class="xw-row {status}" role="row"><span class="xw-s" role="rowheader">{link}'
            f'<small>{html.escape(str(r.get("Industry") or ""))}</small></span>'
            f'<span class="xw-pill {status}" role="cell">{STATUS_LABEL[status]}</span>'
            f"{rank_cell}{ema_cell}{hi_cell}"
            f'<span class="xw-why" role="cell">{html.escape(r["why"] or "clear; nearest: " + nearest_rule(r, rules))}</span>'
            f'<span class="xw-ret {ret_cls}" role="cell">{ret_txt}</span></div>'
        )
    head = ('<div class="xw-row xw-head" role="row"><span role="columnheader">Holding</span>'
            '<span role="columnheader">At the next rebalance</span>'
            f'<span role="columnheader" title="{BUFFER_HELP}">Rank buffer (top {rules.buffer_n} qualified)</span>'
            f'<span role="columnheader" title="{CUSHION_HELP}">50D EMA</span>'
            f'<span role="columnheader" title="{CUSHION_HELP}">−{(1 - rules.high_pct):.0%} from 52W high</span>'
            '<span role="columnheader">Closest to</span><span class="xw-ret" role="columnheader">Since entry</span></div>')
    return f'<div class="xw" role="table" aria-label="Exit watch">{head}{"".join(out)}</div>'


def _my_holdings(rank_df: pd.DataFrame) -> tuple[list[str], dict[str, float], str]:
    entries = holdings_store.items()
    cmp = pd.to_numeric(rank_df.drop_duplicates("Symbol").set_index("Symbol").get("CMP"),
                        errors="coerce")
    since = {s: (float(cmp.get(s)) / p - 1) for s, p in entries
             if p and cmp is not None and pd.notna(cmp.get(s))}
    return [s for s, _p in entries], since, "your buy price"


def _edit_holdings() -> None:
    def _save_text():
        holdings_store.save(parse_holdings(st.session_state.get("xw_text", "")))

    current = holdings_store.to_text(holdings_store.items()).replace(",", ", ")
    if st.session_state.get("_xw_shown") != current:
        st.session_state["xw_text"] = current
        st.session_state["_xw_shown"] = current
    with st.container(horizontal=True, vertical_alignment="bottom", key="xw_editbar"):
        st.text_input("Your holdings", key="xw_text",
                      placeholder="Symbols with an optional buy price, e.g. HFCL 126.5, QUESS@340, TCS",
                      help="Kept in this browser only, like the watchlist. Nothing is sent to the server.")
        st.button("Save", type="primary", key="xw_save", on_click=_save_text)
        with st.popover("Upload from Kite", icon=":material/upload:"):
            st.caption("Kite Console → Portfolio → Holdings → Download (CSV). Symbols and "
                       "average cost are read; quantities are not stored.")
            up = st.file_uploader("Holdings CSV", type=["csv"], key="xw_csv",
                                  label_visibility="collapsed")
            if up is not None:
                try:
                    got = holdings_from_kite_csv(pd.read_csv(up))
                except Exception as exc:  # a wrong file is reported, not raised
                    st.error(f"Could not read that file: {exc}")
                else:
                    if st.button(f"Use these {len(got)} holdings", key="xw_csv_use"):
                        holdings_store.save(got)
                        st.rerun()


def _held_since(book: pd.DataFrame | None, sym: str) -> str:
    if book is None or book.empty or "Entry Date" not in book.columns:
        return ""
    d = pd.to_datetime(book.loc[book["Symbol"] == sym, "Entry Date"], errors="coerce")
    return "" if d.empty or pd.isna(d.iloc[0]) else f"Held since {_day(d.iloc[0])}"


def sells_html(a: pd.DataFrame, sells: list[str], since: dict[str, float], entries) -> str:
    by = a.set_index("Symbol")
    # Column names for a screen reader only: the list reads as rows by eye.
    rows = ['<div class="ac-row sell sr-only" role="row"><span role="columnheader">Holding</span>'
            '<span role="columnheader">Reason</span><span role="columnheader">Held</span>'
            '<span role="columnheader">Since entry</span></div>']
    for s in sells:
        why = by.loc[s, "why"] if s in by.index else ""
        ret = since.get(s)
        cls = "" if ret is None or pd.isna(ret) else ("up" if ret >= 0 else "down")
        rows.append(
            f'<div class="ac-row sell" role="row"><span class="xw-s" role="rowheader"><a href="{stock_href(s)}" target="_self">'
            f'{html.escape(s)}</a><small>{html.escape(str(by.loc[s, "Industry"]) if s in by.index else "")}</small></span>'
            f'<span class="ac-why" role="cell"><b>Sell</b> · {html.escape(why)}</span>'
            f'<span class="ac-when" role="cell">{html.escape(entries(s))}</span>'
            f'<span class="xw-ret {cls}" role="cell">{_fmt.pct(ret)}</span></div>')
    return f'<div class="xw" role="table" aria-label="Sell">{"".join(rows)}</div>'


def buys_html(rank_df: pd.DataFrame, buys: list[str], qrank: pd.Series) -> str:
    by = rank_df.drop_duplicates("Symbol").set_index("Symbol")

    def ret_cell(v) -> str:
        v = pd.to_numeric(v, errors="coerce")
        tone = "" if pd.isna(v) else ("up" if v >= 0 else "down")
        return f'<span class="n {tone}" role="cell">{_fmt.pct(v)}</span>'

    rows = ['<div class="ac-row buy ac-head" role="row"><span role="columnheader">Stock</span>'
            '<span role="columnheader">Qualified</span>'
            '<span class="n" role="columnheader">Price</span><span class="n" role="columnheader">3M</span>'
            '<span class="n" role="columnheader">6M</span>'
            '<span class="n" role="columnheader">From 52W high</span></div>']
    for s in buys:
        r = by.loc[s]
        hi = pd.to_numeric(r.get("% High"), errors="coerce")
        hi_txt = "–" if pd.isna(hi) else ("At high" if hi > -0.05 else _fmt.pct(hi, fraction=False))
        rows.append(
            f'<div class="ac-row buy" role="row"><span class="xw-s" role="rowheader"><a href="{stock_href(s)}" target="_self">'
            f'{html.escape(s)}</a><small>{html.escape(str(r.get("Industry") or ""))}</small></span>'
            f'<span class="n" role="cell">#{int(qrank.get(s, 0))}</span>'
            f'<span class="n" role="cell">{_fmt.price(r.get("CMP"))}</span>'
            f'{ret_cell(r.get("3M Return"))}{ret_cell(r.get("6M Return"))}'
            f'<span class="n" role="cell">{hi_txt}</span></div>')
    return f'<div class="xw" role="table" aria-label="Buy">{"".join(rows)}</div>'


def _book_equity(book, record, rank_df, adj_close, benchmark_close, system) -> pd.Series | None:
    """The model book's daily value to today (src/ui/book_series.py), for buy sizing."""
    from src.engine.systems import inception, ledger_path
    from src.engine.track_record import load_ledger
    from src.ui.book_series import book_series
    try:
        ledger = load_ledger(ledger_path(system), inception(system))
    except (ValueError, OSError):
        return (record or {}).get("equity_curve")
    series = book_series(book, record, ledger, rank_df, adj_close, benchmark_close, MODEL_BOOK_CAPITAL)
    return series.equity if series is not None else (record or {}).get("equity_curve")


def render_actions_view(rank_df: pd.DataFrame, adj_close: pd.DataFrame,
                        benchmark_close: pd.Series | None,
                        model_book_note: str | None = None,
                        system: str = "750") -> None:
    """Show next-rebalance actions from the canonical Track Record book.

    record_run().live_book is exposed through current_book(); Actions does
    not maintain a second model-book implementation.
    """
    # Rebuilt from docs/ACTIONS_REQUIREMENTS.md (owner, 20 Nov 2026); the helpers below stay for it.
    from src.ui.views import actions_page
    actions_page.render(rank_df, adj_close, benchmark_close, system, model_book_note)
