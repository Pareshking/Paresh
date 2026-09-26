"""
Sectors: industries ranked by how their stocks are doing, one row each.

Every figure is read straight off the ranking table, so the page needs no
momentum engine: a median of each group's returns, and shares of its stocks
that pass the Screener's own filters.
"""

import html
from urllib.parse import quote

import numpy as np
import pandas as pd
import streamlit as st

from src.ui import page_kit as kit
from src.ui.charts import render_sector_treemap
from src.ui.components import gap_count, render_data_quality_footer, to_bool_mask
from src.ui.screener_table import render_screener_table

RANK_BY = {
    "3M median": "3M Return",
    "6M median": "6M Return",
    "Share passing": "Pass %",
    "Top-50 count": "Top 50",
}
# A group of one is a stock, not an industry trend.
MIN_STOCKS = 2


def _leader_link(sym: str) -> str:
    if not sym or sym == "—":
        return "—"
    return (f'<a class="ib-lead" href="?stock={quote(sym, safe="")}" target="_self">'
            f'{html.escape(sym)}</a>')


def _pct(v) -> str:
    if v is None or pd.isna(v):
        return "—"
    return f"{'+' if v > 0 else '−' if v < 0 else ''}{abs(v) * 100:.1f}%"


def _tone(v) -> str:
    if v is None or pd.isna(v):
        return ""
    return "up" if v > 0 else "down" if v < 0 else ""


def industry_board(rank_df: pd.DataFrame, col: str = "Industry") -> tuple[pd.DataFrame, list[str]]:
    """One row per industry, and the names left out for having one stock.

    3M / 6M are medians, so one runaway stock cannot carry its group. "Above
    50 EMA" and "Near 52W high" are the Screener's own flags, the same ones
    its filters use.
    """
    if col not in rank_df.columns or rank_df.empty:
        return pd.DataFrame(), []
    df = rank_df.assign(
        _grp=rank_df[col].replace("", np.nan),
        _ema=to_bool_mask(rank_df.get("Above 50 EMA", pd.Series(False, index=rank_df.index))).to_numpy(),
        _near=to_bool_mask(rank_df.get("Near 52W High", pd.Series(False, index=rank_df.index))).to_numpy(),
        _rank=pd.to_numeric(rank_df.get("Rank"), errors="coerce"),
    ).dropna(subset=["_grp"])
    rows, singles = [], []
    for name, g in df.groupby("_grp"):
        if len(g) < MIN_STOCKS:
            singles.append(str(name))
            continue
        lead = g.sort_values("_rank")["Symbol"].tolist()
        rows.append({
            "Industry": str(name),
            "Stocks": len(g),
            "3M Return": pd.to_numeric(g.get("3M Return"), errors="coerce").median(),
            "6M Return": pd.to_numeric(g.get("6M Return"), errors="coerce").median(),
            "EMA %": float(g["_ema"].mean()),
            "Near %": float(g["_near"].mean()),
            "Pass": int((g["_ema"] & g["_near"]).sum()),
            "Pass %": float((g["_ema"] & g["_near"]).mean()),
            "Top 50": int((g["_rank"] <= 50).sum()),
            "Best": g["_rank"].min(),
            "Leaders": lead[:3],
        })
    return pd.DataFrame(rows), sorted(singles)


def board_html(board: pd.DataFrame) -> str:
    """The leaderboard as a table; on a phone each row folds to name, one
    line of detail and the 3M figure."""
    lim = max(0.05, float(board["3M Return"].abs().max() or 0))
    rows = []
    for i, (_, r) in enumerate(board.iterrows(), start=1):
        v = r["3M Return"]
        w = 0 if pd.isna(v) else min(50.0, abs(v) / lim * 50)
        side = "left:50%" if (v or 0) >= 0 else "right:50%"
        leads = "".join(_leader_link(s) for s in r["Leaders"][:2])
        rows.append(
            f'<div class="ib-row" role="row">'
            f'<span class="ib-n">{i}</span>'
            f'<span class="ib-name"><b>{html.escape(r["Industry"])}</b>'
            f'<small>{r["Stocks"]} stocks · {r["EMA %"] * 100:.0f}% above 50-day EMA · {r["Top 50"]} in top 50</small></span>'
            f'<span class="ib-num ib-d">{r["Stocks"]}</span>'
            f'<span class="ib-3m"><b class="{_tone(v)}">{_pct(v)}</b>'
            f'<span class="ib-bar"><i class="{_tone(v)}" style="{side};width:{w:.1f}%"></i><em></em></span></span>'
            f'<span class="ib-num ib-d {_tone(r["6M Return"])}">{_pct(r["6M Return"])}</span>'
            f'<span class="ib-num ib-d">{r["EMA %"] * 100:.0f}%</span>'
            f'<span class="ib-num ib-d">{r["Near %"] * 100:.0f}%</span>'
            f'<span class="ib-num ib-d">{r["Pass"]}</span>'
            f'<span class="ib-num ib-d">{r["Top 50"]}</span>'
            f'<span class="ib-leads ib-d">{leads}</span></div>'
        )
    head = ('<div class="ib-row ib-head" role="row"><span>#</span><span>Industry</span>'
            '<span class="ib-num ib-d">Stocks</span><span class="ib-3m">3M (median)</span>'
            '<span class="ib-num ib-d">6M</span><span class="ib-num ib-d" title="Share above their 50-day EMA">Above EMA</span>'
            '<span class="ib-num ib-d" title="Share within 20% of their 52-week high">Near high</span><span class="ib-num ib-d">Pass both</span>'
            '<span class="ib-num ib-d">Top 50</span><span class="ib-d">Leaders</span></div>')
    return f'<div class="ib" role="table" aria-label="Industry leaderboard">{head}{"".join(rows)}</div>'


