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
from src.engine.systems import inception, ledger_path
from src.engine.track_record import load_ledger
from src.loaders.price_loader import fetch_benchmark_history
from src.ui import page_kit as kit
from src.ui import system_param
from src.ui.canonical_book import current_book
from src.ui.theme import render_saas_table

PORTFOLIO_STARTING_CAPITAL = 2_000_000.0


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
    # For Nifty 750, Industry is the canonical NSE industry taxonomy.  The
    # app may also carry TradingView sector/industry fields for other systems,
    # but Portfolio exposure must not silently replace the NSE taxonomy here.
    out["Sector / Industry"] = mapped("Industry", "—").replace("", np.nan).fillna("—")
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
        out["Previous Value (₹)"] = out.apply(
            lambda r: float(r["Shares"]) * float(prev.get(r["Symbol"], np.nan))
            if pd.notna(prev.get(r["Symbol"], np.nan)) else np.nan,
            axis=1,
        )
        out["Day P&L %"] = np.where(
            out["Previous Value (₹)"] > 0,
            out["Day P&L (₹)"] / out["Previous Value (₹)"] * 100.0,
            np.nan,
        )
    else:
        out["Day P&L (₹)"] = np.nan
        out["Previous Value (₹)"] = np.nan
        out["Day P&L %"] = np.nan

    out["Status"] = "Held"
    return out.sort_values(
        ["Current Value (₹)", "Symbol"], ascending=[False, True]
    ).reset_index(drop=True)


