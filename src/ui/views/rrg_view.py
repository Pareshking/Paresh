"""
Relative Rotation Graph (RRG ®) View Controller.
"""

import re

import pandas as pd
import streamlit as st

from src.engine.momentum import MomentumEngine
from src.ui.charts import render_rrg_chart
from src.ui.components import render_data_quality_footer
from src.ui.theme import render_saas_table


@st.cache_data(show_spinner=False, ttl=3600)
def compute_rrg_data(
    prices_hash: str,
    _adj_close: pd.DataFrame,
    _rank_df: pd.DataFrame,
    ind_column: str = "Industry",
    lookback_weeks: int = 12,
    tail_weeks: int = 6,
    timeframe: str = "Weekly candle",
    benchmark_choice: str = "Nifty 50 (Large-Cap 50)",
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

    # Benchmark calculation
    if "50" in benchmark_choice and "Market Cap (Cr)" in _rank_df.columns:
        top50 = _rank_df.sort_values("Market Cap (Cr)", ascending=False)["Symbol"].head(50)
        top50_valid = [s for s in top50 if s in daily_ret.columns]
        benchmark_ret = daily_ret[top50_valid].mean(axis=1) if len(top50_valid) >= 5 else daily_ret.mean(axis=1)
    elif "Midcap" in benchmark_choice and "Market Cap (Cr)" in _rank_df.columns:
        mid150 = _rank_df.sort_values("Market Cap (Cr)", ascending=False)["Symbol"].iloc[100:250]
        mid_valid = [s for s in mid150 if s in daily_ret.columns]
        benchmark_ret = daily_ret[mid_valid].mean(axis=1) if len(mid_valid) >= 5 else daily_ret.mean(axis=1)
    else:
        benchmark_ret = daily_ret.mean(axis=1)

    sectors: dict[str, list[str]] = {}
    if ind_column == "Symbol":
        top_syms = _rank_df["Symbol"].tolist() if "Symbol" in _rank_df.columns else list(daily_ret.columns)
        sectors = {s: [s] for s in top_syms if s in daily_ret.columns}
    else:
        ind_map = _rank_df.set_index("Symbol")[ind_column].to_dict() if "Symbol" in _rank_df.columns else {}
        for sym, ind in ind_map.items():
            if ind and str(ind).strip() and str(ind).strip().lower() != "nan" and sym in daily_ret.columns:
                sectors.setdefault(str(ind).strip(), []).append(sym)
        sectors = {k: v for k, v in sectors.items() if len(v) >= 2}

    if not sectors:
        return pd.DataFrame()

    raw_data = {}
    cum_bench = (1 + benchmark_ret.fillna(0)).cumprod().replace(0, 1.0)

    for ind, syms in sectors.items():
        sect_ret = daily_ret[syms].mean(axis=1).fillna(0)
        cum_sect = (1 + sect_ret).cumprod()
        rs_line = cum_sect / cum_bench
        rs_smooth = rs_line.ewm(span=max(lookback // 2, 8)).mean()
        rs_ratio = rs_smooth / rs_smooth.rolling(lookback, min_periods=max(lookback // 3, 10)).mean()
        rs_mom = rs_ratio / rs_ratio.shift(step)
        raw_data[ind] = {"ratio": rs_ratio, "mom": rs_mom, "stocks": len(syms)}

    all_latest_ratio = pd.Series({ind: d["ratio"].iloc[-1] for ind, d in raw_data.items()}).dropna()
    all_latest_mom = pd.Series({ind: d["mom"].iloc[-1] for ind, d in raw_data.items()}).dropna()

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
    calc: MomentumEngine,
    rank_df: pd.DataFrame,
    adj_close: pd.DataFrame,
) -> None:
    """Renders Relative Rotation Graph (RRG ®) rotational analysis and quadrant matrix."""
    st.markdown(
        """
        <div style="font-family: 'Plus Jakarta Sans', sans-serif; font-size: 1.10rem; font-weight: 800; color: #0f172a; margin-bottom: 2px;">
            Relative Rotation Graph (RRG ®)
        </div>
        <div style="font-size: 0.76rem; color: #64748b; margin-bottom: 14px;">
            Track clockwise relative strength and momentum rotation against benchmark indices.
        </div>
        """,
        unsafe_allow_html=True,
    )

    col_chart, col_side = st.columns([3.1, 1.1], gap="medium")

    with col_side:
        st.markdown("<div style='font-weight:700;font-size:0.85rem;margin-bottom:6px;color:#0f172a;'>Universe Scope</div>", unsafe_allow_html=True)
        scope_pill = st.segmented_control(
            "Selection Scope",
            ["Sector Indices", "Top Stocks", "TV Sectors"],
            default="Sector Indices",
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
        c_bm, c_tf, c_tail, c_lb = st.columns([1.6, 1.2, 1.3, 1.0], vertical_alignment="center")
        bm_choice = c_bm.selectbox(
            "Benchmark",
            ["Nifty 500 (Universe Equal-Weighted)", "Nifty 50 (Large-Cap 50)", "Nifty Midcap 150"],
            index=0,
            key="rrg_bm_choice",
        )
        tf_choice = c_tf.selectbox(
            "Candle Timeframe",
            ["Weekly candle", "Daily candle"],
            index=0,
            key="rrg_tf_choice",
        )
        tail_w = c_tail.slider("Tail Length (Weeks)", min_value=2, max_value=20, value=6, step=1, key="rrg_tl_w")
        lookback_w = c_lb.number_input("RS Lookback", min_value=4, max_value=52, value=12, step=1, key="rrg_lb_w")

        n_total_dates = len(adj_close)
        min_date_idx = max(0, n_total_dates - 120)
        date_options = [d.strftime("%Y-%m-%d") for d in adj_close.index[min_date_idx:]]

        if len(date_options) > 1:
            sel_date_str = st.select_slider(
                "Historic Timeline Scrubbing",
                options=date_options,
                value=date_options[-1],
                format_func=lambda x: f"Showing data for {tail_w} weeks ending: {pd.to_datetime(x):%d %b %Y}",
                key="rrg_timeline_scrub",
            )
        else:
            sel_date_str = adj_close.index[-1].strftime("%Y-%m-%d")

    ph = f"{sel_date_str}_{adj_close.shape[0]}x{adj_close.shape[1]}_{bm_choice}_{tf_choice}_{target_col}"
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
        leading_items = rrg_df[rrg_df["Quadrant"] == "Leading"].sort_values("RS_Ratio", ascending=False)["Industry"].head(8).tolist()
        default_highlight = leading_items if leading_items else rrg_df.sort_values("RS_Ratio", ascending=False).head(6)["Industry"].tolist()

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
            quad_items = rrg_df[rrg_df["Quadrant"] == target_quad].sort_values("RS_Ratio", ascending=False)["Industry"].head(8).tolist()
            st.session_state[ms_key] = quad_items

        def _clear_rrg_all() -> None:
            st.session_state[ms_key] = []

        with col_side:
            spotlight = st.multiselect(
                "Search and add indices / stocks",
                all_inds,
                key=ms_key,
                placeholder="Search and add…",
            )

            # 4-Quadrant 1-Click Filters
            st.html("<div style='margin-top:10px;margin-bottom:6px;font-size:0.72rem;font-weight:700;color:#64748b;font-family:Plus Jakarta Sans;text-align:left;text-transform:uppercase;letter-spacing:0.05em;'>QUICK QUADRANT SELECTION:</div>")
            q_row1_c1, q_row1_c2 = st.columns(2)
            q_row1_c1.button("Leading", key=f"btn_rrg_lead_{target_col}", help="Show top Leading assets (max 8)", width="stretch", on_click=_set_rrg_quadrant, args=("Leading",))
            q_row1_c2.button("Improving", key=f"btn_rrg_imp_{target_col}", help="Show top Improving assets (max 8)", width="stretch", on_click=_set_rrg_quadrant, args=("Improving",))

            q_row2_c1, q_row2_c2 = st.columns(2)
            q_row2_c1.button("Weakening", key=f"btn_rrg_weak_{target_col}", help="Show top Weakening assets (max 8)", width="stretch", on_click=_set_rrg_quadrant, args=("Weakening",))
            q_row2_c2.button("Lagging", key=f"btn_rrg_lag_{target_col}", help="Show top Lagging assets (max 8)", width="stretch", on_click=_set_rrg_quadrant, args=("Lagging",))

            # Active Items Chips with Filled Quadrant Color Styling & 1-Click Remove
            st.html("<div style='margin-top:12px;margin-bottom:6px;font-size:0.72rem;font-weight:700;color:#64748b;font-family:Plus Jakarta Sans;text-align:left;text-transform:uppercase;letter-spacing:0.05em;'>ACTIVE SELECTION (CLICK TO REMOVE):</div>")
            active_list = spotlight if spotlight is not None else []

            if not active_list:
                st.caption("No assets selected. Click a quadrant above or search.")

            quad_styles = {
                "Leading": {"bg": "#dcfce7", "text": "#15803d", "border": "#86efac", "icon": "🟢"},
                "Weakening": {"bg": "#fef9c3", "text": "#a16207", "border": "#fde047", "icon": "🟡"},
                "Lagging": {"bg": "#ffe4e6", "text": "#be123c", "border": "#fca5a5", "icon": "🔴"},
                "Improving": {"bg": "#e0f2fe", "text": "#0284c7", "border": "#7dd3fc", "icon": "🔵"},
            }

            for sym in active_list:
                q_row = rrg_df[rrg_df["Industry"] == sym]
                quad = q_row["Quadrant"].iloc[0] if not q_row.empty else "Leading"
                q_cfg = quad_styles.get(quad, quad_styles["Leading"])
                btn_lbl = f"{q_cfg['icon']}  {sym}  ·  {quad}"
                
                clean_btn_key = re.sub(r"[^a-zA-Z0-9_]", "_", f"del_rrg_{target_col}_{sym}")
                st.button(
                    btn_lbl,
                    key=clean_btn_key,
                    help=f"Click to remove {sym} ({quad}) from RRG",
                    width="stretch",
                    on_click=_remove_rrg_item,
                    args=(sym,),
                )

            if active_list:
                st.button("Clear All Selections", key=f"btn_rrg_clr_{target_col}", help="Clear all selections", width="stretch", on_click=_clear_rrg_all)

            st.markdown(
                """
                <div style='margin-top:14px;background-color:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:12px;font-size:0.75rem;color:#475569;line-height:1.45;'>
                    <strong style='color:#0f172a;'>Tip:</strong> Click and drag on the chart to zoom.<br><br>
                    <strong style='color:#0f172a;'>Lifecycle:</strong> Assets start in 
                    <span style='color:#2563eb;font-weight:600;'>Improving</span>, rotate into 
                    <span style='color:#15803d;font-weight:600;'>Leading</span>, transition to 
                    <span style='color:#ca8a04;font-weight:600;'>Weakening</span>, and finish in 
                    <span style='color:#dc2626;font-weight:600;'>Lagging</span>.
                </div>
                """,
                unsafe_allow_html=True,
            )

        with col_chart:
            target_highlight = spotlight if spotlight else []
            render_rrg_chart(rrg_df, highlight_industries=target_highlight, current_date_str=sel_date_str)

            st.markdown("<div style='margin-top:14px;margin-bottom:6px;font-weight:700;font-size:0.88rem;color:#0f172a;font-family:Plus Jakarta Sans;'>Relative Strength & Momentum Matrix</div>", unsafe_allow_html=True)
            view_cols = ["Industry", "RS_Ratio", "RS_Momentum", "Quadrant", "Stocks"]
            view_df = rrg_df[view_cols].sort_values("RS_Ratio", ascending=False).reset_index(drop=True)
            render_saas_table(view_df, key="rrg_matrix_table", max_height=260)

    render_data_quality_footer(
        total_stocks=len(rank_df),
        gap_count=int((rank_df.get("Data Gap", pd.Series()) == "🔴").sum()),
        short_count=int((rank_df.get("Short History", pd.Series()) == "Yes").sum()),
    )
