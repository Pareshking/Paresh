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


def build_portfolio_history(record: dict, capital: float) -> dict:
    """Scale the canonical Track Record replay into portfolio-level history."""
    equity = pd.to_numeric(pd.Series(record.get("equity_curve", pd.Series(dtype=float))), errors="coerce").dropna()
    benchmark = pd.to_numeric(pd.Series(record.get("benchmark", pd.Series(dtype=float))), errors="coerce").reindex(equity.index).ffill()
    equity_value = equity * float(capital)
    peak = equity_value.cummax()
    drawdown = equity_value / peak - 1.0
    monthly = record.get("monthly", pd.DataFrame())
    trades = record.get("closed_trades", pd.DataFrame())
    tradebook = record.get("tradebook", pd.DataFrame())
    return {
        "equity": equity_value,
        "benchmark": benchmark * float(capital),
        "drawdown": drawdown,
        "max_drawdown": float(drawdown.min()) if not drawdown.empty else float("nan"),
        "monthly": monthly.copy() if isinstance(monthly, pd.DataFrame) else pd.DataFrame(),
        "trades": trades.copy() if isinstance(trades, pd.DataFrame) else pd.DataFrame(),
        "tradebook": tradebook.copy() if isinstance(tradebook, pd.DataFrame) else pd.DataFrame(),
    }

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
            value=2000000,
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

    # Historical portfolio ledger comes from the same canonical Track Record replay.
    history = build_portfolio_history(record, float(portfolio_capital))
    equity = history["equity"]
    benchmark = history["benchmark"]
    drawdown = history["drawdown"]
    monthly = history["monthly"]
    trades = history["trades"]
    tradebook = history["tradebook"]
    current_return = total_value / float(portfolio_capital) - 1.0 if portfolio_capital else np.nan
    closed = trades[trades["Status"] == "Closed"] if not trades.empty and "Status" in trades.columns else trades
    closed_valid = closed[closed["Return %"].notna()] if not closed.empty and "Return %" in closed.columns else closed
    wins = int((closed_valid["Return %"] > 0).sum()) if not closed_valid.empty else 0
    losses = int((closed_valid["Return %"] < 0).sum()) if not closed_valid.empty else 0

    kit.readings([
        kit.Reading("Starting capital", f"₹{portfolio_capital:,.0f}", "fixed model capital"),
        kit.Reading("Current value", f"₹{total_value:,.0f}", "cash + current holdings"),
        kit.Reading("Since start", f"{current_return:+.1%}" if np.isfinite(current_return) else "—", "current book vs ₹20 lakh", "up" if current_return >= 0 else "down"),
        kit.Reading("Closed trades", f"{len(closed_valid)}", f"{wins} winners · {losses} losers"),
        kit.Reading("Max drawdown", "—" if not np.isfinite(history["max_drawdown"]) else f"{history['max_drawdown']:.1%}", "from portfolio equity curve", "down" if np.isfinite(history["max_drawdown"]) and history["max_drawdown"] < 0 else ""),
        kit.Reading("Rebalance periods", f"{len(monthly)}", "completed model periods"),
    ], "Portfolio history")

    history_view = st.segmented_control(
        "Portfolio history",
        ["Equity curve", "Past trades", "Rebalance log", "Month by month", "Drawdown"],
        default="Equity curve", key="portfolio_history_view", label_visibility="collapsed"
    ) or "Equity curve"

    if history_view == "Equity curve":
        with kit.card("Portfolio equity curve", "portfolio_equity", "₹20 lakh starting capital · canonical Track Record replay"):
            if equity.empty:
                st.info("No completed portfolio history is available yet.")
            else:
                kit.growth_chart(
                    [f"{d:%b %Y}" for d in equity.index],
                    equity.tolist(),
                    benchmark.tolist() if not benchmark.empty else None,
                    key="portfolio_equity_curve",
                )
                st.caption("Historical curve ends at the latest completed reporting period; the current book above is marked through the latest available close.")

    elif history_view == "Past trades":
        with kit.card("Past trades", "portfolio_trades", "realised trades plus positions still open at the historical window close"):
            if trades.empty:
                st.info("No historical trades are available yet.")
            else:
                outcome = st.pills("Outcome", ["All", "Winners", "Losers", "Still open"], default="All", key="portfolio_trade_outcome")
                tv = trades.copy()
                if outcome == "Winners":
                    tv = tv[tv["Return %"] > 0]
                elif outcome == "Losers":
                    tv = tv[tv["Return %"] < 0]
                elif outcome == "Still open":
                    tv = tv[tv["Status"] == "Open"]
                cols = [c for c in ["Month", "Symbol", "Entry Date", "Entry Price", "Exit Date", "Exit Price", "Return %", "Holding (Days)", "Reason for Exit", "Status"] if c in tv.columns]
                render_saas_table(tv[cols], max_height=560)
                st.download_button(
                    "Export past trades CSV", tv[cols].to_csv(index=False).encode(),
                    f"portfolio_trades_{ist_now():%Y%m%d}.csv", "text/csv",
                    key="dl_port_trades_csv",
                )

    elif history_view == "Rebalance log":
        with kit.card("Rebalance history", "portfolio_rebalances", "every BUY, SELL and HOLD from the canonical model replay"):
            if tradebook.empty:
                st.info("No rebalance history is available yet.")
            else:
                af = st.pills("Action", ["All", "Buy", "Sell", "Hold"], default="All", key="portfolio_rebalance_action")
                rv = tradebook.copy()
                if af == "Buy":
                    rv = rv[rv["Action"].str.contains("BUY", na=False)]
                elif af == "Sell":
                    rv = rv[rv["Action"].str.contains("SELL", na=False)]
                elif af == "Hold":
                    rv = rv[rv["Action"].str.contains("HOLD", na=False)]
                cols = [c for c in ["Period", "Action", "Symbol", "Price", "Return %", "Weight %", "Reason / Signal"] if c in rv.columns]
                render_saas_table(rv[cols], max_height=560)
                st.download_button(
                    "Export rebalance log CSV", rv[cols].to_csv(index=False).encode(),
                    f"portfolio_rebalance_{ist_now():%Y%m%d}.csv", "text/csv",
                    key="dl_port_rebalance_csv",
                )

    elif history_view == "Month by month":
        with kit.card("Month by month", "portfolio_monthly", "completed portfolio periods from the canonical replay"):
            if monthly.empty:
                st.info("No monthly history is available yet.")
            else:
                mv = monthly.copy()
                for c in ("Period Start", "Period End"):
                    if c in mv.columns:
                        mv[c] = pd.to_datetime(mv[c], errors="coerce").dt.strftime("%d %b %Y")
                cols = [c for c in ["Period Start", "Period End", "Strategy Net", "Benchmark", "Alpha vs Benchmark", "Turnover %", "Cost Drag %", "Buys", "Sells", "Holdings"] if c in mv.columns]
                render_saas_table(mv[cols])
                st.download_button(
                    "Export monthly performance CSV", mv[cols].to_csv(index=False).encode(),
                    f"portfolio_monthly_{ist_now():%Y%m%d}.csv", "text/csv",
                    key="dl_port_monthly_csv",
                )

    else:
        with kit.card("Portfolio drawdown", "portfolio_drawdown", "peak-to-trough decline of portfolio equity"):
            if drawdown.empty:
                st.info("No drawdown history is available yet.")
            else:
                kit.growth_chart(
                    [f"{d:%b %Y}" for d in drawdown.index],
                    drawdown.tolist(),
                    None,
                    key="portfolio_drawdown_curve",
                )
                st.caption(f"Maximum drawdown over the displayed completed history: {history['max_drawdown']:.1%}.")

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
