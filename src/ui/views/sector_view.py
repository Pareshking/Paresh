"""
Industry & Sector Momentum Analytics View Controller.
"""

import html
from urllib.parse import quote

import numpy as np
import pandas as pd
import streamlit as st

from src.engine.momentum import MomentumEngine
from src.ui.charts import render_sector_treemap
from src.ui.components import gap_count, render_data_quality_footer, to_bool_mask
from src.ui.theme import render_saas_table


def _leader_link(sym: str) -> str:
    if not sym or sym == "—":
        return "—"
    return (
        f'<a href="?stock={quote(sym, safe="")}" target="_self" '
        f'style="color:#4f46e5;font-weight:700;text-decoration:none;'
        f'border-bottom:1px dotted #c7d2fe;">{html.escape(sym)}</a>'
    )


def render_sector_card(r: pd.Series) -> None:
    """Renders a modern sector card with top holdings and breadth metrics."""
    ind_name = r.get("Industry", "Sector")
    n_stocks = int(r.get("Stocks", 0))
    ret_3m = r.get("3M Return", 0.0)
    ret_6m = r.get("6M Return", 0.0)
    p_52w = r.get("% 52W High", 0.0)
    p_ema = r.get("% 20 EMA", 0.0)
    mcap = r.get("Total MCap (Cr)", 0.0)

    ret_clr_3m = "#15803d" if ret_3m >= 0 else "#b91c1c"
    ret_clr_6m = "#15803d" if ret_6m >= 0 else "#b91c1c"

    # Returns are stored as fractions (0.105 = 10.5%); multiply before display.
    ret_3m_pct = ret_3m * 100
    ret_6m_pct = ret_6m * 100

    leaders_html = " &nbsp;·&nbsp; ".join(
        _leader_link(r.get(f"Top {i}", "—")) for i in range(1, 6)
        if r.get(f"Top {i}", "—") != "—"
    )

    card_html = f"""
    <div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:10px; padding:14px; margin-bottom:12px; box-shadow:0 1px 2px rgba(0,0,0,0.02);">
        <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:8px;">
            <div>
                <div style="font-family:'Outfit',sans-serif; font-weight:800; font-size:0.92rem; color:#0f172a; line-height:1.2;">
                    {html.escape(str(ind_name))}
                </div>
                <div style="font-size:0.72rem; color:#64748b; margin-top:2px;">
                    {n_stocks} stocks · ₹{mcap:,.0f} Cr MCap
                </div>
            </div>
            <span style="font-family:'JetBrains Mono',monospace; font-size:0.72rem; font-weight:700; color:#4f46e5; background:#eef2ff; border:1px solid #c7d2fe; padding:2px 6px; border-radius:4px;">
                Rank #{int(r.get('Rank', 0))}
            </span>
        </div>

        <div style="display:grid; grid-template-columns:1fr 1fr; gap:8px; background:#f8fafc; border-radius:6px; padding:8px; margin-bottom:10px;">
            <div>
                <div style="font-size:0.68rem; color:#64748b; font-weight:600; text-transform:uppercase;">3M Return</div>
                <div style="font-family:'JetBrains Mono',monospace; font-size:0.84rem; font-weight:700; color:{ret_clr_3m};">{ret_3m_pct:+.1f}%</div>
            </div>
            <div>
                <div style="font-size:0.68rem; color:#64748b; font-weight:600; text-transform:uppercase;">6M Return</div>
                <div style="font-family:'JetBrains Mono',monospace; font-size:0.84rem; font-weight:700; color:{ret_clr_6m};">{ret_6m_pct:+.1f}%</div>
            </div>
            <div>
                <div style="font-size:0.68rem; color:#64748b; font-weight:600; text-transform:uppercase;">Near 52W High</div>
                <div style="font-family:'JetBrains Mono',monospace; font-size:0.78rem; font-weight:600; color:#0f172a;">{p_52w:.0f}% stocks</div>
            </div>
            <div>
                <div style="font-size:0.68rem; color:#64748b; font-weight:600; text-transform:uppercase;">Above 20 EMA</div>
                <div style="font-family:'JetBrains Mono',monospace; font-size:0.78rem; font-weight:600; color:#0f172a;">{p_ema:.0f}% stocks</div>
            </div>
        </div>

        <div style="font-size:0.72rem; color:#475569; line-height:1.8;">
            <strong style="color:#0f172a;">Leaders:</strong> {leaders_html}
        </div>
    </div>
    """
    st.html(card_html)


