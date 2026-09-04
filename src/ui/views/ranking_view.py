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


@st.dialog("📈 Stock Analysis", width="large")
def _stock_dialog(
    symbol: str,
    rank_df: pd.DataFrame,
    adj_close: pd.DataFrame,
    high_prices: pd.DataFrame | None,
    low_prices: pd.DataFrame | None,
    volume_data: pd.DataFrame | None,
    open_prices: pd.DataFrame | None,
) -> None:
    render_stock_view(
        symbol,
        rank_df,
        adj_close,
        high_prices=high_prices,
        low_prices=low_prices,
        volume_data=volume_data,
        open_prices=open_prices,
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

# ── CSS injected once per card-grid render ───────────────────────────────────
_CARD_CSS = """
<style>
.sq-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:12px;padding:4px 2px 12px;}
@media(max-width:520px){.sq-grid{grid-template-columns:1fr;}}
.sq-card{background:#fff;border:1px solid #e2e8f0;border-radius:14px;padding:14px 15px;
  position:relative;transition:box-shadow .15s;}
.sq-card:hover{box-shadow:0 4px 16px rgba(79,70,229,.10);}
.sq-top{display:flex;align-items:flex-start;gap:9px;margin-bottom:8px;}
.sq-badge{flex-shrink:0;font-family:'JetBrains Mono',monospace;font-size:.7rem;font-weight:800;
  padding:3px 8px;border-radius:20px;border:1px solid;}
.sq-badge-gold{background:#fef3c7;color:#92400e;border-color:#fcd34d;}
.sq-badge-indigo{background:#eef2ff;color:#4338ca;border-color:#c7d2fe;}
.sq-nameblock{flex:1;min-width:0;}
.sq-sym{font-family:'Outfit',sans-serif;font-weight:900;font-size:1.05rem;color:#0f172a;
  text-decoration:none;border-bottom:1px dotted #94a3b8;}
.sq-sym:hover{color:#4f46e5;}
.sq-ind{font-size:.7rem;color:#64748b;margin-top:1px;overflow:hidden;
  text-overflow:ellipsis;white-space:nowrap;}
.sq-right{display:flex;flex-direction:column;align-items:flex-end;gap:3px;margin-left:auto;}
.sq-cmp{font-family:'JetBrains Mono',monospace;font-weight:800;font-size:1.0rem;
  color:#0f172a;white-space:nowrap;}
.sq-delta{font-family:'JetBrains Mono',monospace;
  font-size:.62rem;font-weight:800;padding:2px 7px;border-radius:20px;white-space:nowrap;}
.sq-delta-up{background:#d1fae5;color:#065f46;}
.sq-delta-dn{background:#fecdd3;color:#9f1239;}
.sq-delta-flat{background:#f1f5f9;color:#64748b;}
.sq-chips{display:flex;gap:4px;flex-wrap:wrap;margin-bottom:8px;}
.sq-chip{font-size:.62rem;font-weight:700;padding:1px 6px;border-radius:4px;border:1px solid;white-space:nowrap;}
.sq-chip-n50{background:#ede9fe;color:#5b21b6;border-color:#ddd6fe;}
.sq-chip-n500{background:#ecfdf5;color:#065f46;border-color:#bbf7d0;}
.sq-chip-mid{background:#fff7ed;color:#9a3412;border-color:#fed7aa;}
.sq-chip-sm{background:#fef9c3;color:#713f12;border-color:#fde68a;}
.sq-chip-other{background:#f1f5f9;color:#475569;border-color:#e2e8f0;}
.sq-score-wrap{height:4px;background:#e2e8f0;border-radius:4px;margin-bottom:4px;overflow:hidden;}
.sq-score-bar{height:4px;background:linear-gradient(90deg,#4f46e5,#059669);border-radius:4px;}
.sq-score-lbl{font-family:'JetBrains Mono',monospace;font-size:.6rem;color:#94a3b8;margin-bottom:9px;}
.sq-metrics{display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:2px;
  border-top:1px solid #f1f5f9;padding-top:9px;margin-bottom:9px;}
.sq-metric{text-align:center;}
.sq-metric-label{font-size:.58rem;color:#94a3b8;font-weight:600;text-transform:uppercase;letter-spacing:.04em;}
.sq-metric-val{font-family:'JetBrains Mono',monospace;font-size:.78rem;font-weight:700;margin-top:1px;}
.sq-pos{color:#059669;}.sq-neg{color:#e11d48;}.sq-warn{color:#d97706;}.sq-neu{color:#0f172a;}
.sq-footer{display:flex;justify-content:space-between;align-items:center;
  border-top:1px solid #f1f5f9;padding-top:8px;
  font-family:'JetBrains Mono',monospace;font-size:.68rem;color:#64748b;}
.sq-vol-high{color:#e11d48;font-weight:700;}
.sq-vol-surge{color:#d97706;font-weight:700;}
.sq-vol-normal{color:#64748b;}
</style>"""


def _render_intelligence_strip(rank_df: pd.DataFrame) -> None:
    """Dark strip: market status · breadth · 52W Hi count · regime signal."""
    now = ist_now()
    hour_min = now.hour * 60 + now.minute
    is_open = 9 * 60 + 15 <= hour_min <= 15 * 60 + 30 and now.weekday() < 5
    mkt_status = "OPEN" if is_open else "CLOSED"
    dot_shadow = "box-shadow:0 0 6px #34d399;" if is_open else ""
    dot_color  = "#34d399" if is_open else "#94a3b8"

    n_total = len(rank_df)
    ema_mask = to_bool_mask(rank_df.get("Above 50 EMA", pd.Series(dtype=object)))
    hi_mask  = to_bool_mask(rank_df.get("Near 52W High", pd.Series(dtype=object)))
    n_ema = int(ema_mask.sum()) if n_total else 0
    n_hi  = int(hi_mask.sum())  if n_total else 0
    breadth_pct = round(n_ema / n_total * 100) if n_total else 0

    if breadth_pct >= 65:
        regime, regime_bg = "BULL TRENDING", "#4f46e5"
    elif breadth_pct >= 50:
        regime, regime_bg = "BULL MIXED",    "#059669"
    elif breadth_pct >= 35:
        regime, regime_bg = "BEAR MIXED",    "#d97706"
    else:
        regime, regime_bg = "BEAR TRENDING", "#e11d48"

    sep = "border-right:1px solid rgba(255,255,255,.1);"
    lbl = "color:rgba(255,255,255,.4);margin-right:4px;"
    val = "color:#fff;font-weight:600;"
    item = (
        f'display:inline-flex;align-items:center;gap:0;'
        f'padding:0 14px;{sep}'
    )

    strip = (
        f'<div style="background:#0f172a;padding:7px 0 7px 14px;'
        f'display:flex;align-items:center;overflow-x:auto;white-space:nowrap;'
        f'font-family:\'JetBrains Mono\',monospace;font-size:.64rem;">'
        # NSE open/closed
        f'<span style="{item}">'
        f'<span style="width:7px;height:7px;border-radius:50%;background:{dot_color};'
        f'flex-shrink:0;{dot_shadow}margin-right:6px;"></span>'
        f'<span style="{lbl}">NSE</span>'
        f'<span style="{val}">{mkt_status}</span>'
        f'</span>'
        # Breadth
        f'<span style="{item}">'
        f'<span style="{lbl}">BREADTH</span>'
        f'<span style="color:#34d399;font-weight:700;">{breadth_pct}%</span>'
        f'<span style="color:rgba(255,255,255,.3);margin-left:4px;">&gt;50 EMA</span>'
        f'</span>'
        # 52W Hi count
        f'<span style="{item}">'
        f'<span style="{lbl}">52W HI</span>'
        f'<span style="color:#818cf8;font-weight:700;">{n_hi}</span>'
        f'<span style="color:rgba(255,255,255,.3);margin-left:4px;">stocks near</span>'
        f'</span>'
        # Regime pill
        f'<span style="{item}">'
        f'<span style="{lbl}">REGIME</span>'
        f'<span style="background:{regime_bg};color:#fff;padding:2px 8px;'
        f'border-radius:4px;font-size:.58rem;font-weight:700;letter-spacing:.05em;">{regime}</span>'
        f'</span>'
        # Universe count
        f'<span style="display:inline-flex;align-items:center;padding:0 14px;margin-left:auto;">'
        f'<span style="{lbl}">UNIVERSE</span>'
        f'<span style="{val}">{n_total} stocks</span>'
        f'</span>'
        f'</div>'
    )
    st.markdown(strip, unsafe_allow_html=True)


def _idx_chips_html(indices_raw: str) -> str:
    """Build index chip HTML for a raw comma-separated Indices string."""
    chips = ""
    for part in str(indices_raw or "").split(","):
        s = part.strip()
        if not s or s == "—":
            continue
        if "50" in s and "500" not in s:
            chips += '<span class="sq-chip sq-chip-n50">N50</span>'
        elif "500" in s:
            chips += '<span class="sq-chip sq-chip-n500">N500</span>'
        elif "MIDCAP" in s.upper():
            chips += '<span class="sq-chip sq-chip-mid">MID</span>'
        elif "SMALLCAP" in s.upper():
            chips += '<span class="sq-chip sq-chip-sm">SM</span>'
    return chips


def _card_html(row: pd.Series) -> str:
    """Return the HTML for a single screener card (no st.* calls)."""
    sym      = str(row.get("Symbol", ""))
    industry = str(row.get("Industry") or "—")
    rank_raw = row.get("Rank")
    rank_num = int(rank_raw) if pd.notna(rank_raw) else None
    score    = row.get("Score")
    indices  = str(row.get("Indices") or "")

    cmp_val  = row.get("CMP")
    ret_12m  = row.get("12M Return")
    ret_3m   = row.get("3M Return")
    sharpe3  = row.get("3M Sharpe")
    dd_12m   = row.get("Max DD 12M")
    delta1m  = row.get("Rank Δ 1M")
    sl_val   = row.get("Stop Loss")
    vol      = str(row.get("Volume") or "Normal")
    above_ema = bool(to_bool_mask(pd.Series([row.get("Above 50 EMA")])).iloc[0])
    near_hi   = bool(to_bool_mask(pd.Series([row.get("Near 52W High")])).iloc[0])

    # Card wrapper style — 52W Hi highlight, below-EMA dimming
    card_style = ""
    if near_hi:
        card_style += "border-color:#c7d2fe;background:linear-gradient(135deg,#fafbff 0%,#f8fafc 100%);"
    card_opacity = "" if above_ema else "opacity:.58;"

    # Rank badge
    if rank_num is not None:
        badge_cls = "sq-badge-gold" if rank_num <= 3 else "sq-badge-indigo"
        badge_html = f'<span class="sq-badge {badge_cls}">#{rank_num}</span>'
    else:
        badge_html = ""

    # Rank delta badge (top-right)
    if pd.notna(delta1m) and delta1m is not None:
        d = int(delta1m)
        if d > 0:
            delta_html = f'<span class="sq-delta sq-delta-up">▲{d}</span>'
        elif d < 0:
            delta_html = f'<span class="sq-delta sq-delta-dn">▼{abs(d)}</span>'
        else:
            delta_html = '<span class="sq-delta sq-delta-flat">—</span>'
    else:
        delta_html = ""

    # CMP
    cmp_html = f"₹{cmp_val:,.0f}" if pd.notna(cmp_val) and cmp_val else "—"

    # Chips
    chips_html = _idx_chips_html(indices)
    if not chips_html and industry and industry != "—":
        ind_s = industry[:10] + "…" if len(industry) > 11 else industry
        chips_html = f'<span class="sq-chip sq-chip-other">{ind_s}</span>'

    # Score bar
    score_pct = 0
    score_label = "—"
    if score is not None and pd.notna(score):
        score_pct = int(max(0, min(100, float(score) * 100)))
        score_label = f"{float(score):.3f}"
    bar_html = (
        f'<div class="sq-score-wrap"><div class="sq-score-bar" style="width:{score_pct}%"></div></div>'
        f'<div class="sq-score-lbl">Score {score_label}</div>'
    )

    # Metrics
    def _fmt_pct(v, scale=100):
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return "—", "sq-neu"
        f = float(v) * scale
        clr = "sq-pos" if f > 0 else ("sq-neg" if f < 0 else "sq-neu")
        return f"{f:+.1f}%", clr

    def _fmt_ratio(v):
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return "—", "sq-neu"
        f = float(v)
        clr = "sq-pos" if f > 1 else ("sq-warn" if f > 0 else "sq-neg")
        return f"{f:.2f}", clr

    r12_txt, r12_clr = _fmt_pct(ret_12m)
    r3_txt,  r3_clr  = _fmt_pct(ret_3m)
    sh_txt,  sh_clr  = _fmt_ratio(sharpe3)
    dd_txt,  dd_clr  = _fmt_pct(dd_12m, scale=1)  # already in %

    metrics_html = (
        '<div class="sq-metrics">'
        f'<div class="sq-metric"><div class="sq-metric-label">12M Ret</div>'
        f'<div class="sq-metric-val {r12_clr}">{r12_txt}</div></div>'
        f'<div class="sq-metric"><div class="sq-metric-label">3M Ret</div>'
        f'<div class="sq-metric-val {r3_clr}">{r3_txt}</div></div>'
        f'<div class="sq-metric"><div class="sq-metric-label">Sharpe</div>'
        f'<div class="sq-metric-val {sh_clr}">{sh_txt}</div></div>'
        f'<div class="sq-metric"><div class="sq-metric-label">Max DD</div>'
        f'<div class="sq-metric-val {dd_clr}">{dd_txt}</div></div>'
        '</div>'
    )

    # Footer
    sl_str = f"SL ₹{sl_val:,.0f}" if sl_val and pd.notna(sl_val) else ""
    vol_icon = "🔥" if vol == "High" else ("⚡" if vol == "Surge" else "•")
    vol_cls = "sq-vol-high" if vol == "High" else ("sq-vol-surge" if vol == "Surge" else "sq-vol-normal")
    footer_html = (
        f'<div class="sq-footer">'
        f'<span>{sl_str}</span>'
        f'<span class="{vol_cls}">{vol_icon} {vol}</span>'
        f'</div>'
    )

    return (
        f'<div class="sq-card" style="{card_style}{card_opacity}">'
        + f'<div class="sq-top">'
        + badge_html
        + f'<div class="sq-nameblock">'
        + f'<a href="?stock={sym}" class="sq-sym">{sym}</a>'
        + f'<div class="sq-ind">{industry}</div>'
        + f'</div>'
        + f'<div class="sq-right"><span class="sq-cmp">{cmp_html}</span>{delta_html}</div>'
        + f'</div>'
        + (f'<div class="sq-chips">{chips_html}</div>' if chips_html else "")
        + bar_html
        + metrics_html
        + footer_html
        + '</div>'
    )


def _render_card_grid(view: pd.DataFrame) -> None:
    """Card grid over the WHOLE result set, revealed a batch at a time.

    Uses CSS grid (auto-fill minmax 260px) rendered in one st.markdown call
    so ?stock=SYM links navigate the parent Streamlit app and layout adapts
    from 4-col desktop → 1-col mobile without any Python viewport detection.
    """
    total = len(view)
    if total == 0:
        st.info("No stocks match the active filters.")
        return

    state_key = "rank_cards_shown"
    shown = min(int(st.session_state.get(state_key, CARD_BATCH)), total)
    if shown < CARD_BATCH:
        shown = min(CARD_BATCH, total)

    card_items = view.head(shown).reset_index(drop=True)
    cards_inner = "".join(_card_html(card_items.iloc[i]) for i in range(len(card_items)))
    st.markdown(
        _CARD_CSS + f'<div class="sq-grid">{cards_inner}</div>',
        unsafe_allow_html=True,
    )

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
    """Legacy single-card renderer — kept for external callers; internally card grid uses _card_html."""
    st.markdown(_CARD_CSS + _card_html(row), unsafe_allow_html=True)


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
    tv_ind_opts = sorted(
        [
            f"[TV_INDUSTRY] {i}"
            for i in rank_df.get("TV_Industry", pd.Series()).dropna().unique()
            if str(i).strip()
        ]
    )
    stock_opts = [
        f"[STOCK] {row['Symbol']} — {row.get('Industry', '')}"
        for _, row in rank_df.sort_values("Rank").iterrows()
    ]

    search_options = stock_opts + idx_opts + ind_opts + sec_opts + tv_ind_opts

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
        elif s_val.startswith("[TV_INDUSTRY] "):
            target_tv_ind = s_val.replace("[TV_INDUSTRY] ", "").strip()
            view = view[
                view.get("TV_Industry", pd.Series("", index=view.index)).str.upper()
                == target_tv_ind.upper()
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
        f"<div style='font-family:\"JetBrains Mono\",monospace;font-size:0.72rem;"
        f"color:#64748b;padding:5px 10px;background:#f8fafc;border:1px solid #e2e8f0;"
        f"border-radius:8px;line-height:1.5;'>"
        f"Showing <strong style='color:#0f172a;'>{n_view}</strong> of {n_total} &nbsp;·&nbsp; "
        f"<span style='color:#059669;font-weight:700;'>{n_ema}</span> &gt;50 EMA &nbsp;·&nbsp; "
        f"<span style='color:#4f46e5;font-weight:700;'>{n_hi}</span> near 52W Hi"
        f"</div>",
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
        default="Cards",
        key="rank_view_mode",
        label_visibility="collapsed",
    )


    # ── Single Stock Technical Deep Dive (Activated by Search Selection) ──────
    if single_stock_drill and single_stock_drill in adj_close.columns:
        _stock_dialog(
            single_stock_drill,
            rank_df,
            adj_close,
            high_prices,
            low_prices,
            volume_data,
            open_prices,
        )

    # Sorting
    asc = sort_by == "Rank"
    if sort_by in view.columns:
        view = view.sort_values(sort_by, ascending=asc)

    active_cols = [c for c in DISPLAY_COLS if c in view.columns]

    # ── Section header above the results ────────────────────────────────────
    now = ist_now()
    month_label = now.strftime("%b %Y")
    st.markdown(
        f'<div style="font-size:0.73rem;font-weight:800;color:#0f172a;'
        f'letter-spacing:0.01em;margin:14px 0 6px;padding-bottom:6px;'
        f'border-bottom:2px solid #eef2ff;">'
        f'Top Ranked &nbsp;·&nbsp; <span style="color:#64748b;font-weight:500;">{month_label}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

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
