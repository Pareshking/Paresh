"""The model portfolio's record run, shared by Portfolio, Actions and Track Record.

Lives in the engine, not in a view, so no page imports another page for it.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.engine.backtester import run_backtest
from src.engine.corporate_actions import load_events
from src.engine.extra_universe import SYSTEM_750
from src.engine.pipeline import price_fingerprint
from src.engine.rank_history import month_books
from src.engine.systems import inception, membership_for
from src.engine.track_record import TRACK_RECORD_CONFIG, months_to_cover
from src.loaders import former_members, nse_prices
from src.loaders.ranking_store import actions_digest


@st.cache_data(show_spinner=False, max_entries=6)
def _month_books(key: str, _prices: pd.DataFrame, _tradebook: pd.DataFrame, _membership: dict | None) -> dict:
    """Each month's book with its start and end ranks and gates (engine/rank_history.py)."""
    cfg = TRACK_RECORD_CONFIG
    return month_books(_prices, _tradebook, membership=_membership,
                       ema_period=cfg["ema_period"], high_pct=cfg["high_pct"],
                       config_weights=cfg["config_weights"])


def record_sector_map(symbols) -> dict[str, str]:
    """The industry each symbol is capped under in the canonical record.

    One source for the live replay and the monthly ledger update, so the two
    cannot cap different groupings. The same labels Actions and the research
    backtest read: the NSE index file's industry, TradingView mapped onto it
    for names that have left the index.
    """
    syms = [str(s) for s in symbols]
    idx = pd.read_csv(former_members.INDEX_FILE)
    idx.columns = [str(c).strip() for c in idx.columns]
    nse = dict(zip(idx["Symbol"].astype(str), idx["Industry"].astype(str)))
    out = {s: nse[s] for s in syms if s in nse}
    # industry_for maps TradingView labels for EVERY name it is given, current
    # members included, so it must only see the names the index file lacks
    # (as in the research backtest); for 3 of 2026-10's 20 names it disagreed.
    out.update(former_members.industry_for([s for s in syms if s not in out]))
    return out


def _benchmark_key(benchmark_close: pd.Series | None, start: pd.Period) -> str:
    """Cache-key component for the benchmark the record is measured against.

    run_backtest receives the benchmark as `_benchmark_close`, which
    st.cache_data does not hash, and the key string above used to omit it. A
    page whose benchmark download failed (an empty series) therefore cached a
    flat 0% benchmark under the same key a healthy page then read, so every page
    showed alpha equal to the strategy return until the cache expired.

    Only the slice that can reach the record is fingerprinted (from shortly
    before inception), so a 2-year and a 5-year download of the same index
    still share one cached replay.
    """
    if benchmark_close is None or benchmark_close.empty:
        return "nobench"
    window = pd.to_numeric(benchmark_close, errors="coerce").loc[
        start.start_time - pd.Timedelta(days=40):]
    return price_fingerprint(window.to_frame())


def record_run(adj_close: pd.DataFrame, benchmark_close: pd.Series | None,
               system: str = SYSTEM_750) -> dict:
    """The strategy under the RECORD's pinned configuration, through today.

    One cached run serves the month-to-date here and the model book on the
    Actions page, so both describe the same portfolio. Each system replays
    from its own inception on its own point-in-time membership; Nano Cap and
    Combined replay at least one month, so their first book (signalled at
    the close before inception) exists from inception's first session.
    """
    if adj_close is None or adj_close.empty:
        return {}
    as_of = pd.Timestamp(adj_close.index[-1])
    start = inception(system)
    if pd.Period(as_of, freq="M") < start:
        return {}
    months = months_to_cover(as_of, start)
    if system != SYSTEM_750:
        months = max(months, 1)
    if months <= 0:
        return {}
    cfg = TRACK_RECORD_CONFIG
    # Whole-history fingerprint + applied events: the old key (date, width,
    # months) served an hour-stale MTD after a restatement or a new split.
    events = load_events()
    # The pinned run is scored on the index as it stood, so the names it once
    # held and has since dropped must have prices (loaders/former_members.py).
    membership = membership_for(system)
    prices = former_members.with_former_members(adj_close, membership)
    if system == SYSTEM_750:
        # The 750's record is struck on NSE's closes as published, so this run
        # must be too or its month-to-date would disagree with the frozen months.
        nse, _ = nse_prices.basis_frame(adj_close, membership, months=months)
        if nse is not None:
            prices, events = nse, []
            # The frame may run past the other source's last session (NSE's file is
            # ahead on the first working day): the window is counted back from its end.
            months = months_to_cover(pd.Timestamp(prices.index[-1]), start)
    result = run_backtest(
        f"trackrec_{system}_{price_fingerprint(prices)}_{actions_digest(events)}_{months}"
        f"_{_benchmark_key(benchmark_close, start)}",
        prices,
        top_n=cfg["top_n"],
        rebal_freq=cfg["rebal_freq"],
        ema_period=cfg["ema_period"],
        high_pct=cfg["high_pct"],
        weight_method=cfg["weight_method"],
        config_weights=cfg["config_weights"],
        cost_bps=cfg["cost_bps"],
        buffer_n=cfg["buffer_n"],
        stock_cap=cfg["stock_cap"],
        sector_cap=cfg["sector_cap"],
        sector_map=record_sector_map(prices.columns),
        _benchmark_close=benchmark_close,
        backtest_months=months,
        _membership=membership,
        stateful_history=True,
        # The backtest needs warm-up prices before inception, but its stateful
        # tradebook must not create portfolio ownership before the canonical
        # Track Record start. Backtest UI already enforces this boundary; the
        # Track Record caller must pass the same boundary to keep Actions and
        # Portfolio history on the identical canonical book.
        history_start=start.start_time,
        _actions=events,
    )
    result = result or {}

    # The backtest is the canonical accounting engine and already receives
    # history_start above. Keep this adapter boundary defensive as well: a
    # stale cache or a future engine regression must never expose pre-inception
    # ownership in Actions/Portfolio history. This filters presentation records
    # only; it does not change the simulated equity curve, selection, sizing,
    # or P&L calculation.
    tradebook = result.get("tradebook")
    if isinstance(tradebook, pd.DataFrame) and "Period Start" in tradebook.columns:
        period_start = pd.to_datetime(tradebook["Period Start"], errors="coerce")
        result["tradebook"] = tradebook.loc[
            period_start.ge(start.start_time) | period_start.isna()
        ].reset_index(drop=True)

    closed_trades = result.get("closed_trades")
    if isinstance(closed_trades, pd.DataFrame) and "Exit Date" in closed_trades.columns:
        exit_date = pd.to_datetime(closed_trades["Exit Date"], errors="coerce")
        result["closed_trades"] = closed_trades.loc[
            exit_date.ge(start.start_time) | exit_date.isna()
        ].reset_index(drop=True)

    # Add the month in progress first: its rebalance (signalled on the last session of the
    # month before, filled on the 1st) sits outside the backtest window, and without it the
    # last completed month would read as "held to date" with no new book beside it.
    result = with_live_month(result)
    tb = result.get("tradebook")
    if isinstance(tb, pd.DataFrame) and not tb.empty:
        result["month_books"] = _month_books(
            f"{system}_{price_fingerprint(prices)}_{months}", prices, tb, membership)
    return result


