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
from src.ui import page_kit as kit
from src.ui.components import gap_count, render_data_quality_footer
from src.ui.theme import render_saas_table


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
    """Share of stocks above each average, over time, with the 40% and 60%
    bands shaded. Altair ships with Streamlit, so no CDN is needed."""
    import altair as alt

    data = pct.copy()
    data.index.name = "Date"
    long = data.reset_index().melt("Date", var_name="Average", value_name="Share").dropna()
    long["Average"] = long["Average"].str.replace("D", "-day ", regex=False) + ma_type
    order = sorted(long["Average"].unique(), key=lambda s: int(s.split("-")[0]))
    palette = ["#4F46E5", "#98A1AE", "#0E1726", "#B54708", "#067647"]
    bands = alt.Chart(pd.DataFrame({"lo": [60, 0], "hi": [100, 40], "c": ["#E8F5EE", "#FDEDEB"]})).mark_rect(
        opacity=0.55).encode(y="lo:Q", y2="hi:Q", color=alt.Color("c:N", scale=None))
    lines = alt.Chart(long).mark_line(strokeWidth=2.2).encode(
        x=alt.X("Date:T", title=None, axis=alt.Axis(format="%d %b", labelColor="#5E6878", grid=False)),
        y=alt.Y("Share:Q", title=None, scale=alt.Scale(domain=[0, 100]),
                axis=alt.Axis(labelExpr="datum.value + '%'", labelColor="#5E6878", gridColor="#EDEFF3",
                              domain=False, ticks=False)),
        color=alt.Color("Average:N", sort=order, scale=alt.Scale(domain=order, range=palette[: len(order)]),
                        legend=alt.Legend(orient="top", title=None, labelColor="#3C4657")),
        tooltip=[alt.Tooltip("Date:T", format="%d %b %Y"), "Average:N",
                 alt.Tooltip("Share:Q", format=".0f", title="% above")],
    )
    st.altair_chart((bands + lines).properties(height=280).configure_view(strokeWidth=0).configure(background="#FFFFFF"),
                    width="stretch", key="br_part_chart")


def _highs_lows_chart(hl_df: pd.DataFrame, is_pct: bool) -> None:
    """New highs up in green, new lows down in red, one bar pair per session."""
    import altair as alt

    h_col, l_col = ("% New Highs", "% New Lows") if is_pct else ("New Highs", "New Lows")
    data = pd.DataFrame({
        "Date": hl_df.index,
        "Highs": pd.to_numeric(hl_df[h_col], errors="coerce").to_numpy(),
        "Lows": -pd.to_numeric(hl_df[l_col], errors="coerce").to_numpy(),
    })
    long = data.melt("Date", var_name="Kind", value_name="Value").dropna()
    unit = "% of stocks" if is_pct else "stocks"
    bars = alt.Chart(long).mark_bar(width={"band": 0.85}).encode(
        x=alt.X("Date:T", title=None, axis=alt.Axis(format="%d %b", labelColor="#5E6878", grid=False)),
        y=alt.Y("Value:Q", title=None,
                axis=alt.Axis(labelExpr="abs(datum.value)", labelColor="#5E6878", gridColor="#EDEFF3",
                              domain=False, ticks=False)),
        color=alt.Color("Kind:N", scale=alt.Scale(domain=["Highs", "Lows"], range=["#067647", "#B42318"]),
                        legend=alt.Legend(orient="top", title=None, labelColor="#3C4657")),
        tooltip=[alt.Tooltip("Date:T", format="%d %b %Y"), "Kind:N",
                 alt.Tooltip("abs_v:Q", format=".1f" if is_pct else ".0f", title=unit)],
    ).transform_calculate(abs_v="abs(datum.Value)")
    zero = alt.Chart(pd.DataFrame({"y": [0]})).mark_rule(color="#98A1AE").encode(y="y:Q")
    st.altair_chart((bars + zero).properties(height=260).configure_view(strokeWidth=0).configure(background="#FFFFFF"),
                    width="stretch", key="br_hl_chart")


def _participation_word(val: float) -> tuple[str, str]:
    """What a share of stocks above an average reads as, and its tone."""
    if val >= 60:
        return "strong participation", "up"
    if val <= 40:
        return "below 40% reads as weak", "down"
    return "neutral", "warn"


def _ratio_word(ratio: float) -> tuple[str, str]:
    if ratio > 2:
        return "highs outnumber lows: broadening", "up"
    if ratio < 1:
        return "below 1 = the market is narrowing", "down" if ratio < 0.5 else "warn"
    return "roughly balanced", "warn"


