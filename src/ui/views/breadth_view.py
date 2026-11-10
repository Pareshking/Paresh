"""
Market Breadth View Controller.
"""

import pandas as pd
import streamlit as st

from src.engine.breadth import (
    OBSERVED_SUFFIX,
    compute_hl_timeseries,
    compute_ma_breadth,
    get_recent_hl_events,
)
from src.core.config import SHORT_FORMS
from src.engine.pipeline import price_fingerprint
from src.ui import lw_chart as lw
from src.ui import page_kit as kit
from src.ui.components import gap_count, render_data_quality_footer
from src.ui.theme import render_saas_table
from src.engine import size_leadership as sl
from src.loaders.index_levels import fetch_index_levels, nse_benchmarks
from src.ui.views.market_questions_view import render_breadth_questions, size_closes


def index_members(rank_df: pd.DataFrame, index_name: str) -> list[str]:
    """Symbols tagged with exactly this index (config.SHORT_FORMS tags)."""
    if "Indices" not in rank_df.columns:
        return []
    tag = SHORT_FORMS.get(index_name, index_name).upper()
    tags = rank_df["Indices"].fillna("").astype(str).map(
        lambda v: {t.strip().upper() for t in v.split(",") if t.strip()}
    )
    return rank_df.loc[tags.map(lambda ts: tag in ts), "Symbol"].tolist()


def _participation_chart(pct: pd.DataFrame, ma_type: str) -> None:
    """Share of stocks above each average, over time, with the 40% and 60% lines.
    Hover for the date and every average's value."""
    palette = [lw.INDIGO, lw.GREY, lw.INK, lw.AMBER, lw.GREEN]
    names = {c: str(c).replace("D", "-day ") + ma_type for c in pct.columns}
    order = sorted(pct.columns, key=lambda c: int(str(c).rstrip("D")))
    series = [
        {"name": names[c], "type": "line", "color": palette[i % len(palette)], "fmt": "share",
         "range": [0, 100], "data": lw.series_points(pct.index, pct[c])}
        for i, c in enumerate(order)
    ]
    lw.render([{"height": 300, "top": 0.04, "series": series, "levels": [
        {"value": 60, "color": lw.GREEN, "title": "60%"},
        {"value": 40, "color": lw.RED, "title": "40%"}]}], key="br_part_chart")


def _highs_lows_chart(hl_df: pd.DataFrame, is_pct: bool) -> None:
    """New highs up in green, new lows down in red, one bar pair per session.
    Hover for the date and both counts."""
    h_col, l_col = ("% New Highs", "% New Lows") if is_pct else ("New Highs", "New Lows")
    fmt = "share1" if is_pct else "int"
    highs = pd.to_numeric(hl_df[h_col], errors="coerce")
    lows = -pd.to_numeric(hl_df[l_col], errors="coerce")
    lw.render([{"height": 280, "series": [
        {"name": "New highs", "type": "histogram", "color": lw.GREEN, "fmt": fmt,
         "data": lw.series_points(hl_df.index, highs)},
        {"name": "New lows", "type": "histogram", "color": lw.RED, "fmt": fmt, "abs": True,
         "data": lw.series_points(hl_df.index, lows)},
    ]}], key="br_hl_chart")


