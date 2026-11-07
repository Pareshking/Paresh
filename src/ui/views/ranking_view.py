"""The Screener page: one ranking table for desktop and phone, and the stock route."""


import hashlib
import html
import re
import time

import pandas as pd
import streamlit as st

from src.ui.widget_state import mirror_key, remember
from src.ui.system_param import keep_system_only, stock_href

from src.core.config import SHORT_FORMS
from src.core.market_time import ist_now
from src.ui.components import (
    compute_signals,
    gap_count,
    render_data_quality_footer,
    signal_chips_html,
    to_bool_mask,
)
from src.ui.views.stock_view import render_stock_view
from src.engine.breadth import new_extreme_counts
from src.engine.calendar_momentum import calendar_start_positions
from src.ui.screener_table import INDEX_NAMES, column_count, render_screener_table

# Stored in session state by `rank_density_mode`, so these strings are an
# on-disk contract, not labels -- see the format_func in the density control.
# All three draw the one table in src/ui/screener_table.py; they differ only
# in which columns they show.
_DENSITY_OPTIONS = ["Executive (11)", "Core (17)", "Full Quant (35)"]

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
        return None if value in (None, _DENSITY_OPTIONS[1]) else _DENSITY_CODES.get(value)
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
    # One row: the title, today's signal chips, Export CSV. The count is the
    # top bar's Universe and the date its Prices pill, so no subtitle; the
    # chips sit here rather than on a row of their own (owner, 2026-09-27:
    # no repeats, and no space left where text was taken out).
    head = st.container(key="scr_head", horizontal=True, vertical_alignment="center",
                        gap="medium", wrap=True)
    head.html('<div class="scr-head"><h1>Screener</h1></div>', width="content")
    head.html(signal_chips_html(compute_signals(rank_df)) or "<span></span>", width="stretch")
    c_export = head.container(width="content")

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
        "High Volume": "High volume",
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
        with st.popover("Filters & sort", icon=":material/tune:", width="content"), \
                st.container(key="scr_filters"):
            # On a phone theme.py pins this panel to the bottom of the screen
            # as a sheet; on a desktop it is an ordinary dropdown.
            # Largest companies first, in the names the table uses.
            _order = ["N50", "NN50", "MID150", "SMALL250", "MICRO250"]
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
                default=_kept("rank_density_mode", _DENSITY_OPTIONS[1], list(_DENSITY_OPTIONS)),
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
        density_mode = _DENSITY_OPTIONS[1]

    view = rank_df.copy()
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

    render_top50_changes(rank_df, adj_close)
    if footnote is not None:
        footnote()

    render_data_quality_footer(
        total_stocks=len(rank_df),
        gap_count=gap_count(rank_df),
        short_count=int((rank_df.get("Short History", pd.Series()) == "Yes").sum()),
    )


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


@st.cache_data(show_spinner=False, ttl=3600)
def _new_high_counts(_key: str, _prices: pd.DataFrame) -> pd.DataFrame:
    return new_extreme_counts(_prices)["high"]


