"""
Stock Rankings View Controller with Grid Cards and High-Density Table Views.
Inspired by Investrack, Stockin.id, and Tickerboom.
"""


import pandas as pd
import streamlit as st

from src.core.market_time import ist_now
from src.ui.charts import render_candlestick_drilldown
from src.ui.components import render_data_quality_footer, to_bool_mask
from src.ui.views.stock_view import render_stock_view
from src.ui.theme import (
    render_master_screener_table,
    render_saas_table,
    render_styled_table,
)

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
    "FFill %",
    "Data Gap",
]


CARD_BATCH = 48


def _render_card_grid(view: pd.DataFrame) -> None:
    """Card grid over the WHOLE result set, revealed a batch at a time.

    It used to render view.head(48) and stop -- silently. Rank #49 onward
    simply did not exist in card view, with nothing on screen to say so, which
    is how a 750-stock screener came to look like a 48-stock one.

    Streamlit has no viewport-driven lazy loading, so this is the honest
    equivalent: render a batch, say exactly how many of how many are shown, and
    let the reader ask for more. Rendering all 750 cards at once is what the
    original cap was avoiding, and that instinct was right -- it is thousands
    of DOM nodes on a phone.
    """
    total = len(view)
    if total == 0:
        st.info("No stocks match the active filters.")
        return

    state_key = "rank_cards_shown"
    shown = min(int(st.session_state.get(state_key, CARD_BATCH)), total)
    # A narrowed filter must not leave the counter stranded above the new total.
    if shown < CARD_BATCH:
        shown = min(CARD_BATCH, total)

    card_items = view.head(shown).reset_index(drop=True)
    n_cols = 4
    for i in range(0, len(card_items), n_cols):
        cols = st.columns(n_cols)
        for j in range(n_cols):
            if i + j < len(card_items):
                with cols[j]:
                    render_stock_card(card_items.iloc[i + j])
        st.markdown(" ")

    st.caption(f"Showing {shown} of {total} stocks.")
    if shown < total:
        c_more, c_all, _ = st.columns([1, 1, 3])
        remaining = total - shown
        if c_more.button(
            f"Show {min(CARD_BATCH, remaining)} more", key="rank_cards_more",
            width="stretch",
        ):
            st.session_state[state_key] = shown + CARD_BATCH
            st.rerun()
        if c_all.button(
            f"Show all {total}", key="rank_cards_all", width="stretch",
        ):
            st.session_state[state_key] = total
            st.rerun()
    elif total > CARD_BATCH:
        if st.button("Collapse to first 48", key="rank_cards_reset"):
            st.session_state[state_key] = CARD_BATCH
            st.rerun()


