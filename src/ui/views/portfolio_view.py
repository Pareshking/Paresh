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
from src.engine.track_record import build_combined_grid, load_ledger
from src.loaders.price_loader import fetch_benchmark_history
from src.ui import page_kit as kit
from src.ui import system_param
from src.ui.canonical_book import current_book
from src.ui.charts import render_correlation_heatmap
from src.ui.theme import render_saas_table
from src.ui.views.qualified_view import correlation, correlation_note
from src.ui.views.track_record_view import grid_display, render_record_sections

PORTFOLIO_STARTING_CAPITAL = 2_000_000.0


def live_month_state(live_period: str | None, today: pd.Timestamp | None = None) -> str:
    """Is the latest marked month still running, or closed but not yet frozen?

    "mtd"     the marked month is the calendar month in India now.
    "closed"  the calendar has moved on (1 Oct, with the 30 Sep close the
              latest price): the marked month is finished, but the Track
              Record freezes it only in the first days of the next month.
    "none"    nothing is marked.

    Presentation only: the ledger, the book and every return are unchanged.
    """
    if not live_period:
        return "none"
    now = pd.Timestamp(today if today is not None else ist_now().date())
    return "mtd" if pd.Period(live_period, freq="M") >= now.to_period("M") else "closed"


def _month_labels(live_period: str | None, state: str, today: pd.Timestamp | None = None) -> dict:
    """The words for the marked month and for the month now running."""
    now = pd.Timestamp(today if today is not None else ist_now().date())
    marked = pd.Period(live_period, freq="M").strftime("%b") if live_period else ""
    if state == "closed":
        return {
            "prefix": f"{marked} (closed)",
            "badge": "CLOSED",
            "next": f"{now.to_period('M').strftime('%b')} MTD",
        }
    return {"prefix": f"{marked} MTD" if marked else "MTD", "badge": "MTD", "next": ""}


def _no_return_clause(labels: dict) -> str:
    marked = labels["prefix"].split(" ")[0]
    return (f" {marked} MTD has no return yet: the new book was bought at the first close of "
            "the month and starts accruing the next session.")


def _calendar_note(labels: dict, live_period: str | None, state: str, pending: bool = False) -> str:
    """A note under the calendar only when the live month needs one (owner, 2026-10-07:
    the quarter / FY convention and "live month-to-date" are not needed)."""
    if not live_period:
        return ""
    marked = labels["prefix"].split(" ")[0]
    if state == "closed":
        return f"{marked} is closed, not yet frozen."
    if pending:
        return _no_return_clause(labels).strip()
    return ""


def _compound_returns(values: list[float]) -> float | None:
    """Compound a sequence of period returns into one period return."""
    valid = [float(v) for v in values if pd.notna(v)]
    if not valid:
        return None
    return float(np.prod([1.0 + v for v in valid]) - 1.0)


def _benchmark_returns_from_daily(
    benchmark_close: pd.Series | None,
    as_of: pd.Timestamp,
    inception_date: pd.Timestamp,
) -> tuple[float, float, float]:
    """Calculate benchmark day, MTD and inception returns from daily closes.

    These are presentation/accounting facts, not backtest outputs. Every value
    is measured from the same canonical NIFTY 500 daily series and the same
    portfolio as-of session.
    """
    if benchmark_close is None or benchmark_close.empty or pd.isna(as_of):
        return np.nan, np.nan, np.nan
    s = pd.to_numeric(benchmark_close, errors="coerce").dropna().sort_index()
    s = s.loc[:pd.Timestamp(as_of)]
    if len(s) < 2:
        return np.nan, np.nan, np.nan

    day = float(s.iloc[-1] / s.iloc[-2] - 1.0)
    month_start = pd.Timestamp(as_of).normalize().replace(day=1)
    prior_month = s.loc[s.index < month_start]
    mtd_base = float(prior_month.iloc[-1]) if not prior_month.empty else np.nan
    mtd = float(s.iloc[-1] / mtd_base - 1.0) if np.isfinite(mtd_base) and mtd_base > 0 else np.nan

    if isinstance(inception_date, pd.Period):
        inception_ts = inception_date.start_time.normalize()
    else:
        inception_ts = pd.Timestamp(inception_date).normalize()
    base = s.loc[s.index < inception_ts]
    if base.empty:
        base = s.loc[s.index <= inception_ts]
    inception_base = float(base.iloc[-1]) if not base.empty else float(s.iloc[0])
    total = float(s.iloc[-1] / inception_base - 1.0) if inception_base > 0 else np.nan
    return day, mtd, total