def render_sector_view(rank_df: pd.DataFrame, adj_close: pd.DataFrame) -> None:
    """Industries ranked, with the treemap as a second view."""
    has_tv = [c for c in ("TV_Industry", "TV_Sector") if c in rank_df.columns]
    tax = {"NSE industry": "Industry"}
    if "TV_Industry" in has_tv:
        tax["TradingView industry"] = "TV_Industry"
    if "TV_Sector" in has_tv:
        tax["TradingView sector"] = "TV_Sector"

    by = st.session_state.get("sector_rank_by") or "3M median"
    col = tax.get(st.session_state.get("sector_tax_choice") or "NSE industry", "Industry")
    board, singles = industry_board(rank_df, col)
    if not board.empty:
        board = board.sort_values([RANK_BY[by], "3M Return"], ascending=False,
                                  na_position="last").reset_index(drop=True)

    actions = kit.page_head(
        "Sectors",
        f"{len(board)} {'industries' if col == 'Industry' else 'groups'} ranked by "
        f"{by.replace('median', 'median return').replace('3M', '3-month').replace('6M', '6-month').lower()}"
        " · pick one below to see its stocks",
        actions=True,
    )
    with actions:
        st.selectbox("Rank by", list(RANK_BY), key="sector_rank_by",
                     format_func=lambda k: f"Rank by: {k}", label_visibility="collapsed", width=190)
        if len(tax) > 1:
            st.selectbox("Classification", list(tax), key="sector_tax_choice",
                         label_visibility="collapsed", width=190)

    if board.empty:
        st.info("No industry has two or more ranked stocks to compare.")
        return

    lead = board.sort_values("3M Return", ascending=False).iloc[0]
    weak = board.sort_values("3M Return").iloc[0]
    most = board.sort_values(["Top 50", "3M Return"], ascending=False).iloc[0]
    rising = int((board["3M Return"] > 0).sum())
    best_sym = (rank_df[rank_df[col] == most.Industry].sort_values("Rank")["Symbol"].head(1).tolist() or ["—"])[0]
    kit.readings([
        kit.Reading("Leading", lead.Industry,
                    f"median {_pct(lead['3M Return'])} in 3 months · {lead['Top 50']} of the top 50",
                    _tone(lead["3M Return"])),
        kit.Reading("Rising", f"{rising} of {len(board)}", "median 3-month return above zero"),
        kit.Reading("Most in the top 50", most.Industry,
                    f"{most['Top 50']} stocks · best rank #{int(most.Best)} {best_sym}"),
        kit.Reading("Weakest", weak.Industry,
                    f"median {_pct(weak['3M Return'])} · {weak.Pass} of {weak.Stocks} pass both filters",
                    _tone(weak["3M Return"])),
    ], "Industries today")

    view = st.segmented_control("View", ["Table", "Treemap"], default="Table",
                                key="sector_layout_choice", label_visibility="collapsed") or "Table"
    if view == "Treemap":
        with kit.card("Industry treemap", "sec_tree", "size = market cap · colour = 3-month return"):
            render_sector_treemap(rank_df, taxonomy_col=col,
                                  return_col="6M Return" if by == "6M median" else "3M Return",
                                  size_by="Market Cap")
    else:
        with kit.card("Industry leaderboard", "sec_board", "leaders link to their stock pages"):
            st.html(board_html(board))
            if singles:
                kit.caption(f"Left out: {', '.join(singles)} (one stock each). One stock is not an industry trend.")

    with kit.card("Stocks in an industry", "sec_stocks"):
        pick = st.selectbox("Industry", board["Industry"].tolist(), key="sector_pick",
                            label_visibility="collapsed")
        members = rank_df[rank_df[col] == pick].sort_values("Rank")
        render_screener_table(members, adj_close, "Core")

    render_data_quality_footer(
        total_stocks=len(rank_df),
        gap_count=gap_count(rank_df),
        short_count=int((rank_df.get("Short History", pd.Series()) == "Yes").sum()),
    )