def render_breadth_view(rank_df: pd.DataFrame, adj_close: pd.DataFrame,
                        history_prices: pd.DataFrame | None = None,
                        benchmark_close: pd.Series | None = None) -> None:
    """Two questions first (owner, 7 Nov: tipsheet's question pages as the
    model): are most stocks taking part, and is the market in an uptrend; each
    with its verdict, evidence, what changed and what would change it. Then
    today's charts and the stocks making new highs and lows."""
    kit.page_head("Market breadth",
                  "Two questions, answered from the ranked stocks and NSE's index closes; then today's charts.")
    levels, bench = fetch_index_levels(), nse_benchmarks()
    size_ok = False
    if levels is not None and bench is not None and "nifty50" in bench:
        size_ok, _ = sl.cross_check(levels, bench["nifty50"])
    nifty500 = (benchmark_close if benchmark_close is not None and len(benchmark_close)
                else (bench or {}).get("nifty500"))
    render_breadth_questions(rank_df, history_prices if history_prices is not None else adj_close,
                             nifty500, size_closes(levels, size_ok))

    with st.container(key="br_chart_head", horizontal=True, vertical_alignment="center", gap="small"):
        st.html('<h2 id="q-charts" class="br-charts-h">Today\'s charts</h2>', width="stretch")
        history_days = st.segmented_control(
            "Period", [63, 126, 252], default=126, required=True,
            format_func=lambda x: {63: "3M", 126: "6M", 252: "1Y"}[x],
            key="br_lb_days", label_visibility="collapsed",
        ) or 126
        with st.popover("Chart settings", icon=":material/tune:"):
            ma_type = st.segmented_control("Average", ["EMA", "SMA"], default="EMA",
                                           key="br_ma_type") or "EMA"
            sel_mas = st.multiselect("Periods", ["10D", "20D", "50D", "100D", "200D"],
                                     default=["50D", "200D"], key="br_sel_mas")
            bview = st.segmented_control("Participation by", ["Universe", "By Index"],
                                         default="Universe", key="br_bview") or "Universe"
            hl_window = st.segmented_control(
                "New high / low means", [52, 126, 252], default=252, required=True,
                format_func=lambda x: {52: "52-day", 126: "126-day", 252: "52-week"}[x],
                key="hl_win_sel",
            ) or 252
            hl_disp = st.segmented_control("Show highs and lows as", ["% of Universe", "Stock Count"],
                                           default="% of Universe", key="hl_fmt_radio") or "% of Universe"

    if not sel_mas:
        kit.empty("Pick at least one moving average", "under Chart settings.")
        return

    # Whole-history fingerprint, not last date + shape (an intraday refresh
    # or a restatement kept the old key and served stale breadth).
    ph = price_fingerprint(adj_close)
    breadth_df = compute_ma_breadth(
        ph, adj_close, tuple(sel_mas), lookback=history_days, ma_type=ma_type
    )
    hl_df = compute_hl_timeseries(ph, adj_close, window=hl_window, lookback=history_days)

    # The figure tiles that sat here repeated the evidence table above.

    if not breadth_df.empty:
        if bview == "Universe":
            with kit.card("Participation", "br_part", f"above each {ma_type}"):
                # Percentage series only; the companion count columns are
                # metadata for the readings, not lines on the chart.
                _pct_cols = [c for c in breadth_df.columns if not c.endswith(OBSERVED_SUFFIX)]
                _participation_chart(breadth_df[_pct_cols], ma_type)
        else:
            rows = []
            for idx_name in ("NIFTY 50", "NIFTY NEXT 50", "NIFTY MIDCAP 150",
                             "NIFTY SMALLCAP 250", "NIFTY MICROCAP 250"):
                # Exact tags, as indices_loader writes them (config.SHORT_FORMS).
                valid_syms = [s for s in index_members(rank_df, idx_name) if s in adj_close.columns]
                if not valid_syms:
                    continue
                ma_s = (
                    adj_close[valid_syms].ewm(span=50).mean()
                    if ma_type == "EMA"
                    else adj_close[valid_syms].rolling(50).mean()
                )
                # Over stocks that HAVE a price and an MA on the last row -- the
                # same denominator the universe breadth uses; a missing print
                # is not a stock below its average.
                _last, _ma = adj_close[valid_syms].iloc[-1], ma_s.iloc[-1]
                _obs = _last.notna() & _ma.notna()
                if not _obs.any():
                    continue
                pct = float((_last[_obs] > _ma[_obs]).sum() / _obs.sum() * 100)
                rows.append((idx_name.title(), pct,
                             f"{pct:.0f}% · {int(_obs.sum())}", pct <= 40))
            with kit.card("Participation by index", "br_idx", f"above 50-day {ma_type}"):
                if rows:
                    st.html(kit.bar_list(rows, scale=100))
                else:
                    kit.caption("No index tags on the ranked stocks.")

    if not hl_df.empty:
        with kit.card("New highs against new lows", "br_hl"):
            _highs_lows_chart(hl_df, is_pct=hl_disp == "% of Universe")

        hl_events_df = get_recent_hl_events(adj_close, rank_df, window=hl_window, lookback=20)
        with kit.card("Stocks making new highs and lows", "br_events", "last 20 sessions"):
            if hl_events_df.empty:
                kit.caption("No stock made a new high or low in the last 20 sessions.")
            else:
                ev_sel = st.segmented_control(
                    "Filter Events", ["All", "Highs", "Lows"], default="All",
                    key="hl_ev_filter", label_visibility="collapsed",
                ) or "All"
                disp = hl_events_df
                if ev_sel == "Highs":
                    disp = hl_events_df[hl_events_df["Event"].str.contains("high", case=False)]
                elif ev_sel == "Lows":
                    disp = hl_events_df[hl_events_df["Event"].str.contains("low", case=False)]
                render_saas_table(disp, max_height=420)

    render_data_quality_footer(
        total_stocks=len(rank_df),
        gap_count=gap_count(rank_df),
        short_count=int((rank_df.get("Short History", pd.Series()) == "Yes").sum()),
    )
