"""Current model Portfolio view.

Portfolio is an accounting/presentation view of the Track Record's canonical
current book. It does not select stocks or calculate a competing model book.
"""
from __future__ import annotations

import html

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


def _overview_note(labels: dict, state: str) -> str:
    base = ("Since inception compounds the frozen record through the latest completed month "
            "and the marked month. ")
    if state == "closed":
        marked = labels["prefix"].split(" ")[0]
        return (
            base + f"{marked} is closed but not yet frozen into the Track Record, which freezes it "
            f"in the first days of the month. {labels['next']} is not available until the first "
            "close of the new month. "
            "Current-book P&L is the unrealised return on today's holdings, so it can differ."
        )
    return (
        base.replace("the marked month", "the current live month-to-date return")
        + "Current-book P&L is the unrealised return on today's holdings, so it can differ."
    )


def _no_return_clause(labels: dict) -> str:
    marked = labels["prefix"].split(" ")[0]
    return (f" {marked} MTD has no return yet: the new book was bought at the first close of "
            "the month and starts accruing the next session.")


def _calendar_note(labels: dict, live_period: str | None, state: str, pending: bool = False) -> str:
    base = ("Calendar quarters (Q1 = Jan·Feb·Mar). CY compounds Jan–Dec; "
            "FY compounds Apr of the row's year through Mar of the next.")
    if not live_period:
        return base
    marked = labels["prefix"].split(" ")[0]
    if state == "closed":
        return (f"{base} The {marked} cells are closed but not yet frozen into the Track Record. "
                f"{labels['next']}: not available until the first close of the new month.")
    if pending:
        return base + _no_return_clause(labels)
    return f"{base} The {marked} cells are live month-to-date, not frozen."


def _compound_returns(values: list[float]) -> float | None:
    """Compound a sequence of period returns into one period return."""
    valid = [float(v) for v in values if pd.notna(v)]
    if not valid:
        return None
    return float(np.prod([1.0 + v for v in valid]) - 1.0)


