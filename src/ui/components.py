"""
Reusable UI Components and Widgets for NSE Momentum Dashboard.
Inspired by Investrack, Stockin.id, and Tickerboom financial terminal designs.
"""

from datetime import datetime
from typing import Any

import pandas as pd
import streamlit as st

from src.core.types import MarketRegime, RegimeData, SignalAlert
from src.ui.theme import clean_html


def compute_signals(
    rank_df: pd.DataFrame,
    regime_status: MarketRegime,
    dma_dist: float,
    pct_above_ema: float,
) -> list[SignalAlert]:
    """Generates automated market & momentum signals."""
    signals: list[SignalAlert] = []

    if "Rank (-1M)" in rank_df.columns:
        rank_df_tmp = rank_df.copy()
        rank_df_tmp["_delta_1m"] = rank_df_tmp["Rank (-1M)"] - rank_df_tmp["Rank"]

        # Fresh entries into top 50
        fresh = rank_df_tmp[
            (rank_df_tmp["Rank"] <= 50) & (rank_df_tmp["Rank (-1M)"] > 50)
        ]
        if len(fresh) > 0:
            syms = ", ".join(fresh.sort_values("Rank")["Symbol"].tolist())
            signals.append(
                SignalAlert(
                    icon="🔺",
                    text=f"{len(fresh)} stock(s) entered Top 50 this month: {syms}",
                    color="#059669",
                    category="momentum",
                )
            )

        # Exited top 50
        fallen = rank_df_tmp[
            (rank_df_tmp["Rank"] > 50) & (rank_df_tmp["Rank (-1M)"] <= 50)
        ]
        if len(fallen) > 0:
            syms = ", ".join(fallen.sort_values("Rank")["Symbol"].tolist())
            signals.append(
                SignalAlert(
                    icon="🔻",
                    text=f"{len(fallen)} stock(s) exited Top 50: {syms}",
                    color="#e11d48",
                    category="momentum",
                )
            )

        # Biggest single-stock jump
        biggest = rank_df_tmp.nlargest(1, "_delta_1m")
        if not biggest.empty:
            r = biggest.iloc[0]
            if r["_delta_1m"] > 75:
                signals.append(
                    SignalAlert(
                        icon="🚀",
                        text=f"{r['Symbol']} surged +{int(r['_delta_1m'])} ranks (#{int(r['Rank (-1M)'])} → #{int(r['Rank'])})",
                        color="#4f46e5",
                        category="breakout",
                    )
                )

    # Qualified count check (Safely parse boolean or string icons)
    ab_ema = (
        rank_df["Above 50 EMA"].map(
            lambda x: x is True or str(x).strip() in ["✅", "True", "1"]
        )
        if "Above 50 EMA" in rank_df.columns
        else pd.Series(True, index=rank_df.index)
    )
    nr_hi = (
        rank_df["Near 52W High"].map(
            lambda x: x is True or str(x).strip() in ["✅", "True", "1"]
        )
        if "Near 52W High" in rank_df.columns
        else pd.Series(True, index=rank_df.index)
    )
    rk_col = rank_df.get(
        "Composite Rank", rank_df.get("Rank", pd.Series(1, index=rank_df.index))
    )
    # Force native, index-aligned boolean masks. Pandas 3 / PyArrow-backed
    # columns can otherwise produce mixed-dtype logical operations at runtime.
    ab_ema = pd.Series(ab_ema, index=rank_df.index, dtype="bool")
    nr_hi = pd.Series(nr_hi, index=rank_df.index, dtype="bool")
    has_rank = pd.Series(rk_col.notna(), index=rank_df.index, dtype="bool")
    qualified = rank_df[ab_ema & nr_hi & has_rank]
    if len(qualified) < 15:
        signals.append(
            SignalAlert(
                icon="⚠️",
                text=f"Only {len(qualified)} stocks qualify for portfolio construction (target is >= 20)",
                color="#d97706",
                category="risk",
            )
        )

    # Breadth alert
    if pct_above_ema < 40:
        signals.append(
            SignalAlert(
                icon="🔴",
                text=f"Market breadth weak: only {pct_above_ema:.0f}% of stocks are trading above 50 EMA",
                color="#e11d48",
                category="breadth",
            )
        )
    elif pct_above_ema > 75:
        signals.append(
            SignalAlert(
                icon="🟢",
                text=f"Broad bullish participation: {pct_above_ema:.0f}% of universe trading above 50 EMA",
                color="#059669",
                category="breadth",
            )
        )

    if regime_status == MarketRegime.BEARISH:
        signals.append(
            SignalAlert(
                icon="🐻",
                text=f"Benchmark regime BEARISH — Nifty is {dma_dist:+.1f}% below its 200 DMA",
                color="#e11d48",
                category="regime",
            )
        )

    return signals