def render_sector_view(
    calc: MomentumEngine,
    rank_df: pd.DataFrame,
    adj_close: pd.DataFrame,
) -> None:
    """Renders comprehensive Industry & Sector momentum analytics."""
    st.markdown(
        """
        <div style="font-family: 'Plus Jakarta Sans', sans-serif; font-size: 1.10rem; font-weight: 800; color: #0f172a; margin-bottom: 2px;">
            Sector & Industry Momentum Analytics
        </div>
        <div style="font-size: 0.76rem; color: #64748b; margin-bottom: 14px;">
            Evaluate macro industry breadth, market capitalization weighting, and stage-2 sector leadership.
        </div>
        """,
        unsafe_allow_html=True,
    )

    c_tax, c_metric, c_view = st.columns([1.6, 1.4, 1.0], vertical_alignment="center")

    has_tv_data = "TV_Sector" in rank_df.columns or "TV_Industry" in rank_df.columns
    if has_tv_data:
        tax_opts = ["NSE Industry"]
        if "TV_Industry" in rank_df.columns:
            tax_opts.append("TV Industry (119)")
        if "TV_Sector" in rank_df.columns:
            tax_opts.append("TV Sector (20)")
        ind_choice = c_tax.selectbox(
            "Taxonomy Classification",
            tax_opts,
            index=0,
            key="sector_tax_choice",
        )
        if not ind_choice:
            ind_choice = "NSE Industry"
        ind_col = {
            "NSE Industry": "Industry",
            "TV Industry (119)": "TV_Industry",
            "TV Sector (20)": "TV_Sector",
        }[ind_choice]
    else:
        c_tax.markdown(
            "<span style='font-family:IBM Plex Mono;font-size:0.8rem;color:#475569;'>Classification: <strong>NSE Industry</strong></span>",
            unsafe_allow_html=True,
        )
        ind_col = "Industry"

    sort_metric = c_metric.segmented_control(
        "Sort / Sizing Basis",
        ["Market Cap", "3M Return", "6M Return", "Momentum"],
        default="Market Cap",
        key="sector_metric_choice",
        label_visibility="collapsed",
    )
    if not sort_metric:
        sort_metric = "Market Cap"

    layout_choice = c_view.segmented_control(
        "Sector Layout",
        ["Cards", "Table", "Treemap"],
        default="Cards",
        key="sector_layout_choice",
        label_visibility="collapsed",
    )
    if not layout_choice:
        layout_choice = "Cards"

    # Prepare Industry Table Data
    work_df = rank_df.copy()
    if ind_col != "Industry":
        work_df["Industry"] = work_df[ind_col].replace("", np.nan)
        work_df = work_df.dropna(subset=["Industry"])

    ind_rank_df = calc.get_industry_rankings(work_df)

    # Share of each group near its 52-week high, above its 20 EMA, and total
    # market cap.
    #
    # "Near 52W High" is the SCREENER's own flag (within 20% of the canonical
    # 52-week high, momentum.py). This used to recompute its own version --
    # within 10%, over a raw rolling max -- under the same label, so the card
    # and the screener counted different stocks as "near". The 20 EMA has no
    # screener column, so it is computed here, once for the whole universe
    # rather than once per group (a rolling max and an EWM over the full
    # history, ~100 times per rerun).
    near_mask = (
        to_bool_mask(work_df["Near 52W High"])
        if "Near 52W High" in work_df.columns
        else pd.Series(False, index=work_df.index)
    )
    in_frame = [s for s in work_df["Symbol"].unique() if s in adj_close.columns]
    if in_frame:
        latest = adj_close[in_frame].iloc[-1]
        ema20_last = adj_close[in_frame].ewm(span=20, min_periods=10).mean().iloc[-1]
        above_ema20 = (latest > ema20_last)
    else:
        above_ema20 = pd.Series(dtype=bool)
    work_df = work_df.assign(
        _near=near_mask.to_numpy(),
        _above20=work_df["Symbol"].map(above_ema20).fillna(False).astype(bool).to_numpy(),
        _priced=work_df["Symbol"].isin(in_frame).to_numpy(),
    )
    ind_52w, ind_ema, ind_mcap = {}, {}, {}
    for ind_name, grp in work_df.groupby("Industry"):
        ind_mcap[ind_name] = (
            grp["Market Cap (Cr)"].sum() if "Market Cap (Cr)" in grp.columns else 0.0
        )
        n = int(grp["_priced"].sum())
        ind_52w[ind_name] = (grp.loc[grp["_priced"], "_near"].sum() / n * 100) if n else 0.0
        ind_ema[ind_name] = (grp.loc[grp["_priced"], "_above20"].sum() / n * 100) if n else 0.0

    if "Industry" in ind_rank_df.columns:
        ind_rank_df["Total MCap (Cr)"] = ind_rank_df["Industry"].map(ind_mcap).fillna(0)
        ind_rank_df["% 52W High"] = ind_rank_df["Industry"].map(ind_52w).fillna(0)
        ind_rank_df["% 20 EMA"] = ind_rank_df["Industry"].map(ind_ema).fillna(0)

        # Sort strictly according to selected metric
        if sort_metric == "Market Cap":
            ind_rank_df = ind_rank_df.sort_values(
                "Total MCap (Cr)", ascending=False
            ).reset_index(drop=True)
        elif sort_metric == "3M Return":
            ind_rank_df = ind_rank_df.sort_values(
                "3M Return", ascending=False
            ).reset_index(drop=True)
        elif sort_metric == "6M Return":
            ind_rank_df = ind_rank_df.sort_values(
                "6M Return", ascending=False
            ).reset_index(drop=True)
        else:
            ind_rank_df = ind_rank_df.sort_values("Rank", ascending=True).reset_index(
                drop=True
            )

        ind_rank_df["Rank"] = range(1, len(ind_rank_df) + 1)

    # ── Render Selected Layout ───────────────────────────────────────────────
    if layout_choice == "Treemap":
        ret_col = "6M Return" if sort_metric == "6M Return" else "3M Return"
        render_sector_treemap(
            rank_df, taxonomy_col=ind_col, return_col=ret_col, size_by=sort_metric
        )

    elif layout_choice == "Table":
        disp_ind_cols = [
            "Rank",
            "Industry",
            "Stocks",
            "Total MCap (Cr)",
            "3M Return",
            "6M Return",
            "% 52W High",
            "% 20 EMA",
            "Top 1",
            "Top 2",
            "Top 3",
        ]
        render_saas_table(
            ind_rank_df[[c for c in disp_ind_cols if c in ind_rank_df.columns]],
            max_height=520,
        )

    else:
        # Cards View
        n_cards = len(ind_rank_df)
        for r_start in range(0, n_cards, 3):
            cols = st.columns(3)
            for c_idx, i in enumerate(range(r_start, min(r_start + 3, n_cards))):
                with cols[c_idx]:
                    render_sector_card(ind_rank_df.iloc[i])

    render_data_quality_footer(
        total_stocks=len(rank_df),
        gap_count=gap_count(rank_df),
        short_count=int((rank_df.get("Short History", pd.Series()) == "Yes").sum()),
    )
