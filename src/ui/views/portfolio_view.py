"""
Portfolio Construction View Controller with Capital Sizing & Zerodha Basket Exports.
"""

from datetime import datetime

import numpy as np
import pandas as pd
import streamlit as st

from src.core.types import WeightMethod
from src.engine.momentum import MomentumEngine
from src.engine.portfolio import PortfolioOptimizer
from src.ui.components import render_data_quality_footer, to_bool_mask
from src.ui.theme import render_saas_table


def render_portfolio_view(
    calc: MomentumEngine,
    rank_df: pd.DataFrame,
    sector_cap: float,
    stock_cap: float,
    vol_target_on: bool,
    vol_target_val: float,
) -> None:
    """Renders Portfolio Construction with Equal Weight, Inverse Vol, Capital Sizing & Broker Exports."""
    # ── Weighting Scheme & Universe Controls (Single Aligned Row) ───────────
    c_wm, c_n, c_cap = st.columns([1.5, 1, 1.2], vertical_alignment="center")

    selected_method = c_wm.segmented_control(
        "Weighting Scheme",
        [
            WeightMethod.EQUAL_WEIGHT.value,
            WeightMethod.INVERSE_VOLATILITY.value,
        ],
        default=WeightMethod.EQUAL_WEIGHT.value,
        key="port_weight_method_seg",
        label_visibility="collapsed",
    )
    if not selected_method:
        selected_method = WeightMethod.EQUAL_WEIGHT.value

    port_n = c_n.slider("Holdings (Top N)", 10, 40, 20, 5, key="port_top_n")
    portfolio_capital = c_cap.number_input(
        "Capital (₹ INR)",
        min_value=50000,
        max_value=100000000,
        value=1000000,
        step=50000,
        format="%d",
        key="port_total_capital_input",
    )

    if stock_cap > sector_cap:
        st.error(
            f"⛔ Stock cap ({stock_cap:.0%}) cannot exceed sector cap ({sector_cap:.0%}). Adjust in Config."
        )
        return

    # .map() preserves the source dtype when there are no rows to infer from,
    # so on an empty frame these came back str and float64 and "ab_ema & nr_hi"
    # died in Arrow's and_kleene. to_bool_mask always yields a real bool mask.
    ab_ema = (
        to_bool_mask(rank_df["Above 50 EMA"])
        if "Above 50 EMA" in rank_df.columns
        else pd.Series(True, index=rank_df.index, dtype=bool)
    )
    nr_hi = (
        to_bool_mask(rank_df["Near 52W High"])
        if "Near 52W High" in rank_df.columns
        else pd.Series(True, index=rank_df.index, dtype=bool)
    )
    port_universe = rank_df[ab_ema & nr_hi].sort_values("Rank").head(port_n)

    if port_universe.empty:
        st.info("No stocks currently pass filters for portfolio construction.")
        return

    port_syms = port_universe["Symbol"].tolist()
    sector_map = rank_df.set_index("Symbol")["Industry"].to_dict()
    log_ret = calc.log_ret
    pc = PortfolioOptimizer(log_ret, sector_map=sector_map)

    # Compute raw weights
    if selected_method == WeightMethod.INVERSE_VOLATILITY.value:
        raw_w = pc.inverse_volatility(port_syms)
    else:
        raw_w = pc.equal_weight(port_syms)

    # Apply constraints
    try:
        constrained_w = pc.apply_constraints(
            raw_w, sector_cap=sector_cap, stock_cap=stock_cap
        )
    except ValueError as e:
        st.error(f"Constraint error: {e}")
        return

    # Volatility targeting
    real_vol = 0.0
    scale = 1.0
    if vol_target_on:
        try:
            constrained_w, scale, real_vol = pc.volatility_target(
                constrained_w, target_vol=vol_target_val
            )
            cash_pct = (1.0 - scale) * 100
            c1, c2, c3 = st.columns(3)
            c1.metric("Realized Portfolio Vol (Ann.)", f"{real_vol:.1%}")
            c2.metric("Target Volatility", f"{vol_target_val:.0%}")
            c3.metric(
                "Invested Allocation",
                f"{scale:.0%}",
                delta=(
                    f"{cash_pct:.0f}% cash buffer" if cash_pct > 1 else "Fully invested"
                ),
            )
            st.divider()
        except ValueError as e:
            st.error(f"Volatility target error: {e}")
            return

    summary = pc.summary(constrained_w, rank_df)
    if summary.empty:
        st.info("Unable to calculate non-zero portfolio allocation.")
        return

    # Enrich with Capital, Share Counts, and CMP
    cmp_map = rank_df.set_index("Symbol")["CMP"].to_dict()
    sl_map = rank_df.set_index("Symbol")["Stop Loss"].to_dict()

    summary["CMP"] = summary["Symbol"].map(cmp_map)
    summary["Target Value (₹)"] = (
        summary["Weight %"] / 100.0 * portfolio_capital
    ).round(0)
    summary["Shares to Buy"] = (
        (summary["Target Value (₹)"] / summary["CMP"].replace(0, np.nan))
        .fillna(0)
        .astype(int)
    )
    summary["Actual Value (₹)"] = (summary["Shares to Buy"] * summary["CMP"]).round(0)
    summary["Stop Loss"] = summary["Symbol"].map(sl_map)

    total_allocated = summary["Actual Value (₹)"].sum()
    unallocated_cash = max(0, portfolio_capital - total_allocated)

    # ── Executive KPI Cards ──────────────────────────────────────────────────
    top_sec = (
        summary.groupby("Industry")["Weight %"].sum().max()
        if "Industry" in summary.columns
        else 0.0
    )

    kpi_port_html = f"""
    <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 12px;">
        <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 10px 14px; box-shadow: 0 1px 2px rgba(0,0,0,0.02);">
            <div style="font-family: 'Plus Jakarta Sans', sans-serif; font-size: 0.72rem; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em;">Capital Sized</div>
            <div style="font-family: 'Outfit', sans-serif; font-size: 1.5rem; font-weight: 800; color: #0f172a; margin-top: 2px;">₹{portfolio_capital:,.0f}</div>
            <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.70rem; color: #4f46e5; font-weight: 600;">Target Portfolio</div>
        </div>
        <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 10px 14px; box-shadow: 0 1px 2px rgba(0,0,0,0.02);">
            <div style="font-family: 'Plus Jakarta Sans', sans-serif; font-size: 0.72rem; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em;">Allocated Capital</div>
            <div style="font-family: 'Outfit', sans-serif; font-size: 1.5rem; font-weight: 800; color: #059669; margin-top: 2px;">₹{total_allocated:,.0f}</div>
            <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.70rem; color: #059669; font-weight: 600;">{len(summary)} Stock Orders</div>
        </div>
        <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 10px 14px; box-shadow: 0 1px 2px rgba(0,0,0,0.02);">
            <div style="font-family: 'Plus Jakarta Sans', sans-serif; font-size: 0.72rem; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em;">Remaining Cash Buffer</div>
            <div style="font-family: 'Outfit', sans-serif; font-size: 1.5rem; font-weight: 800; color: #0f172a; margin-top: 2px;">₹{unallocated_cash:,.0f}</div>
            <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.70rem; color: #64748b;">{unallocated_cash/portfolio_capital*100:.1f}% Cash</div>
        </div>
        <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 10px 14px; box-shadow: 0 1px 2px rgba(0,0,0,0.02);">
            <div style="font-family: 'Plus Jakarta Sans', sans-serif; font-size: 0.72rem; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em;">Top Sector Weight</div>
            <div style="font-family: 'Outfit', sans-serif; font-size: 1.5rem; font-weight: 800; color: #0f172a; margin-top: 2px;">{top_sec:.1f}%</div>
            <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.70rem; color: #64748b;">Cap: {sector_cap:.0%}</div>
        </div>
    </div>
    """
    st.markdown(kpi_port_html, unsafe_allow_html=True)

    st.markdown(" ")

    # ── Allocation Table & Sector Breakdown ──────────────────────────────────
    ca, cb = st.columns([1.5, 1], gap="medium")
    with ca:
        st.markdown("##### Capital Sized Rebalance Order Sheet")
        disp_cols = [
            "Symbol",
            "Weight %",
            "CMP",
            "Shares to Buy",
            "Target Value (₹)",
            "Actual Value (₹)",
            "Stop Loss",
            "Industry",
        ]
        render_saas_table(
            summary[[c for c in disp_cols if c in summary.columns]],
            key="order_sheet_table",
            max_height=320,
        )

    with cb:
        st.markdown("##### Sector Allocation")
        if "Industry" in summary.columns:
            sec_agg = (
                summary.groupby("Industry")
                .agg(
                    Weight=("Weight %", "sum"),
                    Count=("Symbol", "count"),
                )
                .sort_values("Weight", ascending=False)
                .reset_index()
            )

            ind_items_html = []
            for _, r in sec_agg.iterrows():
                ind_items_html.append(f"""
                    <div style="margin-bottom: 9px;">
                        <div style="display: flex; justify-content: space-between; font-size: 0.76rem; font-family: 'Plus Jakarta Sans', sans-serif; margin-bottom: 3px;">
                            <span style="font-weight: 600; color: #0f172a;">{r['Industry']}</span>
                            <span style="font-family: 'JetBrains Mono', monospace; color: #475569; font-weight: 700;">{int(r['Count'])} stock{'s' if r['Count']>1 else ''} ({r['Weight']:.1f}%)</span>
                        </div>
                        <div style="width: 100%; height: 6px; background-color: #f1f5f9; border-radius: 99px; overflow: hidden;">
                            <div style="width: {min(100, r['Weight'])}%; height: 100%; background: linear-gradient(90deg, #4f46e5, #06b6d4); border-radius: 99px;"></div>
                        </div>
                    </div>
                    """)
            breakdown_html = f"""
            <div style="background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 14px 16px; box-shadow: 0 1px 2px rgba(0,0,0,0.02); max-height: 320px; overflow-y: auto;">
                {''.join(ind_items_html)}
            </div>
            """
            st.html(breakdown_html)

    st.divider()

    # ── Zerodha Kite Basket Orders Hub ───────────────────────────────────────
    st.markdown("##### Zerodha Kite Basket Orders")
    st.caption(
        "One-click rebalance execution directly formatted for Zerodha Kite Basket Orders."
    )

    # Zerodha Kite Basket CSV Format
    kite_rows = []
    for _, r in summary.iterrows():
        if r["Shares to Buy"] > 0:
            kite_rows.append(
                {
                    "Instrument": r["Symbol"],
                    "Exchange": "NSE",
                    "Order Type": "MARKET",
                    "Action": "BUY",
                    "Quantity": int(r["Shares to Buy"]),
                    "Price": 0,
                    "ProductType": "CNC",
                    "TriggerPrice": 0,
                }
            )
    kite_df = pd.DataFrame(kite_rows)

    zc1, zc2 = st.columns([1.5, 2.5], vertical_alignment="center")
    with zc1:
        st.download_button(
            "Download Zerodha Kite Basket CSV",
            kite_df.to_csv(index=False).encode(),
            f"zerodha_kite_basket_{datetime.now():%Y%m%d}.csv",
            "text/csv",
            type="primary",
            key="dl_kite_basket_btn",
            width="stretch",
        )

    with zc2:
        st.caption(
            f"Ready to import into **Zerodha Kite > Orders > Baskets**: `{len(kite_df)}` CNC Market orders · Total execution value: **₹{total_allocated:,.0f}**"
        )

    with st.expander("Inspect Zerodha Kite Basket Schema", expanded=False):
        render_saas_table(kite_df, key="zerodha_basket_preview_table", max_height=240)

    render_data_quality_footer(
        total_stocks=len(rank_df),
        gap_count=int((rank_df.get("Data Gap", pd.Series()) == "🔴").sum()),
        short_count=int((rank_df.get("Short History", pd.Series()) == "Yes").sum()),
    )
