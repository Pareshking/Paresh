"""The Screener page: one ranking table for desktop and phone, and the stock route."""


import hashlib
import html
import re
import time

import pandas as pd
import streamlit as st

from src.ui import formats as _fmt

from src.ui.widget_state import mirror_key, remember
from src.ui.system_param import keep_system_only, stock_href

from src.core.config import SHORT_FORMS
from src.core.market_time import ist_now
from src.ui.components import (
    compute_signals,
    data_freshness,
    gap_count,
    signal_chips_html,
    to_bool_mask,
)
from src.ui import page_kit as kit
from src.ui.industry_names import short_industry
from src.ui.views.stock_view import render_stock_view
from src.engine.breadth import new_extreme_counts
from src.engine.calendar_momentum import rank_history_position
from src.ui.screener_table import INDEX_NAMES, column_count, render_screener_table

# Stored in session state by `rank_density_mode`, so these strings are an
# on-disk contract, not labels -- see the format_func in the density control.
# All three draw the one table in src/ui/screener_table.py; they differ only
# in which columns they show.
_DENSITY_OPTIONS = ["Executive (11)", "Core (17)", "Full Quant (35)"]
# Full Quant is the default on desktop and phone (owner, 7 Nov); the phone
# keeps every column and scrolls sideways.
_DEFAULT_DENSITY = _DENSITY_OPTIONS[2]

# "Big movers": rank moved this many places in a month, up or down. 15 caught
# 630 of 750 (the median stock moves ~58 places a month); 150 is about the
# biggest sixth (owner, 13 Oct).
BIG_MOVE_PLACES = 150




# The Screener's filters also live in the address (audit F35). A stock link is
# a plain anchor, so opening a stock reloads the app in a new session and the
# session's state is gone; the browser's Back returns to the address the
# filters were written to, and they are read back from it.
_PRESET_CODES = {"All Universe": "all", "Top 50 Qualified": "top50q",
                 "Top 50 Not Qualified": "top50nq", "Passed Filters": "pass",
                 "Momentum Movers": "movers", "High Volume": "volume"}
_DENSITY_CODES = {"Executive (11)": "exec", "Core (17)": "core", "Full Quant (35)": "full"}
_URL_KEYS = {"rank_quick_pills": "view", "rank_index_filter": "idx",
             "rank_only_passing": "pass", "rank_density_mode": "cols"}


def _from_url(key: str):
    raw = st.query_params.get(_URL_KEYS[key])
    if raw is None:
        return None
    raw = str(raw)
    if key == "rank_quick_pills":
        return next((k for k, c in _PRESET_CODES.items() if c == raw), None)
    if key == "rank_density_mode":
        return next((k for k, c in _DENSITY_CODES.items() if c == raw), None)
    if key == "rank_index_filter":
        return [t for t in raw.split(",") if t]
    if key == "rank_only_passing":
        return raw == "1"
    return None


def _to_url(key: str, value) -> str | None:
    """The address form of a filter, or None for its default (left out)."""
    if key == "rank_quick_pills":
        return None if value in (None, "All Universe") else _PRESET_CODES.get(value)
    if key == "rank_density_mode":
        return None if value in (None, _DEFAULT_DENSITY) else _DENSITY_CODES.get(value)
    if key == "rank_index_filter":
        return ",".join(value) if value else None
    if key == "rank_only_passing":
        return "1" if value else None
    return None


def _sync_url(values: dict) -> None:
    """Write changed filters to the address; one write per change, since each
    write is a browser history entry."""
    for key, value in values.items():
        name, want = _URL_KEYS[key], _to_url(key, value)
        have = st.query_params.get(name)
        if want != (None if have is None else str(have)):
            if want is None:
                del st.query_params[name]
            else:
                st.query_params[name] = want


def _kept(key: str, default, options: list | None = None):
    """A Screener filter's value: the widget's, else the address's, else its
    session mirror, else the default. A stored value no longer among the
    options falls back to the default."""
    if key in st.session_state:
        value = st.session_state[key]
    else:
        from_url = _from_url(key)
        value = from_url if from_url is not None else st.session_state.get(mirror_key(key), default)
    if options is not None and value is not None and value not in options:
        return default
    return value

_SEARCH_KINDS = {"[STOCK] ": "", "[INDEX] ": "index", "[INDUSTRY] ": "industry",
                 "[SECTOR] ": "sector", "[TV_INDUSTRY] ": "sub-industry"}


def search_label(value: str) -> str:
    """What the search list shows for an option (audit F36). The value keeps its
    bracketed kind, which the handlers read; the reader sees "LAURUSLABS ·
    Healthcare" and "Healthcare · industry", not "[STOCK]" or "[INDUSTRY]"."""
    for tag, kind in _SEARCH_KINDS.items():
        if value.startswith(tag):
            rest = value[len(tag):]
            if not kind:
                sym, _, ind = rest.partition(" — ")
                ind = ind.strip()
                return sym if ind in ("", "nan", "<NA>", "None") else f"{sym} · {ind}"
            return f"{rest} · {kind}"
    return value

