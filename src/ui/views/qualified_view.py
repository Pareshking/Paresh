"""
Qualified: the best-ranked stocks that pass both filters -- above their
50-day EMA and within 20% of their 52-week high.
"""


import numpy as np
import pandas as pd
import streamlit as st

from src.core.market_time import ist_now
from src.ui import page_kit as kit
from src.ui.components import gap_count, render_data_quality_footer, to_bool_mask
from src.ui.screener_table import render_screener_table
from src.ui.views.stock_view import _benchmark_returns, _price_day

# Industries shown by name before the rest fold into "others".
TOP_INDUSTRIES = 6


def _pct(v: float | None) -> str:
    if v is None or pd.isna(v):
        return "—"
    return f"{'+' if v > 0 else '−' if v < 0 else ''}{abs(v) * 100:.1f}%"


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


def correlation_note(mean: float | None) -> str:
    """What the average correlation means. None is its own state: an unknown
    is never labelled as good or bad, and 0.0 is a number, not a missing one."""
    if mean is None or pd.isna(mean):
        return "needs two stocks with price history"
    if mean < 0.3:
        return "90 days · low, so the list is well spread"
    if mean < 0.7:
        return "90 days · moderate: some move together"
    return "90 days · high: they tend to move as one"


def industry_rows(df: pd.DataFrame) -> list[tuple[str, float, str, bool]]:
    """Top industries by count, the rest folded into one row."""
    counts = df["Industry"].fillna("Unclassified").value_counts()
    n = len(df)
    rows = [(str(k), float(v), f"{v} · {v / n * 100:.0f}%", False)
            for k, v in counts.iloc[:TOP_INDUSTRIES].items()]
    rest = counts.iloc[TOP_INDUSTRIES:]
    if len(rest):
        v = int(rest.sum())
        rows.append((f"{len(rest)} others", float(v), f"{v} · {v / n * 100:.0f}%", False))
    return rows


def render_qualified_view(rank_df: pd.DataFrame, adj_close: pd.DataFrame, *,
                          embedded: bool = False) -> None:
    """The qualified list: readings, the table, where they come from.

    `embedded` draws it as the Actions page's "Buy candidates" section: no page
    header or footer, the picker and export in a bar of their own.
    """
    ab_ema = (to_bool_mask(rank_df["Above 50 EMA"]) if "Above 50 EMA" in rank_df.columns
              else pd.Series(True, index=rank_df.index, dtype=bool))
    nr_hi = (to_bool_mask(rank_df["Near 52W High"]) if "Near 52W High" in rank_df.columns
             else pd.Series(True, index=rank_df.index, dtype=bool))
    passing = rank_df[ab_ema & nr_hi].sort_values("Rank")

    top_n = int(st.session_state.get("qual_top_n", 30) or 30)
    if embedded:
        actions = st.container(horizontal=True, vertical_alignment="center", key="qual_pool_bar")
        with actions:
            kit.caption(f"The {top_n} best-ranked of the {len(passing)} stocks that pass both "
                        "filters today: above their 50-day EMA and within 20% of their 52-week high.")
    else:
        actions = kit.page_head(
            "Qualified",
            f"The {top_n} best-ranked stocks that pass both filters: above their 50-day "
            "EMA and within 20% of their 52-week high",
            actions=True,
        )
    view = passing.head(top_n).copy()
    with actions:
        st.segmented_control("Show", [10, 15, 20, 25, 30], default=30, required=True,
                             key="qual_top_n", format_func=lambda n: f"Top {n}",
                             label_visibility="collapsed")
        st.download_button("Export CSV", view.to_csv(index=False).encode(),
                           f"qualified_{ist_now():%Y%m%d}.csv", "text/csv",
                           key="dl_qual_csv", icon=":material/download:",
                           disabled=view.empty)

    if view.empty:
        st.info("No stock passes both filters today: above its 50-day EMA and within "
                "20% of its 52-week high.")
        return

    bench = _benchmark_returns(_price_day())
    _corr, corr_mean = correlation(adj_close, view["Symbol"].tolist())
    avg3 = pd.to_numeric(view.get("3M Return"), errors="coerce").mean()
    avg6 = pd.to_numeric(view.get("6M Return"), errors="coerce").mean()
    kit.readings([
        kit.Reading("Qualified", f"{len(view)}", f"of {len(passing)} that pass both filters"),
        kit.Reading("Average 3M return", _pct(avg3),
                    f"Nifty 500 {_pct(bench[3])} over the same 3 months" if 3 in bench else "calendar 3 months",
                    _tone(avg3)),
        kit.Reading("Average 6M return", _pct(avg6),
                    f"Nifty 500 {_pct(bench[6])}" if 6 in bench else "calendar 6 months",
                    _tone(avg6)),
        kit.Reading("Average correlation", "—" if corr_mean is None else f"{corr_mean:.2f}", correlation_note(corr_mean)),
    ], "Qualified list today")

    with kit.card("The list", "qual_list", "Same table as the Screener · click a row to open the stock"):
        render_screener_table(view, adj_close, "Core")

    with kit.card("Where they come from", "qual_ind", "by industry"):
        rows = industry_rows(view)
        st.html(kit.bar_list(rows, scale=max(r[1] for r in rows)))
        top2 = sum(r[1] for r in rows[:2]) / len(view)
        if top2 >= 0.4:
            kit.caption(f"{rows[0][0]} and {rows[1][0]} hold {top2:.0%} of the list; "
                        "worth knowing before sizing a portfolio.")

    if embedded:
        return
    render_data_quality_footer(
        total_stocks=len(rank_df),
        gap_count=gap_count(rank_df),
        short_count=int((rank_df.get("Short History", pd.Series()) == "Yes").sum()),
    )
