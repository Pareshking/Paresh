"""
Multi-Strategy Overlay & 6-Month Walk-Forward Backtest Matrix View Controller.
"""

from __future__ import annotations

from typing import Sequence

import numpy as np
import pandas as pd
import streamlit as st

from src.engine.momentum import MomentumEngine
from src.ui.charts import render_multi_strategy_growth_chart
from src.ui.components import render_data_quality_footer
from src.ui.theme import render_saas_table


@st.cache_data(show_spinner=False, ttl=3600)
def compute_overlay_cached(
    price_hash: str,
    weights_key: tuple[float, ...],
    _calc: MomentumEngine,
    _rank_df: pd.DataFrame,
    top_n: int,
) -> pd.DataFrame:
    return _calc.get_multi_strategy_overlay(_rank_df, top_n=top_n)


@st.cache_data(show_spinner=False, ttl=3600)
def compute_multi_strategy_monthly_matrix(
    price_hash: str,
    _adj_close: pd.DataFrame,
    _rank_df: pd.DataFrame,
    top_n: int = 20,
    n_months: int = 6,
) -> tuple[pd.DataFrame, dict[str, pd.Series]]:
    """
    Computes walk-forward monthly returns & cumulative trajectories for all quantitative models:
      1. 🎯 Multi-Strategy Consensus
      2. 🔬 Residual (α) Momentum
      3. 🏭 Industry-Relative Momentum
      4. ⚡ Momentum Acceleration
      5. 📊 Composite Multi-Window
      6. 🏛️ Benchmark (Nifty 500)
    """
    if len(_adj_close) < 140:
        return pd.DataFrame(), {}

    prices = _adj_close.dropna(axis=1, how="all").copy()
    daily_ret = prices.pct_change(fill_method=None)

    month_ends = prices.resample("ME").last().index
    valid_month_ends = [
        d
        for d in month_ends
        if d in prices.index or prices.index.get_indexer([d], method="pad")[0] > 0
    ]

    if len(valid_month_ends) < n_months + 1:
        rebal_indices = list(
            range(max(0, len(prices) - (n_months * 21) - 1), len(prices) - 1, 21)
        )
        rebal_dates = [prices.index[idx] for idx in rebal_indices]
    else:
        rebal_dates = valid_month_ends[-(n_months + 1) :]

    strategies = {
        "🎯 Consensus Model": "Consensus",
        "🔬 Residual (α) Momentum": "Residual",
        "🏭 Industry-Relative": "IndRel",
        "⚡ Momentum Acceleration": "Accel",
        "📊 Composite Multi-Window": "Composite",
    }

    month_cols = []
    strat_monthly_rets: dict[str, list[float]] = {k: [] for k in strategies}
    bench_monthly_rets: list[float] = []

    # Daily trajectory tracking
    all_daily_dates: list[pd.Timestamp] = []
    strat_daily_rets: dict[str, list[float]] = {k: [] for k in strategies}
    bench_daily_rets: list[float] = []

    for p_idx in range(len(rebal_dates) - 1):
        t_start = rebal_dates[p_idx]
        t_end = rebal_dates[p_idx + 1]

        # Slice strictly up to t_start (Zero Lookahead)
        p_slice = prices.loc[:t_start]
        if len(p_slice) < 60:
            continue

        month_label = f"{t_start:%b %Y}"
        month_cols.append(month_label)

        # 1. Composite Sharpe x R2
        log_ret_s = np.log(p_slice / p_slice.shift(1).replace(0, np.nan))
        p_6m = p_slice.iloc[-126:] if len(p_slice) >= 126 else p_slice
        ret_6m = (p_slice.iloc[-1] / p_slice.iloc[0].clip(lower=0.01)) - 1
        vol_6m = (
            log_ret_s.iloc[-126:].std() * np.sqrt(126)
            if len(log_ret_s) >= 126
            else log_ret_s.std() * np.sqrt(len(log_ret_s))
        )
        sharpe_6m = ret_6m / vol_6m.replace(0, np.nan)
        log_p = np.log(p_6m.clip(lower=0.01))
        t_arr = np.arange(len(log_p))
        r2_6m = log_p.corrwith(pd.Series(t_arr, index=log_p.index, dtype=float)) ** 2
        comp_score = sharpe_6m * r2_6m.fillna(0)

        # 2. Residual Alpha
        mkt_ret = daily_ret.loc[:t_start].mean(axis=1).iloc[-126:]
        stk_ret = daily_ret.loc[:t_start].iloc[-126:]
        cov_m = stk_ret.apply(lambda col: col.cov(mkt_ret))
        var_m = float(mkt_ret.var())
        beta = cov_m / max(var_m, 1e-8)
        alpha_res = (stk_ret.mean() * 252) - (beta * (float(mkt_ret.mean()) * 252))

        # 3. Industry-Relative Momentum
        ind_map = (
            _rank_df.set_index("Symbol")["Industry"].to_dict()
            if "Industry" in _rank_df.columns
            else {}
        )
        ind_scores: dict[str, list[float]] = {}
        for sym, score in comp_score.items():
            ind = ind_map.get(sym, "General")
            ind_scores.setdefault(ind, []).append(score)
        ind_means = {k: float(np.nanmean(v)) for k, v in ind_scores.items()}
        ind_rel_score = comp_score - comp_score.index.map(
            lambda s: ind_means.get(ind_map.get(s, "General"), 0)
        )

        # 4. Momentum Acceleration (Short vs Long)
        ret_1m = (p_slice.iloc[-1] / p_slice.iloc[-min(21, len(p_slice))].clip(lower=0.01)) - 1
        ret_3m = (p_slice.iloc[-1] / p_slice.iloc[-min(63, len(p_slice))].clip(lower=0.01)) - 1
        ret_12m = (p_slice.iloc[-1] / p_slice.iloc[-min(252, len(p_slice))].clip(lower=0.01)) - 1
        accel_score = (ret_1m + ret_3m) - ret_12m

        # Top-N picks per system
        picks = {
            "Composite": comp_score.dropna().nlargest(top_n).index.tolist(),
            "Residual": alpha_res.dropna().nlargest(top_n).index.tolist(),
            "IndRel": ind_rel_score.dropna().nlargest(top_n).index.tolist(),
            "Accel": accel_score.dropna().nlargest(top_n).index.tolist(),
        }
        rank_sum = (
            comp_score.rank(ascending=False)
            + alpha_res.rank(ascending=False)
            + ind_rel_score.rank(ascending=False)
            + accel_score.rank(ascending=False)
        )
        picks["Consensus"] = rank_sum.dropna().nsmallest(top_n).index.tolist()

        fwd_slice = daily_ret.loc[t_start:t_end].iloc[1:]  # T+1 execution
        if fwd_slice.empty:
            continue

        b_daily = fwd_slice.mean(axis=1)
        b_month_cum = float((1 + b_daily).prod() - 1)
        bench_monthly_rets.append(b_month_cum)
        bench_daily_rets.extend(b_daily.tolist())
        all_daily_dates.extend(b_daily.index.tolist())

        for name, key in strategies.items():
            syms = [s for s in picks[key] if s in fwd_slice.columns]
            if syms:
                s_daily = fwd_slice[syms].mean(axis=1)
                s_cum = float((1 + s_daily).prod() - 1)
                strat_daily_rets[name].extend(s_daily.tolist())
            else:
                s_cum = 0.0
                strat_daily_rets[name].extend([0.0] * len(fwd_slice))
            strat_monthly_rets[name].append(s_cum)

    # Build Comparison Matrix DataFrame
    rows = []
    bench_cum = (
        float(np.prod([1 + r for r in bench_monthly_rets]) - 1)
        if bench_monthly_rets
        else 0.0
    )
    for name in strategies:
        m_rets = strat_monthly_rets[name]
        cum_ret = float(np.prod([1 + r for r in m_rets]) - 1) if m_rets else 0.0
        alpha_val = cum_ret - bench_cum
        win_months = sum(1 for s_r, b_r in zip(m_rets, bench_monthly_rets) if s_r > b_r)
        win_rate = (win_months / len(m_rets) * 100) if m_rets else 0.0

        r_dict: dict[str, Any] = {"Strategy Model": name}
        for m_lbl, r in zip(month_cols, m_rets):
            r_dict[m_lbl] = r
        r_dict["6M Net Return"] = cum_ret
        r_dict["6M Alpha"] = alpha_val
        r_dict["Win Rate"] = win_rate / 100.0
        rows.append(r_dict)

    # Add Benchmark Row
    b_dict: dict[str, Any] = {"Strategy Model": "🏛️ Benchmark (Nifty 500)"}
    for m_lbl, r in zip(month_cols, bench_monthly_rets):
        b_dict[m_lbl] = r
    b_dict["6M Net Return"] = bench_cum
    b_dict["6M Alpha"] = 0.0
    b_dict["Win Rate"] = 0.50
    rows.append(b_dict)

    matrix_df = pd.DataFrame(rows)

    # Construct Cumulative Growth Curves
    curves: dict[str, pd.Series] = {}
    if all_daily_dates:
        d_idx = pd.to_datetime(all_daily_dates)
        curves["🏛️ Benchmark (Nifty 500)"] = (
            1 + pd.Series(bench_daily_rets[: len(d_idx)], index=d_idx)
        ).cumprod()
        for name in strategies:
            d_rets = strat_daily_rets[name][: len(d_idx)]
            curves[name] = (1 + pd.Series(d_rets, index=d_idx)).cumprod()

    return matrix_df, curves