def _frame_key(df: pd.DataFrame) -> str:
    """Content fingerprint of a display frame: shape, columns and every cell.

    Deliberately NOT a fingerprint of the filter settings that produced the
    frame. Keying on the controls means any input they miss -- a new price
    row, a weight change, a column added upstream -- serves a cached answer
    for a table that has moved on, and a stale export is the one failure here
    nobody would notice: the numbers look plausible and nothing says they are
    yesterday's. Hashing the cells cannot miss such a change.
    """
    try:
        digest = hashlib.md5(
            pd.util.hash_pandas_object(df, index=True).values.tobytes()
        ).hexdigest()
        return f"{df.shape[0]}x{df.shape[1]}_{digest}_{','.join(map(str, df.columns))}"
    except Exception:
        # Un-fingerprintable means un-cacheable: a key that never repeats
        # recomputes rather than risking a wrong hit.
        return f"nokey_{id(df)}_{time.time()}"


@st.cache_data(show_spinner=False, ttl=3600)
def _rankings_csv(view_key: str, _export_df: pd.DataFrame) -> bytes:
    """Serialise the export once per distinct table, not once per rerun.

    st.download_button needs its bytes up front, so the whole frame was written
    to CSV on EVERY rerun -- every filter click, sort change and density toggle
    -- whether or not anyone ever pressed the button. Measured at ~40ms for 750
    rows x 47 columns, against ~7ms to hash the frame and find out it has not
    changed.
    """
    return _export_df.to_csv(index=False).encode()


DISPLAY_COLS = [
    "Rank",
    "Symbol",
    "Industry",
    "Indices",
    "Rank Δ 1M",
    "Rank Δ 3M",
    "CMP",
    "1M Return",
    "1M Sharpe",
    "3M Return",
    "3M Sharpe",
    "6M Return",
    "6M Sharpe",
    "9M Return",
    "9M Sharpe",
    "12M Return",
    "12M Sharpe",
    "% High",
    "52W High Date",
    "% ATH",
    "Max DD 1M",
    "Max DD 3M",
    "Max DD 6M",
    "Max DD 9M",
    "Max DD 12M",
    "% 50 EMA",
    "Volume",
    "Stop Loss",
    "Chand Exit",
    "Market Cap (Cr)",
    "Above 50 EMA",
    "Near 52W High",
    "At ATH",
    "ATH",
    "Short History",
    # How many of the five calendar horizons produced a score. The composite
    # renormalises over whatever is available, so a 2-of-5 name is ranked on
    # the same scale as a 5-of-5 one -- this is the only column that says so.
    "Horizons Scored",
    "FFill %",
    "Data Gap",
]


def export_columns(view: pd.DataFrame) -> list[str]:
    """Every column the ranking carries, the on-screen ones first.

    DISPLAY_COLS is a screen-layout decision; the CSV must also carry Score
    and the other columns behind the rank, or the file cannot be audited.
    """
    active = [c for c in DISPLAY_COLS if c in view.columns]
    return active + [c for c in view.columns if c not in active]


