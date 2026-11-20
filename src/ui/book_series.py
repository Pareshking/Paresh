"""The model book's daily value: one series for every page (S152, owner 20 Nov 2026).

`record['equity_curve']` is the backtest replay and ends at the last completed
month by design (engine/model_record.with_live_month); the month in progress
is added from today's holdings. Portfolio did that, the Dashboard and Actions
read the replay raw, so the Dashboard said "−8.1% below its peak" on 19 Nov
when the book was −3.1%, and Actions sized new buys against the 30 Oct value.
Owner: "Shouldn't we have common approach?" This module is that approach:
every page that needs the book's value over time reads `book_series`.

The series: the frozen months' replay bent to each month's recorded return,
then the live month as today's sized holdings marked each session plus the
cash residual. Its last point is the portfolio value at the top of Portfolio.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass
class BookSeries:
    equity: pd.Series          # ₹, daily, frozen months then the live month
    benchmark: pd.Series       # the record's benchmark on the same path (Nifty 500)
    value: float               # the account today: the last point of `equity`
    holdings: float            # today's holdings marked at today's prices
    table: pd.DataFrame        # build_portfolio_tracker's table, the holdings with their accounting
    history: dict              # build_portfolio_history's output
    prices: pd.DataFrame       # the price frame clipped to the record's session
    benchmark_close: pd.Series | None
    as_of: pd.Timestamp | None

    @property
    def uninvested(self) -> float:
        return self.value - self.holdings


def book_series(book: pd.DataFrame, record: dict, ledger: dict, rank_df: pd.DataFrame,
                prices: pd.DataFrame, benchmark_close: pd.Series | None, capital: float) -> BookSeries | None:
    """The book's value each session to the record's own as-of date."""
    from src.ui.views.portfolio_view import _daily_with_live, build_portfolio_history, build_portfolio_tracker

    if book is None or book.empty:
        return None
    meta = (record or {}).get("live_meta") or {}
    book = book.copy()
    book.attrs["as_of"] = meta.get("as_of")
    book.attrs["fill_date"] = meta.get("fill_date")
    as_of = pd.to_datetime(meta.get("as_of"), errors="coerce")
    px = prices if prices is not None else pd.DataFrame()
    bc = benchmark_close
    # One market session for the whole page: the record's as-of date.
    if pd.notna(as_of):
        px = px.loc[:as_of]
        if bc is not None:
            bc = pd.to_numeric(bc, errors="coerce").dropna().loc[:as_of]
    history = build_portfolio_history(record, capital, ledger, meta)
    table = build_portfolio_tracker(book, rank_df, capital, px, equity_curve=history["equity"])
    if table is None or table.empty:
        return None
    equity_m = history["equity"]
    value = float(equity_m.iloc[-1]) if not equity_m.empty else float(capital)
    holdings = float(pd.to_numeric(table["Current Value (₹)"], errors="coerce").sum())
    eq, bm = _daily_with_live(history, table, px, meta, bc, value, holdings)
    return BookSeries(equity=eq, benchmark=bm, value=value, holdings=holdings, table=table, history=history,
                      prices=px, benchmark_close=bc, as_of=None if pd.isna(as_of) else pd.Timestamp(as_of))