def render_ticker_ribbon(rank_df: pd.DataFrame, regime: RegimeData) -> None:
    """Renders top live marquee ticker ribbon (Stockin.id style)."""
    top_picks = rank_df.sort_values("Rank").head(8)
    if top_picks.empty:
        return

    border_clr = "#059669" if regime.distance_pct >= 0 else "#e11d48"
    items_html = (
        f'<div class="ticker-item" style="border-left: 3px solid {border_clr};">'
        f'<span style="font-weight: 700; color: #0f172a;">NIFTY 500</span>'
        f'<span style="color: #475569;">₹{regime.current_price:,.0f}</span>'
        f'<span style="font-weight: 700; color: {border_clr};">{regime.distance_pct:+.1f}% (200D)</span>'
        f"</div>"
    )

    for _, row in top_picks.iterrows():
        sym = row["Symbol"]
        cmp_val = row.get("CMP", 0)
        ret_3m = row.get("3M Return", 0)
        ret_str = f"{ret_3m:+.1%}" if pd.notna(ret_3m) else "—"
        ret_clr = "#059669" if ret_3m >= 0 else "#e11d48"
        rank_num = int(row["Rank"]) if pd.notna(row.get("Rank")) else "—"

        items_html += (
            f'<div class="ticker-item">'
            f'<span style="color: #64748b; font-size: 0.72rem;">#{rank_num}</span>'
            f'<span style="font-weight: 800; color: #0f172a;">{sym}</span>'
            f'<span style="color: #334155;">₹{cmp_val:,.0f}</span>'
            f'<span style="font-weight: 700; color: {ret_clr};">{ret_str}</span>'
            f"</div>"
        )

    st.markdown(
        clean_html(f'<div class="ticker-ribbon">{items_html}</div>'),
        unsafe_allow_html=True,
    )


def render_header_kpi_bar(
    regime: RegimeData,
    total_stocks: int,
    above_ema: int,
    pct_above_ema: float,
    gap_count: int,
) -> None:
    """Renders the executive status bar.

    Hierarchy is the point. The previous bar rendered every figure at the same
    0.74rem mono weight, separated by pipes, so universe size, breadth and the
    200-DMA distance -- the numbers a user actually reads first -- were the
    smallest text on the page. Each figure is now a labelled stat with a quiet
    uppercase key and a prominent tabular value, and regime is a status pill
    rather than a coloured bullet in a run of text.
    """
    if regime.status == MarketRegime.BULLISH:
        regime_cls = "up"
    elif regime.status == MarketRegime.BEARISH:
        regime_cls = "down"
    else:
        regime_cls = "flat"
    dma_cls = "up" if regime.distance_pct >= 0 else "down"
    today_str = datetime.now().strftime("%d %b %Y")
    breadth_cls = "up" if pct_above_ema >= 50 else "down"

    header_html = f"""
    <div class="u-statusbar" role="status" aria-label="Market status">
      <div class="u-brand">Paresh Patel<small>Momentum Terminal</small></div>
      <span class="u-regime {regime_cls}"><span class="dot"></span>{regime.status.value}</span>
      <span class="u-spacer"></span>
      <div class="u-stats">
        <div class="u-stat">
          <span class="k">Benchmark</span>
          <span class="v">&#8377;{regime.current_price:,.0f}
            <span class="sub {dma_cls}">{regime.distance_pct:+.1f}% vs 200D</span></span>
        </div>
        <div class="u-stat">
          <span class="k">Universe</span>
          <span class="v">{total_stocks:,}</span>
        </div>
        <div class="u-stat">
          <span class="k">Above 50 EMA</span>
          <span class="v {breadth_cls}">{above_ema:,}<span class="sub">{pct_above_ema:.0f}%</span></span>
        </div>
        <div class="u-stat">
          <span class="k">As of</span>
          <span class="v">{today_str}</span>
        </div>
      </div>
    </div>
    """
    st.html(header_html)


