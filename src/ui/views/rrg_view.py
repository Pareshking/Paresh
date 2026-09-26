"""
Relative Rotation Graph (RRG ®) View Controller.
"""

from typing import Sequence
import re

import numpy as np
import pandas as pd
import streamlit as st

from src.engine.pipeline import price_fingerprint
from src.ui import page_kit as kit
from src.ui.charts import render_rrg_chart
from src.ui.components import gap_count, render_data_quality_footer
from src.ui.theme import render_saas_table


# The benchmark options, named once so the selector and the dispatch cannot
# disagree. Each is an EQUAL-WEIGHTED proxy computed from the loaded universe,
# not the NSE index of a similar name.
BENCHMARK_UNIVERSE: str = "Loaded universe (equal-weighted)"
BENCHMARK_TOP50: str = "Top 50 by market cap (equal-weighted)"
BENCHMARK_MID: str = "Market-cap ranks 101-250 (equal-weighted)"
BENCHMARK_OPTIONS: list[str] = [BENCHMARK_UNIVERSE, BENCHMARK_TOP50, BENCHMARK_MID]


@st.cache_data(show_spinner=False, ttl=3600)
def compute_rrg_data(
    prices_hash: str,
    _adj_close: pd.DataFrame,
    _rank_df: pd.DataFrame,
    ind_column: str = "Industry",
    lookback_weeks: int = 12,
    tail_weeks: int = 6,
    timeframe: str = "Weekly candle",
    benchmark_choice: str = BENCHMARK_UNIVERSE,
    end_date_str: str | None = None,
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

    # Benchmark calculation.
    #
    # This dispatched on `"50" in benchmark_choice`, and ALL THREE option
    # labels contain "50" -- "Nifty 500 (Universe Equal-Weighted)", "Nifty 50
    # (Large-Cap 50)" and "Nifty Midcap 150". The first branch therefore always
    # won: the Midcap branch was unreachable, the whole-universe branch was
    # unreachable, and the three benchmarks were one series. Changing the
    # selector did nothing to the chart. Same defect class as the screener's
    # N50/NN50 collision -- a substring test standing in for an identity.
    #
    # The labels were also claims the code does not honour. None of these is an
    # NSE index: they are EQUAL-WEIGHTED proxies built from whatever universe
    # the Configuration tab has loaded. The README requires ^CRSLDX wherever a
    # V1 module needs a market benchmark "unless a module has an explicitly
    # documented reason not to" -- RRG compares sector breadth against a peer
    # group rather than against a capitalisation-weighted index, so an
    # equal-weighted proxy is the intended input. That is the documented
    # reason; the labels now say what they are.
    has_mcap = "Market Cap (Cr)" in _rank_df.columns

    def _equal_weighted(symbols: Sequence[str]) -> pd.Series | None:
        valid = [s for s in symbols if s in daily_ret.columns]
        return daily_ret[valid].mean(axis=1) if len(valid) >= 5 else None

    benchmark_ret = None
    if has_mcap and benchmark_choice == BENCHMARK_TOP50:
        ordered = _rank_df.sort_values("Market Cap (Cr)", ascending=False)["Symbol"]
        benchmark_ret = _equal_weighted(ordered.head(50))
    elif has_mcap and benchmark_choice == BENCHMARK_MID:
        ordered = _rank_df.sort_values("Market Cap (Cr)", ascending=False)["Symbol"]
        benchmark_ret = _equal_weighted(ordered.iloc[100:250])
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


def render_rrg_view(
    rank_df: pd.DataFrame,
    adj_close: pd.DataFrame,
) -> None:
    """Renders Relative Rotation Graph (RRG ®) rotational analysis and quadrant matrix."""
    kit.page_head(
        "Relative rotation",
        "Which industries are gaining strength against the market, and which are fading: "
        "they rotate clockwise from Improving to Leading, Weakening and Lagging",
    )

    col_chart, col_side = st.columns([3.1, 1.1], gap="medium")

    with col_side:
        st.html('<div class="pg-card-h"><h2>Compare</h2></div>')
        scope_pill = st.segmented_control(
            "Selection Scope",
            ["Sector Indices", "Top Stocks", "TV Sectors"],
            default="Sector Indices",
            format_func=lambda k: {"Sector Indices": "Industries", "Top Stocks": "Top stocks",
                                   "TV Sectors": "TradingView sectors"}[k],
            key="rrg_scope_pill",
            label_visibility="collapsed",
        )
        if not scope_pill:
            scope_pill = "Sector Indices"

        target_col = "Industry"
        if scope_pill == "Top Stocks":
            target_col = "Symbol"
        elif scope_pill == "TV Sectors" and "TV_Sector" in rank_df.columns:
            target_col = "TV_Sector"

    with col_chart:
        c_bm, c_tf, c_tail, c_lb = st.columns(
            [1.6, 1.2, 1.3, 1.0], vertical_alignment="center"
        )
        bm_choice = c_bm.selectbox(
            "Benchmark",
            BENCHMARK_OPTIONS,
            index=0,
            key="rrg_bm_choice",
            help=(
                "Equal-weighted proxies built from the universe loaded in the "
                "Configuration tab — not the NSE indices of similar names. RRG "
                "compares a sector against its peer group, so an equal-weighted "
                "proxy is the intended input rather than the ^CRSLDX benchmark "
                "used elsewhere in V1."
            ),
        )
        tf_choice = c_tf.selectbox(
            "Timeframe",
            ["Weekly candle", "Daily candle"],
            format_func=lambda k: k.split()[0],
            index=0,
            key="rrg_tf_choice",
        )
        tail_w = c_tail.slider(
            "Tail (weeks)",
            min_value=2,
            max_value=20,
            value=6,
            step=1,
            key="rrg_tl_w",
        )
        lookback_w = c_lb.number_input(
            "Lookback (weeks)", min_value=4, max_value=52, value=12, step=1, key="rrg_lb_w"
        )

        n_total_dates = len(adj_close)
        min_date_idx = max(0, n_total_dates - 120)
        date_options = [d.strftime("%Y-%m-%d") for d in adj_close.index[min_date_idx:]]

        if len(date_options) > 1:
            sel_date_str = st.select_slider(
                "As of",
                options=date_options,
                value=date_options[-1],
                format_func=lambda x: f"{tail_w} weeks to {pd.to_datetime(x):%d %b %Y}",
                key="rrg_timeline_scrub",
            )
        else:
            sel_date_str = adj_close.index[-1].strftime("%Y-%m-%d")

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
    )

    if not rrg_df.empty:
        all_inds = sorted(rrg_df["Industry"].tolist())
        leading_items = (
            rrg_df[rrg_df["Quadrant"] == "Leading"]
            .sort_values("RS_Ratio", ascending=False)["Industry"]
            .head(8)
            .tolist()
        )
        default_highlight = (
            leading_items
            if leading_items
            else rrg_df.sort_values("RS_Ratio", ascending=False)
            .head(6)["Industry"]
            .tolist()
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
            quad_items = (
                rrg_df[rrg_df["Quadrant"] == target_quad]
                .sort_values("RS_Ratio", ascending=False)["Industry"]
                .head(8)
                .tolist()
            )
            st.session_state[ms_key] = quad_items

        def _clear_rrg_all() -> None:
            st.session_state[ms_key] = []

        with col_side:
            spotlight = st.multiselect(
                "Show",
                all_inds,
                key=ms_key,
                placeholder="Search and add…",
            )

            # 4-Quadrant 1-Click Filters
            kit.caption("Show the top of one quadrant:")
            q_row1_c1, q_row1_c2 = st.columns(2)
            q_row1_c1.button(
                "Leading",
                key=f"btn_rrg_lead_{target_col}",
                help="Show top Leading assets (max 8)",
                width="stretch",
                on_click=_set_rrg_quadrant,
                args=("Leading",),
            )
            q_row1_c2.button(
                "Improving",
                key=f"btn_rrg_imp_{target_col}",
                help="Show top Improving assets (max 8)",
                width="stretch",
                on_click=_set_rrg_quadrant,
                args=("Improving",),
            )

            q_row2_c1, q_row2_c2 = st.columns(2)
            q_row2_c1.button(
                "Weakening",
                key=f"btn_rrg_weak_{target_col}",
                help="Show top Weakening assets (max 8)",
                width="stretch",
                on_click=_set_rrg_quadrant,
                args=("Weakening",),
            )
            q_row2_c2.button(
                "Lagging",
                key=f"btn_rrg_lag_{target_col}",
                help="Show top Lagging assets (max 8)",
                width="stretch",
                on_click=_set_rrg_quadrant,
                args=("Lagging",),
            )

            # Active Items Chips with Filled Quadrant Color Styling & 1-Click Remove
            kit.caption("On the chart (click one to remove it):")
            active_list = spotlight if spotlight is not None else []

            if not active_list:
                kit.caption("Nothing selected. Pick a quadrant above, or search.")

            for sym in active_list:
                q_row = rrg_df[rrg_df["Industry"] == sym]
                quad = q_row["Quadrant"].iloc[0] if not q_row.empty else "Leading"
                btn_lbl = f"{sym} · {quad}  ✕"

                clean_btn_key = re.sub(
                    r"[^a-zA-Z0-9_]", "_", f"del_rrg_{target_col}_{sym}"
                )
                st.button(
                    btn_lbl,
                    key=clean_btn_key,
                    help=f"Click to remove {sym} ({quad}) from RRG",
                    width="stretch",
                    on_click=_remove_rrg_item,
                    args=(sym,),
                )

            if active_list:
                st.button(
                    "Clear all",
                    key=f"btn_rrg_clr_{target_col}",
                    help="Clear all selections",
                    width="stretch",
                    on_click=_clear_rrg_all,
                )

            kit.caption(
                "Drag on the chart to zoom. A stock or industry usually moves "
                "Improving → Leading → Weakening → Lagging."
            )

        with col_chart:
            target_highlight = spotlight if spotlight else []
            render_rrg_chart(
                rrg_df,
                highlight_industries=target_highlight,
                current_date_str=sel_date_str,
            )

            st.html('<div class="pg-card-h" style="margin-top:14px"><h2>Strength and momentum, by name</h2>'
                    "<span>RS ratio above 100 = stronger than the benchmark · momentum above 100 = gaining</span></div>")
            view_cols = ["Industry", "RS_Ratio", "RS_Momentum", "Quadrant", "Stocks"]
            view_df = (
                rrg_df[view_cols]
                .sort_values("RS_Ratio", ascending=False)
                .reset_index(drop=True)
            )
            render_saas_table(view_df, max_height=260)

    render_data_quality_footer(
        total_stocks=len(rank_df),
        gap_count=gap_count(rank_df),
        short_count=int((rank_df.get("Short History", pd.Series()) == "Yes").sum()),
    )
