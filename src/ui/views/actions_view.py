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
from src.core.market_time import ist_now
from src.loaders.nse_calendar import published_holidays
from src.engine.exit_watch import (
    STATUS_LABEL,
    UNKNOWN,
    WATCH,
    Rules,
    assess,
    holdings_from_kite_csv,
    parse_holdings,
    qualified_ranks,
)
from src.core.config import MODEL_BOOK_CAPITAL
from src.engine.actions import buy_orders, plan_rebalance
from src.engine.track_record import TRACK_RECORD_CONFIG
from src.ui import holdings_store
from src.ui import page_kit as kit
from src.ui.components import gap_count, render_data_quality_footer
from src.ui.views.qualified_view import render_qualified_view
from src.ui.canonical_book import current_book
from src.ui.widget_state import remember, resolve

SOURCES = ["Model book", "My holdings"]

KITE_CAPITAL_KEY = "ac_kite_capital"
KITE_MIN_CAPITAL = 10_000
KITE_MAX_CAPITAL = 1_000_000_000

# Said once, as the Hold table's heading tooltips, not as a caption on every visit.
CUSHION_HELP = ("Cushion: how far the price can fall from today before it crosses this line, "
                "with the line held where it is today.")
BUFFER_HELP = "Counts only stocks that pass both filters, the same count the strategy uses."


def kite_capital() -> int:
    """The capital the Kite basket is sized on: the reader's, else Portfolio's ₹20 lakh."""
    return resolve(KITE_CAPITAL_KEY, int(MODEL_BOOK_CAPITAL), lo=KITE_MIN_CAPITAL, hi=KITE_MAX_CAPITAL)