def render_ranking_view(
    rank_df: pd.DataFrame,
    adj_close: pd.DataFrame,
    high_prices: pd.DataFrame | None = None,
    low_prices: pd.DataFrame | None = None,
    volume_data: pd.DataFrame | None = None,
    open_prices: pd.DataFrame | None = None,
    regime=None,
    footnote=None,
    book_symbols=None,
    history_prices: pd.DataFrame | None = None,
) -> None:
    """The Screener: market strip, search and presets, the ranking table, and
    this month's top-50 moves. ?stock=SYMBOL opens that stock's page instead.

    footnote, if given, is called after the top-50 moves: Nano Cap and
    Combined say there what is ranked and what is too new to rank.
    """
    # ── Stock detail route ───────────────────────────────────────────────────
    # ?stock=SYMBOL opens the detail page instead of the screener. A query
    # parameter rather than session state on purpose: it survives a refresh,
    # it can be shared or bookmarked, and it is the only mechanism a link
    # inside the hand-built HTML table can reach -- those cells cannot call
    # back into Python.
    # Reduced to the characters an NSE ticker can hold (M&M, BAJAJ-AUTO): the
    # value is whatever the URL says, and it is echoed back on a miss.
    requested = re.sub(
        r"[^A-Z0-9&._-]", "", str(st.query_params.get("stock") or "").strip().upper()
    )[:32]
    if requested:
        # Write the parameter back, once per symbol. On Streamlit Cloud the app
        # runs in a frame inside paresh.streamlit.app, and a ?stock= link
        # navigates only that frame: the page opened while the address bar
        # still read the bare domain, so a refresh, bookmark or shared link
        # lost the stock. Streamlit reports a st.query_params write to the host
        # page (SET_QUERY_PARAM), which is what updates the address bar -- the
        # Back button's clear() already worked for exactly this reason. Once
        # per symbol because each write also pushes a browser history entry.
        if st.session_state.get("_stock_url_synced") != requested:
            st.query_params["stock"] = requested
            st.session_state["_stock_url_synced"] = requested

        def _back() -> None:
            if st.button("← Back to screener", key="stock_page_back"):
                st.session_state.pop("_stock_url_synced", None)
                keep_system_only()
                st.rerun()

        # The tab names the stock, not "Screener" (pre-launch audit, WCAG 2.4.2).
        st.set_page_config(page_title=f"{requested} · Paresh Patel")
        render_stock_view(
            requested,
            rank_df,
            adj_close,
            high_prices=high_prices,
            low_prices=low_prices,
            volume_data=volume_data,
            open_prices=open_prices,
            on_back=_back,
            book_symbols=book_symbols,
            history_prices=history_prices,
        )
        return

    # Arrived back from a stock page without the Back button -- the brand
    # link, say. The session has dropped ?stock=, but a link to the page you
    # are already on does not update the address bar, which still named the
    # stock: a refresh would have reopened it. Writing the parameters is what
    # updates the address bar, exactly as the Back button's clear() does.
    if st.session_state.pop("_stock_url_synced", None):
        keep_system_only()

    # Build dynamic predictive search suggestions.
    #
    # The Indices column stores SHORT FORMS -- "N50", "NN50", "MID150",
    # "SMALL250", "MICRO250" -- because indices_loader writes
    # SHORT_FORMS.get(name, name). The option list used to add the long names
    # ("NIFTY 50", "NIFTY MIDCAP 150", and a "NIFTY 500" the app does not even
    # load as a constituent index) on top of the tags, and the filter matched
    # by substring. On the real 750-symbol universe that gave 11 options of
    # which 6 returned an empty screener.
    #
    # So: one option per tag ACTUALLY present, labelled with the index's real
    # name, and the tag carried alongside for an exact match.
    tag_to_name = {short: long for long, short in SHORT_FORMS.items() if short}
    present_tags: set[str] = set()
    if "Indices" in rank_df.columns:
        for item in rank_df["Indices"].dropna():
            for sub in str(item).split(","):
                if sub.strip():
                    present_tags.add(sub.strip())

    idx_label_to_tag = {
        f"[INDEX] {tag_to_name.get(tag, tag)}": tag for tag in present_tags
    }
    idx_opts = sorted(idx_label_to_tag)
    ind_opts = (
        sorted(
            [
                f"[INDUSTRY] {i}"
                for i in rank_df["Industry"].dropna().unique()
                if str(i).strip()
            ]
        )
        if "Industry" in rank_df.columns
        else []
    )
    sec_opts = sorted(
        [
            f"[SECTOR] {s}"
            for s in rank_df.get("TV_Sector", pd.Series()).dropna().unique()
            if str(s).strip()
        ]
    )
    tv_ind_opts = sorted(
        [
            f"[TV_INDUSTRY] {i}"
            for i in rank_df.get("TV_Industry", pd.Series()).dropna().unique()
            if str(i).strip()
        ]
    )
    # Built with pandas string concatenation rather than a row loop. This list
    # is rebuilt on every rerun of the screener -- the whole universe, sorted,
    # before any filter narrows it -- and iterrows() made that ~32ms against
    # ~1ms here.
    #
    # It zips two column arrays rather than concatenating two string Series,
    # because the f-string's handling of missing values is not reproducible
    # with .astype(str): on an object column that leaves NaN as NaN, and the
    # concatenation then propagates it, so a stock with no Industry dropped out
    # of the dropdown as a bare NaN instead of reading "SYMBOL — nan". Feeding
    # the raw values back through an f-string keeps every rendering -- "nan",
    # "<NA>", numbers, text -- exactly as it was.
    _by_rank = rank_df.sort_values("Rank")
    _symbols = _by_rank["Symbol"].to_numpy()
    _industries = (
        _by_rank["Industry"].to_numpy()
        if "Industry" in _by_rank.columns
        else [""] * len(_by_rank)
    )
    stock_opts = [
        f"[STOCK] {sym} — {ind}" for sym, ind in zip(_symbols, _industries)
    ]

    search_options = stock_opts + idx_opts + ind_opts + sec_opts + tv_ind_opts

    # ── Page header ──────────────────────────────────────────────────────────

    n_total = len(rank_df)
    # The title answers the reader's first question (which lead, and can the
    # book buy them?); "Screener" is the kicker (PAGE_DESIGN §2a, 21 Nov 2026).
    c_export = kit.page_head(screener_title(rank_df), screener_lede(rank_df, adj_close),
                             actions=True, kicker="Screener")
    chips = signal_chips_html(compute_signals(rank_df))
    if chips:
        st.html(chips)

    # No tile strip: regime and breadth are the market line's, the pass count
    # is the "Pass both filters" button's, the top-50 moves the closing
    # section's (owner, 2026-09-27: no figure shown twice on a page).

    # ── Search, presets, sort and columns ────────────────────────────────────
    passes = (to_bool_mask(rank_df.get("Above 50 EMA"))
              & to_bool_mask(rank_df.get("Near 52W High")))
    preset_counts = {
        "All Universe": n_total,
        "Top 50 Qualified": int(((rank_df["Rank"] <= 50) & passes).sum()),
        "Top 50 Not Qualified": int(((rank_df["Rank"] <= 50) & ~passes).sum()),
        "Passed Filters": int(passes.sum()),
        "Momentum Movers": int((rank_df["Rank Δ 1M"].abs() >= BIG_MOVE_PLACES).sum())
        if "Rank Δ 1M" in rank_df.columns else 0,
        "High Volume": int((rank_df.get("Volume", pd.Series("", index=rank_df.index)) == "High").sum()),
    }
    preset_names = {
        "All Universe": "All", "Top 50 Qualified": "Top 50 qualified",
        "Top 50 Not Qualified": "Top 50 not qualified",
        "Passed Filters": "Pass both filters", "Momentum Movers": "Big movers",
        "High Volume": "Volume spike",
    }

    def _open_searched_stock() -> None:
        # Choosing a stock opens its page, like every other stock link, so the
        # search box is how you get to any stock by name.
        val = str(st.session_state.get("rank_search_predictive") or "")
        if val.startswith("[STOCK] "):
            st.query_params["stock"] = val.replace("[STOCK] ", "").split(" — ")[0].strip()
            st.session_state["rank_search_predictive"] = None

    with st.container(key="scr_toolbar", horizontal=True, vertical_alignment="center",
                      gap="small"):
        selected_search = st.selectbox(
            "Search stock, industry or index",
            options=search_options,
            index=None,
            placeholder="Search stock, industry or index",
            key="rank_search_predictive",
            label_visibility="collapsed",
            format_func=search_label,
            on_change=_open_searched_stock,
            width=260,
        )
        filt = st.pills(
            "Presets",
            list(preset_counts),
            default=_kept("rank_quick_pills", "All Universe", list(preset_counts)),
            format_func=lambda o: f"{preset_names[o]} {preset_counts[o]}",
            key="rank_quick_pills",
            label_visibility="collapsed",
            width="content",
        )
        with st.popover("Filters & columns", icon=":material/tune:", width="content"), \
                st.container(key="scr_filters"):
            # On a phone theme.py pins this panel to the bottom of the screen
            # as a sheet; on a desktop it is an ordinary dropdown.
            # Largest companies first, in the names the table uses.
            _order = ["N50", "NN50", "MID150", "SMALL250", "MICRO250", "NANO250", "NANO"]   # S194 L3: our two groups last
            index_names = {
                tag: INDEX_NAMES.get(tag, tag_to_name.get(tag, tag))
                for tag in sorted(present_tags, key=lambda t: (_order.index(t) if t in _order else 99, t))
            }
            index_pick = st.pills(
                "Index",
                list(index_names),
                selection_mode="multi",
                default=[t for t in (_kept("rank_index_filter", []) or []) if t in index_names],
                format_func=lambda t: index_names.get(t, t),
                key="rank_index_filter",
            )
            only_passing = st.toggle("Only stocks that pass both filters",
                                     value=bool(_kept("rank_only_passing", False)),
                                     key="rank_only_passing")
            # No "Sort by" here: the column headers are the one sort (owner,
            # 7 Nov). A second, server-side sort disagreed with the headers
            # after a click, and the export followed it rather than the screen.

            # The option VALUES are fixed strings: they are what session state
            # stores, and a stored value that vanishes from the list on the
            # next run is a crash, not a relabel. Only the TEXT is computed,
            # from the table that will actually be drawn.
            def _density_label(option: str) -> str:
                n = column_count(option, rank_df.columns)
                return f"{option.split(' (')[0]} ({n})"

            density_mode = st.segmented_control(
                "Columns",
                _DENSITY_OPTIONS,
                default=_kept("rank_density_mode", _DEFAULT_DENSITY, list(_DENSITY_OPTIONS)),
                format_func=_density_label,
                key="rank_density_mode",
            )
            st.caption("Click a column header to sort the table.")
            st.button("Reset", key="rank_filters_reset", type="tertiary",
                      on_click=_reset_screener_filters)
    # Mirrors that outlive the widgets, so the filters are still set after a
    # visit to a stock page and Back (audit F35): Streamlit drops a widget's
    # state on any run that does not draw it, and the stock page does not.
    _filters = {"rank_quick_pills": filt, "rank_index_filter": index_pick,
                "rank_only_passing": only_passing, "rank_density_mode": density_mode}
    for _k, _v in _filters.items():
        remember(_k, _v)
    _sync_url(_filters)
    if not density_mode:
        density_mode = _DEFAULT_DENSITY
    # The key to the marks (S87 item 9), in short lines, two columns on a wide
    # screen (PAGE_DESIGN §2a: it was one 1,240 px line).
    st.html(_KEY_HTML.format(when=_trail_words(adj_close)))

    view = with_book_columns(rank_df, book_symbols,
                             history_prices if history_prices is not None else adj_close)
    # Sessions at a new 52-week high in the last month and three: a stock that
    # keeps making them is strong.
    _nh = _new_high_counts(f"{adj_close.index[-1]}_{adj_close.shape}", adj_close)
    view["New Highs 1M"] = view["Symbol"].map(_nh["1M"]).fillna(0).astype(int)
    view["New Highs 3M"] = view["Symbol"].map(_nh["3M"]).fillna(0).astype(int)
    if selected_search and str(selected_search).strip():
        s_val = str(selected_search).strip()
        if s_val.startswith("[INDUSTRY] "):
            target_ind = s_val.replace("[INDUSTRY] ", "").strip()
            view = view[view["Industry"].str.upper() == target_ind.upper()]
        elif s_val.startswith("[SECTOR] "):
            target_sec = s_val.replace("[SECTOR] ", "").strip()
            view = view[
                view.get("TV_Sector", pd.Series("", index=view.index)).str.upper()
                == target_sec.upper()
            ]
        elif s_val.startswith("[TV_INDUSTRY] "):
            target_tv_ind = s_val.replace("[TV_INDUSTRY] ", "").strip()
            view = view[
                view.get("TV_Industry", pd.Series("", index=view.index)).str.upper()
                == target_tv_ind.upper()
            ]
        elif s_val.startswith("[INDEX] "):
            # Exact tag membership, not a substring. "NN50" CONTAINS "N50", so
            # substring matching returned all 100 Nifty 50 + Nifty Next 50
            # names for a filter labelled Nifty 50.
            target_tag = idx_label_to_tag.get(
                s_val, s_val.replace("[INDEX] ", "").strip()
            ).upper()
            view = view[
                view["Indices"]
                .fillna("")
                .astype(str)
                .apply(lambda v: target_tag in [t.strip().upper() for t in v.split(",")])
            ]
        # A [STOCK] choice never filters: _open_searched_stock has already sent
        # the reader to that stock's page. There is no free-text branch either:
        # st.selectbox only returns an option it was given, and every option
        # carries one of the prefixes above.

    if filt == "Top 50 Qualified":
        view = view[
            (view["Rank"] <= 50)
            & to_bool_mask(view.get("Above 50 EMA"))
            & to_bool_mask(view.get("Near 52W High"))
        ]
    elif filt == "Top 50 Not Qualified":
        view = view[
            (view["Rank"] <= 50)
            & ~(to_bool_mask(view.get("Above 50 EMA"))
                & to_bool_mask(view.get("Near 52W High")))
        ]
    elif filt == "Passed Filters":
        view = view[
            to_bool_mask(view.get("Above 50 EMA"))
            & to_bool_mask(view.get("Near 52W High"))
        ]
    elif filt == "Momentum Movers":
        if "Rank Δ 1M" in view.columns:
            view = view[view["Rank Δ 1M"].abs() >= BIG_MOVE_PLACES].sort_values(
                "Rank Δ 1M", ascending=False
            )
    elif filt == "High Volume":
        view = view[view.get("Volume", "") == "High"]

    if index_pick:
        wanted = {t.upper() for t in index_pick}
        view = view[
            view["Indices"].fillna("").astype(str)
            .apply(lambda v: bool(wanted & {t.strip().upper() for t in v.split(",")}))
        ]
    if only_passing:
        view = view[
            to_bool_mask(view.get("Above 50 EMA")) & to_bool_mask(view.get("Near 52W High"))
        ]

    # Rows arrive in rank order, except Big movers, which lists the biggest
    # rank changes first; the table's header arrow says which.
    movers = filt == "Momentum Movers" and "Rank Δ 1M" in view.columns
    if not movers:
        view = view.sort_values("Rank", kind="stable")
    render_screener_table(view, adj_close, density_mode,
                          sort_key="d1m" if movers else "rank", sort_desc=movers, page_rows=50)

    # Export EVERY column the ranking carries, not just the ones on screen.
    # DISPLAY_COLS is a screen-layout decision -- it drops Score, the raw
    # composite the whole ranking is sorted by, along with Composite Rank,
    # Rank (-1M)/(-3M), 52W High, ATR, ATR %, Persistence and Exp Rank. Anyone
    # exporting to a spreadsheet wants the underlying numbers, and silently
    # withholding the score behind the rank makes the file impossible to audit.
    # Display order first so the familiar columns lead, then the rest.
    export_cols = export_columns(view)
    export_df = view[export_cols]
    c_export.download_button(
        "Export CSV",
        _rankings_csv(_frame_key(export_df), export_df),
        f"nse_momentum_rankings_{ist_now():%Y%m%d}.csv",
        "text/csv",
        key="dl_rank_csv",
        icon=":material/download:",
        help=f"The {len(view)} stocks shown, with all {len(export_cols)} ranking "
             f"columns, including the ones not in the table. Rows are in "
             f"{'rank-change' if movers else 'rank'} order: a column header you "
             f"click re-sorts the table on screen, not the file.",
        width="stretch",
    )

    render_top50_changes(rank_df, adj_close, held=set(book_symbols or ()))
    if footnote is not None:
        footnote()
    st.html(data_line(rank_df, adj_close))


