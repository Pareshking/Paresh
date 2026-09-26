"""The Screener page: one ranking table for desktop and phone, and the stock route."""


import hashlib
import html
import re
import time
from urllib.parse import quote

import pandas as pd
import streamlit as st

from src.ui.widget_state import remember, resolve

from src.core.config import SHORT_FORMS
from src.core.market_time import ist_now
from src.ui.components import gap_count, render_data_quality_footer, to_bool_mask
from src.ui.views.stock_view import render_stock_view
from src.ui.screener_table import INDEX_NAMES, column_count, render_screener_table
from src.ui.theme import render_master_screener_table, screener_column_count

# Stored in session state by `rank_density_mode`, so these strings are an
# on-disk contract, not labels -- see the format_func in the density control.
# Executive and Core draw the design's table (src/ui/screener_table.py); Full
# Quant keeps the wide research table.
_DENSITY_OPTIONS = ["Executive (11)", "Core (17)", "Full Quant (35)"]


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
) -> None:
    """The Screener: market strip, search and presets, the ranking table, and
    this month's top-50 moves. ?stock=SYMBOL opens that stock's page instead."""
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
                st.query_params.clear()
                st.rerun()

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
    # The ranking's own date, not the wall clock: on 1 Oct a table ranked on
    # 30 Sep closes is September's ranking, and labelling it "Oct" said
    # otherwise.
    from src.core import startup_metrics as _metrics

    try:
        price_day = pd.Timestamp(
            str(_metrics.snapshot().get("facts", {}).get("price_as_of") or "")[:10]
        )
        month_label = price_day.strftime("%B %Y")
        close_label = f"closes of {price_day:%a %d %b}"
    except (ValueError, TypeError):
        month_label = ist_now().strftime("%B %Y")
        close_label = "latest closes"

    n_total = len(rank_df)
    c_title, c_export = st.columns([4, 1], vertical_alignment="bottom")
    c_title.html(
        f'<div class="scr-head"><h1>Screener</h1><p>{n_total} NSE stocks ranked by '
        f"risk-adjusted momentum · {html.escape(month_label)} ranking, "
        f"{html.escape(close_label)}</p></div>"
    )

    render_market_strip(rank_df, regime)

    # ── Search, presets, sort and columns ────────────────────────────────────
    passes = (to_bool_mask(rank_df.get("Above 50 EMA"))
              & to_bool_mask(rank_df.get("Near 52W High")))
    preset_counts = {
        "All Universe": n_total,
        "Top 50 Qualified": int(((rank_df["Rank"] <= 50) & passes).sum()),
        "Passed Filters": int(passes.sum()),
        "Momentum Movers": int((rank_df["Rank Δ 1M"].abs() >= 15).sum())
        if "Rank Δ 1M" in rank_df.columns else 0,
        "High Volume": int((rank_df.get("Volume", pd.Series("", index=rank_df.index)) == "High").sum()),
    }
    preset_names = {
        "All Universe": "All", "Top 50 Qualified": "Top 50 qualified",
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
            on_change=_open_searched_stock,
            width=340,
        )
        filt = st.pills(
            "Presets",
            list(preset_counts),
            default="All Universe",
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
                format_func=lambda t: index_names.get(t, t),
                key="rank_index_filter",
            )
            only_passing = st.toggle("Only stocks that pass both filters",
                                     key="rank_only_passing")
            # Explicit index, resolved through the mirror. Under st.navigation
            # only the active page runs, so this key is discarded the moment
            # the reader looks at another page -- without it their chosen sort
            # silently reverts to "Rank".
            _SORT_OPTIONS = [
                "Rank", "3M Return", "6M Return", "3M Sharpe", "% High", "Market Cap (Cr)",
            ]
            sort_by = st.selectbox(
                "Sort by",
                _SORT_OPTIONS,
                index=resolve("rank_sort_by_idx", 0, lo=0, hi=len(_SORT_OPTIONS) - 1),
                key="rank_sort_by",
            )
            remember("rank_sort_by_idx", _SORT_OPTIONS.index(sort_by))

            # The option VALUES are fixed strings: they are what session state
            # stores, and a stored value that vanishes from the list on the
            # next run is a crash, not a relabel. Only the TEXT is computed,
            # from the table that will actually be drawn.
            def _density_label(option: str) -> str:
                if option.startswith("Full"):
                    n = screener_column_count(option, rank_df.columns)
                else:
                    n = column_count(option)
                return f"{option.split(' (')[0]} ({n})"

            density_mode = st.segmented_control(
                "Columns",
                _DENSITY_OPTIONS,
                default=_DENSITY_OPTIONS[1],
                format_func=_density_label,
                key="rank_density_mode",
            )
            st.caption("Click a column header in the table to sort by it too.")
            st.button("Reset", key="rank_filters_reset", type="tertiary",
                      on_click=_reset_screener_filters)
    if not density_mode:
        density_mode = _DENSITY_OPTIONS[1]

    view = rank_df.copy()
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
    elif filt == "Passed Filters":
        view = view[
            to_bool_mask(view.get("Above 50 EMA"))
            & to_bool_mask(view.get("Near 52W High"))
        ]
    elif filt == "Momentum Movers":
        if "Rank Δ 1M" in view.columns:
            view = view[view["Rank Δ 1M"].abs() >= 15].sort_values(
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

    asc = sort_by == "Rank"
    if sort_by in view.columns and not (filt == "Momentum Movers" and sort_by == "Rank"):
        view = view.sort_values(sort_by, ascending=asc)

    # Count through the boolean mask. Summing the raw column concatenates
    # under the pandas 3 string dtype and yields '' for an empty view.
    n_view = len(view)
    n_ema = int(to_bool_mask(view.get("Above 50 EMA")).sum())
    n_hi = int(to_bool_mask(view.get("Near 52W High")).sum())
    st.html(
        f'<div class="scr-count">Showing <strong>{n_view}</strong> of {n_total}'
        f" · {n_ema} above 50-day EMA · {n_hi} within 20% of their 52-week high"
        f" · click a column to sort, a row to open the stock</div>"
    )

    if str(density_mode).startswith("Full"):
        # The research view: every window and every data-health column.
        render_master_screener_table(view, prices_df=adj_close, density=density_mode)
    else:
        render_screener_table(view, adj_close, density_mode)

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
             f"columns, including the ones not in the table.",
        width="stretch",
    )

    render_top50_changes(rank_df, month_label.split(" ")[0])

    render_data_quality_footer(
        total_stocks=len(rank_df),
        gap_count=gap_count(rank_df),
        short_count=int((rank_df.get("Short History", pd.Series()) == "Yes").sum()),
    )


