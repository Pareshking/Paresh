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


import pandas as pd
import streamlit as st

from src.loaders.nse_calendar import published_holidays
from src.engine.exit_watch import (
    holdings_from_kite_csv,
    parse_holdings,
)
from src.core.config import MODEL_BOOK_CAPITAL
from src.ui import holdings_store
from src.ui import page_kit as kit
from src.ui.widget_state import resolve

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
                    from src.core.logger import logger
                    logger.warning("Holdings CSV not read: %s", exc)
                    # A failure is an amber note (S193 E, R4).
                    kit.note("That file could not be read as Kite’s holdings CSV.",
                             "It needs an Instrument or Symbol column. Your saved holdings are unchanged.", kind="warning")
                else:
                    if st.button(f"Use these {len(got)} holdings", key="xw_csv_use"):
                        holdings_store.save(got)
                        st.rerun()






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