def _reset_screener_filters() -> None:
    # Popped, not assigned: each of these widgets passes its own default, and
    # a session-state value on top of a default makes Streamlit print a
    # warning on the page.
    for key in ("rank_index_filter", "rank_only_passing",
                "rank_density_mode", "rank_quick_pills"):
        st.session_state.pop(key, None)
        st.session_state.pop(mirror_key(key), None)
        if _URL_KEYS[key] in st.query_params:
            del st.query_params[_URL_KEYS[key]]
    st.session_state.pop("scr_show_all", None)


@st.cache_data(show_spinner=False, ttl=3600)
def _new_high_counts(_key: str, _prices: pd.DataFrame) -> pd.DataFrame:
    return new_extreme_counts(_prices)["high"]


def top50_changes(rank_df: pd.DataFrame):
    """Stocks that entered and left the top 50 in the last calendar month, by rank.

    "Rank (-1M)" is the rank on the last session on or before the same date a
    month back (`rank_history_position`), the date every page's rank trail uses.
    """
    if "Rank (-1M)" not in rank_df.columns:
        return None, None
    prev = pd.to_numeric(rank_df["Rank (-1M)"], errors="coerce")
    now = pd.to_numeric(rank_df["Rank"], errors="coerce")
    entered = rank_df[(now <= 50) & (prev > 50)].sort_values("Rank")
    left = rank_df[(now > 50) & (prev <= 50)].sort_values("Rank")
    return entered, left


