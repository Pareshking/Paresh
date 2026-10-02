"""
Relative Rotation Graph (RRG ®) View Controller.
"""

import html
import re

import numpy as np
import pandas as pd
import streamlit as st

from src.loaders.price_loader import fetch_benchmark_history
from src.ui.system_param import stock_href
from src.engine.pipeline import price_fingerprint
from src.ui import page_kit as kit
from src.ui.charts import render_rrg_chart
from src.ui.components import gap_count, render_data_quality_footer


# The benchmarks, named once so the selector and the dispatch cannot disagree.
# Real NSE indices, as every other page measures against (Nifty 500 is the
# portfolio's benchmark). Value: the Yahoo symbol of the index.
BENCHMARK_N500: str = "Nifty 500"
BENCHMARK_N50: str = "Nifty 50"
BENCHMARK_SYMBOLS: dict[str, str] = {BENCHMARK_N500: "^CRSLDX", BENCHMARK_N50: "^NSEI"}
BENCHMARK_OPTIONS: list[str] = list(BENCHMARK_SYMBOLS)


@st.cache_data(show_spinner=False, ttl=3600)
def compute_rrg_data(
    prices_hash: str,
    _adj_close: pd.DataFrame,
    _rank_df: pd.DataFrame,
    ind_column: str = "Industry",
    lookback_weeks: int = 12,
    tail_weeks: int = 6,
    timeframe: str = "Weekly candle",
    benchmark_choice: str = BENCHMARK_N500,
    end_date_str: str | None = None,
    _benchmark: pd.Series | None = None,
) -> pd.DataFrame:
    """Computes Sharpely / JdK Relative Rotation Graph (RRG) coordinates and rotation trails."""
    if _adj_close.empty or len(_adj_close) < 25:
        return pd.DataFrame()

    prices = _adj_close.loc[:end_date_str] if end_date_str else _adj_close
    if len(prices) < 20:
        return pd.DataFrame()

    is_daily = "Daily" in timeframe
    step = 1 if is_daily else 5
    lookback = (lookback_weeks * 5) if not is_daily else max(lookback_weeks * 5, 20)
    tail_length = tail_weeks

    daily_ret = prices.pct_change(fill_method=None)

    # The benchmark is the chosen index's own return series. If it could not be
    # fetched, the loaded universe's equal-weighted return stands in, so the
    # chart still draws; the caption on the page says which was used.
    benchmark_ret = None
    if _benchmark is not None and len(_benchmark) > 20:
        level = pd.to_numeric(_benchmark, errors="coerce").dropna()
        benchmark_ret = level.pct_change(fill_method=None).reindex(daily_ret.index)
        if benchmark_ret.notna().sum() < 20:
            benchmark_ret = None
    if benchmark_ret is None:
        benchmark_ret = daily_ret.mean(axis=1)

    sectors: dict[str, list[str]] = {}
    if ind_column == "Symbol":
        top_syms = (
            _rank_df["Symbol"].tolist()
            if "Symbol" in _rank_df.columns
            else list(daily_ret.columns)
        )
        sectors = {s: [s] for s in top_syms if s in daily_ret.columns}
    else:
        ind_map = (
            _rank_df.set_index("Symbol")[ind_column].to_dict()
            if "Symbol" in _rank_df.columns
            else {}
        )
        for sym, ind in ind_map.items():
            if (
                ind
                and str(ind).strip()
                and str(ind).strip().lower() != "nan"
                and sym in daily_ret.columns
            ):
                sectors.setdefault(str(ind).strip(), []).append(sym)
        sectors = {k: v for k, v in sectors.items() if len(v) >= 2}

    if not sectors:
        return pd.DataFrame()

    raw_data = {}
    # Relative strength must compare the sector and the benchmark over the SAME
    # observations. Filling a missing return with 0 invents a flat session:
    # when the benchmark is the filled side the sector's real move is measured
    # against a stationary benchmark, which biases RS-Ratio directionally.
    # Missing observations are excluded pairwise instead.
    valid_bench = benchmark_ret.dropna()

    for ind, syms in sectors.items():
        # mean(axis=1) already ignores individual members that are missing; the
        # result is NaN only on dates where the whole sector is unobserved.
        sect_ret = daily_ret[syms].mean(axis=1)
        paired = pd.concat(
            [sect_ret.rename("sect"), valid_bench.rename("bench")],
            axis=1, join="inner",
        ).dropna()
        if len(paired) < 2:
            continue
        cum_sect = (1 + paired["sect"]).cumprod()
        cum_bench = (1 + paired["bench"]).cumprod()
        rs_line = cum_sect / cum_bench.replace(0, np.nan)
        rs_smooth = rs_line.ewm(span=max(lookback // 2, 8)).mean()
        rs_ratio = (
            rs_smooth
            / rs_smooth.rolling(lookback, min_periods=max(lookback // 3, 10)).mean()
        )
        rs_mom = rs_ratio / rs_ratio.shift(step)
        raw_data[ind] = {"ratio": rs_ratio, "mom": rs_mom, "stocks": len(syms)}

    all_latest_ratio = pd.Series(
        {ind: d["ratio"].iloc[-1] for ind, d in raw_data.items()}
    ).dropna()
    all_latest_mom = pd.Series(
        {ind: d["mom"].iloc[-1] for ind, d in raw_data.items()}
    ).dropna()

    if all_latest_ratio.empty:
        return pd.DataFrame()

    spread = 6.5
    r_mean, r_std = all_latest_ratio.mean(), max(all_latest_ratio.std(), 1e-8)
    m_mean, m_std = all_latest_mom.mean(), max(all_latest_mom.std(), 1e-8)

    rows = []
    for ind, d in raw_data.items():
        if ind not in all_latest_ratio.index:
            continue

        ratio_z = 100 + ((all_latest_ratio[ind] - r_mean) / r_std) * spread
        mom_z = 100 + ((all_latest_mom[ind] - m_mean) / m_std) * spread

        if ratio_z >= 100 and mom_z >= 100:
            quad = "Leading"
        elif ratio_z >= 100 and mom_z < 100:
            quad = "Weakening"
        elif ratio_z < 100 and mom_z < 100:
            quad = "Lagging"
        else:
            quad = "Improving"

        trail_r, trail_m = [], []
        ratio_series = d["ratio"].dropna()
        mom_series = d["mom"].dropna()
        n_trail = min(tail_length, len(ratio_series) // step)
        if n_trail > 0:
            for t_idx in range(-n_trail * step, 0, step):
                if abs(t_idx) < len(ratio_series) and abs(t_idx) < len(mom_series):
                    tr = 100 + ((ratio_series.iloc[t_idx] - r_mean) / r_std) * spread
                    tm = 100 + ((mom_series.iloc[t_idx] - m_mean) / m_std) * spread
                    trail_r.append(round(tr, 2))
                    trail_m.append(round(tm, 2))
            trail_r.append(round(ratio_z, 2))
            trail_m.append(round(mom_z, 2))

        rows.append(
            {
                "Industry": ind,
                "RS_Ratio": round(ratio_z, 2),
                "RS_Momentum": round(mom_z, 2),
                "Quadrant": quad,
                "Stocks": d["stocks"],
                "Trail_R": trail_r,
                "Trail_M": trail_m,
            }
        )

    return pd.DataFrame(rows)


QUADRANTS = [("Leading", "lead"), ("Improving", "imp"), ("Weakening", "weak"), ("Lagging", "lag")]


def quadrant_lists_html(rrg_df: pd.DataFrame, is_stocks: bool) -> str:
    """Four lists, one per quadrant, strongest first, with RS · Momentum."""
    cols = []
    for quad, cls in QUADRANTS:
        sub = rrg_df[rrg_df["Quadrant"] == quad].sort_values("RS_Ratio", ascending=False)
        items = "".join(
            '<div class="rq-i"><span>'
            + (f'<a href="{stock_href(r.Industry)}" target="_self">{html.escape(str(r.Industry))}</a>'
               if is_stocks else html.escape(str(r.Industry)))
            + f'</span><b>{r.RS_Ratio:.1f} · {r.RS_Momentum:.1f}</b></div>'
            for r in sub.itertuples()
        ) or '<div class="rq-i"><span class="rq-none">None</span></div>'
        cols.append(f'<div class="rq {cls}"><div class="rq-h"><b>{quad}</b>'
                    f'<span>{len(sub)}</span></div>{items}</div>')
    return f'<div class="rq-grid">{"".join(cols)}</div>'


def render_rrg_view(
    rank_df: pd.DataFrame,
    adj_close: pd.DataFrame,
) -> None:
    """Relative rotation: the chart first and full width, controls in one row."""
    head = kit.page_head(
        "Relative rotation",
        "Which industries are gaining strength against the market and which are fading. "
        "They rotate clockwise: Improving → Leading → Weakening → Lagging.",
        actions=True,
    )
    with head:
        scope_pill = st.segmented_control(
            "Compare",
            ["Sector Indices", "Top Stocks", "TV Sectors"],
            default="Sector Indices",
            format_func=lambda k: {"Sector Indices": "Industries", "Top Stocks": "Top stocks",
                                   "TV Sectors": "TV sectors"}[k],
            key="rrg_scope_pill",
            label_visibility="collapsed",
        ) or "Sector Indices"
        settings = st.popover("Chart settings", icon=":material/tune:")

    target_col = "Industry"
    if scope_pill == "Top Stocks":
        target_col = "Symbol"
    elif scope_pill == "TV Sectors" and "TV_Sector" in rank_df.columns:
        target_col = "TV_Sector"

    with settings:
        bm_choice = st.selectbox(
            "Benchmark",
            BENCHMARK_OPTIONS,
            index=0,
            key="rrg_bm_choice",
            help="Each industry's strength is measured against this index.",
        )
        tf_choice = st.segmented_control(
            "Timeframe",
            ["Weekly candle", "Daily candle"],
            format_func=lambda k: k.split()[0],
            default="Weekly candle",
            required=True,
            key="rrg_tf_choice",
        ) or "Weekly candle"
        tail_w = st.slider("Tail (weeks)", min_value=2, max_value=20, value=6, step=1,
                           key="rrg_tl_w")
        lookback_w = st.number_input("Lookback (weeks)", min_value=4, max_value=52, value=12,
                                     step=1, key="rrg_lb_w")
        n_total_dates = len(adj_close)
        date_options = [d.strftime("%Y-%m-%d") for d in adj_close.index[max(0, n_total_dates - 120):]]
        if len(date_options) > 1:
            sel_date_str = st.select_slider(
                "As of",
                options=date_options,
                value=date_options[-1],
                format_func=lambda x: f"{pd.to_datetime(x):%d %b %Y}",
                key="rrg_timeline_scrub",
            )
        else:
            sel_date_str = adj_close.index[-1].strftime("%Y-%m-%d")

    bm_series = fetch_benchmark_history(period="5y", symbol=BENCHMARK_SYMBOLS[bm_choice])
    bm_used = bm_choice if len(bm_series) > 20 else "equal-weighted universe (index unavailable)"
    kit.caption(
        f"Benchmark {bm_used} · {tf_choice.split()[0].lower()} · tail {tail_w}w · lookback "
        f"{lookback_w}w · {pd.to_datetime(sel_date_str):%d %b %Y}"
    )

    ph = f"{sel_date_str}_{price_fingerprint(adj_close)}_{bm_choice}_{tf_choice}_{target_col}"
    rrg_df = compute_rrg_data(
        ph,
        adj_close,
        rank_df,
        ind_column=target_col,
        lookback_weeks=lookback_w,
        tail_weeks=tail_w,
        timeframe=tf_choice,
        benchmark_choice=bm_choice,
        end_date_str=sel_date_str,
        _benchmark=bm_series,
    )

    if rrg_df.empty:
        st.info("Not enough price history to draw the rotation for these settings.")
    else:
        all_inds = sorted(rrg_df["Industry"].tolist())
        leading_items = (
            rrg_df[rrg_df["Quadrant"] == "Leading"]
            .sort_values("RS_Ratio", ascending=False)["Industry"].head(8).tolist()
        )
        default_highlight = (
            leading_items
            if leading_items
            else rrg_df.sort_values("RS_Ratio", ascending=False).head(6)["Industry"].tolist()
        )

        ms_key = f"rrg_ms_{target_col}"
        if ms_key not in st.session_state:
            st.session_state[ms_key] = default_highlight
        else:
            valid_existing = [s for s in st.session_state[ms_key] if s in all_inds]
            if not valid_existing and default_highlight:
                st.session_state[ms_key] = default_highlight
            else:
                st.session_state[ms_key] = valid_existing

        def _remove_rrg_item(item_to_remove: str) -> None:
            current = st.session_state.get(ms_key, [])
            st.session_state[ms_key] = [s for s in current if s != item_to_remove]

        def _set_rrg_quadrant(target_quad: str) -> None:
            st.session_state[ms_key] = (
                rrg_df[rrg_df["Quadrant"] == target_quad]
                .sort_values("RS_Ratio", ascending=False)["Industry"].head(8).tolist()
            )

        def _clear_rrg_all() -> None:
            st.session_state[ms_key] = []

        with st.container(key="pgcard_rrg_chart"):
            with st.container(horizontal=True, vertical_alignment="center", key="rrg_selbar"):
                counts = rrg_df["Quadrant"].value_counts()
                for quad, cls in QUADRANTS:
                    st.button(
                        f"{quad} · {int(counts.get(quad, 0))}",
                        key=f"btn_rrg_{cls}_{target_col}",
                        help=f"Show the top of {quad} (up to 8)",
                        on_click=_set_rrg_quadrant,
                        args=(quad,),
                    )
                active_list = list(st.session_state.get(ms_key, []))
                for sym in active_list:
                    st.button(
                        f"{sym}  ✕",
                        key=re.sub(r"[^a-zA-Z0-9_]", "_", f"del_rrg_{target_col}_{sym}"),
                        help=f"Remove {sym} from the chart",
                        on_click=_remove_rrg_item,
                        args=(sym,),
                    )
                with st.popover("+ Add", key=f"rrg_add_{target_col}"):
                    st.multiselect("Show on the chart", all_inds, key=ms_key,
                                   placeholder="Search…")
                if active_list:
                    st.button("Clear", key=f"btn_rrg_clr_{target_col}", on_click=_clear_rrg_all,
                              type="tertiary")

            render_rrg_chart(
                rrg_df,
                highlight_industries=list(st.session_state.get(ms_key, [])),
                current_date_str=sel_date_str,
            )
            kit.caption(
                f"Tails show the last {tail_w} weeks. Faded lines are the others; tap a dot to isolate it, "
                "tap again to clear."
            )

        with kit.card("Quadrants", "rrg_quads", "RS · Momentum, 100 = benchmark"):
            st.html(quadrant_lists_html(rrg_df, is_stocks=(target_col == "Symbol")))
            st.download_button(
                "Export CSV",
                rrg_df.drop(columns=[c for c in ("Trail_R", "Trail_M") if c in rrg_df.columns])
                .to_csv(index=False).encode(),
                "rrg.csv", "text/csv", key="dl_rrg_csv",
            )

    render_data_quality_footer(
        total_stocks=len(rank_df),
        gap_count=gap_count(rank_df),
        short_count=int((rank_df.get("Short History", pd.Series()) == "Yes").sum()),
    )