def build_portfolio_tracker(
    book: pd.DataFrame,
    rank_df: pd.DataFrame,
    capital: float,
    prices: pd.DataFrame | None = None,
    equity_curve: pd.Series | None = None,
) -> pd.DataFrame:
    """Enrich the canonical Track Record book with portfolio accounting.

    Membership and target weights come only from the canonical book. Ranking
    data supplies labels/current observations; prices are used only for day-P&L.
    When the account equity curve is supplied, new positions are sized from the
    account value immediately before their fill, and current weights are marked
    against the same account value shown in performance history.
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
    # Shares are fixed at the original fill. A later rebalance may change the
    # target weight of a retained holding, but must never retroactively resize
    # its historical entry quantity.
    entry_weight = (
        pd.to_numeric(out["Entry Weight %"], errors="coerce")
        if "Entry Weight %" in out.columns
        else pd.Series(np.nan, index=out.index)
    )
    out["Entry Weight %"] = entry_weight.where(entry_weight.notna(), out["Target Weight %"])
    out["Entry Price"] = pd.to_numeric(out["Entry Price"], errors="coerce")
    out["Current Price"] = pd.to_numeric(out["Price Now"], errors="coerce")
    entry = pd.to_datetime(out["Entry Date"], errors="coerce")

    # The account compounds between rebalances. Size a position from account
    # equity immediately before its fill, rather than repeatedly pretending
    # every month's holdings were bought with the original starting capital.
    # The baseline point before inception ensures the first book starts at the
    # configured starting capital. Keep the fixed-capital fallback for callers
    # that only use this helper in isolated presentation tests.
    curve = pd.Series(dtype=float)
    if isinstance(equity_curve, pd.Series) and not equity_curve.empty:
        curve = pd.to_numeric(equity_curve, errors="coerce").dropna().sort_index()

    def _capital_before_fill(fill_date) -> float:
        if pd.isna(fill_date) or curve.empty:
            return float(capital)
        prior = curve.loc[curve.index < pd.Timestamp(fill_date)]
        return float(prior.iloc[-1]) if not prior.empty else float(capital)

    out["Capital at Entry (₹)"] = entry.map(_capital_before_fill).astype(float)
    # The model trades the whole book back to its target weights at every rebalance, so the
    # shares held today are those the latest fill bought: account value before that fill x
    # target weight / price at that fill. Sizing a retained name from its first entry would
    # let winners outgrow the account (holdings above 100% of it, negative cash).
    fill = pd.to_datetime(book.attrs.get("fill_date"), errors="coerce")
    fill_px = pd.Series(np.nan, index=out.index)
    if pd.notna(fill) and prices is not None and not prices.empty:
        hist = prices.reindex(columns=out["Symbol"].tolist()).ffill().loc[:fill]
        if not hist.empty:
            fill_px = out["Symbol"].map(pd.to_numeric(hist.iloc[-1], errors="coerce"))
    if fill_px.notna().any():
        base = _capital_before_fill(fill)
        size_px = fill_px.where(fill_px.notna(), out["Entry Price"])
        out["Shares"] = (
            (base * out["Target Weight %"] / 100.0) / size_px.replace(0, np.nan)
        ).fillna(0.0).apply(np.floor).astype(int)
    else:
        out["Shares"] = (
            (out["Capital at Entry (₹)"] * out["Entry Weight %"] / 100.0)
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
    total_value = (
        float(curve.iloc[-1])
        if not curve.empty and float(curve.iloc[-1]) > 0
        else total_current + max(float(capital) - total_invested, 0.0)
    )
    out["Weight %"] = np.where(
        total_value > 0, out["Current Value (₹)"] / total_value * 100.0, 0.0
    )
    out["Weight Drift %"] = out["Weight %"] - out["Target Weight %"]

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
    # Current Book is presented by open-position P&L %: strongest return first.
    # Sort the numeric field, not its formatted display string.
    return out.sort_values(
        ["P&L %", "Symbol"], ascending=[False, True], na_position="last"
    ).reset_index(drop=True)


def _daily_path(replay: pd.Series | None, months: dict, key: str, capital: float) -> pd.Series:
    """Daily account value through the frozen months.

    The ledger gives one return per month; the backtest replay gives the path inside it.
    Each month's replay path is bent so it ends exactly on the ledger's month return
    (frozen months are the record), then chained from the previous month-end value.
    A month the replay does not cover contributes only its month-end point.
    """
    ordered = sorted(months)
    if not ordered:
        return pd.Series(dtype=float)
    rp = pd.to_numeric(replay, errors="coerce").dropna() if replay is not None else pd.Series(dtype=float)
    if not rp.empty:
        rp = rp[~rp.index.duplicated()].sort_index()
    first = pd.Period(ordered[0], freq="M")
    dates = [first.start_time - pd.Timedelta(days=1)]
    values = [float(capital)]
    value = float(capital)
    for m in ordered:
        period = pd.Period(m, freq="M")
        ret = pd.to_numeric((months[m] or {}).get(key), errors="coerce")
        end_value = value * (1.0 + float(ret)) if pd.notna(ret) else value
        days = rp.loc[period.start_time:period.end_time] if not rp.empty else rp
        before = rp.loc[:period.start_time - pd.Timedelta(days=1)] if not rp.empty else rp
        prev = float(before.iloc[-1]) if not before.empty else (float(days.iloc[0]) if len(days) else np.nan)
        if len(days) >= 2 and np.isfinite(prev) and prev > 0 and pd.notna(ret):
            ratio_end = float(days.iloc[-1]) / prev
            fix = (1.0 + float(ret)) / ratio_end if ratio_end > 0 else 1.0
            n = len(days)
            for k, (d, v) in enumerate(days.items(), start=1):
                dates.append(pd.Timestamp(d))
                values.append(value * (float(v) / prev) * fix ** (k / n))
            values[-1] = end_value
        else:
            dates.append(period.end_time)
            values.append(end_value)
        value = end_value
    return pd.Series(values, index=pd.DatetimeIndex(dates), dtype=float)


def build_portfolio_history(
    record: dict,
    capital: float,
    ledger: dict | None = None,
    live_meta: dict | None = None,
    today: pd.Timestamp | None = None,
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
    monthly_grid_rows = []
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

    monthly_grid_rows = list(monthly_rows)
    live_period_key = None
    live_mtd = {"strategy": np.nan, "benchmark": np.nan}

    # The ledger deliberately stops at the last closed month. Portfolio must
    # also show the current live month-to-date point, otherwise its
    # "since-inception" figure lags the same live record used by Track Record.
    live_meta = live_meta or {}
    live_s = pd.to_numeric(live_meta.get("strategy_mtd"), errors="coerce")
    live_b = pd.to_numeric(live_meta.get("benchmark_mtd"), errors="coerce")
    live_mtd["strategy"] = live_s
    live_mtd["benchmark"] = live_b
    live_period_raw = live_meta.get("mtd_period")
    if live_period_raw and not pd.notna(live_s):
        # The first session of a month: the new book is bought at its close, so there is a
        # month and a book but no return yet. Name the month so the page says so, and add
        # no point to the equity curve or the calendar grid.
        live_period_key = str(pd.Period(live_period_raw, freq="M"))
    if pd.notna(live_s) and live_period_raw:
        live_period = pd.Period(live_period_raw, freq="M")
        live_period_key = str(live_period)
        live_state = live_month_state(live_period_key, today)
        live_end = live_period.end_time
        if live_end > equity.index[-1] if not equity.empty else True:
            base_value = float(equity.iloc[-1]) if not equity.empty else float(capital)
            base_benchmark = float(benchmark.iloc[-1]) if not benchmark.empty else float(capital)
            equity = pd.concat([equity, pd.Series([base_value * (1.0 + float(live_s))], index=[live_end])])
            if pd.notna(live_b):
                benchmark = pd.concat([benchmark, pd.Series([base_benchmark * (1.0 + float(live_b))], index=[live_end])])
            if pd.notna(live_s) or pd.notna(live_b):
                monthly_grid_rows.append({
                    "Month": live_period.strftime("%b %Y"),
                    "Period": str(live_period),
                    "Strategy Net": float(live_s) if pd.notna(live_s) else np.nan,
                    "Benchmark": float(live_b) if pd.notna(live_b) else np.nan,
                    "Alpha vs Benchmark": float(live_s - live_b) if pd.notna(live_s) and pd.notna(live_b) else np.nan,
                    "Origin": "Live MTD" if live_state == "mtd" else "Closed, awaiting freeze",
                    "Universe": "Current list",
                    "Frozen On": "—",
                    "Priced From": live_meta.get("as_of") or "—",
                    "Config": "Live month-to-date" if live_state == "mtd" else "Closed month, not yet frozen",
                })
    equity_daily = _daily_path(record.get("equity_curve"), months, "strategy", capital)
    benchmark_daily = _daily_path(record.get("benchmark"), months, "benchmark", capital)
    peak = equity.cummax()
    drawdown = equity / peak - 1.0
    closed = record.get("closed_trades")
    tradebook = record.get("tradebook")
    return {
        "equity": equity,
        "benchmark": benchmark,
        "equity_daily": equity_daily,
        "benchmark_daily": benchmark_daily,
        "drawdown": drawdown,
        "max_drawdown": float(drawdown.min()) if not drawdown.empty else float("nan"),
        "monthly": pd.DataFrame(monthly_rows),
        "monthly_grid": pd.DataFrame(monthly_grid_rows),
        "mtd_period": live_period_key,
        "mtd_state": live_month_state(live_period_key, today),
        # Account-level cumulative returns are derived from the exact equity
        # series displayed on this page. They therefore chain the same frozen
        # months plus the same live/closed-awaiting-freeze month as Track Record.
        "strategy_total_return": (
            float(equity.iloc[-1] / capital - 1.0)
            if not equity.empty and capital > 0 else np.nan
        ),
        "benchmark_total_return": (
            float(benchmark.iloc[-1] / capital - 1.0)
            if not benchmark.empty and capital > 0 else np.nan
        ),
        "strategy_mtd": float(live_mtd["strategy"]) if pd.notna(live_mtd["strategy"]) else np.nan,
        "benchmark_mtd": float(live_mtd["benchmark"]) if pd.notna(live_mtd["benchmark"]) else np.nan,
        "trades": closed.copy() if isinstance(closed, pd.DataFrame) else pd.DataFrame(),
        "tradebook": tradebook.copy() if isinstance(tradebook, pd.DataFrame) else pd.DataFrame(),
    }

def _daily_with_live(history: dict, table: pd.DataFrame, prices: pd.DataFrame | None, meta: dict,
                     benchmark_close: pd.Series | None, value: float, current: float):
    """The daily curves: frozen months, then the live month from today's holdings.

    The live month is the sized holdings marked each session since the latest fill, plus
    the cash residual, so its last point is the account value shown at the top.
    Falls back to the month-end curve if no daily path exists.
    """
    eq = history["equity_daily"]
    bm = history["benchmark_daily"]
    if len(eq) < 2:
        return history["equity"], history["benchmark"]
    fill = pd.to_datetime(meta.get("fill_date"), errors="coerce")
    if pd.notna(fill) and prices is not None and not prices.empty and not table.empty:
        px = prices.reindex(columns=table["Symbol"].tolist()).ffill().loc[fill:]
        px = px[px.index > eq.index[-1]]
        if len(px):
            shares = table.set_index("Symbol")["Shares"].reindex(px.columns).fillna(0.0)
            cash = float(value) - float(current)
            live = (px * shares).sum(axis=1) + cash
            eq = pd.concat([eq, live])
            if benchmark_close is not None and len(benchmark_close):
                bc = pd.to_numeric(benchmark_close, errors="coerce").dropna()
                base = bc.loc[:history["equity_daily"].index[-1]]
                if len(base) and len(bm):
                    ratio = bc.reindex(live.index, method="ffill") / float(base.iloc[-1])
                    bm = pd.concat([bm, (ratio * float(bm.iloc[-1])).dropna()])
    return eq[~eq.index.duplicated()], bm[~bm.index.duplicated()]


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
    book.attrs["fill_date"] = meta.get("fill_date")

    # The whole Portfolio page must describe one market session. The canonical
    # Track Record sets the common strategy/benchmark as-of date; every
    # benchmark reading below is clipped to that same date.
    _common_as_of = pd.to_datetime(meta.get("as_of"), errors="coerce")
    if pd.notna(_common_as_of):
        # The canonical book may deliberately stop before the newest raw price
        # row. Keep every Portfolio-derived reading on that same session:
        # current marks, day P&L, correlation and performance charts all use
        # this clipped frame rather than silently mixing dates.
        prices = prices.loc[:_common_as_of]
        if benchmark_close is not None:
            benchmark_close = pd.to_numeric(benchmark_close, errors="coerce").dropna()
            benchmark_close = benchmark_close.loc[:_common_as_of]

    try:
        ledger = load_ledger(ledger_path(system), inception(system))
    except (ValueError, OSError) as exc:
        st.error(f"Portfolio Track Record could not be read: {exc}")
        return

    history = build_portfolio_history(record, capital, ledger, meta)
    equity = history["equity"]
    table = build_portfolio_tracker(book, rank_df, capital, prices, equity_curve=equity)
    if table.empty:
        st.info("The canonical model book could not be sized.")
        return

    invested = float(table["Invested Value (₹)"].sum())
    current = float(table["Current Value (₹)"].sum())
    # Total account value is sourced from the same compounded ledger/replay
    # series as Track Record. Cash is the residual after marking current
    # positions, so realized P&L from sold positions is not lost.
    value = float(equity.iloc[-1]) if not equity.empty else float(capital)
    cash = value - current
    pnl = current - invested
    pnl_pct = pnl / invested * 100.0 if invested else np.nan
    day_pnl = float(table["Day P&L (₹)"].sum(skipna=True))
    previous_value = float(table["Previous Value (₹)"].sum(skipna=True))
    day_pnl_pct = day_pnl / previous_value * 100.0 if previous_value > 0 else np.nan
    benchmark_day_pct, benchmark_mtd_daily, benchmark_total_daily = _benchmark_returns_from_daily(
        benchmark_close, _common_as_of, inception(system)
    )
    # Mark/fill dates remain available through live_meta and the canonical book;
    # the compact header no longer duplicates them.
    n_holdings = len(table)
    monthly_grid = history["monthly_grid"]
    mtd_period = history["mtd_period"]
    mtd_state = history["mtd_state"]
    labels = _month_labels(mtd_period, mtd_state)
    strategy_mtd = history["strategy_mtd"]
    # Benchmark return is calculated directly from the same daily NIFTY 500
    # closes used by the benchmark loader, never from backtest compounding.
    benchmark_mtd = benchmark_mtd_daily
    trades = history["trades"]
    tradebook = history["tradebook"]

    closed = trades[trades["Status"] == "Closed"] if not trades.empty and "Status" in trades.columns else trades
    closed_valid = closed[closed["Return %"].notna()] if not closed.empty and "Return %" in closed.columns else closed
    wins = int((closed_valid["Return %"] > 0).sum()) if not closed_valid.empty else 0
    losses = int((closed_valid["Return %"] < 0).sum()) if not closed_valid.empty else 0

    kit.page_head("Portfolio", "")

    # Frozen Portfolio KPI design: six centered cards, with benchmark
    # comparisons shown as a second layer only where a comparable period exists.
    kit.readings([
        kit.Reading(
            "Portfolio value",
            f"₹{value:,.0f}",
            f"Invested: ₹{capital:,.0f}",
        ),
        kit.Reading(
            "Since inception",
            kit.pct(history["strategy_total_return"]),
            f"NIFTY 500 {kit.pct(benchmark_total_daily)}",
            "up" if history["strategy_total_return"] >= 0 else "down",
        ),
        kit.Reading(
            "Unrealised P&L",
            "—" if not np.isfinite(pnl_pct) else f"{pnl_pct:+.1f}%",
            "",
            "" if not np.isfinite(pnl_pct) else ("up" if pnl >= 0 else "down"),
        ),
        kit.Reading(
            "Day P&L",
            "—" if not np.isfinite(day_pnl_pct) else f"{day_pnl_pct:+.1f}%",
            f"NIFTY 500 {kit.pct(benchmark_day_pct)}",
            "up" if day_pnl_pct >= 0 else "down",
        ),
        kit.Reading("Cash / realised balance", f"₹{cash:,.0f}"),
        kit.Reading(
            "MTD return",
            kit.pct(strategy_mtd),
            f"NIFTY 500 {kit.pct(benchmark_mtd)}",
            "up" if strategy_mtd >= 0 else "down",
        ),
    ], "Portfolio snapshot")
    # One canonical table; the columns users scan first come first.
    display_cols = [
        "Symbol", "Current Price", "P&L %", "P&L (₹)", "Weight %", "Target Weight %",
        "Weight Drift %", "Day P&L (₹)", "Day P&L %", "Current Value (₹)", "Shares",
        "Entry Date", "Entry Price", "Invested Value (₹)", "Holding Days",
        "Rank at Rebalance", "Rank at Entry", "Current Rank", "1M Return",
        "Sector / Industry",
    ]
    current_view = table[[c for c in display_cols if c in table.columns]].copy()
    if "Entry Date" in current_view.columns:
        current_view["Entry Date"] = pd.to_datetime(current_view["Entry Date"], errors="coerce").dt.strftime("%d %b %Y").fillna("—")
    for col in ("P&L %", "Weight %", "Target Weight %", "Weight Drift %", "1M Return"):
        if col in current_view.columns:
            current_view[col] = pd.to_numeric(current_view[col], errors="coerce")

    with kit.card(
        "Current book",
        "portfolio_current",
        f"{n_holdings} positions",
    ):
        render_saas_table(current_view, max_height=620, variant="portfolio")

    sector = table.groupby("Sector / Industry", dropna=False).agg(
        Weight=("Weight %", "sum"), Holdings=("Symbol", "count")
    ).sort_values("Weight", ascending=False).reset_index()
    with kit.card("Industry exposure", "portfolio_exposure"):
        st.html(kit.bar_list([
            (f"{row['Sector / Industry']} ({int(row['Holdings'])})", float(row["Weight"]),
             f"{row['Weight']:.1f}%", False)
            for _, row in sector.iterrows()
        ], scale=max(float(sector["Weight"].max()) if not sector.empty else 0.0, 1.0)))

    # The reading sits in the heading (owner, 2026-10-07), not in a caption below.
    _corr, _corr_mean = correlation(prices, table["Symbol"].tolist())
    _corr_head = (f"Average {_corr_mean:.2f}, {correlation_note(_corr_mean)}" if _corr is not None
                  else "90-day correlation of the holdings")
    with kit.card("How they move together", "portfolio_corr", _corr_head):
        if _corr is None:
            st.caption("Not enough price history to compare these holdings.")
        else:
            render_correlation_heatmap(_corr, table["Symbol"].tolist())

    # ── Performance: one card, equity and drawdown together ─────────────────
    with kit.card("Equity & drawdown", "portfolio_equity"):
        if equity.empty:
            st.info("No completed portfolio history is available yet.")
        else:
            mtd_gap = (strategy_mtd - benchmark_mtd
                       if np.isfinite(strategy_mtd) and np.isfinite(benchmark_mtd) else np.nan)
            month = labels["prefix"].split(" ")[0]
            eq_d, bm_d = _daily_with_live(history, table, prices, meta, benchmark_close, value, current)
            dd_d = eq_d / eq_d.cummax() - 1.0
            kit.metric_row([
                kit.Metric(f"{month} strategy", kit.pct(strategy_mtd)),
                kit.Metric(f"{month} Nifty 500", kit.pct(benchmark_mtd)),
                kit.Metric(f"{month} alpha", kit.pct(mtd_gap)),
                kit.Metric("Max drawdown", kit.pct(float(dd_d.min()), signed=False)),
            ], key="pf_equity")
            kit.equity_chart(
                eq_d.index, eq_d.tolist(),
                bm_d.reindex(eq_d.index, method="ffill").tolist() if not bm_d.empty else None,
                key="portfolio_equity_curve_v4",
                drawdown=dd_d.tolist(),
            )
            st.caption("Daily account value; frozen months follow the Track Record's month returns.")

    with kit.card("Calendar returns", "portfolio_monthly", "Strategy, Nifty 500 and Alpha, per year"):
        grid = build_combined_grid(
            ledger,
            mtd_period=pd.Period(mtd_period, freq="M") if mtd_period else None,
            mtd_values={"strategy": strategy_mtd, "benchmark": benchmark_mtd,
                        "alpha": (strategy_mtd - benchmark_mtd
                                  if np.isfinite(strategy_mtd) and np.isfinite(benchmark_mtd) else None)},
        )
        if grid.empty:
            st.info("No monthly history is available yet.")
        else:
            render_saas_table(grid_display(grid))
            note = _calendar_note(labels, mtd_period, mtd_state,
                                  pending=bool(mtd_period) and not np.isfinite(strategy_mtd))
            if note:
                st.caption(note)

    # ── The frozen record: since inception, each month, provenance, the 3 systems ──
    render_record_sections(prices, benchmark_close, system, show_reconstruction_note=False)

    # ── Activity ────────────────────────────────────────────────────────────
    with kit.card("Trades", "portfolio_trades"):
        if trades.empty:
            st.info("No trades are available yet.")
        else:
            outcome = st.pills("Outcome", ["All", "Winners", "Losers", "Open"], default="All",
                               key="portfolio_trade_outcome_v3", label_visibility="collapsed")
            tv = trades.copy()
            if outcome == "Winners":
                tv = tv[tv["Return %"] > 0]
            elif outcome == "Losers":
                tv = tv[tv["Return %"] < 0]
            elif outcome == "Open":
                tv = tv[tv["Status"] == "Open"]
            cols = [c for c in ["Symbol", "Status", "Entry Date", "Entry Price", "Exit Date",
                                "Exit Price", "Return %", "Holding (Days)", "Reason for Exit"]
                    if c in tv.columns]
            render_saas_table(tv[cols], max_height=600)
            st.caption(f"{len(closed_valid)} closed · {wins} winners · {losses} losers")

    with kit.card("Rebalances", "portfolio_rebalances"):
        if tradebook.empty:
            st.info("No rebalances are available yet.")
        else:
            action = st.pills("Action", ["All", "Buy", "Sell", "Hold"], default="All",
                              key="portfolio_rebalance_action_v3", label_visibility="collapsed")
            rv = tradebook.copy()
            if action in ("Buy", "Sell", "Hold"):
                rv = rv[rv["Action"].str.contains(action.upper(), na=False)]
            cols = [c for c in ["Period", "Action", "Symbol", "Price", "Weight %", "Return %",
                                "Reason / Signal"] if c in rv.columns]
            render_saas_table(rv[cols], max_height=600)

    with st.popover("Export", icon=":material/download:"):
        st.download_button("Holdings CSV", table.to_csv(index=False).encode(),
                           f"portfolio_{ist_now():%Y%m%d}.csv", "text/csv", key="dl_port_csv_v3")
        if not trades.empty:
            st.download_button("Trades CSV", trades.to_csv(index=False).encode(),
                               f"portfolio_trades_{ist_now():%Y%m%d}.csv", "text/csv",
                               key="dl_port_trades_csv_v3")
        if not tradebook.empty:
            st.download_button("Rebalances CSV", tradebook.to_csv(index=False).encode(),
                               f"portfolio_rebalances_{ist_now():%Y%m%d}.csv", "text/csv",
                               key="dl_port_rebalance_csv_v3")
        if not monthly_grid.empty:
            st.download_button("Monthly returns CSV", monthly_grid.to_csv(index=False).encode(),
                               f"portfolio_monthly_{ist_now():%Y%m%d}.csv", "text/csv",
                               key="dl_port_monthly_csv_v4")