def biggest_jumps(rank_df: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    """The n stocks that climbed most places in the last calendar month."""
    if "Rank (-1M)" not in rank_df.columns:
        return rank_df.iloc[0:0]
    prev = pd.to_numeric(rank_df["Rank (-1M)"], errors="coerce")
    now = pd.to_numeric(rank_df["Rank"], errors="coerce")
    gain = (prev - now)
    out = rank_df.assign(Places_gained=gain, Rank_last_month=prev)[gain > 0]
    return out.sort_values("Places_gained", ascending=False).head(n)


def system_note(system_name: str, ranked, members, *, nano: bool,
                reason: str = "too new to rank (under three months of prices)") -> tuple[str, str]:
    """The Screener's footnote for the systems beyond the 750: what is ranked, and the
    stocks too new to rank (owner, 27 Sep 2026). The Nifty 1000 passes its own
    reason: most of its unranked stocks are not new, their history is still being
    collected (S175)."""
    ranked_set = {str(x) for x in ranked}
    members = {str(x) for x in members}
    unranked = sorted(members - ranked_set)
    head = (f"{system_name} · {len(ranked_set)} of {len(members)} stocks ranked"
            + (" among themselves." if nano else " as one list."))
    body = (f"{len(unranked)} {reason}: "
            + ", ".join(unranked[:12]) + (" and more." if len(unranked) > 12 else ".")) if unranked else ""
    return head, body


def _month_ago(adj_close: pd.DataFrame | None, months: int = 1) -> pd.Timestamp | None:
    """The session a rank N months ago is read on (the engine's own rule)."""
    if adj_close is None or len(adj_close.index) == 0:
        return None
    idx = pd.DatetimeIndex(adj_close.index)
    pos = rank_history_position(idx, months)
    return idx[pos] if pos >= 0 else None


def _day(ts: pd.Timestamp | None) -> str:
    return "" if ts is None else f"{ts.day} {ts:%b}"


def _trail_words(adj_close: pd.DataFrame | None) -> str:
    d3, d1 = _month_ago(adj_close, 3), _month_ago(adj_close, 1)
    return f"on {_day(d3)} and {_day(d1)}" if d3 is not None and d1 is not None else "3 months and a month ago"


def _movers_heading(adj_close: pd.DataFrame | None) -> str:
    """ "What moved since 19 Oct": the session the 1M rank change counts from."""
    d = _month_ago(adj_close, 1)
    return "What moved in the last month" if d is None else f"What moved since {_day(d)}"


def _passes(df: pd.DataFrame) -> pd.Series:
    return to_bool_mask(df.get("Above 50 EMA")) & to_bool_mask(df.get("Near 52W High"))


def screener_title(rank_df: pd.DataFrame) -> str:
    """The answer to "which stocks lead, and can the book buy them?"."""
    if rank_df is None or rank_df.empty or "Rank" not in rank_df.columns:
        return "Screener"
    now = pd.to_numeric(rank_df["Rank"], errors="coerce")
    top = rank_df[now <= 50]
    n_top = len(top)
    if not n_top:
        return "Screener"
    n_q = int(_passes(top).sum())
    head = f"{n_q} of the top {n_top} can be bought"
    prev = pd.to_numeric(top.get("Rank (-1M)"), errors="coerce") if "Rank (-1M)" in top.columns else None
    if prev is None or prev.isna().all():
        return head + "."
    new = int((prev > 50).sum())
    return f"{head}; {new} of the {n_top} are new this month."


def screener_lede(rank_df: pd.DataFrame, adj_close: pd.DataFrame | None) -> str:
    when = "" if adj_close is None or not len(adj_close.index) else f" at the {pd.Timestamp(adj_close.index[-1]):%-d %b} close"
    return (f"The {len(rank_df)} ranked stocks, by momentum{when}. The book buys the top 20 qualified "
            "and keeps a holding while it is in the top 40.")


# Two columns of short lines on a wide screen, one on a phone. No tag-shaped
# text in the CSS (PAGE_DESIGN §6: a comment holding one drops the block).
_KEY_HTML = (
    "<style>.scr-key{{columns:2;column-gap:40px;font-size:var(--fs-13);color:var(--c-text_2);margin:4px 0 0}}"
    ".scr-key p{{margin:0 0 6px;break-inside:avoid;max-width:80ch;line-height:1.5}}"
    ".scr-key b{{color:var(--c-ink);font-weight:600}}"
    "@media (max-width:900px){{.scr-key{{columns:1}}}}</style>"
    '<div class="scr-key">'
    "<p><b>Qualified:</b> above the 50D EMA and within 20% of the 52W high. The qualified place is the "
    "stock's place among them, the number Actions and the Dashboard use; “Out” means it fails a filter, "
    "and the filter columns show ✗ and by how much.</p>"
    "<p><b>Rank before:</b> the rank among the ranked stocks {when}, the dates the Dashboard's rank trail "
    "uses. Past figures are grey; a click on a column heading sorts every stock.</p>"
    "<p><b>Held:</b> in the model book. The book buys the top 20 qualified and keeps a holding while it is in "
    "the top 40; in rank order the two rows where those places fall are named.</p>"
    "<p><b>Big movers:</b> rank moved 150 places or more in a month. <b>Volume spike:</b> today's volume "
    "1.5 times its 20-day average or more.</p></div>"
)


@st.cache_data(show_spinner=False, ttl=3600)
def _qualified_trail(key: str, _prices: pd.DataFrame, symbols: tuple) -> dict:
    from src.engine import dashboard_insights as di
    _, trails = di.rank_trails(_prices, [s for s in symbols if s in _prices.columns])
    return {"3m": {s: r[0] for s, r in trails.items() if r[0] is not None},
            "1m": {s: r[1] for s, r in trails.items() if r[1] is not None}}


def with_book_columns(rank_df: pd.DataFrame, book_symbols=None,
                      history_prices: pd.DataFrame | None = None) -> pd.DataFrame:
    """A copy of the ranking with the columns the Screener table reads beside
    the rank: "Qualified Rank", the qualified place 3M and 1M ago, and "Held".

    S87 (owner, 7 Nov): the place among the qualified (the list the book buys
    from, as on Actions) and the model book's holdings, marked "Held". The trail
    is the Dashboard's rank trail, from its own function, so one stock reads the
    same on every page (S154; Screener decision A, 21 Nov 2026).

    Worked out over the WHOLE ranking, then cut by the caller. The Watchlist and
    the stock page's peers drew the same table from the bare ranking, so every
    row read "Out" and nothing was "Held" (S184, 22 Nov 2026); a place worked out
    on a cut list would be the place within the cut, not among the qualified.
    """
    from src.engine.exit_watch import qualified_ranks
    view = rank_df.copy()
    view["Qualified Rank"] = view["Symbol"].map(qualified_ranks(rank_df))
    trail = qualified_trail(history_prices, rank_df)
    if trail is not None:
        view["Qualified (-3M)"] = view["Symbol"].map(trail["3m"])
        view["Qualified (-1M)"] = view["Symbol"].map(trail["1m"])
    view["Held"] = view["Symbol"].isin(set(book_symbols or ()))
    return view


def qualified_trail(prices: pd.DataFrame | None, rank_df: pd.DataFrame) -> dict | None:
    """{"3m": {symbol: place}, "1m": {...}}: the Dashboard's rank trail for every
    ranked stock (`dashboard_insights.rank_trails`, S154). None when it cannot
    be worked out; the table then leaves the two columns out."""
    if prices is None or prices.empty or rank_df is None or rank_df.empty:
        return None
    try:
        from src.engine.pipeline import price_fingerprint
        syms = tuple(str(x) for x in rank_df["Symbol"])
        return _qualified_trail(f"{price_fingerprint(prices)}_{hash(syms)}", prices, syms)
    except Exception:  # noqa: BLE001 -- a failure costs the two columns, never the Screener
        return None


def data_line(rank_df: pd.DataFrame, adj_close: pd.DataFrame | None) -> str:
    """The data date and the counts; no source named (owner, 20 Nov 2026). A
    dataset that is behind is said, in the caution colour, by what it is."""
    when = "" if adj_close is None or not len(adj_close.index) else f"{_fmt.data_to(adj_close.index[-1])}. "
    short_n = int((rank_df.get("Short History", pd.Series(dtype=str)) == "Yes").sum())
    line = (f"{when}{len(rank_df)} stocks ranked; {gap_count(rank_df)} with a price gap, "
            f"{short_n} with a short history.")
    behind = []
    try:
        for item in data_freshness() or []:
            label = str(item.get("label") or "")
            if item.get("stale") and "ranked from" not in label.lower():
                behind.append(f"{html.escape(label)} are to {html.escape(str(item.get('as_of') or ''))}")
    except Exception:  # noqa: BLE001
        behind = []
    extra = (' <span style="color:var(--c-caution)">' + "; ".join(behind) + ".</span>") if behind else ""
    return f'<p class="qp-note" style="margin-top:28px">{html.escape(line)}{extra}</p>'


_MOVERS_CSS = (
    "<style>.mv-sec{border-top:1px solid var(--c-rule_strong);margin-top:40px;padding-top:22px}"
    ".mv-kick{margin:0 0 6px;font-size:var(--fs-12);font-weight:600;letter-spacing:.06em;text-transform:uppercase;color:var(--c-muted)}"
    ".mv-sec h2.mv-h{font-family:var(--font-serif)!important;font-weight:400!important;font-size:var(--fs-30)!important;"
    "line-height:1.2!important;margin:0 0 6px!important;max-width:36ch;letter-spacing:-0.3px!important}"
    ".mv-h .up{color:var(--c-up)}.mv-h .down{color:var(--c-down)}"
    ".mv-note{font-size:var(--fs-13);color:var(--c-muted);margin:0;max-width:80ch}"
    ".mv-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:40px;margin-top:22px;align-items:start}"
    ".mv-card h3{font-size:var(--fs-15)!important;font-weight:600!important;margin:0!important;font-family:var(--font-ui)!important}"
    ".mv-card h3 span{font-family:var(--font-mono);font-weight:500;color:var(--c-muted);margin-left:4px}"
    ".mv-card p{font-size:var(--fs-12);color:var(--c-muted);margin:2px 0 8px}"
    ".mv-wrap{overflow-x:auto}"
    "table.mv-t{border-collapse:collapse;width:100%;font-size:var(--fs-13);border-top:1.5px solid var(--c-ink)}"
    ".mv-t th{font-size:var(--fs-12);font-weight:600;color:var(--c-muted);padding:8px;border-bottom:1px solid var(--c-rule_strong);"
    "text-align:right;white-space:nowrap}"
    ".mv-t th.l,.mv-t td.l{text-align:left}"
    ".mv-t td{padding:6px 8px;border-bottom:1px solid var(--c-rule);text-align:right;white-space:nowrap;"
    "font-family:var(--font-mono);font-variant-numeric:tabular-nums}"
    ".mv-t td.l{font-family:var(--font-ui)}"
    ".mv-t td.l a{font-family:var(--font-mono);font-weight:600;color:var(--c-ink);text-decoration:none}"
    ".mv-t td.l a:hover{text-decoration:underline}"
    ".mv-t td.l small{display:block;font-size:var(--fs-12);color:var(--c-muted)}"
    ".mv-t .past{color:var(--c-faint)}.mv-t .now{font-weight:600}"
    ".mv-t .pos{color:var(--c-up)}.mv-t .neg{color:var(--c-down)}"
    ".mv-held{font-size:var(--fs-12);font-family:var(--font-ui);font-weight:600;border:1px solid var(--c-ink);"
    "padding:0 4px;margin-left:6px;border-radius:4px}"
    "@media (max-width:900px){.mv-grid{grid-template-columns:1fr;gap:28px}.mv-sec h2.mv-h{font-size:var(--fs-24)!important}}</style>"
)


def render_top50_changes(rank_df: pd.DataFrame, adj_close: pd.DataFrame | None = None,
                         held: set | None = None) -> None:
    """What moved in the month: the biggest climbs, the stocks that entered the
    top 50 and those that left it, every row shown (PAGE_DESIGN §2: no "View
    all"), headed by the finding (Screener redesign, 21 Nov 2026)."""
    entered, left = top50_changes(rank_df)
    if entered is None:
        return
    jumps = biggest_jumps(rank_df)
    held = held or set()
    d1 = _month_ago(adj_close, 1)
    was_head = f"Rank {_day(d1)}" if d1 is not None else "Rank 1M ago"

    def esc(value) -> str:
        return html.escape(str(value))

    def ret(row) -> tuple[str, str]:
        v = pd.to_numeric(pd.Series([row.get("1M Return")]), errors="coerce").iloc[0]
        if pd.isna(v):
            return "–", ""
        v = round(float(v) * 100, 1)
        return f"{'+' if v > 0 else '−' if v < 0 else ''}{abs(v):.1f}%", ("pos" if v > 0 else "neg" if v < 0 else "")

    def table(title: str, note: str, rows, count: int | None = None) -> str:
        body = []
        for row in rows:
            now = int(row["Rank"])
            prev = pd.to_numeric(pd.Series([row.get("Rank (-1M)")]), errors="coerce").iloc[0]
            was = "–" if pd.isna(prev) else str(int(prev))
            moved = None if pd.isna(prev) else int(prev) - now
            mv = "–" if moved is None else (f"+{moved}" if moved > 0 else f"−{abs(moved)}" if moved < 0 else "0")
            mcls = "" if not moved else ("pos" if moved > 0 else "neg")
            r_txt, r_cls = ret(row)
            sym = str(row["Symbol"])
            tag = '<span class="mv-held">Held</span>' if sym in held else ""
            body.append(
                f'<tr><td class="l"><a href="{stock_href(sym)}" target="_self">{esc(sym)}</a>{tag}'
                f'<small>{esc(short_industry(row.get("Industry")))}</small></td>'
                f'<td class="past">{was}</td><td class="now">{now}</td>'
                f'<td class="{mcls}">{mv}</td><td class="{r_cls}">{esc(r_txt)}</td></tr>')
        n = len(body) if count is None else count
        cnt = f"<span>{n}</span>" if n >= 0 else ""
        return (f'<div class="mv-card"><h3>{esc(title)}{cnt}</h3><p>{esc(note)}</p>'
                '<div class="mv-wrap"><table class="mv-t"><thead><tr><th class="l">Stock</th>'
                f'<th>{esc(was_head)}</th><th>Now</th><th>Places</th><th>1M return</th></tr></thead>'
                f'<tbody>{"".join(body)}</tbody></table></div></div>')

    jr = jumps.to_dict("records")
    n_in, n_out = len(entered), len(left)
    finding = (f'<span class="up">{n_in} stock{"s" if n_in != 1 else ""} entered the top 50</span> and '
               f'<span class="down">{n_out} left</span>')
    if jr:
        j = jr[0]
        finding += (f"; {esc(j['Symbol'])} climbed {int(j['Places_gained'])} places, "
                    f"from #{int(j['Rank_last_month'])} to #{int(j['Rank'])}")
    when = (f"Ranks among the ranked stocks on {_day(d1)}, the last session on or before the same date a month "
            "back, against today. Every row shown.") if d1 is not None else "Every row shown."
    jumps_html = (table("Biggest jumps", "The ten that climbed most places, 1 to 5.", jr[:5], len(jr))
                  + (table("Biggest jumps, 6 to 10", "\u00a0", jr[5:], -1) if len(jr) > 5 else ""))
    st.html(
        _MOVERS_CSS
        + f'<div class="mv-sec" id="t50-movement"><p class="mv-kick">{esc(_movers_heading(adj_close))}</p>'
        f'<h2 class="mv-h">{finding}.</h2><p class="mv-note">{esc(when)}</p>'
        f'<div class="mv-grid">{jumps_html}</div>'
        '<div class="mv-grid">'
        + table("Entered the top 50", f"In the top 50 now, not on {_day(d1) or 'the date a month back'}.",
                entered.to_dict("records"))
        + table("Left the top 50", f"In the top 50 on {_day(d1) or 'the date a month back'}, not now.",
                left.to_dict("records"))
        + "</div></div>"
    )