def render_stock_card(row: pd.Series) -> None:
    """Renders a modern stock screener card (Tickerboom style)."""
    sym = row["Symbol"]
    industry = row.get("Industry", "—")
    rank_num = int(row["Rank"]) if pd.notna(row.get("Rank")) else "—"

    cmp_val = row.get("CMP", 0)
    ret_3m = row.get("3M Return", 0)
    ret_6m = row.get("6M Return", 0)
    ret_3m_clr = "#059669" if ret_3m >= 0 else "#e11d48"
    ret_6m_clr = "#059669" if ret_6m >= 0 else "#e11d48"
    pct_hi = row.get("% High", 0)
    hi_clr = "#059669" if pct_hi >= -10 else ("#d97706" if pct_hi >= -20 else "#64748b")
    sl_val = row.get("Stop Loss", 0)
    chand_val = row.get("Chand Exit", 0)
    sharpe_3m = row.get("3M Sharpe", 0)
    vol = row.get("Volume", "Normal")
    vol_icon = "🔥" if vol == "High" else ("⚡" if vol == "Surge" else "•")

    card_html = f"""
    <div style="background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 14px 16px; margin-bottom: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.03); transition: all 0.15s ease;">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 10px;">
            <div>
                <span style="font-size: 0.72rem; font-weight: 700; color: #4f46e5; background-color: #eef2ff; border: 1px solid #c7d2fe; padding: 2px 7px; border-radius: 20px; font-family: 'IBM Plex Mono', monospace;">
                    #{rank_num}
                </span>
                <a href="?stock={sym}" target="_self" style="font-weight: 600; font-size: 1.02rem; color: #0f172a; margin-left: 6px; text-decoration: none; border-bottom: 1px dotted #94a3b8;" title="Open {sym}">
                    {sym}
                </a>
            </div>
            <div style="font-family: 'IBM Plex Mono', monospace; font-weight: 800; font-size: 1.05rem; color: #0f172a;">
                ₹{cmp_val:,.0f}
            </div>
        </div>

        <div style="font-size: 0.75rem; color: #64748b; margin-bottom: 12px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
            {industry}
        </div>

        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; font-family: 'IBM Plex Mono', monospace; font-size: 0.78rem; border-top: 1px solid #f1f5f9; padding-top: 10px;">
            <div>
                <span style="color: #64748b;">3M Ret:</span>
                <strong style="color: {ret_3m_clr};">{ret_3m:+.1%}</strong>
            </div>
            <div>
                <span style="color: #64748b;">6M Ret:</span>
                <strong style="color: {ret_6m_clr};">{ret_6m:+.1%}</strong>
            </div>
            <div>
                <span style="color: #64748b;">3M Sharpe:</span>
                <strong>{sharpe_3m:.2f}</strong>
            </div>
            <div>
                <span style="color: #64748b;">52W Dist:</span>
                <strong style="color: {hi_clr};">{pct_hi:+.1f}%</strong>
            </div>
            <div>
                <span style="color: #64748b;">Stop Loss:</span>
                <strong style="color: #e11d48;">₹{sl_val:,.0f}</strong>
            </div>
        </div>

        <div style="margin-top: 10px; padding-top: 8px; border-top: 1px solid #f1f5f9; display: flex; justify-content: space-between; font-size: 0.74rem; font-family: 'IBM Plex Mono', monospace;">
            <div>
                <span style="color: #64748b;">Chandelier:</span>
                <strong style="color: #059669;">₹{chand_val:,.0f}</strong>
            </div>
            <div>
                <span style="color: #64748b;">Volume:</span>
                <strong style="color: #4f46e5;">{vol_icon} {vol}</strong>
            </div>
        </div>
    </div>
    """
    st.html(card_html)