def build_portfolio_history(
    record: dict,
    capital: float,
    ledger: dict | None = None,
    live_meta: dict | None = None,
) -> dict:
    """Build frozen history plus the current live month-to-date point."""
    months = (ledger or {}).get("months", {})
    ordered = sorted(months)
    strategy_value = float(capital)
    benchmark_value = float(capital)
    equity_dates = []
    equity_rows = []
    benchmark_dates = []
    benchmark_rows = []
    monthly_rows = []
    if ordered:
        first = pd.Period(ordered[0], freq="M")
        base = first.start_time - pd.Timedelta(days=1)
        equity_dates.append(base)
        equity_rows.append(strategy_value)
        benchmark_dates.append(base)
        benchmark_rows.append(benchmark_value)
        for key in ordered:
            entry = months[key] or {}
            s_ret = pd.to_numeric(entry.get("strategy"), errors="coerce")
            b_ret = pd.to_numeric(entry.get("benchmark"), errors="coerce")
            if pd.notna(s_ret):
                strategy_value *= 1.0 + float(s_ret)
            if pd.notna(b_ret):
                benchmark_value *= 1.0 + float(b_ret)
            period = pd.Period(key, freq="M")
            equity_dates.append(period.end_time)
            equity_rows.append(strategy_value)
            benchmark_dates.append(period.end_time)
            benchmark_rows.append(benchmark_value)
            monthly_rows.append({
                "Month": period.strftime("%b %Y"),
                "Period": key,
                "Strategy Net": float(s_ret) if pd.notna(s_ret) else np.nan,
                "Benchmark": float(b_ret) if pd.notna(b_ret) else np.nan,
                "Alpha vs Benchmark": float(s_ret - b_ret) if pd.notna(s_ret) and pd.notna(b_ret) else np.nan,
                "Origin": "Recorded" if entry.get("origin") == "recorded" else "Backfilled",
                "Universe": "Point-in-time" if entry.get("universe") == "point_in_time" else "Current list",
                "Frozen On": entry.get("finalized_on") or "—",
                "Priced From": entry.get("data_as_of") or "—",
                "Config": entry.get("config") or "—",
            })
    equity = pd.Series(equity_rows, index=pd.DatetimeIndex(equity_dates), dtype=float)
    benchmark = pd.Series(benchmark_rows, index=pd.DatetimeIndex(benchmark_dates), dtype=float)

    # The ledger deliberately stops at the last closed month. Portfolio must
    # also show the current live month-to-date point, otherwise its
    # "since-inception" figure lags the same live record used by Track Record.
    live_meta = live_meta or {}
    live_s = pd.to_numeric(live_meta.get("strategy_mtd"), errors="coerce")
    live_b = pd.to_numeric(live_meta.get("benchmark_mtd"), errors="coerce")
    live_period_raw = live_meta.get("mtd_period")
    if pd.notna(live_s) and live_period_raw:
        live_period = pd.Period(live_period_raw, freq="M")
        live_end = live_period.end_time
        if live_end > equity.index[-1] if not equity.empty else True:
            base_value = float(equity.iloc[-1]) if not equity.empty else float(capital)
            base_benchmark = float(benchmark.iloc[-1]) if not benchmark.empty else float(capital)
            equity = pd.concat([equity, pd.Series([base_value * (1.0 + float(live_s))], index=[live_end])])
            if pd.notna(live_b):
                benchmark = pd.concat([benchmark, pd.Series([base_benchmark * (1.0 + float(live_b))], index=[live_end])])
    peak = equity.cummax()
    drawdown = equity / peak - 1.0
    closed = record.get("closed_trades")
    tradebook = record.get("tradebook")
    return {
        "equity": equity,
        "benchmark": benchmark,
        "drawdown": drawdown,
        "max_drawdown": float(drawdown.min()) if not drawdown.empty else float("nan"),
        "monthly": pd.DataFrame(monthly_rows),
        "trades": closed.copy() if isinstance(closed, pd.DataFrame) else pd.DataFrame(),
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
    """Render the canonical ₹20 lakh model portfolio as a portfolio dashboard."""
    del sector_cap, stock_cap, vol_target_on, vol_target_val, liquidity_floor_cr, traded_value

    capital = PORTFOLIO_STARTING_CAPITAL
    system = system_param.current() or SYSTEM_750
    prices = getattr(calc, "prices", pd.DataFrame())
    benchmark_close = fetch_benchmark_history(period="5y")

    try:
        book, record = current_book(prices, benchmark_close, system)
    except (ValueError, KeyError) as exc:
        st.error(f"Canonical Track Record book is invalid: {exc}")
        return
    if book.empty:
        st.info("The Track Record has no current model book for this system yet.")
        return

    meta = record.get("live_meta", {}) or {}
    book.attrs["as_of"] = meta.get("as_of")
    table = build_portfolio_tracker(book, rank_df, capital, prices)
    if table.empty:
        st.info("The canonical model book could not be sized.")
        return

    invested = float(table["Invested Value (₹)"].sum())
    current = float(table["Current Value (₹)"].sum())
    cash = max(capital - invested, 0.0)
    value = current + cash
    pnl = current - invested
    pnl_pct = pnl / invested * 100.0 if invested else np.nan
    day_pnl = float(table["Day P&L (₹)"].sum(skipna=True))
    previous_value = float(table["Previous Value (₹)"].sum(skipna=True))
    day_pnl_pct = day_pnl / previous_value * 100.0 if previous_value > 0 else np.nan
    exposure = current / value * 100.0 if value else 0.0
    # Mark/fill dates remain available through live_meta and the canonical book;
    # the compact header no longer duplicates them.
    n_holdings = len(table)

    try:
        ledger = load_ledger(ledger_path(system), inception(system))
    except (ValueError, OSError) as exc:
        st.error(f"Portfolio Track Record could not be read: {exc}")
        return

    history = build_portfolio_history(record, capital, ledger, meta)
    equity = history["equity"]
    benchmark = history["benchmark"]
    drawdown = history["drawdown"]
    monthly = history["monthly"]
    trades = history["trades"]
    tradebook = history["tradebook"]

    closed = trades[trades["Status"] == "Closed"] if not trades.empty and "Status" in trades.columns else trades
    closed_valid = closed[closed["Return %"].notna()] if not closed.empty and "Return %" in closed.columns else closed
    wins = int((closed_valid["Return %"] > 0).sum()) if not closed_valid.empty else 0
    losses = int((closed_valid["Return %"] < 0).sum()) if not closed_valid.empty else 0
    historical_return = float(equity.iloc[-1] / capital - 1.0) if not equity.empty else np.nan
    benchmark_return = float(benchmark.iloc[-1] / capital - 1.0) if not benchmark.empty else np.nan

    head = kit.page_head(
        "Portfolio",
        "₹20 lakh model portfolio · current holdings, exposure and performance.",
        actions=True,
    )
    with head:
        st.download_button(
            "Export holdings CSV",
            table.to_csv(index=False).encode(),
            f"portfolio_{ist_now():%Y%m%d}.csv",
            "text/csv",
            key="dl_port_csv_v2",
        )

    # Primary readings answer the three questions users need first:
    # how much is here, how is the current book doing, and what happened today.
    kit.readings([
        kit.Reading("Portfolio value", f"₹{value:,.0f}", "₹20 lakh starting capital"),
        kit.Reading(
            "Current-book P&L",
            "—" if not np.isfinite(pnl_pct) else f"{pnl_pct:+.1f}%",
            f"₹{pnl:+,.0f} · unrealised",
            "" if not np.isfinite(pnl_pct) else ("up" if pnl >= 0 else "down"),
        ),
        kit.Reading(
            "Day P&L",
            f"₹{day_pnl:+,.0f} ({day_pnl_pct:+.1f}%)" if np.isfinite(day_pnl_pct) else f"₹{day_pnl:+,.0f}",
            "latest close vs previous close",
            "up" if day_pnl >= 0 else "down",
        ),
        kit.Reading("Cash", f"₹{cash:,.0f}", f"{100.0 - exposure:.1f}% of portfolio"),
    ], "Portfolio snapshot")
    as_of_text = meta.get("as_of") or "latest available close"
    as_of_display = as_of_text if isinstance(as_of_text, str) else pd.Timestamp(as_of_text).strftime("%d %b %Y")
    st.caption(
        f"Marked {as_of_display} · {n_holdings} positions · "
        f"{exposure:.1f}% invested · ₹{invested:,.0f} invested"
    )

    # One canonical table; the columns users scan first come first.
    display_cols = [
        "Symbol", "Company", "Sector / Industry", "Current Price",
        "P&L (₹)", "P&L %", "Weight %", "Target Weight %",
        "Weight Drift %", "Day P&L (₹)",
        "Current Value (₹)", "Shares", "Day P&L %", "Entry Date",
        "Entry Price", "Invested Value (₹)", "Previous Value (₹)",
        "Holding Days", "Rank at Rebalance", "Rank at Entry", "Current Rank",
        "1M Return", "3M Return", "6M Return", "12M Return", "Status",
    ]
    current_view = table[[c for c in display_cols if c in table.columns]].copy()
    if "Entry Date" in current_view.columns:
        current_view["Entry Date"] = pd.to_datetime(current_view["Entry Date"], errors="coerce").dt.strftime("%d %b %Y").fillna("—")
    for col in ("P&L %", "Weight %", "Target Weight %", "Weight Drift %", "1M Return", "3M Return", "6M Return", "12M Return"):
        if col in current_view.columns:
            current_view[col] = pd.to_numeric(current_view[col], errors="coerce")

    with kit.card(
        "Current book",
        "portfolio_current",
        f"{n_holdings} positions · primary metrics first · swipe horizontally for detail",
    ):
        render_saas_table(current_view, max_height=620, variant="portfolio")

    sector = table.groupby("Sector / Industry", dropna=False).agg(
        Weight=("Weight %", "sum"), Holdings=("Symbol", "count")
    ).sort_values("Weight", ascending=False).reset_index()
    largest_industry = (
        f"Largest industry exposure · {sector.iloc[0]['Weight']:.1f}%"
        if not sector.empty else "NSE industry exposure"
    )
    with kit.card("Current exposure", "portfolio_exposure", largest_industry):
        st.html(kit.bar_list([
            (str(row["Sector / Industry"]), float(row["Weight"]), f"{row['Weight']:.1f}% · {int(row['Holdings'])} holdings", False)
            for _, row in sector.iterrows()
        ], scale=max(float(sector["Weight"].max()) if not sector.empty else 0.0, 1.0)))

    history_group = st.segmented_control(
        "Portfolio history",
        ["Performance", "Activity"],
        default="Performance",
        key="portfolio_history_group_v3",
        label_visibility="collapsed",
    ) or "Performance"
    if history_group == "Performance":
        history_tab = st.segmented_control(
            "Performance view",
            ["Overview", "Equity", "Drawdown", "Monthly"],
            default="Overview",
            key="portfolio_history_performance_v3",
            label_visibility="collapsed",
        ) or "Overview"
    else:
        history_tab = st.segmented_control(
            "Activity view",
            ["Trades", "Rebalances"],
            default="Trades",
            key="portfolio_history_activity_v3",
            label_visibility="collapsed",
        ) or "Trades"

    with kit.card("Portfolio history", "portfolio_history_header", "performance history · current month marked to latest close"):
        st.caption(
            f"Inception · {inception(system).strftime('%b %Y')}  · "
            f"₹{capital:,.0f} starting capital  · {len(monthly)} completed months"
        )

    if history_tab == "Overview":
        with kit.card(
            "Performance overview",
            "portfolio_performance_overview",
            "since inception · completed months plus the current month-to-date mark",
        ):
            if equity.empty:
                st.info("No completed portfolio history is available yet.")
            else:
                a, b, c, d = st.columns(4)
                with a:
                    st.metric("Ending value", f"₹{equity.iloc[-1]:,.0f}")
                with b:
                    st.metric("Since inception", f"{historical_return:+.1%}" if np.isfinite(historical_return) else "—")
                with c:
                    st.metric("Benchmark", f"{benchmark_return:+.1%}" if np.isfinite(benchmark_return) else "—")
                with d:
                    st.metric("Max drawdown", f"{history['max_drawdown']:.1%}" if np.isfinite(history["max_drawdown"]) else "—")
                st.caption(
                    "Since inception compounds the frozen record through the latest completed month and the current live month-to-date return. "
                    "Current-book P&L is the unrealised return on today's holdings, so it can differ."
                )

    elif history_tab == "Equity":
        with kit.card(
            "Equity curve",
            "portfolio_equity",
            "₹20 lakh starting point · strategy vs benchmark · latest month marked to date",
        ):
            if equity.empty:
                st.info("No completed portfolio history is available yet.")
            else:
                kit.equity_chart(
                    [d.strftime("%b %Y") for d in equity.index],
                    equity.tolist(),
                    benchmark.tolist() if not benchmark.empty else None,
                    key="portfolio_equity_curve_v2",
                )
                a, b, c, d = st.columns(4)
                with a:
                    st.metric("Ending value", f"₹{equity.iloc[-1]:,.0f}")
                with b:
                    st.metric("Since inception", f"{historical_return:+.1%}" if np.isfinite(historical_return) else "—")
                with c:
                    st.metric("Benchmark", f"{benchmark_return:+.1%}" if np.isfinite(benchmark_return) else "—")
                with d:
                    st.metric("Max drawdown", f"{history['max_drawdown']:.1%}" if np.isfinite(history["max_drawdown"]) else "—")
                st.caption("Completed months come from the recorded performance history; the final point is the current month-to-date mark.")

    elif history_tab == "Trades":
        with kit.card("Past trades", "portfolio_trades", "closed trades plus positions still open at the historical window close"):
            if trades.empty:
                st.info("No historical trades are available yet.")
            else:
                outcome = st.pills("Outcome", ["All", "Winners", "Losers", "Still open"], default="All", key="portfolio_trade_outcome_v2")
                tv = trades.copy()
                if outcome == "Winners":
                    tv = tv[tv["Return %"] > 0]
                elif outcome == "Losers":
                    tv = tv[tv["Return %"] < 0]
                elif outcome == "Still open":
                    tv = tv[tv["Status"] == "Open"]
                cols = [c for c in ["Symbol", "Status", "Entry Date", "Entry Price", "Exit Date", "Exit Price", "Return %", "Holding (Days)", "Reason for Exit"] if c in tv.columns]
                render_saas_table(tv[cols], max_height=600)
                st.caption(f"{len(closed_valid)} closed trades · {wins} winners · {losses} losers")
                st.download_button("Export past trades CSV", tv[cols].to_csv(index=False).encode(), f"portfolio_trades_{ist_now():%Y%m%d}.csv", "text/csv", key="dl_port_trades_csv_v2")

    elif history_tab == "Rebalances":
        with kit.card("Rebalance history", "portfolio_rebalances", "every BUY, SELL and HOLD from the canonical model replay"):
            if tradebook.empty:
                st.info("No rebalance history is available yet.")
            else:
                action = st.pills("Action", ["All", "Buy", "Sell", "Hold"], default="All", key="portfolio_rebalance_action_v2")
                rv = tradebook.copy()
                if action == "Buy":
                    rv = rv[rv["Action"].str.contains("BUY", na=False)]
                elif action == "Sell":
                    rv = rv[rv["Action"].str.contains("SELL", na=False)]
                elif action == "Hold":
                    rv = rv[rv["Action"].str.contains("HOLD", na=False)]
                cols = [c for c in ["Period", "Action", "Symbol", "Price", "Weight %", "Return %", "Reason / Signal"] if c in rv.columns]
                render_saas_table(rv[cols], max_height=600)
                st.download_button("Export rebalance CSV", rv[cols].to_csv(index=False).encode(), f"portfolio_rebalances_{ist_now():%Y%m%d}.csv", "text/csv", key="dl_port_rebalance_csv_v2")

    elif history_tab == "Monthly":
        with kit.card("Month-by-month performance", "portfolio_monthly", "frozen monthly record · no current-month partial return"):
            if monthly.empty:
                st.info("No monthly history is available yet.")
            else:
                cols = [c for c in ["Month", "Strategy Net", "Benchmark", "Alpha vs Benchmark", "Origin", "Priced From", "Frozen On", "Universe"] if c in monthly.columns]
                render_saas_table(monthly[cols], max_height=600)
                st.download_button("Export monthly performance CSV", monthly[cols].to_csv(index=False).encode(), f"portfolio_monthly_{ist_now():%Y%m%d}.csv", "text/csv", key="dl_port_monthly_csv_v2")

    elif history_tab == "Drawdown":
        with kit.card("Drawdown", "portfolio_drawdown", "peak-to-trough decline in portfolio value"):
            if drawdown.empty:
                st.info("No drawdown history is available yet.")
            else:
                kit.drawdown_chart([d.strftime("%b %Y") for d in drawdown.index], drawdown.tolist(), key="portfolio_drawdown_curve_v2")
                st.caption(f"Maximum drawdown including the current month-to-date point: {history['max_drawdown']:.1%}.")