def _calendar_grid_html(monthly: pd.DataFrame, live_period: str | None,
                        live_state: str = "mtd") -> str:
    """Render calendar-month performance from the canonical monthly record."""
    if monthly.empty:
        return '<div class="pg-note">No monthly performance is available yet.</div>'

    frame = monthly.copy()
    frame["Period"] = pd.PeriodIndex(frame["Period"], freq="M")
    frame["Year"] = frame["Period"].dt.year
    frame["MonthNo"] = frame["Period"].dt.month
    frame["Strategy Net"] = pd.to_numeric(frame["Strategy Net"], errors="coerce")
    frame["Benchmark"] = pd.to_numeric(frame["Benchmark"], errors="coerce")
    # Plain dicts by column name: itertuples() renames columns that are not
    # identifiers ("Strategy Net" became "_2"), and reading them back by name
    # raised KeyError on every Monthly render (production, 1 Oct 2026).
    lookup = {
        (int(row["Year"]), int(row["MonthNo"])): row
        for row in frame.to_dict("records")
    }
    live = pd.Period(live_period, freq="M") if live_period else None
    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                   "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    def fmt(value: float | None) -> str:
        return "—" if value is None or pd.isna(value) else f"{value:+.1%}"

    def cell(row, live_cell=False):
        if row is None:
            return '<div class="pcg-cell pcg-empty">—</div>'
        strategy = float(row["Strategy Net"]) if pd.notna(row["Strategy Net"]) else None
        benchmark = float(row["Benchmark"]) if pd.notna(row["Benchmark"]) else None
        gap = strategy - benchmark if strategy is not None and benchmark is not None else None
        badge = (f'<span class="pcg-mtd">{"CLOSED" if live_state == "closed" else "MTD"}</span>'
                 if live_cell else "")
        return (
            f'<div class="pcg-cell">'
            f'<div class="pcg-top">{badge}</div>'
            f'<div class="pcg-s">{fmt(strategy)}</div>'
            f'<div class="pcg-b">{fmt(benchmark)}</div>'
            f'<div class="pcg-g">Alpha {fmt(gap)}</div>'
            f'</div>'
        )

    def aggregate(periods):
        s = [lookup[(p.year, p.month)]["Strategy Net"] for p in periods if (p.year, p.month) in lookup]
        b = [lookup[(p.year, p.month)]["Benchmark"] for p in periods if (p.year, p.month) in lookup]
        return _compound_returns(s), _compound_returns(b)

    years = sorted(frame["Year"].unique())
    rows = []
    for year in years:
        cells = []
        for month_no in range(1, 13):
            row = lookup.get((int(year), month_no))
            is_live = live is not None and row is not None and row["Period"] == live
            cells.append(cell(row, is_live))
        cy_s, cy_b = aggregate([pd.Period(f"{year}-{m:02d}", freq="M") for m in range(1, 13)])
        fy_periods = [
            pd.Period(
                f"{year if m <= 12 else year + 1:04d}-{m if m <= 12 else m - 12:02d}",
                freq="M",
            )
            for m in range(4, 16)
        ]
        fy_s, fy_b = aggregate(fy_periods) if all(
            (p.year, p.month) in lookup for p in fy_periods
        ) else (None, None)
        cy_gap = cy_s - cy_b if cy_s is not None and cy_b is not None else None
        fy_gap = fy_s - fy_b if fy_s is not None and fy_b is not None else None
        def aggregate_cell(s, b, gap):
            if s is None:
                return '<div class="pcg-cell pcg-empty">—</div>'
            return (
                '<div class="pcg-cell">'
                f'<div class="pcg-s">{fmt(s)}</div>'
                f'<div class="pcg-b">{fmt(b)}</div>'
                f'<div class="pcg-g">Alpha {fmt(gap)}</div>'
                '</div>'
            )
        rows.append(
            f'<div class="pcg-row"><div class="pcg-year">{year}</div>'
            + "".join(cells)
            + aggregate_cell(cy_s, cy_b, cy_gap)
            + aggregate_cell(fy_s, fy_b, fy_gap)
            + "</div>"
        )

    return (
        '<style>'
        '.pcg-wrap{font-family:var(--font-ui,system-ui,sans-serif);}'
        '.pcg-scroll{overflow-x:auto;-webkit-overflow-scrolling:touch;border:1px solid #E3E6EB;border-radius:14px;background:#fff;}'
        '.pcg-grid{min-width:1560px;}'
        '.pcg-row{display:grid;grid-template-columns:64px repeat(12,minmax(105px,1fr)) 110px 110px;}'
        '.pcg-row:not(.pcg-head){border-top:1px solid #EDEFF3;}'
        '.pcg-head{background:#F7F8FA;position:sticky;top:0;z-index:2;}'
        '.pcg-year,.pcg-month{padding:9px 8px;font-size:11px;font-weight:700;color:#5E6878;text-align:center;}'
        '.pcg-year{background:#fff;position:sticky;left:0;z-index:3;border-right:1px solid #EDEFF3;}'
        '.pcg-cell{min-height:70px;padding:8px 7px;border-left:1px solid #F0F1F4;display:flex;flex-direction:column;justify-content:center;gap:2px;}'
        '.pcg-empty{align-items:center;color:#98A1AE;}'
        '.pcg-top{height:12px;text-align:right;}'
        '.pcg-mtd{display:inline-block;padding:2px 5px;border-radius:5px;background:#EEF2FF;color:#4338CA;font-size:9px;font-weight:800;letter-spacing:.3px;}'
        '.pcg-s,.pcg-b,.pcg-g{font-family:var(--font-mono,ui-monospace,monospace);font-size:11px;line-height:1.35;white-space:nowrap;}'
        '.pcg-s{font-weight:750;color:#0E1726;}.pcg-b{color:#5E6878;}.pcg-g{font-weight:650;color:#4F46E5;}'
        '.pcg-key{display:flex;flex-wrap:wrap;gap:14px;margin-top:9px;font-size:11.5px;color:#5E6878;}'
        '@media(max-width:640px){.pcg-grid{min-width:1500px}.pcg-row{grid-template-columns:58px repeat(12,105px) 108px 108px}.pcg-cell{min-height:64px;padding:7px 6px}.pcg-s,.pcg-b,.pcg-g{font-size:10.5px}}'
        '</style>'
        '<div class="pcg-wrap"><div class="pcg-scroll"><div class="pcg-grid">'
        '<div class="pcg-row pcg-head"><div class="pcg-year">Year</div>'
        + "".join(f'<div class="pcg-month">{m}</div>' for m in month_names)
        + '<div class="pcg-month">CY</div><div class="pcg-month">FY</div></div>'
        + "".join(rows)
        + '</div></div>'
        '<div class="pcg-key"><span><b>Strategy</b></span><span><b>Nifty 500</b></span><span><b>Alpha</b> = Strategy − Nifty 500</span></div></div>'
    )


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
    out["Shares"] = (
        (out["Capital at Entry (₹)"] * out["Target Weight %"] / 100.0)
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
        float(curve.iloc[-1]) if not curve.empty and float(curve.iloc[-1]) > 0
        else float(capital)
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
    return out.sort_values(
        ["Current Value (₹)", "Symbol"], ascending=[False, True]
    ).reset_index(drop=True)


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

def _fnum(v) -> float | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if np.isfinite(f) else None


def _rupees(v, sign: bool = False) -> str:
    f = _fnum(v)
    if f is None:
        return "—"
    if not sign:
        return f"₹{f:,.0f}"
    return f"{'+' if f >= 0 else '−'}₹{abs(f):,.0f}"


@st.dialog("Position", width="large")
def _holding_dialog(h: dict) -> None:
    """A trade ticket for one holding: where it was bought, where it is, and
    how far it sits from its target weight. Figures only, nothing keyed."""
    sym = str(h.get("Symbol", ""))
    st.caption(" · ".join(str(x) for x in (h.get("Company"), h.get("Sector / Industry"))
                          if x and str(x) != "nan") or sym)
    pnl_pct = _fnum(h.get("P&L %"))
    day_pct = _fnum(h.get("Day P&L %"))
    kit.metric_row([
        kit.Metric("Price", f"₹{_fnum(h.get('Current Price')):,.2f}" if _fnum(h.get("Current Price")) is not None else "—"),
        kit.Metric("Value", _rupees(h.get("Current Value (₹)"))),
        kit.Metric("P&L", _rupees(h.get("P&L (₹)"), sign=True),
                   delta=f"{pnl_pct:+.1f}%" if pnl_pct is not None else None, tone="normal"),
        kit.Metric("Today", _rupees(h.get("Day P&L (₹)"), sign=True),
                   delta=f"{day_pct:+.1f}%" if day_pct is not None else None, tone="normal"),
    ], key="hd_value")
    w, t, d = _fnum(h.get("Weight %")), _fnum(h.get("Target Weight %")), _fnum(h.get("Weight Drift %"))
    kit.metric_row([
        kit.Metric("Weight", f"{w:.1f}%" if w is not None else "—"),
        kit.Metric("Target", f"{t:.1f}%" if t is not None else "—"),
        kit.Metric("Drift", f"{d:+.1f}%" if d is not None else "—"),
        kit.Metric("Shares", f"{int(_fnum(h.get('Shares'))):,}" if _fnum(h.get("Shares")) is not None else "—"),
    ], key="hd_weight")
    kit.metric_row([
        kit.Metric("Bought", str(h.get("Entry Date") or "—")),
        kit.Metric("At", f"₹{_fnum(h.get('Entry Price')):,.2f}" if _fnum(h.get("Entry Price")) is not None else "—"),
        kit.Metric("Held", f"{int(_fnum(h.get('Holding Days'))):,} days" if _fnum(h.get("Holding Days")) is not None else "—"),
        kit.Metric("Rank now", f"#{int(_fnum(h.get('Current Rank')))}" if _fnum(h.get("Current Rank")) is not None else "—",
                   help="Rank at entry: " + (f"#{int(_fnum(h.get('Rank at Entry')))}" if _fnum(h.get("Rank at Entry")) is not None else "—")),
    ], key="hd_entry")
    st.html(f'<a href="{system_param.stock_href(sym)}" target="_self" class="pg-link">'
            f'Open {html.escape(sym)} →</a>')


def _render_book_grid(book: pd.DataFrame) -> None:
    """The current book as an st.dataframe, with a bar for each weight. Ticking
    a row opens that position's ticket. The HTML table stays the default: it
    colours profit and loss and is the layout the Portfolio tests pin."""
    grid = book.copy()
    if "Symbol" in grid.columns:
        grid["Chart"] = grid["Symbol"].astype(str).map(kit.tradingview_url)
    shown = [c for c in ["Symbol", "Company", "Sector / Industry", "Current Price", "P&L (₹)",
                         "P&L %", "Weight %", "Target Weight %", "Weight Drift %",
                         "Day P&L (₹)", "Current Value (₹)", "Shares", "Entry Price",
                         "Holding Days", "Current Rank", "3M Return", "Chart"]
             if c in grid.columns]
    grid = grid[shown].reset_index(drop=True)
    event = st.dataframe(
        grid, hide_index=True, width="stretch",
        height=min(620, 44 + 35 * len(grid)),
        column_config=kit.stock_grid_config(grid.columns),
        on_select="rerun", selection_mode="single-row", key="portfolio_book_grid",
    )
    st.caption("Tick a row's box for that position's ticket. Click a column header to sort.")
    rows = list(getattr(getattr(event, "selection", None), "rows", []) or [])
    picked = int(rows[0]) if rows and 0 <= rows[0] < len(grid) else None
    # Open once per pick: the selection outlives the dialog, so a later rerun
    # (switching a view below, say) must not open it again.
    if picked is None:
        st.session_state.pop("_pf_book_seen", None)
    elif st.session_state.get("_pf_book_seen") != picked:
        st.session_state["_pf_book_seen"] = picked
        _holding_dialog(book.reset_index(drop=True).iloc[picked].to_dict())


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

    try:
        ledger = load_ledger(ledger_path(system), inception(system))
    except (ValueError, OSError) as exc:
        st.error(f"Portfolio Track Record could not be read: {exc}")
        return

    history = build_portfolio_history(record, capital, ledger, meta)
    equity = history["equity"]
    benchmark = history["benchmark"]
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
    exposure = current / value * 100.0 if value else 0.0
    # Mark/fill dates remain available through live_meta and the canonical book;
    # the compact header no longer duplicates them.
    n_holdings = len(table)
    drawdown = history["drawdown"]
    monthly = history["monthly"]
    monthly_grid = history["monthly_grid"]
    mtd_period = history["mtd_period"]
    mtd_state = history["mtd_state"]
    labels = _month_labels(mtd_period, mtd_state)
    strategy_mtd = history["strategy_mtd"]
    benchmark_mtd = history["benchmark_mtd"]
    trades = history["trades"]
    tradebook = history["tradebook"]

    closed = trades[trades["Status"] == "Closed"] if not trades.empty and "Status" in trades.columns else trades
    closed_valid = closed[closed["Return %"].notna()] if not closed.empty and "Return %" in closed.columns else closed
    wins = int((closed_valid["Return %"] > 0).sum()) if not closed_valid.empty else 0
    losses = int((closed_valid["Return %"] < 0).sum()) if not closed_valid.empty else 0

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
        kit.Reading("Cash / realised balance", f"₹{cash:,.0f}", f"{100.0 - exposure:.1f}% of account value"),
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
        book_style = st.segmented_control(
            "Book style", ["Table", "Grid"], default="Table",
            key="portfolio_book_style", label_visibility="collapsed",
        ) or "Table"
        if book_style == "Grid":
            _render_book_grid(current_view)
        else:
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

    with kit.card("Portfolio history", "portfolio_history_header", "performance history · latest month marked to the latest close"):
        st.caption(
            f"Inception · {inception(system).strftime('%b %Y')}  · "
            f"₹{capital:,.0f} starting capital  · {len(monthly)} completed months"
        )

    if history_tab == "Overview":
        with kit.card(
            "Performance overview",
            "portfolio_performance_overview",
            "since inception · completed months plus the latest marked month",
        ):
            if equity.empty:
                st.info("No completed portfolio history is available yet.")
            else:
                mtd_gap = strategy_mtd - benchmark_mtd if np.isfinite(strategy_mtd) and np.isfinite(benchmark_mtd) else np.nan
                total_alpha = (
                    history["strategy_total_return"] - history["benchmark_total_return"]
                    if np.isfinite(history["strategy_total_return"])
                    and np.isfinite(history["benchmark_total_return"]) else np.nan
                )
                kit.metric_row([
                    kit.Metric("Portfolio value", f"₹{equity.iloc[-1]:,.0f}"),
                    kit.Metric("Since inception · Strategy", kit.pct(history["strategy_total_return"])),
                    kit.Metric("Since inception · Nifty 500", kit.pct(history["benchmark_total_return"])),
                    kit.Metric("Since inception · Alpha", kit.pct(total_alpha)),
                ], key="pf_overview")
                kit.metric_row([
                    kit.Metric(f"{labels['prefix']} · Strategy", kit.pct(strategy_mtd)),
                    kit.Metric(f"{labels['prefix']} · Nifty 500", kit.pct(benchmark_mtd)),
                    kit.Metric(f"{labels['prefix']} · Alpha", kit.pct(mtd_gap)),
                ], key="pf_overview_mtd")
                st.caption(_overview_note(labels, mtd_state))

    elif history_tab == "Equity":
        with kit.card(
            "Equity curve",
            "portfolio_equity",
            "₹20 lakh starting point · strategy vs benchmark · latest month marked",
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
                # This month's figures: the curve's own legend already carries
                # the since-inception values (owner, 1 Oct 2026).
                mtd_gap = strategy_mtd - benchmark_mtd if np.isfinite(strategy_mtd) and np.isfinite(benchmark_mtd) else np.nan
                kit.metric_row([
                    kit.Metric(f"{labels['prefix']} · Strategy", kit.pct(strategy_mtd)),
                    kit.Metric(f"{labels['prefix']} · Nifty 500", kit.pct(benchmark_mtd)),
                    kit.Metric(f"{labels['prefix']} · Alpha", kit.pct(mtd_gap)),
                    kit.Metric("Max drawdown", kit.pct(history["max_drawdown"], signed=False)),
                ], key="pf_equity")
                st.caption(
                    "Completed months come from the recorded performance history; "
                    + ("the final point is the current month-to-date mark." if mtd_state == "mtd"
                       else f"the final point is {labels['prefix'].split(' ')[0]}, closed but not yet frozen.")
                )

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
        with kit.card(
            "Calendar grid",
            "portfolio_monthly",
            "Strategy, Nifty 500 and Alpha, per year",
        ):
            if monthly_grid.empty:
                st.info("No monthly history is available yet.")
            else:
                st.html(_calendar_grid_html(monthly_grid, mtd_period, mtd_state))
                st.caption(_calendar_note(labels, mtd_period, mtd_state,
                                          pending=bool(mtd_period) and not np.isfinite(strategy_mtd)))
                cols = [c for c in ["Month", "Strategy Net", "Benchmark", "Alpha vs Benchmark", "Origin", "Priced From", "Frozen On", "Universe"] if c in monthly_grid.columns]
                st.download_button(
                    "Export monthly performance CSV",
                    monthly_grid[cols].to_csv(index=False).encode(),
                    f"portfolio_monthly_{ist_now():%Y%m%d}.csv",
                    "text/csv",
                    key="dl_port_monthly_csv_v3",
                )

    elif history_tab == "Drawdown":
        with kit.card("Drawdown", "portfolio_drawdown", "peak-to-trough decline in portfolio value"):
            if drawdown.empty:
                st.info("No drawdown history is available yet.")
            else:
                kit.drawdown_chart([d.strftime("%b %Y") for d in drawdown.index], drawdown.tolist(), key="portfolio_drawdown_curve_v2")
                st.caption(f"Maximum drawdown including the current month-to-date point: {history['max_drawdown']:.1%}.")

