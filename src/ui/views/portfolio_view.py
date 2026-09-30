"""Current model Portfolio view.

Portfolio is an accounting/presentation view of the Track Record's canonical
current book. It does not select stocks or calculate a competing model book.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

from src.core.market_time import ist_now
from src.engine.extra_universe import SYSTEM_750
from src.loaders.price_loader import fetch_benchmark_history
from src.ui import page_kit as kit
from src.ui import system_param
from src.ui.canonical_book import current_book
from src.ui.theme import render_saas_table


def build_portfolio_tracker(
    book: pd.DataFrame,
    rank_df: pd.DataFrame,
    capital: float,
    prices: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Enrich the canonical Track Record book with portfolio accounting.

    Membership and target weights come only from the canonical book. Ranking
    data supplies labels/current observations; prices are used only for day-P&L.
    """
    if book is None or book.empty:
        return pd.DataFrame()

    out = book.copy()
    lookup = (
        rank_df.drop_duplicates("Symbol").set_index("Symbol")
        if rank_df is not None and not rank_df.empty
        else pd.DataFrame()
    )

    def mapped(column: str, default=np.nan):
        if isinstance(lookup, pd.DataFrame) and column in lookup.columns:
            return out["Symbol"].map(lookup[column])
        return pd.Series(default, index=out.index)

    out["Company"] = mapped("Company Name", "").replace("", np.nan).fillna(
        mapped("Company", "").replace("", np.nan)
    ).fillna(out["Symbol"])
    out["Sector / Industry"] = mapped("TV_Sector", "").replace("", np.nan).fillna(
        mapped("Industry", "—")
    )
    out["Current Rank"] = pd.to_numeric(mapped("Rank"), errors="coerce")
    out["Market Cap (Cr)"] = pd.to_numeric(mapped("Market Cap (Cr)"), errors="coerce")

    for months in (1, 3, 6, 12):
        out[f"{months}M Return"] = pd.to_numeric(
            mapped(f"{months}M Return"), errors="coerce"
        )

    out["Target Weight %"] = pd.to_numeric(out["Weight %"], errors="coerce").fillna(0.0)
    out["Entry Price"] = pd.to_numeric(out["Entry Price"], errors="coerce")
    out["Current Price"] = pd.to_numeric(out["Price Now"], errors="coerce")
    out["Shares"] = (
        (capital * out["Target Weight %"] / 100.0)
        / out["Entry Price"].replace(0, np.nan)
    ).fillna(0.0).apply(np.floor).astype(int)
    out["Invested Value (₹)"] = (out["Shares"] * out["Entry Price"]).round(0)
    out["Current Value (₹)"] = (out["Shares"] * out["Current Price"]).round(0)
    out["P&L (₹)"] = (out["Current Value (₹)"] - out["Invested Value (₹)"]).round(0)
    out["P&L %"] = np.where(
        out["Invested Value (₹)"] > 0,
        out["P&L (₹)"] / out["Invested Value (₹)"] * 100.0,
        np.nan,
    )

    total_invested = float(out["Invested Value (₹)"].sum())
    total_current = float(out["Current Value (₹)"].sum())
    cash = max(float(capital) - total_invested, 0.0)
    total_value = total_current + cash
    out["Weight %"] = np.where(
        total_value > 0, out["Current Value (₹)"] / total_value * 100.0, 0.0
    )
    out["Weight Drift %"] = out["Weight %"] - out["Target Weight %"]

    entry = pd.to_datetime(out["Entry Date"], errors="coerce")
    as_of = pd.to_datetime(book.attrs.get("as_of"), errors="coerce")
    if pd.isna(as_of):
        as_of = pd.Timestamp.now().normalize()
    out["Holding Days"] = (as_of - entry).dt.days.fillna(0).astype(int)

    if prices is not None and not prices.empty and len(prices.index) >= 2:
        p = prices.reindex(columns=out["Symbol"].tolist()).ffill()
        prev = pd.to_numeric(p.iloc[-2], errors="coerce")
        curr = pd.to_numeric(p.iloc[-1], errors="coerce")
        out["Day P&L (₹)"] = out.apply(
            lambda r: float(r["Shares"]) * (
                float(curr.get(r["Symbol"], np.nan))
                - float(prev.get(r["Symbol"], np.nan))
            )
            if pd.notna(curr.get(r["Symbol"], np.nan))
            and pd.notna(prev.get(r["Symbol"], np.nan))
            else np.nan,
            axis=1,
        )
    else:
        out["Day P&L (₹)"] = np.nan

    out["Status"] = "Held"
    return out.sort_values(
        ["Current Value (₹)", "Symbol"], ascending=[False, True]
    ).reset_index(drop=True)