def render_ranking_view(
    rank_df: pd.DataFrame,
    adj_close: pd.DataFrame,
    high_prices: pd.DataFrame | None = None,
    low_prices: pd.DataFrame | None = None,
    volume_data: pd.DataFrame | None = None,
    open_prices: pd.DataFrame | None = None,
) -> None:
    """Renders the primary stock rankings interface with dynamic search and Grid/Table switcher."""
    # ── Stock detail route ───────────────────────────────────────────────────
    # ?stock=SYMBOL opens the detail page instead of the screener. A query
    # parameter rather than session state on purpose: it survives a refresh,
    # it can be shared or bookmarked, and it is the only mechanism a link
    # inside the hand-built HTML table can reach -- those cells cannot call
    # back into Python.
    requested = str(st.query_params.get("stock") or "").strip().upper()
    if requested:
        def _back() -> None:
            if st.button("← Back to screener", key="stock_page_back"):
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

    # Build dynamic predictive search suggestions
    idx_set = set()
    if "Indices" in rank_df.columns:
        for item in rank_df["Indices"].dropna():
            for sub in str(item).split(","):
                if sub.strip():
                    idx_set.add(sub.strip())
    for co in [
        "NIFTY 50",
        "NIFTY 500",
        "NIFTY TOTAL MARKET",
        "NIFTY MIDCAP 150",
        "NIFTY SMALLCAP 250",
        "NIFTY MICROCAP 250",
    ]:
        idx_set.add(co)

    idx_opts = sorted([f"[INDEX] {i}" for i in idx_set])
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
    stock_opts = [
        f"[STOCK] {row['Symbol']} — {row.get('Industry', '')}"
        for _, row in rank_df.sort_values("Rank").iterrows()
    ]

    search_options = stock_opts + idx_opts + ind_opts + sec_opts

    # ── Tier 1: Primary Search & Preset Filter Bar ───────────────────────────
    c_search, c_pills = st.columns([1.5, 2.5], vertical_alignment="center")

    selected_search = c_search.selectbox(
        "Search Stock, Industry, or Index",
        options=search_options,
        index=None,
        placeholder="Search Stock, Industry, or Index (e.g. TCS, CUPID, NIFTY)…",
        key="rank_search_predictive",
        label_visibility="collapsed",
    )

    filt = c_pills.pills(
        "Universe Filter Presets",
        [
            "All Universe",
            "Top 50 Qualified",
            "Passed Filters",
            "Momentum Movers",
            "High Volume",
        ],
        default="All Universe",
        key="rank_quick_pills",
        label_visibility="collapsed",
    )

    view = rank_df.copy()
    single_stock_drill: str | None = None

    # Dynamic Predictive Filter Execution
    if selected_search and str(selected_search).strip():
        s_val = str(selected_search).strip()
        if s_val.startswith("[STOCK] "):
            target_sym = s_val.replace("[STOCK] ", "").split(" — ")[0].strip()
            view = view[view["Symbol"].str.upper() == target_sym.upper()]
            single_stock_drill = target_sym
        elif s_val.startswith("[INDUSTRY] "):
            target_ind = s_val.replace("[INDUSTRY] ", "").strip()
            view = view[view["Industry"].str.upper() == target_ind.upper()]
        elif s_val.startswith("[SECTOR] "):
            target_sec = s_val.replace("[SECTOR] ", "").strip()
            view = view[
                view.get("TV_Sector", pd.Series("", index=view.index)).str.upper()
                == target_sec.upper()
            ]
        elif s_val.startswith("[INDEX] "):
            target_idx = s_val.replace("[INDEX] ", "").strip()
            view = view[view["Indices"].str.contains(target_idx, case=False, na=False)]
        else:
            matched_syms = rank_df[rank_df["Symbol"].str.upper() == s_val.upper()]
            if len(matched_syms) == 1:
                single_stock_drill = matched_syms.iloc[0]["Symbol"]

            mask = (
                view["Symbol"].str.contains(s_val, case=False, na=False)
                | view["Industry"].str.contains(s_val, case=False, na=False)
                | view["Indices"].str.contains(s_val, case=False, na=False)
                | view.get("TV_Industry", pd.Series("", index=view.index)).str.contains(
                    s_val, case=False, na=False
                )
                | view.get("TV_Sector", pd.Series("", index=view.index)).str.contains(
                    s_val, case=False, na=False
                )
            )
            view = view[mask]

    # Quick Preset filters
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

    # ── Tier 2: Refinement, Column Density & View Toolbar ────────────────────
    c_info, c_sort, c_density, c_view = st.columns(
        [1.8, 0.9, 1.3, 0.6], vertical_alignment="center"
    )

    n_total = len(rank_df)
    n_view = len(view)
    # Count through the boolean mask. Summing the raw column concatenates
    # under the pandas 3 string dtype and yields '' for an empty view.
    n_ema = int(to_bool_mask(view.get("Above 50 EMA")).sum())
    n_hi = int(to_bool_mask(view.get("Near 52W High")).sum())
    c_info.markdown(
        f"<div style='font-family:JetBrains Mono,monospace;font-size:0.75rem;color:#64748b;padding-top:4px;'>Showing <strong style='color:#0f172a;'>{n_view}</strong> of {n_total} stocks &nbsp;·&nbsp; <span style='color:#15803d;font-weight:600;'>{n_ema}</span> &gt; 50 EMA &nbsp;·&nbsp; <span style='color:#4f46e5;font-weight:600;'>{n_hi}</span> near 52W Hi</div>",
        unsafe_allow_html=True,
    )

    sort_by = c_sort.selectbox(
        "Sort By",
        ["Rank", "3M Return", "6M Return", "3M Sharpe", "% High", "Market Cap (Cr)"],
        key="rank_sort_by",
        label_visibility="collapsed",
    )

    density_mode = c_density.segmented_control(
        "Column Density",
        ["Executive (11)", "Core (17)", "Full Quant (35)"],
        default="Full Quant (35)",
        key="rank_density_mode",
        label_visibility="collapsed",
    )
    if not density_mode:
        density_mode = "Full Quant (35)"

    view_mode = c_view.segmented_control(
        "Layout",
        ["Table", "Cards"],
        default="Table",
        key="rank_view_mode",
        label_visibility="collapsed",
    )

    # ── Single Stock Technical Deep Dive (Activated by Search Selection) ──────
    if single_stock_drill and single_stock_drill in adj_close.columns:
        render_candlestick_drilldown(
            single_stock_drill,
            rank_df,
            adj_close,
            high_prices=high_prices,
            low_prices=low_prices,
            volume_data=volume_data,
        )
        curr_ind = (
            rank_df.loc[rank_df["Symbol"] == single_stock_drill, "Industry"].iloc[0]
            if "Industry" in rank_df.columns
            else None
        )
        if curr_ind:
            peers = rank_df[rank_df["Industry"] == curr_ind].sort_values("Rank").head(8)
            if len(peers) > 1:
                st.markdown(f"**Top Industry Peers in {curr_ind}**")
                p_cols = [
                    "Rank",
                    "Symbol",
                    "CMP",
                    "3M Return",
                    "6M Return",
                    "3M Sharpe",
                    "Volume",
                ]
                p_cols = [c for c in p_cols if c in peers.columns]
                render_saas_table(peers[p_cols], key=f"peers_{single_stock_drill}")
        st.markdown("---")

    # Sorting
    asc = sort_by == "Rank"
    if sort_by in view.columns:
        view = view.sort_values(sort_by, ascending=asc)

    active_cols = [c for c in DISPLAY_COLS if c in view.columns]

    if view_mode in ["Table", "📊 Table"] or not view_mode:
        # The symbol links inside the table open the stock page directly. A
        # picker used to sit here as a fallback for when they did not work;
        # they work now, so it was one more control between the reader and the
        # table -- costly on a phone, where vertical space is the scarce thing.
        render_master_screener_table(
            view, prices_df=adj_close, key="rank_master_table", density=density_mode
        )
    else:
        _render_card_grid(view)

    # Export EVERY column the ranking carries, not just the ones on screen.
    # DISPLAY_COLS is a screen-layout decision -- it drops Score, the raw
    # composite the whole ranking is sorted by, along with Composite Rank,
    # Rank (-1M)/(-3M), 52W High, ATR, ATR %, Persistence and Exp Rank. Anyone
    # exporting to a spreadsheet wants the underlying numbers, and silently
    # withholding the score behind the rank makes the file impossible to audit.
    # Display order first so the familiar columns lead, then the rest.
    export_cols = active_cols + [c for c in view.columns if c not in active_cols]
    export_df = view[export_cols]
    st.download_button(
        f"Download Rankings CSV ({len(export_cols)} columns)",
        export_df.to_csv(index=False).encode(),
        f"nse_momentum_rankings_{ist_now():%Y%m%d}.csv",
        "text/csv",
        key="dl_rank_csv",
        help="All ranking columns, including the ones not shown in the table.",
    )

    render_data_quality_footer(
        total_stocks=len(rank_df),
        gap_count=int((rank_df.get("Data Gap", pd.Series()) == "🔴").sum()),
        short_count=int((rank_df.get("Short History", pd.Series()) == "Yes").sum()),
    )


