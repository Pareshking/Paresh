"""
Qualified: the best-ranked stocks that pass both filters -- above their
50D EMA and within 20% of their 52-week high. Drawn inside the Actions page
("Buy candidates").
"""


import numpy as np
import pandas as pd
import streamlit as st

from src.core.market_time import ist_now
from src.ui import formats as _fmt
from src.ui import page_kit as kit
from src.ui.components import to_bool_mask
from src.ui.export import csv_bytes
from src.ui.screener_table import render_screener_table

# Industries shown by name before the rest fold into "others".
TOP_INDUSTRIES = 6


def _pct(v: float | None) -> str:
    """The house rule, from one place (duplicate audit, 10 Nov 2026).

    This copy signed the unrounded value, so −0.04% printed "−0.0%" -- the
    exact thing src/ui/formats.py exists to prevent."""
    return _fmt.pct(v)


def _tone(v: float | None) -> str:
    if v is None or pd.isna(v):
        return ""
    return "up" if v > 0 else "down" if v < 0 else ""


def correlation(adj_close: pd.DataFrame, syms: list[str]) -> tuple[pd.DataFrame | None, float | None]:
    """Pairwise correlation of daily returns over 90 sessions, and its mean."""
    syms = [s for s in syms if s in adj_close.columns]
    if len(syms) < 2:
        return None, None
    corr = adj_close[syms].iloc[-90:].pct_change(fill_method=None).corr()
    return corr, float(np.nanmean(corr.values[np.triu_indices_from(corr, k=1)]))




LEDE = "Best-ranked stocks passing both filters."   # S203 ac.qual.1


def no_pass_lines(high_pct: float | None = None) -> tuple[str, str]:
    """The empty list's title and way out (S203 ac.qual.2): the filters named, the 52-week line read from the
    record's rules, not typed (rule 9)."""
    if high_pct is None:
        from src.engine.track_record import TRACK_RECORD_CONFIG
        high_pct = float(TRACK_RECORD_CONFIG["high_pct"])
    return ("No stock passes both filters today.",
            f"They are a close above the 50D EMA and within {1 - high_pct:.0%} of the 52-week high.")


def _sector_counts(df: pd.DataFrame) -> pd.Series:
    """Stocks per sector, most first (glossary 2: NSE's column name is kept as the key)."""
    return df["Industry"].fillna("Unclassified").value_counts()


def industry_rows(df: pd.DataFrame) -> list[tuple[str, float, str, bool]]:
    """Top industries by count, the rest folded into one row."""
    counts = _sector_counts(df)
    n = len(df)
    rows = [(str(k), float(v), f"{v} · {v / n * 100:.0f}%", False)
            for k, v in counts.iloc[:TOP_INDUSTRIES].items()]
    rest = counts.iloc[TOP_INDUSTRIES:]
    if len(rest):
        v = int(rest.sum())
        rows.append((f"{len(rest)} others", float(v), f"{v} · {v / n * 100:.0f}%", False))
    return rows


def render_qualified_view(rank_df: pd.DataFrame, adj_close: pd.DataFrame) -> None:
    """The qualified list and where it comes from, drawn as the Actions page's
    "Buy candidates" section: the picker and export in a bar of their own."""
    ab_ema = (to_bool_mask(rank_df["Above 50 EMA"]) if "Above 50 EMA" in rank_df.columns
              else pd.Series(True, index=rank_df.index, dtype=bool))
    nr_hi = (to_bool_mask(rank_df["Near 52W High"]) if "Near 52W High" in rank_df.columns
             else pd.Series(True, index=rank_df.index, dtype=bool))
    passing = rank_df[ab_ema & nr_hi].sort_values("Rank")

    top_n = int(st.session_state.get("qual_top_n", 30) or 30)
    actions = st.container(horizontal=True, vertical_alignment="center", key="qual_pool_bar")
    with actions:
        kit.caption(LEDE)
    view = passing.head(top_n).copy()
    # Place among the qualified, as on the Screener (audit, 8 Nov 2026: this table
    # showed "–" in Qualified # for every row).
    from src.engine.exit_watch import qualified_ranks
    view["Qualified Rank"] = view["Symbol"].map(qualified_ranks(rank_df))
    with actions:
        st.segmented_control("Show", [10, 15, 20, 25, 30], default=30, required=True,
                             key="qual_top_n", format_func=lambda n: f"Top {n}",
                             label_visibility="collapsed")
        st.download_button("Export CSV", csv_bytes(view),
                           f"qualified_{ist_now():%Y%m%d}.csv", "text/csv",
                           key="dl_qual_csv", icon=":material/download:",
                           disabled=view.empty)

    if view.empty:
        kit.empty(*no_pass_lines())
        return

    with kit.card("The list", "qual_list"):
        render_screener_table(view, adj_close, "Core")

    with kit.card("Where they come from", "qual_ind"):
        rows = industry_rows(view)
        st.html(kit.bar_list(rows, scale=max(r[1] for r in rows)))
        if line := concentration_line(view):
            kit.caption(line)


def concentration_line(df: pd.DataFrame) -> str:
    """The two sectors that hold the most of the list, when they hold 40% or more (S203 ac.qual.3): "Banks and
    Capital Goods hold 45% of the list." A tie for second names every sector tied: "A, B and C hold …"."""
    if not len(df):
        return ""
    counts = _sector_counts(df)
    if len(counts) < 2 or counts.iloc[:2].sum() / len(df) < 0.4:
        return ""
    named = [str(k) for k, v in counts.items() if v >= counts.iloc[1]]
    share = counts.iloc[:len(named)].sum() / len(df)
    who = ", ".join(named[:-1]) + " and " + named[-1]
    return f"{who} hold {_fmt.fixed(share * 100, 0)}% of the list."
