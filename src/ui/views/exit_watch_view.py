"""
Exit watch: how close each holding is to the three rules that sell it.

The rules are checked at the rebalance (the last session of the month, filled
on the first of the next); a rule broken mid-month sells only if it is still
broken then. This page shows the room left on each, for the model book or for
the reader's own holdings.
"""
from __future__ import annotations

import html
from urllib.parse import quote

import pandas as pd
import streamlit as st

from src.core.market_time import ist_now
from src.engine.exit_watch import (
    CLEAR,
    SELL,
    STATUS_LABEL,
    UNKNOWN,
    WATCH,
    Rules,
    assess,
    holdings_from_kite_csv,
    parse_holdings,
)
from src.engine.track_record import TRACK_RECORD_CONFIG
from src.ui import holdings_store
from src.ui import page_kit as kit
from src.ui.components import gap_count, render_data_quality_footer
from src.ui.views.track_record_view import record_run

SOURCES = ["Model book", "My holdings"]


def next_rebalance(as_of: pd.Timestamp) -> tuple[pd.Timestamp, pd.Timestamp]:
    """The check (last weekday of this month) and the fill (first weekday of
    the next). Exchange holidays are not known here, so these are weekdays."""
    month_end = (as_of + pd.offsets.MonthEnd(0)).normalize()
    check = month_end if month_end.weekday() < 5 else month_end - pd.offsets.BDay(1)
    if check.normalize() < as_of.normalize():
        month_end = (as_of + pd.offsets.MonthEnd(1)).normalize()
        check = month_end if month_end.weekday() < 5 else month_end - pd.offsets.BDay(1)
    fill = (check + pd.offsets.MonthBegin(1)).normalize()
    if fill.weekday() >= 5:
        fill = fill + pd.offsets.BDay(1)
    return check, fill


def _day(t: pd.Timestamp, weekday: bool = False) -> str:
    return (f"{t:%a} " if weekday else "") + f"{t.day} {t:%b}"


def _sessions_between(a: pd.Timestamp, b: pd.Timestamp) -> int:
    return max(0, len(pd.bdate_range(a.normalize() + pd.Timedelta(days=1), b.normalize())))


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
        link = f'<a href="?stock={quote(sym, safe="")}" target="_self">{html.escape(sym)}</a>'
        if status == UNKNOWN:
            out.append(
                f'<div class="xw-row unknown"><span class="xw-s">{link}<small>not ranked</small></span>'
                f'<span class="xw-pill unknown">{STATUS_LABEL[UNKNOWN]}</span>'
                f'<span class="xw-why" style="grid-column: 3 / -1">No rule can be checked: '
                "it is not in the ranked universe.</span></div>")
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
            f"<span>Rank buffer (top {rules.buffer_n} qualified)</span><span>50-day EMA</span>"
            f"<span>−{(1 - rules.high_pct):.0%} from 52-week high</span><span>Closest to</span>"
            '<span class="xw-ret">Since entry</span></div>')
    return f'<div class="xw" role="table" aria-label="Exit watch">{head}{"".join(out)}</div>'


def _model_book(adj_close, benchmark_close) -> tuple[list[str], dict[str, float], str]:
    res = record_run(adj_close, benchmark_close)
    book = res.get("live_book", pd.DataFrame()) if res else pd.DataFrame()
    if book is None or book.empty:
        return [], {}, ""
    since = dict(zip(book["Symbol"], pd.to_numeric(book["Return %"], errors="coerce")))
    return book["Symbol"].tolist(), since, "entry fill"


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
                      placeholder="Symbols with an optional buy price, e.g. HFCL 126.5, QUESS@340, TCS")
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
    kit.caption("Kept in this browser only, like the watchlist. Nothing is sent to the server.")


def render_exit_watch_view(rank_df: pd.DataFrame, adj_close: pd.DataFrame,
                           benchmark_close: pd.Series | None) -> None:
    holdings_store.sync()
    cfg = TRACK_RECORD_CONFIG
    rules = Rules(buffer_n=int(cfg["buffer_n"]), high_pct=float(cfg["high_pct"]))

    as_of = pd.Timestamp(adj_close.index[-1]) if adj_close is not None and len(adj_close) else pd.Timestamp(ist_now().date())
    check, fill = next_rebalance(as_of)
    n_sess = _sessions_between(as_of, check)

    actions = kit.page_head(
        "Exit watch",
        f"How close each holding is to the three rules that sell it. Rules are checked at the "
        f"{_day(check)} close; sales fill on {_day(fill)}.",
        actions=True,
    )
    with actions:
        source = st.segmented_control("Holdings", SOURCES, default=SOURCES[0], key="xw_source",
                                      label_visibility="collapsed") or SOURCES[0]

    if source == "My holdings":
        _edit_holdings()
        symbols, since, since_basis = _my_holdings(rank_df)
        if not symbols:
            st.info("Add your holdings above, or upload the holdings CSV from Kite, to check them "
                    "against the rules.")
            return
    else:
        with st.spinner("Loading the model book…"):
            symbols, since, since_basis = _model_book(adj_close, benchmark_close)
        if not symbols:
            st.info("The model book is not available: the strategy needs about 18 months of "
                    "price history to form one.")
            return

    a = assess(rank_df, symbols, rules)
    counts = a["status"].value_counts()
    n_unknown = int(counts.get(UNKNOWN, 0))
    kit.readings([
        kit.Reading("Sold if unchanged", f"{int(counts.get(SELL, 0))}", "break a rule at today's close",
                    "down" if counts.get(SELL, 0) else ""),
        kit.Reading("Watch", f"{int(counts.get(WATCH, 0))}",
                    "within 3% of the EMA, 5% of the −20% line, or 9 places of the buffer",
                    "warn" if counts.get(WATCH, 0) else ""),
        kit.Reading("Clear", f"{int(counts.get(CLEAR, 0))}", "comfortably inside all three", "up"),
        kit.Reading("Next check", _day(check, weekday=True),
                    f"{n_sess} session{'s' if n_sess != 1 else ''} away · fills {_day(fill, weekday=True)}"),
    ], "Exit watch")
    if n_unknown:
        kit.note(f"{n_unknown} of your holdings are not in the ranked universe.",
                 "No rule can be checked for them; they are listed at the end.")

    with actions:
        st.download_button("Export CSV", a.to_csv(index=False).encode(),
                           f"exit_watch_{ist_now():%Y%m%d}.csv", "text/csv",
                           key="dl_xw_csv", icon=":material/download:")

    with kit.card("Holdings, closest to a sale first", "xw_list",
                  "a rule broken mid-month does not sell until the next rebalance"):
        st.html(rows_html(a, since, rules))
        kit.caption(
            "Cushion = how far the price can fall from today before it crosses that line, with "
            "the line held where it is today. Bars shorten as a holding nears a rule and turn red "
            "once it breaks one. The rank buffer counts only stocks that pass both filters, the "
            f"same count the strategy uses. Since entry is measured from the {since_basis}."
        )

    render_data_quality_footer(
        total_stocks=len(rank_df),
        gap_count=gap_count(rank_df),
        short_count=int((rank_df.get("Short History", pd.Series()) == "Yes").sum()),
    )
