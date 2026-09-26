"""
Portfolio Construction View Controller with Capital Sizing & Zerodha Basket Exports.
"""

import numpy as np
import pandas as pd
import streamlit as st

from src.core.market_time import ist_now
from src.core.types import WeightMethod
from src.engine.momentum import MomentumEngine
from src.engine.portfolio import PortfolioOptimizer
from src.ui import page_kit as kit
from src.ui.components import gap_count, render_data_quality_footer, to_bool_mask
from src.ui.theme import render_saas_table


def render_portfolio_view(
    calc: MomentumEngine,
    rank_df: pd.DataFrame,
    sector_cap: float,
    stock_cap: float,
    vol_target_on: bool,
    vol_target_val: float,
) -> None:
    """Today's model book from the qualified list, sized and ready for Kite."""
    actions = kit.page_head(
        "Portfolio",
        "Today's model book from the qualified list, sized to your capital, ready to send to Zerodha Kite",
        actions=True,
    )

    # ── Settings, in one bar ─────────────────────────────────────────────────
    with st.container(key="pgcard_port_settings", horizontal=True, vertical_alignment="center"):
        selected_method = st.segmented_control(
            "Weighting",
            [WeightMethod.EQUAL_WEIGHT.value, WeightMethod.INVERSE_VOLATILITY.value],
            default=WeightMethod.EQUAL_WEIGHT.value,
            key="port_weight_method_seg",
        ) or WeightMethod.EQUAL_WEIGHT.value
        port_n = st.slider("Holdings", 10, 40, 20, 5, key="port_top_n", width=220)
        portfolio_capital = st.number_input(
            "Capital (₹)", min_value=50000, max_value=100000000, value=1000000,
            step=50000, format="%d", key="port_total_capital_input", width=200,
        )
        st.html(f'<span class="pg-cap">Caps: {stock_cap:.0%} per stock · '
                f"{sector_cap:.0%} per sector (Configuration)</span>")

    if stock_cap > sector_cap:
        kit.note(f"The stock cap ({stock_cap:.0%}) is above the sector cap ({sector_cap:.0%}).",
                 "Lower it in Configuration → Portfolio risk.")
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
        st.info("No stock passes both filters today, so there is no book to build.")
        return

    notes: list[tuple[str, str]] = []
    vol_tiles: list[kit.Reading] = []
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

    # A cap the projection could not honour is reported, not quietly applied.
    # Twenty names across two industries cannot hold a 30% sector cap: the
    # tightest achievable is 50%, and showing "Cap: 30%" beside a 50% sector
    # tells the reader the limit held when it did not.
    # A stock cap at or below 1/N admits exactly one fully-invested portfolio,
    # so the weighting scheme the user picked has no effect whatsoever. At the
    # shipped defaults (Top 20, 5% stock cap) that is precisely the case, and
    # "Inverse Volatility" produced a book identical to Equal Weight with the
    # selector still lit on the user's choice.
    if constrained_w.attrs.get("scheme_neutralised") and len(constrained_w) > 1:
        notes.append((
            "Equal weight and inverse volatility give the same book here.",
            f"A {stock_cap:.0%} stock cap across {len(constrained_w)} holdings "
            f"allows only one fully-invested book, {1/len(constrained_w):.1%} in "
            "every name. Raise the stock cap in Configuration → Portfolio risk, "
            "or hold fewer names, for the weighting to matter.",
        ))

    if constrained_w.attrs.get("caps_relaxed"):
        notes.append((
            "Your caps cannot both be met by this book.",
            f"Stock {stock_cap:.0%} and sector {sector_cap:.0%} cannot hold across "
            f"{len(constrained_w)} names in "
            f"{len(set(sector_map.get(s, 'Other') for s in constrained_w.index))} "
            "industries. Enforced instead: stock "
            f"{constrained_w.attrs['effective_stock_cap']:.1%}, sector "
            f"{constrained_w.attrs['effective_sector_cap']:.1%}, the tightest "
            "limits this book can satisfy.",
        ))

    # Volatility targeting
    real_vol = 0.0
    scale = 1.0
    if vol_target_on:
        try:
            constrained_w, scale, real_vol = pc.volatility_target(
                constrained_w, target_vol=vol_target_val
            )
            cash_pct = (1.0 - scale) * 100
            vol_tiles = [
                kit.Reading("Realised volatility", f"{real_vol:.1%}", "annualised, this book"),
                kit.Reading("Target volatility", f"{vol_target_val:.0%}",
                            f"{scale:.0%} invested" + (f" · {cash_pct:.0f}% held as cash" if cash_pct > 1 else "")),
            ]
        except ValueError as e:
            st.error(f"Volatility target error: {e}")
            return

    summary = pc.summary(constrained_w, rank_df)
    if summary.empty:
        st.info("Unable to calculate non-zero portfolio allocation.")
        return

    # Enrich with Capital, Share Counts, and CMP
    cmp_map = rank_df.set_index("Symbol")["CMP"].to_dict()
    # Stop Loss is ATR-derived, so it is absent whenever the ranking came from
    # a source with no intraday high or low. Indexing it directly raised a
    # KeyError and took the whole Portfolio page down with it; the display list
    # below already drops columns that are not there.
    sl_map = (
        rank_df.set_index("Symbol")["Stop Loss"].to_dict()
        if "Stop Loss" in rank_df.columns
        else {}
    )

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
    if sl_map:
        summary["Stop Loss"] = summary["Symbol"].map(sl_map)

    total_allocated = summary["Actual Value (₹)"].sum()
    unallocated_cash = max(0, portfolio_capital - total_allocated)

    # Zerodha Kite basket: one CNC market buy per holding with shares to buy.
    kite_df = pd.DataFrame([
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
        for _, r in summary.iterrows()
        if r["Shares to Buy"] > 0
    ])
    with actions:
        st.download_button(
            "Download Kite basket",
            kite_df.to_csv(index=False).encode(),
            f"zerodha_kite_basket_{ist_now():%Y%m%d}.csv",
            "text/csv",
            type="primary",
            key="dl_kite_basket_btn",
            icon=":material/download:",
            help="Import in Zerodha Kite → Orders → Baskets",
        )
        st.download_button(
            "Export CSV",
            summary.to_csv(index=False).encode(),
            f"portfolio_{ist_now():%Y%m%d}.csv",
            "text/csv",
            key="dl_port_csv",
        )

    for lead, text in notes:
        kit.note(lead, text)

    sec_agg = (
        summary.groupby("Industry")
        .agg(Weight=("Weight %", "sum"), Count=("Symbol", "count"))
        .sort_values("Weight", ascending=False)
        .reset_index()
        if "Industry" in summary.columns
        else pd.DataFrame(columns=["Industry", "Weight", "Count"])
    )
    enforced_sector_cap = constrained_w.attrs.get("effective_sector_cap", sector_cap)
    top = sec_agg.iloc[0] if len(sec_agg) else None
    at_cap = top is not None and top["Weight"] >= enforced_sector_cap * 100 - 0.05
    kit.readings([
        kit.Reading("Capital", f"₹{portfolio_capital:,.0f}", "the amount you entered"),
        kit.Reading("Invested", f"₹{total_allocated:,.0f}", f"{len(kite_df)} buy orders", "up"),
        kit.Reading("Cash left", f"₹{unallocated_cash:,.0f}",
                    f"{unallocated_cash / portfolio_capital * 100:.1f}% · whole shares only"),
        kit.Reading("Largest sector", "—" if top is None else f"{top['Weight']:.0f}%",
                    "" if top is None else
                    f"{top['Industry']} · {'at' if at_cap else 'under'} the {enforced_sector_cap:.0%} cap"
                    + (" (relaxed)" if constrained_w.attrs.get("caps_relaxed") else ""),
                    "warn" if at_cap else ""),
        *vol_tiles,
    ], "This book")

    left, right = st.columns([1.6, 1], gap="medium")
    with left, kit.card("Orders", "port_orders", "CNC market orders · the Kite basket holds the same"):
        orders = summary.rename(columns={
            "Symbol": "Stock", "CMP": "Price", "Shares to Buy": "Shares",
            "Actual Value (₹)": "Value (₹)", "Weight %": "Weight %",
        })
        cols = ["Stock", "Industry", "Weight %", "Price", "Shares", "Value (₹)", "Stop Loss"]
        render_saas_table(orders[[c for c in cols if c in orders.columns]], max_height=560)
    with right, kit.card("By sector", "port_sectors", "orange = at the sector cap"):
        st.html(kit.bar_list(
            [(str(r["Industry"]), float(r["Weight"]),
              f"{r['Weight']:.0f}% · {int(r['Count'])}",
              r["Weight"] >= enforced_sector_cap * 100 - 0.05)
             for _, r in sec_agg.iterrows()],
            scale=max(enforced_sector_cap * 100, float(sec_agg["Weight"].max() if len(sec_agg) else 0)),
        ))

    render_data_quality_footer(
        total_stocks=len(rank_df),
        gap_count=gap_count(rank_df),
        short_count=int((rank_df.get("Short History", pd.Series()) == "Yes").sum()),
    )