def _reset_screener_filters() -> None:
    # Popped, not assigned: each of these widgets passes its own default, and
    # a session-state value on top of a default makes Streamlit print a
    # warning on the page. The sort's mirror goes back to Rank as well.
    for key in ("rank_index_filter", "rank_only_passing", "rank_sort_by",
                "rank_density_mode", "rank_quick_pills"):
        st.session_state.pop(key, None)
    remember("rank_sort_by_idx", 0)


def render_market_strip(rank_df: pd.DataFrame, regime) -> None:
    """Regime, breadth, pass count and this month's top-50 moves."""
    n = len(rank_df)
    ema = int(to_bool_mask(rank_df.get("Above 50 EMA")).sum())
    passes = int((to_bool_mask(rank_df.get("Above 50 EMA"))
                  & to_bool_mask(rank_df.get("Near 52W High"))).sum())
    pct = ema / n * 100 if n else 0.0
    entered, left = top50_changes(rank_df)
    tiles = []
    if regime is not None:
        bull = str(getattr(regime.status, "value", regime.status)).upper() == "BULLISH"
        dist = float(regime.distance_pct)
        tiles.append(
            f'<div class="ms-tile"><span class="ms-k">Market regime</span>'
            f'<span class="ms-v {"up" if bull else "down"}">{"Bullish" if bull else "Bearish"}</span>'
            f'<span class="ms-s">Nifty 500 at {regime.current_price:,.0f} · '
            f'<b class="{"up" if dist >= 0 else "down"}">{abs(dist):.1f}% '
            f'{"above" if dist >= 0 else "below"}</b> its 200-day average</span></div>'
        )
    tiles.append(
        f'<div class="ms-tile"><span class="ms-k">Breadth</span><span class="ms-v">{pct:.0f}%</span>'
        f'<span class="ms-bar"><i style="width:{pct:.0f}%"></i></span>'
        f'<span class="ms-s">{ema} of {n} above their 50-day EMA</span></div>'
    )
    tiles.append(
        f'<div class="ms-tile"><span class="ms-k">Pass both filters</span><span class="ms-v">{passes}</span>'
        f'<span class="ms-s">Above 50-day EMA and within 20% of their 52-week high</span></div>'
    )
    if entered is not None:
        tiles.append(
            f'<div class="ms-tile"><span class="ms-k">Top 50 this month</span>'
            f'<span class="ms-v"><span class="up">{len(entered)} in</span> '
            f'<span class="ms-dot">·</span> <span class="down">{len(left)} out</span></span>'
            f'<span class="ms-s">See who moved, below the table</span></div>'
        )
    st.html(f'<section class="mkt-strip" aria-label="Market today">{"".join(tiles)}</section>')


def top50_changes(rank_df: pd.DataFrame):
    """Stocks that entered and left the top 50 since last month, by rank."""
    if "Rank (-1M)" not in rank_df.columns:
        return None, None
    prev = pd.to_numeric(rank_df["Rank (-1M)"], errors="coerce")
    now = pd.to_numeric(rank_df["Rank"], errors="coerce")
    entered = rank_df[(now <= 50) & (prev > 50)].sort_values("Rank")
    left = rank_df[(now > 50) & (prev <= 50)].sort_values("Rank")
    return entered, left


def render_top50_changes(rank_df: pd.DataFrame, month: str) -> None:
    entered, left = top50_changes(rank_df)
    if entered is None or (entered.empty and left.empty):
        return

    def chips(df: pd.DataFrame) -> str:
        return "".join(
            f'<a class="t50-chip" href="?stock={quote(str(r.Symbol), safe="")}" target="_self">'
            f'{html.escape(str(r.Symbol))} <span>#{int(r.Rank)}</span></a>'
            for r in df.itertuples()
        ) or '<span class="t50-none">None</span>'

    st.html(
        '<section class="t50" aria-label="Top 50 this month">'
        f'<div class="t50-card"><div class="t50-h"><h2>Entered the top 50 in {html.escape(month)}</h2>'
        f'<span class="up">{len(entered)} stocks</span></div><div class="t50-chips">{chips(entered)}</div></div>'
        f'<div class="t50-card"><div class="t50-h"><h2>Left the top 50</h2>'
        f'<span class="down">{len(left)} stocks · now ranked</span></div>'
        f'<div class="t50-chips">{chips(left)}</div></div></section>'
    )
