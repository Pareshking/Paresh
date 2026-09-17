"""
Stock Rankings View Controller with Grid Cards and High-Density Table Views.
Inspired by Investrack, Stockin.id, and Tickerboom.
"""


import hashlib
import time

import pandas as pd
import streamlit as st

from src.ui.widget_state import remember, resolve

from src.core.config import SHORT_FORMS
from src.core.market_time import ist_now
from src.ui.components import render_data_quality_footer, to_bool_mask
from src.ui.views.stock_view import render_stock_view
from src.ui.theme import render_master_screener_table


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
        + f'<a href="?stock={sym}" target="_self" class="sq-sym">{sym}</a>'
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
        # No free-text fallback, because there is no free text to fall back on.
        # `selected_search` comes from a selectbox whose options are exactly the
        # lists built above, and every one of them carries a [STOCK]/[INDEX]/
        # [INDUSTRY]/[SECTOR]/[TV_INDUSTRY] prefix; st.selectbox only returns an
        # option it was given (accept_new_options defaults to False), so the
        # branch that used to sit here could never run.
        #
        # It also could not have run SAFELY: it passed the reader's text
        # straight into Series.str.contains, which treats its argument as a
        # REGULAR EXPRESSION by default. A single "(" or "*" would have raised
        # re.error and taken the screener down. If free text is ever wanted
        # here, pass regex=False and re-add the branch deliberately.

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
    # Same denominator rule as the strip above: count through the mask, and say
    # how many rows could answer at all.
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

    # Explicit index, resolved through the mirror. Under st.navigation only the
    # active page runs, so this key is discarded the moment the reader looks at
    # another page -- without it their chosen sort silently reverts to "Rank".
    _SORT_OPTIONS = [
        "Rank", "3M Return", "6M Return", "3M Sharpe", "% High", "Market Cap (Cr)",
    ]
    sort_by = c_sort.selectbox(
        "Sort By",
        _SORT_OPTIONS,
        index=resolve("rank_sort_by_idx", 0, lo=0, hi=len(_SORT_OPTIONS) - 1),
        key="rank_sort_by",
        label_visibility="collapsed",
    )
    remember("rank_sort_by_idx", _SORT_OPTIONS.index(sort_by))

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
            view, prices_df=adj_close, density=density_mode
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
        _rankings_csv(_frame_key(export_df), export_df),
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