def render_strategy_view(
    calc: MomentumEngine,
    rank_df: pd.DataFrame,
    adj_close: pd.DataFrame,
    weights: tuple[float, ...],
) -> None:
    """Renders the Multi-Strategy Quantitative Consensus & 6-Month Backtest Analysis."""
    ph = f"{adj_close.index[-1]}_{adj_close.shape[0]}x{adj_close.shape[1]}"

    # ── Section 1: Consensus Actionable Overlap Table ────────────────────────
    c_info, c_slider = st.columns([2, 1], vertical_alignment="center")
    with c_info:
        st.markdown(
            "<div style=\"font-family: 'IBM Plex Mono', monospace; font-size: 0.8rem; color: #475569;\">"
            'Consensus picks simultaneously in top tiers of <strong style="color: #4f46e5;">Residual α</strong>, '
            '<strong style="color: #0284c7;">Industry-Relative</strong> & <strong style="color: #059669;">Acceleration</strong>'
            "</div>",
            unsafe_allow_html=True,
        )
    top_n = c_slider.slider(
        "Top-N Consensus Threshold", 20, 100, 50, 5, key="overlay_top_n_slider"
    )

    with st.spinner("Computing quantitative momentum overlay…"):
        overlay_df = compute_overlay_cached(ph, weights, calc, rank_df, top_n)

    if overlay_df.empty:
        st.info("Unable to calculate multi-strategy overlay.")
        return

    overlap = overlay_df[overlay_df["In All Top"]]

    kpi_strat_html = f"""
    <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 12px;">
        <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 10px 14px; box-shadow: 0 1px 2px rgba(0,0,0,0.02);">
            <div style="font-family: 'Plus Jakarta Sans', sans-serif; font-size: 0.72rem; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em;">Consensus Picks</div>
            <div style="font-family: 'Outfit', sans-serif; font-size: 1.5rem; font-weight: 800; color: #4f46e5; margin-top: 2px;">{len(overlap)}</div>
            <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.70rem; color: #059669; font-weight: 600;">In All 3 Models</div>
        </div>
        <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 10px 14px; box-shadow: 0 1px 2px rgba(0,0,0,0.02);">
            <div style="font-family: 'Plus Jakarta Sans', sans-serif; font-size: 0.72rem; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em;">Residual α Model</div>
            <div style="font-family: 'Outfit', sans-serif; font-size: 1.5rem; font-weight: 800; color: #0f172a; margin-top: 2px;">Top {top_n}</div>
            <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.70rem; color: #64748b;">Idiosyncratic Alpha</div>
        </div>
        <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 10px 14px; box-shadow: 0 1px 2px rgba(0,0,0,0.02);">
            <div style="font-family: 'Plus Jakarta Sans', sans-serif; font-size: 0.72rem; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em;">Industry-Relative</div>
            <div style="font-family: 'Outfit', sans-serif; font-size: 1.5rem; font-weight: 800; color: #0f172a; margin-top: 2px;">Top {top_n}</div>
            <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.70rem; color: #64748b;">Sector-Neutral Peak</div>
        </div>
        <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 10px 14px; box-shadow: 0 1px 2px rgba(0,0,0,0.02);">
            <div style="font-family: 'Plus Jakarta Sans', sans-serif; font-size: 0.72rem; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em;">Acceleration Model</div>
            <div style="font-family: 'Outfit', sans-serif; font-size: 1.5rem; font-weight: 800; color: #0f172a; margin-top: 2px;">Top {top_n}</div>
            <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.70rem; color: #059669; font-weight: 600;">Velocity Surges</div>
        </div>
    </div>
    """
    st.markdown(kpi_strat_html, unsafe_allow_html=True)

    st.markdown("##### 🎯 Multi-Strategy Consensus Table")
    if not overlap.empty:
        disp_cols = [
            "Composite Rank",
            "Symbol",
            "Industry",
            "CMP",
            "Sharpe Rank",
            "Residual Rank",
            "Ind-Rel Rank",
            "Accel Rank",
            "3M Return",
            "6M Return",
            "Persistence",
            "ATR %",
        ]
        active_disp = [c for c in disp_cols if c in overlap.columns]
        render_saas_table(
            overlap[active_disp],
            key="consensus_table",
        )
    else:
        st.info(
            f"No stock qualifies in the top {top_n} of all three systems. Try raising the threshold slider."
        )

    st.divider()

    # System descriptions
    e1, e2, e3 = st.columns(3)
    systems = [
        (
            e1,
            "Residual (α) Momentum",
            "Stock returns regressed against market index. Extracts idiosyncratic alpha after stripping market beta. Low correlation to broad market swings.",
            "#4f46e5",
        ),
        (
            e2,
            "Industry-Relative Momentum",
            "Stock composite Sharpe×R² minus industry peer average. Isolates top sector outperformers independently of sector cycle.",
            "#0284c7",
        ),
        (
            e3,
            "Momentum Acceleration",
            "Short-term momentum (1M+3M+6M) minus long-term momentum (9M+12M). Detects accelerating velocity and early-stage breakouts.",
            "#059669",
        ),
    ]
    for col, title, desc, color in systems:
        with col:
            st.html(f"""
                <div style="
                    background-color: #ffffff;
                    border: 1px solid #e2e8f0;
                    border-top: 3px solid {color};
                    border-radius: 10px;
                    padding: 14px 16px;
                    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.02);
                ">
                    <div style="font-family: 'Outfit', sans-serif; font-weight: 700; font-size: 0.92rem; color: {color}; margin-bottom: 6px;">
                        {title}
                    </div>
                    <div style="font-family: 'Plus Jakarta Sans', sans-serif; font-size: 0.78rem; color: #475569; line-height: 1.5;">
                        {desc}
                    </div>
                </div>
                """)

    st.divider()

    # ── Section 2: 6-Month Multi-Strategy Monthly Backtest Matrix ────────────
    st.markdown(
        "##### 📊 Multi-Strategy Monthly Backtest & Alpha Attribution (Last 6 Months)"
    )
    st.caption(
        "Walk-forward historical performance comparison across quantitative momentum models with zero look-ahead bias."
    )

    with st.spinner("Computing 6-month walk-forward multi-strategy matrix…"):
        matrix_df, curves = compute_multi_strategy_monthly_matrix(
            ph, adj_close, rank_df, top_n=20, n_months=6
        )

    if not matrix_df.empty:
        # Find the #1 performing model
        non_bench = matrix_df[matrix_df["Strategy Model"] != "🏛️ Benchmark (Nifty 500)"]
        if not non_bench.empty:
            best_model_row = non_bench.sort_values(
                "6M Net Return", ascending=False
            ).iloc[0]
            best_name = best_model_row["Strategy Model"]
            best_ret = float(best_model_row["6M Net Return"]) * 100
            best_alpha = float(best_model_row["6M Alpha"]) * 100

            st.html(f"""
                <div style='background: #f0fdf4; border: 1px solid #86efac; border-radius: 8px; padding: 10px 14px; margin-bottom: 12px; font-size: 0.82rem; color: #166534; display: flex; justify-content: space-between; align-items: center;'>
                    <span>🏆 <strong>Current Regime Leader:</strong> {best_name} generated <strong>+{best_ret:.1f}%</strong> (Alpha: <strong>+{best_alpha:.1f}%</strong> vs Nifty 500)</span>
                    <span style='font-family: JetBrains Mono; font-size: 0.75rem; background: #ffffff; border: 1px solid #86efac; padding: 2px 8px; border-radius: 4px; font-weight: 600;'>Trailing 6M</span>
                </div>
                """)

        # Render Styled Monthly Comparison Table
        render_saas_table(
            matrix_df,
            key="multi_strat_monthly_matrix_table",
        )

        # Render Comparative Equity Curves
        if curves:
            render_multi_strategy_growth_chart(curves)

    st.divider()

    # ── Section 3: Full Overlay Ranking Table ────────────────────────────────
    with st.expander("📋 Full Multi-Strategy Overlay Ranking Table"):
        full_cols = [
            "Composite Rank",
            "Symbol",
            "Industry",
            "Sharpe Rank",
            "Residual Rank",
            "Ind-Rel Rank",
            "Accel Rank",
            "In All Top",
            "CMP",
            "3M Return",
        ]
        render_saas_table(
            overlay_df[[c for c in full_cols if c in overlay_df.columns]].head(100),
            key="full_overlay_table",
        )

    render_data_quality_footer(
        total_stocks=len(rank_df),
        gap_count=int((rank_df.get("Data Gap", pd.Series()) == "🔴").sum()),
        short_count=int((rank_df.get("Short History", pd.Series()) == "Yes").sum()),
    )
