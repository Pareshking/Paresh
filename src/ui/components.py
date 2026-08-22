"""
Reusable UI Components and Widgets for NSE Momentum Dashboard.
Inspired by Investrack, Stockin.id, and Tickerboom financial terminal designs.
"""

import html
from datetime import datetime
from typing import Any

import pandas as pd
import streamlit as st

from src.core.types import MarketRegime, RegimeData, SignalAlert
from src.ui.theme import clean_html, is_tick_true



def to_bool_mask(values: "pd.Series | None") -> pd.Series:
    """Coerce a qualification column to a real boolean mask.

    "Above 50 EMA" and "Near 52W High" carry tick marks rather than booleans.
    Under pandas 3 they land in the string dtype, where summing CONCATENATES
    instead of counting, and an empty column sums to '' -- so
    ``int(col.sum())`` raised ``ValueError: invalid literal for int() with
    base 10: ''`` and took the Screener down in production. Using the column
    directly with ``&`` is unsafe for the same reason.

    Every other consumer already coerced these with .map(); this centralises
    that rule so the two representations cannot drift apart again.
    """
    if values is None:
        return pd.Series(dtype=bool)
    return pd.Series(
        [is_tick_true(v) for v in values],
        index=values.index,
        dtype=bool,
    )


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
        to_bool_mask(rank_df["Above 50 EMA"])
        if "Above 50 EMA" in rank_df.columns
        else pd.Series(True, index=rank_df.index)
    )
    nr_hi = (
        to_bool_mask(rank_df["Near 52W High"])
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
    """Renders ultra-minimalist, high-density executive status navbar."""
    regime_color = "#059669" if regime.status == MarketRegime.BULLISH else "#e11d48"
    dma_color = "#059669" if regime.distance_pct >= 0 else "#e11d48"
    today_str = datetime.now().strftime("%d %b %Y")

    header_html = f"""
    <div role="status" aria-label="Market status dashboard" style="display: flex; align-items: center; justify-content: space-between; padding: 7px 14px; background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 9px; box-shadow: 0 1px 2px rgba(0, 0, 0, 0.02); margin-bottom: 6px; flex-wrap: wrap; gap: 8px;">
        <div style="display: flex; align-items: center; gap: 10px;">
            <div class="mac-dots-container" style="margin-bottom: 0;">
                <span class="mac-dot mac-dot-red"></span>
                <span class="mac-dot mac-dot-yellow"></span>
                <span class="mac-dot mac-dot-green"></span>
            </div>
            <div style="width: 1px; height: 14px; background-color: #e2e8f0;"></div>
            <div style="font-family: 'Outfit', sans-serif; font-weight: 800; font-size: 1.05rem; color: #0f172a; letter-spacing: -0.02em;">
                Paresh Patel
            </div>
        </div>
        <div style="display: flex; align-items: center; gap: 10px; font-family: 'JetBrains Mono', monospace; font-size: 0.74rem; flex-wrap: wrap;">
            <span style="color: {regime_color}; font-weight: 700;">● {regime.status.value}</span>
            <span style="color: #cbd5e1;">|</span>
            <span style="color: #475569;">NIFTY <strong style="color: #0f172a;">₹{regime.current_price:,.0f}</strong> (<strong style="color: {dma_color};">{regime.distance_pct:+.1f}%</strong> 200D)</span>
            <span style="color: #cbd5e1;">|</span>
            <span style="color: #475569;">Universe: <strong style="color: #0f172a;">{total_stocks}</strong></span>
            <span style="color: #cbd5e1;">|</span>
            <span style="color: #475569;">&gt;50 EMA: <strong style="color: #059669;">{above_ema} ({pct_above_ema:.0f}%)</strong></span>
            <span style="color: #cbd5e1;">|</span>
            <span style="color: #64748b;">📅 {today_str}</span>
        </div>
    </div>
    """
    st.html(header_html)




def render_signal_alerts(signals: list[SignalAlert]) -> None:
    """Renders sleek 1-line horizontal alert chips."""
    if not signals:
        return

    chips_html = ""
    for s in signals:
        esc_text = html.escape(str(s.text))
        chips_html += (
            f'<div style="display: inline-flex; align-items: center; gap: 6px; padding: 3px 9px; border-radius: 6px; '
            f"background-color: {s.color}0D; border: 1px solid {s.color}25; font-family: 'JetBrains Mono', monospace; "
            f'font-size: 0.72rem; color: {s.color}; font-weight: 600; white-space: nowrap; flex-shrink: 0;">'
            f"<span>{s.icon}</span><span>{esc_text}</span></div>"
        )
    ribbon_html = f"""
    <div role="alert" aria-live="polite" aria-label="Market signals" style="display: flex; align-items: center; gap: 8px; overflow-x: auto; padding: 4px 8px; background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; margin-bottom: 8px; scrollbar-width: thin; scrollbar-color: #cbd5e1 transparent;">
        {chips_html}
    </div>
    """
    st.markdown(ribbon_html, unsafe_allow_html=True)


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



# Sources whose age is worth stating, and how many trading days each may fall
# behind before it is called stale. Market caps publish only after
# the close, so being one trading day behind is their normal state, not a fault.
# (date fact, label, tolerance in trading days, "source is loaded" fact)
#
# The fourth entry matters. A source whose date is unknown used to be dropped
# from the ribbon entirely, so "Market caps" simply vanished when the committed
# snapshot predated AsOf stamping -- the reader saw a clean bar and had no way
# to tell a source was being used undated. If the loader says it loaded
# something, it gets a chip, dated or not.
_FRESHNESS_SOURCES: list[tuple[str, str, int, str | None]] = [
    ("price_as_of", "Prices", 1, "price_path"),
    ("mcap_as_of", "Market caps", 1, "mcap_path"),
    ("ath_as_of", "All-time highs", 3, "ath_path"),
]


def data_freshness() -> list[dict]:
    """Age of each data source, judged in trading days.

    Read from the startup telemetry the loaders already record, so the twelve
    views that render the footer need no extra arguments and cannot disagree
    with each other about how old the data is.

    Trading days, not calendar days: a Monday showing Friday's market caps is
    current, and a festival cluster must not read as an outage.
    """
    from datetime import date as _date

    from src.core import startup_metrics as _metrics
    from src.core.market_time import trading_days_behind

    facts = _metrics.snapshot().get("facts", {})
    items: list[dict] = []
    for key, label, tolerance, presence_key in _FRESHNESS_SOURCES:
        raw = facts.get(key)
        if not raw:
            # No date. If the loader reported using this source anyway, say so
            # rather than omitting the row -- an undated snapshot could be any
            # age, which is the definition of stale.
            presence = str(facts.get(presence_key) or "").strip() if presence_key else ""
            if key == "ath_as_of" and presence in {"absent", "unreadable", "malformed"}:
                # The snapshot is missing, so the engine fell back to the high
                # water mark of the two-year window. That is NOT an all-time
                # high, and the column should not be read as one.
                items.append({
                    "label": label,
                    "as_of": "2y window, not all-time",
                    "behind": None,
                    "stale": True,
                    "source": presence,
                })
            elif presence and presence not in {"absent", "unreadable", "malformed"}:
                items.append({
                    "label": label,
                    "as_of": "date unknown",
                    "behind": None,
                    "stale": True,
                    "source": presence,
                })
            continue
        try:
            as_of = _date.fromisoformat(str(raw)[:10])
        except ValueError:
            continue
        behind = trading_days_behind(as_of)
        # None means older than the horizon entirely, which is stale by any
        # reading. Anything within tolerance is simply the publication lag.
        stale = behind is None or behind > tolerance
        items.append({
            "label": label,
            "as_of": as_of.strftime("%d %b"),
            "behind": behind,
            "stale": stale,
            "source": facts.get(presence_key) if presence_key else None,
        })
    return items


def render_freshness_ribbon() -> None:
    """A bottom ribbon mirroring the signal ribbon at the top of the page.

    Same chip language as render_signal_alerts, deliberately: the top strip
    tells you what the market did, this one tells you how current the numbers
    behind it are, and a reader should not have to learn two visual idioms to
    read the same page.

    Every source is shown with its as-of date, not just the stale ones. A
    warning that appears only on failure means the normal state tells the
    reader nothing; a date that is always present makes staleness self-evident
    and earns trust the rest of the time. Stale sources turn amber and lead.
    """
    items = data_freshness()
    if not items:
        return

    # Stale first: the thing a reader needs to notice should not be third.
    items = sorted(items, key=lambda i: (not i["stale"],))

    chips_html = ""
    for item in items:
        color = "#d97706" if item["stale"] else "#059669"
        icon = "&#9888;&#65039;" if item["stale"] else "&#9679;"
        if item["behind"] is None:
            age = " · stale"
        elif item["behind"] <= 0:
            age = " · today"
        elif item["behind"] == 1:
            age = " · 1 trading day behind"
        else:
            age = f" · {item['behind']} trading days behind"
        label = html.escape(str(item["label"]))
        as_of = html.escape(str(item["as_of"]))
        chips_html += (
            f'<div style="display: inline-flex; align-items: center; gap: 6px; padding: 3px 9px; '
            f'border-radius: 6px; background-color: {color}0D; border: 1px solid {color}25; '
            f"font-family: 'JetBrains Mono', monospace; font-size: 0.72rem; color: {color}; "
            f'font-weight: 600; white-space: nowrap; flex-shrink: 0;">'
            f"<span>{icon}</span><span>{label}: {as_of}{age}</span></div>"
        )

    st.markdown(
        '<div role="status" aria-label="Data freshness" style="display: flex; align-items: center; '
        "gap: 8px; overflow-x: auto; padding: 4px 8px; background-color: #f8fafc; "
        "border: 1px solid #e2e8f0; border-radius: 8px; margin-top: 16px; margin-bottom: 4px; "
        'scrollbar-width: thin; scrollbar-color: #cbd5e1 transparent;">'
        f"{chips_html}</div>",
        unsafe_allow_html=True,
    )


def render_data_quality_footer(
    total_stocks: int, gap_count: int, short_count: int
) -> None:
    """Renders the data quality footer bar, including how old each source is.

    The signature is unchanged on purpose: twelve views call this, and the
    freshness figures come from the loaders' own telemetry rather than from
    twelve call sites that could drift apart.

    The as-of date is shown ALWAYS, not only when something is wrong. A
    warning that appears only on failure means the normal state tells the
    reader nothing; a date that is always present makes staleness
    self-evident and earns trust the rest of the time.

    Styling is inline to match the rest of this bar. The design-system
    stylesheet was reverted, so class-based styling would render unstyled.
    """
    # Drawn here rather than at twelve call sites, for the same reason the
    # freshness figures are read from telemetry: one place to change, and no
    # way for two tabs to disagree.
    #
    # The ribbon owns the as-of dates. This bar used to restate all of them one
    # line below it, plus a "some data is behind" flag duplicating the amber
    # chips -- the same three dates printed twice, a few pixels apart, in two
    # different visual idioms. The ribbon is the better of the two (it carries
    # the age, colours staleness, and leads with the stale source), so the bar
    # keeps only what is unique to it: coverage, data-quality counts, and the
    # stop-loss convention.
    render_freshness_ribbon()

    footer_html = f"""
    <div style="display: flex; align-items: center; gap: 16px; flex-wrap: wrap; padding: 10px 16px; background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; margin-top: 24px; font-family: 'JetBrains Mono', monospace; font-size: 0.75rem; color: #64748b;">
        <span>🟢 <strong style="color: #0f172a;">{total_stocks}</strong> stocks tracked</span>
        <span style="color: #cbd5e1;">|</span>
        <span>🔴 Gap-filled &gt;10%: <strong style="color: #d97706;">{gap_count}</strong></span>
        <span style="color: #cbd5e1;">|</span>
        <span>⏳ Short history (&lt;126D): <strong style="color: #0f172a;">{short_count}</strong></span>
        <span style="color: #cbd5e1;">|</span>
        <span>Stop Loss: <strong style="color: #0f172a;">CMP − 2×ATR</strong></span>
        <span style="margin-left: auto; color: #475569; font-weight: 700;">Paresh Patel</span>
    </div>
    """
    st.html(footer_html)
