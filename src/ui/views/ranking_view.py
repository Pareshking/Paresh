"""
Stock Rankings View Controller with Grid Cards and High-Density Table Views.
Inspired by Investrack, Stockin.id, and Tickerboom.
"""


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
from src.ui.theme import render_master_screener_table, screener_column_count

# Stored in session state by `rank_density_mode`, so these strings are an
# on-disk contract, not labels -- see the format_func in the density control.
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
.sq-chip-nn50{background:#f3e8ff;color:#7e22ce;border-color:#e9d5ff;}
.sq-chip-mid{background:#fff7ed;color:#9a3412;border-color:#fed7aa;}
.sq-chip-sm{background:#fef9c3;color:#713f12;border-color:#fde68a;}
.sq-chip-micro{background:#fef2f2;color:#991b1b;border-color:#fecaca;}
.sq-chip-other{background:#f1f5f9;color:#475569;border-color:#e2e8f0;}
.sq-range-wrap{position:relative;margin:7px 0 10px;padding-top:7px;}
.sq-range-track{height:6px;background:#e2e8f0;border-radius:999px;position:relative;overflow:visible;}
.sq-range-fill{height:6px;background:linear-gradient(90deg,#4f46e5,#059669);border-radius:999px 0 0 999px;}
.sq-range-current{position:absolute;top:50%;width:10px;height:10px;border-radius:50%;background:#059669;border:2px solid #ffffff;box-shadow:0 0 0 1px #059669;transform:translate(-50%,-50%);z-index:3;}
.sq-range-20{position:absolute;top:-6px;width:1px;height:18px;background:#d97706;border-left:1px dashed #d97706;z-index:2;}
.sq-range-20-label{position:absolute;top:-19px;transform:translateX(-50%);font-family:'JetBrains Mono',monospace;font-size:.52rem;font-weight:800;color:#b45309;white-space:nowrap;}
.sq-range-labels{display:flex;justify-content:space-between;gap:6px;margin-top:5px;font-family:'JetBrains Mono',monospace;font-size:.54rem;color:#94a3b8;}
.sq-range-labels span{white-space:nowrap;}
.sq-range-current-label{color:#059669;font-weight:800;}
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
    """Build exact short-form index chips from the canonical Indices tags."""
    chip_classes = {
        "N50": "sq-chip-n50",
        "NN50": "sq-chip-nn50",
        "MID150": "sq-chip-mid",
        "SMALL250": "sq-chip-sm",
        "MICRO250": "sq-chip-micro",
    }
    chips = []
    for part in str(indices_raw or "").split(","):
        tag = part.strip().upper()
        css_class = chip_classes.get(tag)
        if css_class:
            chips.append(
                f'<span class="sq-chip {css_class}">{tag}</span>'
            )
    return "".join(chips)


def _card_html(row: pd.Series) -> str:
    """Return the HTML for a single screener card (no st.* calls)."""
    sym      = str(row.get("Symbol", ""))
    industry = str(row.get("Industry") or "—")
    rank_raw = row.get("Rank")
    rank_num = int(rank_raw) if pd.notna(rank_raw) else None
    indices  = str(row.get("Indices") or "")

    cmp_val  = row.get("CMP")
    ret_12m  = row.get("12M Return")
    ret_3m   = row.get("3M Return")
    ret_1m   = row.get("1M Return")
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
        chips_html = f'<span class="sq-chip sq-chip-other">{html.escape(ind_s)}</span>'

    # 52-week price range bar — current CMP fills the range from 52W low to 52W high.
    # The range values are attached by _attach_52w_range() using the canonical
    # 252-trading-session window. The amber marker is 20% below the 52W high.
    hi_52 = row.get("_52W High")
    lo_52 = row.get("_52W Low")
    current_pos = row.get("_52W Position")
    marker_pos = row.get("_52W 20% Marker")
    if (
        pd.notna(hi_52) and pd.notna(lo_52)
        and pd.notna(current_pos) and float(hi_52) > float(lo_52)
    ):
        fill_pct = max(0.0, min(100.0, float(current_pos)))
        marker_pct = max(0.0, min(100.0, float(marker_pos))) if pd.notna(marker_pos) else None
        marker_html = (
            f'<div class="sq-range-20" style="left:{marker_pct:.2f}%;">'
            f'<span class="sq-range-20-label">−20%</span></div>'
            if marker_pct is not None else ""
        )
        bar_html = (
            '<div class="sq-range-wrap">'
            '<div class="sq-range-track">'
            f'<div class="sq-range-fill" style="width:{fill_pct:.2f}%"></div>'
            f'{marker_html}'
            f'<div class="sq-range-current" style="left:{fill_pct:.2f}%;" '
            f'title="Current ₹{cmp_val:,.0f} · {fill_pct:.1f}% of 52W range"></div>'
            '</div>'
            '<div class="sq-range-labels">'
            f'<span>52W Low ₹{float(lo_52):,.0f}</span>'
            f'<span class="sq-range-current-label">CMP ₹{float(cmp_val):,.0f}</span>'
            f'<span>52W High ₹{float(hi_52):,.0f}</span>'
            '</div>'
            '</div>'
        )
    else:
        bar_html = (
            '<div class="sq-range-wrap">'
            '<div class="sq-range-track"></div>'
            '<div class="sq-range-labels"><span>52W Low —</span><span>52W High —</span></div>'
            '</div>'
        )

    # Metrics
    def _fmt_pct(v, scale=100):
        # pd.isna, not isinstance(v, float): Max DD 12M is float32, and a
        # float32 NaN (any stock under 12 months old) printed "+nan%".
        if v is None or pd.isna(v):
            return "—", "sq-neu"
        f = float(v) * scale
        clr = "sq-pos" if f > 0 else ("sq-neg" if f < 0 else "sq-neu")
        return f"{f:+.1f}%", clr

    r12_txt, r12_clr = _fmt_pct(ret_12m)
    r3_txt,  r3_clr  = _fmt_pct(ret_3m)
    r1_txt,  r1_clr  = _fmt_pct(ret_1m)
    dd_txt,  dd_clr  = _fmt_pct(dd_12m, scale=1)  # already in %

    metrics_html = (
        '<div class="sq-metrics">'
        f'<div class="sq-metric"><div class="sq-metric-label">12M Ret</div>'
        f'<div class="sq-metric-val {r12_clr}">{r12_txt}</div></div>'
        f'<div class="sq-metric"><div class="sq-metric-label">3M Ret</div>'
        f'<div class="sq-metric-val {r3_clr}">{r3_txt}</div></div>'
        f'<div class="sq-metric"><div class="sq-metric-label">1M Ret</div>'
        f'<div class="sq-metric-val {r1_clr}">{r1_txt}</div></div>'
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
        + '<div class="sq-top">'
        + badge_html
        + '<div class="sq-nameblock">'
        + f'<a href="?stock={quote(str(sym), safe="")}" target="_self" class="sq-sym">{html.escape(str(sym))}</a>'
        + f'<div class="sq-ind">{html.escape(str(industry))}</div>'
        + '</div>'
        + f'<div class="sq-right"><span class="sq-cmp">{cmp_html}</span>{delta_html}</div>'
        + '</div>'
        + (f'<div class="sq-chips">{chips_html}</div>' if chips_html else "")
        + bar_html
        + metrics_html
        + footer_html
        + '</div>'
    )


def _attach_52w_range(
    view: pd.DataFrame,
    high_prices: pd.DataFrame | None,
    low_prices: pd.DataFrame | None,
    adj_close: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Attach the canonical 52W range and current-price position for cards.

    The ranking already carries the canonical 52W High. On the production
    close-only screener feed, raw high/low frames are intentionally unavailable,
    so the card must not depend on them being present. For the low end, use the
    available intraday low when present and otherwise the same close history the
    screener is ranking. This keeps the card populated on both price-source
    paths.
    """
    out = view.copy()
    out["_52W High"] = pd.NA
    out["_52W Low"] = pd.NA
    out["_52W Position"] = pd.NA
    out["_52W 20% Marker"] = pd.NA

    # The application defines a trading year as 252 sessions. Use the latest
    # 252 observations available for each symbol, not calendar-day arithmetic.
    for idx, row in out.iterrows():
        symbol = str(row.get("Symbol", "")).strip()
        if not symbol:
            continue

        # Prefer the canonical high already calculated by the ranking engine.
        # This is also available when the screener price source is close-only.
        canonical_hi = row.get("52W High")
        hi = float(canonical_hi) if pd.notna(canonical_hi) else None

        if hi is None and high_prices is not None and symbol in high_prices.columns:
            highs = high_prices[symbol].dropna().sort_index().tail(252)
            if not highs.empty:
                hi = float(highs.max())

        source = None
        if low_prices is not None and symbol in low_prices.columns:
            source = low_prices[symbol]
        elif adj_close is not None and symbol in adj_close.columns:
            source = adj_close[symbol]

        if source is None:
            continue

        lows = source.dropna().sort_index().tail(252)
        if lows.empty:
            continue

        lo = float(lows.min())
        if hi is None or not (pd.notna(hi) and pd.notna(lo) and hi > lo):
            continue

        cmp_val = row.get("CMP")
        if cmp_val is None or pd.isna(cmp_val):
            continue

        current = float(cmp_val)
        position = (current - lo) / (hi - lo) * 100.0

        # The bar itself is normalized from 52W Low (0%) to 52W High
        # (100%). Therefore the visual "−20% from 52W High" guide belongs
        # 20% of the displayed range below the high, i.e. at 80% of the
        # low-to-high bar. Do not use 80% of the absolute high price here:
        # that can fall below the displayed 52W Low (e.g. CASTROLIND:
        # 80% × ₹204 = ₹163.20 < ₹174), which incorrectly clamps the guide
        # to the left edge.
        marker = 80.0

        out.at[idx, "_52W High"] = hi
        out.at[idx, "_52W Low"] = lo
        out.at[idx, "_52W Position"] = position
        out.at[idx, "_52W 20% Marker"] = marker

    return out


def _render_card_grid(
    view: pd.DataFrame,
    high_prices: pd.DataFrame | None = None,
    low_prices: pd.DataFrame | None = None,
    adj_close: pd.DataFrame | None = None,
) -> None:
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

    # The 52W range only for the cards actually drawn: attaching it to the
    # whole filtered view walked all 750 symbols (~0.24s) on every rerun to
    # draw 48 of them (~0.02s).
    card_items = _attach_52w_range(
        view.head(shown), high_prices, low_prices, adj_close
    ).reset_index(drop=True)
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
    # Reduced to the characters an NSE ticker can hold (M&M, BAJAJ-AUTO): the
    # value is whatever the URL says, and it is echoed back on a miss.
    requested = re.sub(
        r"[^A-Z0-9&._-]", "", str(st.query_params.get("stock") or "").strip().upper()
    )[:32]
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

    # The option VALUES are fixed strings and stay that way: they are what
    # session state stores, and a stored value that vanishes from the list on
    # the next run is a crash, not a relabel. Only the TEXT is computed, and it
    # is read back out of the header block the table actually emits -- "Full
    # Quant (35)" sat over a 36-column table because the count was typed a
    # second time, and dropping the ATR columns under a closing-price source
    # would have made both of the wide tiers wrong again.
    def _density_label(option: str) -> str:
        return (f"{option.split(' (')[0]} "
                f"({screener_column_count(option, view.columns)})")

    density_mode = c_density.segmented_control(
        "Column Density",
        _DENSITY_OPTIONS,
        default=_DENSITY_OPTIONS[-1],
        format_func=_density_label,
        key="rank_density_mode",
        label_visibility="collapsed",
    )
    if not density_mode:
        density_mode = _DENSITY_OPTIONS[-1]

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

    # ── Section header above the results ────────────────────────────────────
    # The ranking's own date, not the wall clock: on 1 Oct a table ranked on
    # 30 Sep closes is September's ranking, and labelling it "Oct" said
    # otherwise.
    from src.core import startup_metrics as _metrics

    try:
        month_label = pd.Timestamp(
            str(_metrics.snapshot().get("facts", {}).get("price_as_of") or "")[:10]
        ).strftime("%b %Y")
    except (ValueError, TypeError):
        month_label = ist_now().strftime("%b %Y")
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
        _render_card_grid(view, high_prices, low_prices, adj_close)

    # Export EVERY column the ranking carries, not just the ones on screen.
    # DISPLAY_COLS is a screen-layout decision -- it drops Score, the raw
    # composite the whole ranking is sorted by, along with Composite Rank,
    # Rank (-1M)/(-3M), 52W High, ATR, ATR %, Persistence and Exp Rank. Anyone
    # exporting to a spreadsheet wants the underlying numbers, and silently
    # withholding the score behind the rank makes the file impossible to audit.
    # Display order first so the familiar columns lead, then the rest.
    export_cols = export_columns(view)
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
        gap_count=gap_count(rank_df),
        short_count=int((rank_df.get("Short History", pd.Series()) == "Yes").sum()),
    )