def render_breadth_view(rank_df: pd.DataFrame, adj_close: pd.DataFrame) -> None:
    """How many stocks are taking part: trend participation, and new highs
    against new lows."""
    actions = kit.page_head(
        "Market breadth",
        f"How many stocks are taking part: trend participation and new highs against "
        f"new lows, across the {len(rank_df)}",
        actions=True,
    )
    with actions:
        history_days = st.selectbox(
            "Period", [63, 126, 252], index=1,
            format_func=lambda x: {63: "3 months", 126: "6 months", 252: "1 year"}[x],
            key="br_lb_days", label_visibility="collapsed", width=130,
        )
        with st.popover("Chart settings", icon=":material/tune:"):
            ma_type = st.segmented_control("Average", ["EMA", "SMA"], default="EMA",
                                           key="br_ma_type") or "EMA"
            sel_mas = st.multiselect("Periods", ["10D", "20D", "50D", "100D", "200D"],
                                     default=["50D", "200D"], key="br_sel_mas")
            bview = st.segmented_control("Participation by", ["Universe", "By Index"],
                                         default="Universe", key="br_bview") or "Universe"
            hl_window = st.selectbox(
                "New high / low means", [52, 126, 252], index=2,
                format_func=lambda x: {52: "52-day", 126: "126-day", 252: "52-week"}[x],
                key="hl_win_sel",
            )
            hl_disp = st.segmented_control("Show highs and lows as", ["% of Universe", "Stock Count"],
                                           default="% of Universe", key="hl_fmt_radio") or "% of Universe"

    if not sel_mas:
        st.info("Pick at least one moving average under Chart settings.")
        return

    # Whole-history fingerprint, not last date + shape (an intraday refresh
    # or a restatement kept the old key and served stale breadth).
    ph = price_fingerprint(adj_close)
    breadth_df = compute_ma_breadth(
        ph, adj_close, tuple(sel_mas), lookback=history_days, ma_type=ma_type
    )
    hl_df = compute_hl_timeseries(ph, adj_close, window=hl_window, lookback=history_days)
    hl_name = {52: "52-day", 126: "126-day", 252: "52-week"}[hl_window]

    tiles: list[kit.Reading] = []
    for ma_lbl in sel_mas:
        if breadth_df.empty or ma_lbl not in breadth_df.columns:
            continue
        label = f"Above {ma_lbl.replace('D', '-day')} {ma_type}"
        val = breadth_df[ma_lbl].iloc[-1]
        if pd.isna(val):
            # No symbol had both a price and an MA on this session -- a holiday
            # row, a pre-close fetch, or a frame shorter than the MA's
            # min_periods. `int(nan)` once took the whole page down here.
            tiles.append(kit.Reading(label, "—", "no prices on this session"))
            continue
        # The denominator comes from the engine: stocks that have both a price
        # and an average on this session, not the full column count.
        n_obs = breadth_df.get(f"{ma_lbl}{OBSERVED_SUFFIX}")
        n_observed = (
            int(n_obs.iloc[-1])
            if n_obs is not None and pd.notna(n_obs.iloc[-1])
            else len(adj_close.columns)
        )
        word, tone = _participation_word(val)
        tiles.append(kit.Reading(label, f"{val:.0f}%",
                                 f"{int(round(val / 100 * n_observed))} stocks · {word}", tone))
    if not hl_df.empty:
        today_h = int(hl_df["New Highs"].iloc[-1])
        today_l = int(hl_df["New Lows"].iloc[-1])
        ratio = today_h / max(today_l, 1)
        word, tone = _ratio_word(ratio)
        tiles += [
            kit.Reading(f"New {hl_name} highs", f"{today_h}", "today", "up" if today_h else ""),
            kit.Reading(f"New {hl_name} lows", f"{today_l}",
                        "today" + (" · more lows than highs" if today_l > today_h else ""),
                        "down" if today_l else ""),
            kit.Reading("Highs ÷ lows", f"{ratio:.1f}×", word, tone),
        ]
    if tiles:
        kit.readings(tiles, "Breadth today")

    if not breadth_df.empty:
        if bview == "Universe":
            with kit.card("Participation", "br_part",
                          f"share of stocks above each {ma_type} · green band above 60%, red below 40%"):
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
            with kit.card(f"Participation by index · above the 50-day {ma_type}", "br_idx",
                          "amber = 40% or less"):
                if rows:
                    st.html(kit.bar_list(rows, scale=100))
                else:
                    kit.caption("No index tags on the ranked stocks.")

    if not hl_df.empty:
        with kit.card("New highs against new lows", "br_hl",
                      "each session: green up = new highs · red down = new lows"):
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
                    disp = hl_events_df[hl_events_df["Event"].str.contains("High")]
                elif ev_sel == "Lows":
                    disp = hl_events_df[hl_events_df["Event"].str.contains("Low")]
                render_saas_table(disp, max_height=420)

    render_data_quality_footer(
        total_stocks=len(rank_df),
        gap_count=gap_count(rank_df),
        short_count=int((rank_df.get("Short History", pd.Series()) == "Yes").sum()),
    )
