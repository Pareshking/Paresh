"""
The Market page (/market): are most stocks taking part, and is the market in an uptrend.

Called Breadth, at /breadth, until 21 Nov 2026; the breadth measures it draws keep
their names (src/engine/breadth.py).
"""

import pandas as pd
import streamlit as st

from src.ui import formats as _fmt

from src.engine.breadth import (
    OBSERVED_SUFFIX,
    compute_hl_timeseries,
    compute_ma_breadth,
    get_recent_hl_events,
)
from src.core.config import SHORT_FORMS
from src.engine.pipeline import price_fingerprint
from src.ui import page_kit as kit
from src.ui.page_kit import _series_of
from src.ui.components import gap_count
from src.ui.theme import render_saas_table
from src.loaders.index_levels import nse_benchmarks
from src.engine.extra_universe import NANOCAP_250_NAME, NANOCAP_250_SHORT
from src.ui.views.market_questions_view import render_market_page_questions, size_closes


def index_members(rank_df: pd.DataFrame, index_name: str) -> list[str]:
    """Symbols tagged with exactly this index (config.SHORT_FORMS tags)."""
    if "Indices" not in rank_df.columns:
        return []
    tag = SHORT_FORMS.get(index_name, index_name).upper()
    tags = rank_df["Indices"].fillna("").astype(str).map(
        lambda v: {t.strip().upper() for t in v.split(",") if t.strip()}
    )
    return rank_df.loc[tags.map(lambda ts: tag in ts), "Symbol"].tolist()


def _participation_chart(pct: pd.DataFrame, ma_type: str, pit: dict[str, pd.Series] | None = None) -> None:
    """Share of stocks above each average, over time, with the 40% and 60% lines (the site's chart kit).
    The 50D and 200D EMA lines count the members of each date, leavers included (point-in-time history),
    when that history covers the window; the other averages count today's ranked stocks, said in the label."""
    from src.ui import dash_charts as dc
    order = sorted(pct.columns, key=lambda c: int(str(c).rstrip("D")))
    colours = ["up", "ink", "caution", "teal", "violet"]
    series = []
    for i, c in enumerate(order):
        s, who = pct[c], "today’s stocks"
        if pit and ma_type == "EMA" and c in pit and pit[c].reindex(pct.index).notna().all():
            s, who = pit[c].reindex(pct.index), "members of each date"
        series.append({"name": f"{c} {ma_type}, {who}",
                       "values": [None if pd.isna(v) else round(float(v), 1) for v in s.to_numpy()], "color": colours[i % 5]})
    dc.render("lines", {"dates": [f"{d:%Y-%m-%d}" for d in pct.index], "yfmt": "pct", "range": [0, 100],
                        "levels": [{"v": 60, "label": "60% broad", "color": "up"}, {"v": 40, "label": "40% narrow", "color": "down"}],
                        "series": series}, label="Share of stocks above each average")


def _highs_lows_chart(hl_df: pd.DataFrame, is_pct: bool) -> None:
    """New highs up, new lows down from zero, one bar per session (the site's chart kit)."""
    from src.ui import dash_charts as dc
    h_col, l_col = ("% New Highs", "% New Lows") if is_pct else ("New Highs", "New Lows")
    highs = pd.to_numeric(hl_df[h_col], errors="coerce").fillna(0)
    lows = pd.to_numeric(hl_df[l_col], errors="coerce").fillna(0)
    dc.render("bars", {"values": [round(float(v), 1) for v in highs], "labels": [f"{d:%-d %b}" for d in hl_df.index],
                       "full": [f"{d:%-d %b %Y}" for d in hl_df.index], "unit": "new highs" + (" (% of stocks)" if is_pct else ""),
                       "dp": 1 if is_pct else 0, "xn": 6, "height": 260, "color2": "--down",
                       "also": [["new lows" + (" (% of stocks)" if is_pct else ""), -round(float(v), 1)] for v in lows]},
              label="New highs against new lows each session")


def render_market_view(rank_df: pd.DataFrame, adj_close: pd.DataFrame,
                        history_prices: pd.DataFrame | None = None,
                        benchmark_close: pd.Series | None = None, system: str | None = None) -> None:
    """Two questions first (owner, 7 Nov: tipsheet's question pages as the
    model): are most stocks taking part, and is the market in an uptrend; each
    with its verdict, evidence, what changed and what would change it. Then
    today's charts and the stocks making new highs and lows."""
    # The title answers both questions (render_market_page_questions); index closes from the Dashboard's file (S154).
    from src.engine.extra_universe import SYSTEM_750
    if system is None:
        from src.ui import system_param
        system = system_param.current()
    # The 750's members-of-the-day breadth history is joined only under the 750 (S194 L4, 23 Nov 2026).
    pit_ok = system == SYSTEM_750
    bench = nse_benchmarks()
    nifty500 = (benchmark_close if benchmark_close is not None and len(benchmark_close)
                else _series_of(bench, "nifty500"))
    render_market_page_questions(rank_df, history_prices if history_prices is not None else adj_close,
                             nifty500, size_closes(), pit_ok)

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
                from src.engine import pit_breadth
                past = pit_breadth.load("total_market") if pit_ok else None
                pit = {}
                if past is not None:
                    for c, col in (("50D", "above_50"), ("200D", "above_200")):
                        if col in past:
                            if c in breadth_df:          # history to its last date, today's count after it
                                pit[c] = pit_breadth.splice(breadth_df[c], past, col)
                _participation_chart(breadth_df[_pct_cols], ma_type, pit)
        else:
            rows = []
            # The Nifty 1000's other 250 last (S194 L3): tagged NANO250, present only where the system ranks them.
            for idx_name in ("NIFTY 50", "NIFTY NEXT 50", "NIFTY MIDCAP 150",
                             "NIFTY SMALLCAP 250", "NIFTY MICROCAP 250", NANOCAP_250_SHORT):
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
                rows.append((NANOCAP_250_NAME if idx_name == NANOCAP_250_SHORT else idx_name.title(), pct,
                             f"{pct:.0f}% · {int(_obs.sum())}", pct <= 40))
            with kit.card("Participation by index", "br_idx", f"above 50D {ma_type}"):
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

    # Data date and counts, no sources (owner, 20-21 Nov 2026).
    short_n = int((rank_df.get("Short History", pd.Series(dtype=str)) == "Yes").sum())
    st.html(f'<p class="qp-note" style="margin-top:18px">{_fmt.data_to(adj_close.index[-1])}. {len(rank_df)} stocks ranked; '
            f'{gap_count(rank_df)} with a price gap, {short_n} with a short history.</p>')