def fill_due_note(as_of: pd.Timestamp, fill: pd.Timestamp, today: pd.Timestamp) -> str:
    """Why the page still talks about a rebalance that is due today.

    On the first day of a month the latest close is the previous month's last
    one, and the fill the page names is today's: said once, so the dates read
    as consistent rather than stale. Empty on every other day.
    """
    if fill.normalize() == today.normalize() and as_of.to_period("M") < today.to_period("M"):
        return (f" The calendar is now {today:%b %Y}; the latest close is {as_of:%d %b}. "
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
    return (f"{t:%a} " if weekday else "") + f"{t:%d %b}"


def _sessions_between(a: pd.Timestamp, b: pd.Timestamp) -> int:
    """NSE sessions after `a` up to and including `b` (Dussehra, 20 Oct 2026,
    made the weekday count one too many, 13 Oct)."""
    return max(0, len(pd.date_range(a.normalize() + pd.Timedelta(days=1), b.normalize(), freq=_session())))


def _bar(room: float | None, ok: bool, scale: float, label: str) -> str:
    """A cushion bar: full = lots of room, short = close to the line, red = broken."""
    if not ok:
        return (f'<span class="xw-g broken"><b>{html.escape(label)}</b>'
                '<i><i style="width:100%"></i></i></span>')
    w = 0.0 if room is None or pd.isna(room) else max(4.0, min(100.0, float(room) / scale * 100))
    tone = "tight" if w < 30 else "ok"
    return (f'<span class="xw-g {tone}"><b>{html.escape(label)}</b>'
            f'<i><i style="width:{w:.0f}%"></i></i></span>')


def rows_html(a: pd.DataFrame, since: dict[str, float], rules: Rules) -> str:
    out = []
    for _, r in a.iterrows():
        sym = str(r["Symbol"])
        status = r["status"]
        link = f'<a href="{stock_href(sym)}" target="_self">{html.escape(sym)}</a>'
        if status == UNKNOWN:
            out.append(
                f'<div class="xw-row unknown"><span class="xw-s">{link}</span>'
                f'<span class="xw-pill unknown">{STATUS_LABEL[UNKNOWN]}</span>'
                '<span class="xw-why" style="grid-column: 3 / -1">No rule can be checked.</span></div>')
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
        ret_txt = "—" if ret is None or pd.isna(ret) else f"{'+' if ret >= 0 else '−'}{abs(ret) * 100:.1f}%"
        ret_cls = "" if ret is None or pd.isna(ret) else ("up" if ret >= 0 else "down")
        out.append(
            f'<div class="xw-row {status}"><span class="xw-s">{link}'
            f'<small>{html.escape(str(r.get("Industry") or ""))}</small></span>'
            f'<span class="xw-pill {status}">{STATUS_LABEL[status]}</span>'
            f"{rank_cell}{ema_cell}{hi_cell}"
            f'<span class="xw-why">{html.escape(r["why"] or "clear of all three")}</span>'
            f'<span class="xw-ret {ret_cls}">{ret_txt}</span></div>'
        )
    head = ('<div class="xw-row xw-head"><span>Holding</span><span>At the next rebalance</span>'
            f'<span title="{BUFFER_HELP}">Rank buffer (top {rules.buffer_n} qualified)</span>'
            f'<span title="{CUSHION_HELP}">50D EMA</span>'
            f'<span title="{CUSHION_HELP}">−{(1 - rules.high_pct):.0%} from 52W high</span>'
            '<span>Closest to</span><span class="xw-ret">Since entry</span></div>')
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
    return "" if d.empty or pd.isna(d.iloc[0]) else f"held since {_day(d.iloc[0])}"


def sells_html(a: pd.DataFrame, sells: list[str], since: dict[str, float], entries) -> str:
    by = a.set_index("Symbol")
    rows = []
    for s in sells:
        why = by.loc[s, "why"] if s in by.index else ""
        ret = since.get(s)
        ret_txt = "—" if ret is None or pd.isna(ret) else f"{'+' if ret >= 0 else '−'}{abs(ret) * 100:.1f}%"
        cls = "" if ret is None or pd.isna(ret) else ("up" if ret >= 0 else "down")
        rows.append(
            f'<div class="ac-row sell"><span class="xw-s"><a href="{stock_href(s)}" target="_self">'
            f'{html.escape(s)}</a><small>{html.escape(str(by.loc[s, "Industry"]) if s in by.index else "")}</small></span>'
            f'<span class="ac-why"><b>Sell</b> · {html.escape(why)}</span>'
            f'<span class="ac-when">{html.escape(entries(s))}</span>'
            f'<span class="xw-ret {cls}">{ret_txt}</span></div>')
    return f'<div class="xw">{"".join(rows)}</div>'


def buys_html(rank_df: pd.DataFrame, buys: list[str], qrank: pd.Series) -> str:
    by = rank_df.drop_duplicates("Symbol").set_index("Symbol")

    def pct(v):
        v = pd.to_numeric(v, errors="coerce")
        return "—" if pd.isna(v) else f"{'+' if v >= 0 else '−'}{abs(v) * 100:.1f}%"

    rows = ['<div class="ac-row buy ac-head"><span>Stock</span><span>Qualified</span>'
            '<span class="n">Price</span><span class="n">3M</span><span class="n">6M</span>'
            '<span class="n">From 52W high</span></div>']
    for s in buys:
        r = by.loc[s]
        hi = pd.to_numeric(r.get("% High"), errors="coerce")
        hi_txt = "—" if pd.isna(hi) else ("At high" if hi > -0.05 else f"−{abs(hi):.1f}%")
        rows.append(
            f'<div class="ac-row buy"><span class="xw-s"><a href="{stock_href(s)}" target="_self">'
            f'{html.escape(s)}</a><small>{html.escape(str(r.get("Industry") or ""))}</small></span>'
            f'<span class="n">#{int(qrank.get(s, 0))}</span>'
            f'<span class="n">₹{float(r.get("CMP")):,.2f}</span><span class="n up">{pct(r.get("3M Return"))}</span>'
            f'<span class="n up">{pct(r.get("6M Return"))}</span><span class="n">{hi_txt}</span></div>')
    return f'<div class="xw">{"".join(rows)}</div>'


def render_actions_view(rank_df: pd.DataFrame, adj_close: pd.DataFrame,
                        benchmark_close: pd.Series | None,
                        model_book_note: str | None = None,
                        system: str = "750") -> None:
    """Show next-rebalance actions from the canonical Track Record book.

    record_run().live_book is exposed through current_book(); Actions does
    not maintain a second model-book implementation.
    """
    holdings_store.sync()
    cfg = TRACK_RECORD_CONFIG
    rules = Rules(buffer_n=int(cfg["buffer_n"]), high_pct=float(cfg["high_pct"]))

    as_of = pd.Timestamp(adj_close.index[-1]) if adj_close is not None and len(adj_close) else pd.Timestamp(ist_now().date())
    check, fill = next_rebalance(as_of)
    n_sess = _sessions_between(as_of, check)
    timing_note = fill_due_note(as_of, fill, pd.Timestamp(ist_now().date()))

    # The dates are in the "Next rebalance" tile; the subtitle does not repeat them.
    head = kit.page_head("Actions", "If today's prices hold.", actions=True)
    with head:
        sources = SOURCES if model_book_note is None else ["My holdings"]
        source = st.segmented_control("Holdings", sources, default=sources[0], key="xw_source",
                                      label_visibility="collapsed") or sources[0]
    if model_book_note is not None:
        kit.note("No model book yet.", model_book_note)

    book = None
    if source == "My holdings":
        _edit_holdings()
        symbols, since, _basis = _my_holdings(rank_df)
        entries = lambda s: ""  # noqa: E731 -- buy dates are not recorded for your holdings
        top_n = len(symbols)
    else:
        with st.spinner("Loading the model book…"):
            book, _record = current_book(adj_close, benchmark_close, system)
        symbols = [] if book is None or book.empty else book["Symbol"].tolist()
        since = ({} if not symbols else
                 dict(zip(book["Symbol"], pd.to_numeric(book["Return %"], errors="coerce"))))
        entries = lambda s: _held_since(book, s)  # noqa: E731
        top_n = int(cfg["top_n"])

    if not symbols:
        st.info("Add your holdings above, or upload the holdings CSV from Kite, to see what to "
                "do with them." if source == "My holdings" else
                "The model book is not available: the strategy needs about 18 months of price "
                "history to form one.")
    else:
        a = assess(rank_df, symbols, rules)
        # The caps the model book's own run uses, read from the pinned record
        # config, so the weights here are its weights.
        plan = plan_rebalance(rank_df, symbols, top_n=top_n, buffer_n=rules.buffer_n,
                              stock_cap=float(cfg["stock_cap"]),
                              sector_cap=float(cfg["sector_cap"]))
        n_unknown = int((a["status"] == UNKNOWN).sum())
        n_watch = int(a[a["Symbol"].isin(plan.holds)]["status"].eq(WATCH).sum())
        kit.readings([
            kit.Reading("Sell", f"{len(plan.sells)}", "break a rule at today's close",
                        "down" if plan.sells else ""),
            kit.Reading("Buy", f"{len(plan.buys)}", "", "up" if plan.buys else ""),
            kit.Reading("Hold", f"{len(plan.holds)}",
                        f"{n_watch} close to a rule" if n_watch else "all clear of the rules",
                        "warn" if n_watch else ""),
            kit.Reading("Next rebalance", _day(check, weekday=True),
                        timing_note.strip()
                        or f"{n_sess} session{'s' if n_sess != 1 else ''} away · fills {_day(fill, weekday=True)}"),
        ], "Actions")
        if n_unknown:
            kit.note(f"{n_unknown} holding{'s are' if n_unknown != 1 else ' is'} not ranked; "
                     "no rule can be checked.")

        # The basket used to read a Portfolio capital input removed on 30 Sep, so
        # it sized every basket on ₹10 lakh against Portfolio's ₹20 lakh. Now the
        # reader sets it here, starting at Portfolio's (owner, 12 Oct 2026).
        with head, st.popover("Kite basket", icon=":material/download:", type="primary"):
            capital = float(st.number_input(
                "Capital (₹)", min_value=KITE_MIN_CAPITAL, max_value=KITE_MAX_CAPITAL,
                step=100_000, value=kite_capital(), key=KITE_CAPITAL_KEY,
                help=f"₹{MODEL_BOOK_CAPITAL:,.0f} is the model book on Portfolio. "
                     "For your own holdings, enter your account's size.",
            ))
            remember(KITE_CAPITAL_KEY, int(capital))
            orders = buy_orders(plan, rank_df, capital)
            st.download_button(
                "Download basket CSV", orders.to_csv(index=False).encode(),
                f"kite_actions_{ist_now():%Y%m%d}.csv", "text/csv", type="primary",
                key="dl_actions_basket", icon=":material/download:", disabled=orders.empty,
            )
            kit.caption(f"Buy orders only, each at its target weight of ₹{capital:,.0f}.")

        with kit.card("Sell", "ac_sell"):
            if plan.sells:
                st.html(sells_html(a, plan.sells, since, entries))
                kit.caption("Sell in full; sells are not in the Kite basket.")
            else:
                kit.caption("None.")

        qrank = qualified_ranks(rank_df)
        with kit.card("Buy", "ac_buy", "best qualified, not held"):
            if plan.buys:
                st.html(buys_html(rank_df, plan.buys, qrank))
                chips = "".join(
                    f'<a class="t50-chip" href="{stock_href(s)}" target="_self">'
                    f'<span class="t50-rank">{int(qrank.get(s, 0))}</span>'
                    f'<span>{html.escape(s)}</span></a>'
                    for s in plan.next_in_line)
                if chips:
                    st.html(f'<div class="ac-next"><span>Next in line:</span>{chips}</div>')
            else:
                kit.caption("None.")

        holds = a[a["Symbol"].isin(plan.holds) | (a["status"] == UNKNOWN)]
        with kit.card("Hold", "ac_hold", "closest to a sale first"):
            st.html(rows_html(holds, since, rules))

    with st.expander("Buy candidates · the qualified list", expanded=False):
        render_qualified_view(rank_df, adj_close, embedded=True)

    render_data_quality_footer(
        total_stocks=len(rank_df),
        gap_count=gap_count(rank_df),
        short_count=int((rank_df.get("Short History", pd.Series()) == "Yes").sum()),
    )