def render_portfolio_view(
    calc,
    rank_df: pd.DataFrame,
    sector_cap: float,
    stock_cap: float,
    vol_target_on: bool,
    vol_target_val: float,
    liquidity_floor_cr: float = 0.0,
    traded_value: pd.DataFrame | None = None,
) -> None:
    """Render the current model portfolio from the canonical Track Record book."""
    del sector_cap, stock_cap, vol_target_on, vol_target_val, liquidity_floor_cr, traded_value

    head = kit.page_head(
        "Portfolio",
        "The current model portfolio from the Track Record, with live accounting and position-level P&L.",
        actions=True,
    )

    with st.container(
        key="pgcard_port_settings", horizontal=True, vertical_alignment="center"
    ):
        portfolio_capital = st.number_input(
            "Model capital (₹)",
            min_value=50000,
            max_value=100000000,
            value=1000000,
            step=50000,
            format="%d",
            key="port_total_capital_input",
            width=220,
        )
        st.caption("Capital changes sizing only; it cannot change which stocks are held.")

    system = system_param.current() or SYSTEM_750
    adj_close = getattr(calc, "prices", pd.DataFrame())
    benchmark_close = fetch_benchmark_history(period="5y")

    try:
        book, record = current_book(adj_close, benchmark_close, system)
    except (ValueError, KeyError) as exc:
        st.error(f"Canonical Track Record book is invalid: {exc}")
        return

    if book.empty:
        st.info("The Track Record has no current model book for this system yet.")
        return

    meta = record.get("live_meta", {}) or {}
    book.attrs["as_of"] = meta.get("as_of")
    table = build_portfolio_tracker(
        book, rank_df, float(portfolio_capital), adj_close
    )

    if table.empty:
        st.info("The canonical model book could not be sized.")
        return

    invested = float(table["Invested Value (₹)"].sum())
    current = float(table["Current Value (₹)"].sum())
    cash = max(float(portfolio_capital) - invested, 0.0)
    total_value = current + cash
    pnl = current - invested
    pnl_pct = pnl / invested * 100.0 if invested else np.nan
    day_pnl = float(table["Day P&L (₹)"].sum(skipna=True))
    last_rebalance = meta.get("fill_date")
    as_of = meta.get("as_of")

    with head:
        st.download_button(
            "Export portfolio CSV",
            table.to_csv(index=False).encode(),
            f"portfolio_{ist_now():%Y%m%d}.csv",
            "text/csv",
            key="dl_port_csv",
        )

    kit.readings([
        kit.Reading("Portfolio value", f"₹{total_value:,.0f}", "capital + current holdings"),
        kit.Reading("Invested", f"₹{invested:,.0f}", f"{len(table)} holdings"),
        kit.Reading("Cash", f"₹{cash:,.0f}", f"{cash / portfolio_capital:.1%} of capital"),
        kit.Reading("Total P&L", f"₹{pnl:+,.0f}",
                    "unrealised, model entry to latest close",
                    "up" if pnl >= 0 else "down"),
        kit.Reading("P&L %", "—" if not np.isfinite(pnl_pct) else f"{pnl_pct:+.1f}%",
                    "on invested capital",
                    "" if not np.isfinite(pnl_pct) else ("up" if pnl_pct >= 0 else "down")),
        kit.Reading("Day P&L", f"₹{day_pnl:+,.0f}", "latest close versus previous close",
                    "up" if day_pnl >= 0 else "down"),
    ], "Current model portfolio")

    if as_of is not None or last_rebalance is not None:
        kit.caption(
            (f"Marked as of {pd.Timestamp(as_of):%d %b %Y}" if as_of is not None else "Latest available mark")
            + (f" · last rebalance filled {pd.Timestamp(last_rebalance):%d %b %Y}"
               if last_rebalance is not None else "")
            + " · membership and target weights come from the Track Record."
        )

    display_cols = [
        "Symbol", "Company", "Sector / Industry",
        "Entry Date", "Entry Price", "Current Price", "Shares",
        "Invested Value (₹)", "Current Value (₹)", "P&L (₹)", "P&L %",
        "Weight %", "Target Weight %", "Weight Drift %",
        "Rank at Rebalance", "Rank at Entry", "Current Rank",
        "Holding Days", "1M Return", "3M Return", "6M Return", "12M Return",
        "Status",
    ]
    view = table[[c for c in display_cols if c in table.columns]].copy()
    if "Entry Date" in view.columns:
        view["Entry Date"] = (
            pd.to_datetime(view["Entry Date"], errors="coerce")
            .dt.strftime("%d %b %Y")
            .fillna("—")
        )
    for col in (
        "P&L %",
        "Weight %",
        "Target Weight %",
        "Weight Drift %",
        "1M Return",
        "3M Return",
        "6M Return",
        "12M Return",
    ):
        if col in view.columns:
            view[col] = pd.to_numeric(view[col], errors="coerce").map(
                lambda x: "—" if pd.isna(x) else f"{x:+.1f}%"
            )

    with kit.card(
        "Current holdings",
        "portfolio_current",
        "the same positions recorded by Track Record and used by Actions",
    ):
        render_saas_table(view, max_height=620)

    sector = (
        table.groupby("Sector / Industry", dropna=False)
        .agg(Weight=("Weight %", "sum"), Holdings=("Symbol", "count"))
        .sort_values("Weight", ascending=False)
        .reset_index()
    )
    with kit.card(
        "Exposure by sector", "portfolio_sectors", "current portfolio weight"
    ):
        st.html(
            kit.bar_list(
                [
                    (
                        str(r["Sector / Industry"]),
                        float(r["Weight"]),
                        f"{r['Weight']:.1f}% · {int(r['Holdings'])}",
                        False,
                    )
                    for _, r in sector.iterrows()
                ],
                scale=max(float(sector["Weight"].max()) if not sector.empty else 0.0, 1.0),
            )
        )

    render_saas_table(
        table[["Symbol", "Day P&L (₹)", "P&L (₹)", "Weight Drift %"]].copy(),
        max_height=260,
    )