def render_rank_movers_section(rank_df: pd.DataFrame) -> None:
    """Renders 1-month momentum rank acceleration and breakdown movers (Preserved for modular reuse)."""
    if "Rank (-1M)" not in rank_df.columns:
        return
    m_df = rank_df.dropna(subset=["Rank (-1M)"]).copy()
    m_df["Rank Δ 1M"] = m_df["Rank (-1M)"] - m_df["Rank"]

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("##### 🔺 Top Rank Improvers (1 Month)")
        imp = m_df[m_df["Rank Δ 1M"] > 0].nlargest(10, "Rank Δ 1M")
        if not imp.empty:
            imp_cols = ["Rank", "Symbol", "Rank Δ 1M", "Rank (-1M)", "CMP", "3M Return"]
            render_styled_table(
                imp[[c for c in imp_cols if c in imp.columns]], key="rank_improvers"
            )
        else:
            st.info("No stocks improved ranks.")

    with col_b:
        st.markdown("##### 🔻 Top Rank Fallers (1 Month)")
        fal = m_df[m_df["Rank Δ 1M"] < 0].nsmallest(10, "Rank Δ 1M")
        if not fal.empty:
            fal_cols = ["Rank", "Symbol", "Rank Δ 1M", "Rank (-1M)", "CMP", "3M Return"]
            render_styled_table(
                fal[[c for c in fal_cols if c in fal.columns]], key="rank_fallers"
            )
        else:
            st.info("No stocks dropped ranks.")