_TRADE_ACTION = {
    "🟢 BOUGHT": "🟢 BUY (Entry)",
    "🔴 SOLD": "🔴 SELL (Exit)",
    "⚪ HELD": "⚪ HOLD (Retained)",
}


def with_live_month(result: dict) -> dict:
    """Add the month the backtest window does not cover to the history tables.

    The window ends at the last completed month, so the rebalance filled on the
    1st of this month, the names it sold, and the open positions' live marks
    sit only in `month_changes` and `live_book`. Without this the rebalance
    history and trades stop a month early. Frames are replaced, not mutated.
    """
    changes = result.get("month_changes")
    meta = result.get("live_meta") or {}
    fill = meta.get("fill_date")
    as_of = meta.get("as_of")
    if not isinstance(changes, pd.DataFrame) or changes.empty or fill is None or as_of is None:
        return result
    fill, as_of = pd.Timestamp(fill), pd.Timestamp(as_of)

    label = f"{fill:%d %b %Y} → {as_of:%d %b %Y}"
    rows = []
    for r in changes.to_dict("records"):
        action = r.get("Action")
        price = r.get("Entry Price") if action == "🟢 BOUGHT" else r.get("Exit Price")
        rows.append({
            "Period": label,
            "Period Start": fill,
            "Action": _TRADE_ACTION.get(action, action),
            "Symbol": r.get("Symbol"),
            "Price": price,
            "Return %": r.get("Return %"),
            "Weight %": r.get("Weight %"),
            "Reason / Signal": r.get("Reason"),
        })
    live = pd.DataFrame(rows)
    book = result.get("tradebook")
    if isinstance(book, pd.DataFrame) and not book.empty and "Period Start" in book.columns:
        book = book.loc[pd.to_datetime(book["Period Start"], errors="coerce") != fill]
        result["tradebook"] = pd.concat([book, live], ignore_index=True)
    else:
        result["tradebook"] = live

    closed = result.get("closed_trades")
    keep = pd.DataFrame()
    if isinstance(closed, pd.DataFrame) and not closed.empty:
        status = closed["Status"] if "Status" in closed.columns else pd.Series("", index=closed.index)
        keep = closed.loc[status != "Open"]
        exits = pd.to_datetime(keep.get("Exit Date"), errors="coerce")
        keep = keep.loc[~(exits == fill)]
    extra = []
    for r in changes.loc[changes["Action"] == "🔴 SOLD"].to_dict("records"):
        entry = pd.Timestamp(r["Entry Date"]) if pd.notna(r.get("Entry Date")) else None
        extra.append({
            "Month": f"{fill:%b-%Y}", "Symbol": r["Symbol"],
            "Entry Date": f"{entry:%d %b %Y}" if entry is not None else "—",
            "Entry Price": r.get("Entry Price"),
            "Exit Date": f"{fill:%d %b %Y}", "Exit Price": r.get("Exit Price"),
            "Return %": r.get("Return %"),
            "Holding (Days)": (fill - entry).days if entry is not None else None,
            "Reason for Exit": r.get("Reason"), "Status": "Closed",
        })
    book_now = result.get("live_book")
    if isinstance(book_now, pd.DataFrame):
        for r in book_now.to_dict("records"):
            entry = pd.Timestamp(r["Entry Date"]) if pd.notna(r.get("Entry Date")) else None
            extra.append({
                "Month": f"🟢 Open (as of {as_of:%d %b %Y})", "Symbol": r["Symbol"],
                "Entry Date": f"{entry:%d %b %Y}" if entry is not None else "—",
                "Entry Price": r.get("Entry Price"),
                "Exit Date": f"Not exited (mark {as_of:%d %b %Y})",
                "Exit Price": r.get("Price Now"), "Return %": r.get("Return %"),
                "Holding (Days)": r.get("Holding (Days)"),
                "Reason for Exit": "🟢 Still held", "Status": "Open",
            })
    result["closed_trades"] = pd.concat([keep, pd.DataFrame(extra)], ignore_index=True)
    return result