def top50_changes(rank_df: pd.DataFrame):
    """Stocks that entered and left the top 50 in the last calendar month, by rank.

    "Rank (-1M)" is the rank on the first session on or after the same date a
    month back (`calendar_start_positions`), not the last month-end.
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


def _movers_heading(adj_close: pd.DataFrame | None) -> str:
    """ "Since 6 Oct (one month)": the session the 1M rank change counts from."""
    if adj_close is None or len(adj_close.index) == 0:
        return "In the last month"
    idx = pd.DatetimeIndex(adj_close.index)
    pos = int(calendar_start_positions(idx, 1)[-1])
    start = idx[min(pos, len(idx) - 1)]
    return f"Since {start.day} {start:%b} (one month)"


def render_top50_changes(rank_df: pd.DataFrame, adj_close: pd.DataFrame | None = None) -> None:
    """Render the approved full-width ranking movement cards."""
    entered, left = top50_changes(rank_df)
    if entered is None:
        return
    jumps = biggest_jumps(rank_df)

    def esc(value) -> str:
        return html.escape(str(value))

    def stock_link(sym) -> str:
        return f'<a class="t50-stock" href="{stock_href(sym)}" target="_self">{esc(sym)}</a>'

    def fmt_return(row) -> str:
        # Ranking returns are stored as decimal fractions (e.g. 0.284 = 28.4%),
        # matching the screener table's canonical percentage formatter.
        val = pd.to_numeric(pd.Series([row.get("1M Return")]), errors="coerce").iloc[0]
        if pd.isna(val):
            return "—"
        v = round(float(val) * 100, 1)
        return f"{'+' if v > 0 else '−' if v < 0 else ''}{abs(v):.1f}%"

    def rank_change(row) -> int | None:
        prev = pd.to_numeric(pd.Series([row.get("Rank (-1M)")]), errors="coerce").iloc[0]
        now = pd.to_numeric(pd.Series([row.get("Rank")]), errors="coerce").iloc[0]
        return None if pd.isna(prev) or pd.isna(now) else int(prev - now)

    def row_html(i: int, row, extra: bool = False) -> str:
        delta = rank_change(row)
        delta_html = "—" if delta is None else (
            f'<span class="t50-delta {"positive" if delta > 0 else ("negative" if delta < 0 else "flat")}">'
            f'{"+" if delta > 0 else "−" if delta < 0 else ""}{abs(delta)}</span>'
        )
        ret = fmt_return(row)
        ret_tone = ("negative" if ret.startswith("−") else "positive" if ret.startswith("+")
                    else "flat")
        return (
            f'<div class="t50-row{" t50-extra" if extra else ""}" role="row">'
            f'<span class="t50-num" role="cell">{i}</span>'
            f'<span class="t50-stock-cell" role="rowheader">{stock_link(row["Symbol"])}</span>'
            f'<span class="t50-cell t50-change" role="cell">{delta_html}</span>'
            f'<span class="t50-cell t50-rank" role="cell">{int(row["Rank"])}</span>'
            f'<span class="t50-cell t50-return {ret_tone}" role="cell">{esc(ret)}</span>'
            '</div>'
        )

    def card(title: str, icon: str, tone: str, rows) -> str:
        # A hidden checkbox holds the open/closed state; the "View all" button
        # under the rows is its label, so it works without JS.
        rows = list(rows)
        toggle_id = f"t50-more-{tone}"
        more = len(rows) > 5
        toggle_label = (
            '<span class="t50-when-closed">View all <span>→</span></span>'
            '<span class="t50-when-open">Show less <span>↑</span></span>'
        )
        head = (
            '<div class="t50-col-head" role="row"><span role="columnheader">#</span>'
            '<span role="columnheader">Stock</span><span role="columnheader">Rank change</span>'
            '<span role="columnheader">New rank</span><span role="columnheader">1M %</span></div>'
        )
        body = f'<div class="t50-table-wrap"><div class="t50-table" role="table" aria-label="{esc(title)}">' + head
        body += "".join(row_html(i, row) for i, row in enumerate(rows[:5], 1))
        body += "".join(row_html(i, row, extra=True) for i, row in enumerate(rows[5:], 6))
        body += '</div></div>'
        if more:
            body += f'<label class="t50-more" for="{toggle_id}">{toggle_label}</label>'
        return (
            f'<section class="t50-card t50-{tone}">'
            + (f'<input type="checkbox" class="t50-toggle" id="{toggle_id}">' if more else '')
            + '<div class="t50-card-head"><div class="t50-card-heading">'
            f'<div class="t50-icon" aria-hidden="true">{icon}</div>'
            f'<div><h2>{esc(title)}</h2></div></div>'
            '</div>' + body + '</section>'
        )

    # One heading says when the three cards count from, so no card repeats it.
    # The ranks are compared with a calendar month back (6 Nov against the
    # first session on or after 6 Oct), not with the last month-end, so the
    # heading names that date (owner, 7 Nov).
    html_out = (
        f'<div class="pg-card-h"><h2>{esc(_movers_heading(adj_close))}</h2></div>'
        '<div id="t50-movement" class="t50-grid">'
        + card("Biggest jumps", "↑", "jump", jumps.to_dict("records"))
        + card("Entered top 50", "★", "entered", entered.to_dict("records"))
        + card("Left top 50", "↓", "left", left.to_dict("records"))
        + '</div>'
    )
    st.html(html_out)