import html


def render_signal_alerts(signals: list[SignalAlert]) -> None:
    """Renders the signal ribbon.

    Chips were `white-space: nowrap` with `flex-shrink: 0` inside an
    `overflow-x: auto` row, so a long list of symbols was cut off mid-word with
    nothing on screen indicating more text existed. Chips now wrap on wide
    viewports; on narrow ones the row still scrolls but the stylesheet adds an
    edge fade so the truncation is visible rather than silent.

    Emoji are replaced with typographic marks so the ribbon matches the
    direction glyphs already used in the screener table.
    """
    if not signals:
        return

    tone_by_color = {
        "#059669": ("up", "\u25b2"),
        "#e11d48": ("down", "\u25bc"),
        "#d97706": ("warn", "\u25cf"),
        "#4f46e5": ("info", "\u25b2"),
    }

    chips_html = ""
    for s in signals:
        tone, mark = tone_by_color.get(str(s.color).lower(), ("info", "\u25cf"))
        esc_text = html.escape(str(s.text))
        chips_html += (
            f'<span class="u-signal {tone}">'
            f'<span class="mark" aria-hidden="true">{mark}</span>'
            f"<span>{esc_text}</span></span>"
        )

    st.markdown(
        f'<div class="u-signals" role="status" aria-live="polite" '
        f'aria-label="Market signals">{chips_html}</div>',
        unsafe_allow_html=True,
    )


def stat_pill(label: str, value: Any, color: str = "indigo") -> str:
    """Helper to generate styled badge HTML."""
    color_map = {
        "indigo": ("#eef2ff", "#4f46e5", "#c7d2fe"),
        "emerald": ("#ecfdf5", "#059669", "#a7f3d0"),
        "rose": ("#fff1f2", "#e11d48", "#fecdd3"),
        "amber": ("#fef3c7", "#d97706", "#fde68a"),
        "sky": ("#f0f9ff", "#0284c7", "#bae6fd"),
    }
    bg, fg, bdr = color_map.get(color, color_map["indigo"])
    return (
        f'<span style="display: inline-flex; align-items: center; gap: 6px; border-radius: 6px; '
        f"padding: 3px 10px; font-family: 'IBM Plex Mono', monospace; font-size: 0.76rem; "
        f'background-color: {bg}; color: {fg}; border: 1px solid {bdr}; font-weight: 500; margin: 2px 4px 2px 0;">'
        f'{label}: <strong style="font-weight: 700;">{value}</strong></span>'
    )


def render_data_quality_footer(
    total_stocks: int, gap_count: int, short_count: int
) -> None:
    """Renders the data-quality footer.

    Emoji removed: a coloured status word carries the same meaning without
    depending on the platform's emoji font, and keeps the row on the same
    typographic system as the rest of the terminal.
    """
    gap_cls = "u-warn" if gap_count else ""
    footer_html = f"""
    <div class="u-footer">
      <span>Tracked <strong>{total_stocks:,}</strong></span>
      <span class="u-sep"></span>
      <span>Gap-filled &gt;10% <strong class="{gap_cls}">{gap_count:,}</strong></span>
      <span class="u-sep"></span>
      <span>Short history &lt;126D <strong>{short_count:,}</strong></span>
      <span class="u-sep"></span>
      <span>Stop loss <strong>CMP &minus; 2&times;ATR</strong></span>
      <span class="u-right">Paresh Patel</span>
    </div>
    """
    st.html(footer_html)
