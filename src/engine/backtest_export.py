"""One download for a backtest: the rules it ran under, and every trade it made.

Owner, 2026-10-08: "download all trades history in back test ... one file showing
rules or constraints we used for entry, exit, periods etc, and second sheet with
all the trades with all the required columns". A CSV has no sheets, so the
download is a ZIP of two CSV files that open side by side in Excel:

  backtest_rules.csv    Section, Item, Value, Note: what ran, how names were chosen,
                        sized, sold and costed, and what the trade columns mean
  backtest_trades.csv   one row per position, closed or still open, in entry order

The rules are written from the settings of the run itself (and the engine's own
defaults for the two it does not expose), never from fixed text, so they cannot
describe a different run from the one the trades came from.
"""

from __future__ import annotations

import inspect
import io
import re
import zipfile
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from src.core.config import MOMENTUM_WINDOWS
from src.engine.backtester import run_backtest, sector_slots

TRADE_COLUMNS = [
    "Trade #", "Status", "Symbol", "Sector",
    "Entry signal date", "Entry date", "Entry price", "Entry rank", "Entry weight %",
    "Exit signal date", "Exit date", "Exit price", "Exit rank", "Reason for exit",
    "Mark date", "Mark price", "Holding days", "Price return %",
]

# What each trades column is, written once so the rules file can carry it.
COLUMN_NOTES = {
    "Trade #": "1, 2, 3 ... in order of entry date, then symbol",
    "Status": "Closed = sold at an exit fill; Open = still held at the last session of the reported window",
    "Symbol": "NSE trading symbol (today's ticker where the stock was renamed)",
    "Sector": "The industry the industry cap used for this stock; blank when none is on record",
    "Entry signal date": "Session T the stock was ranked on; every filter and score reads T and nothing later",
    "Entry date": "Session T+1: the close the stock was bought at",
    "Entry price": "Close on the entry date, in the run's price basis",
    "Entry rank": "Rank by composite momentum score among the stocks that passed every filter on T (1 = best)",
    "Entry weight %": "Target weight of the book at entry, after the stock and industry caps",
    "Exit signal date": "Session T the sale was decided on (closed trades only)",
    "Exit date": "Session T+1 after the exit signal: the close the stock was sold at (closed trades only)",
    "Exit price": "Close on the exit date (closed trades only)",
    "Exit rank": "Rank on the exit signal date; blank when the stock no longer passed a filter",
    "Reason for exit": "The first rule that bound, in the order listed under Exit rules",
    "Mark date": "Open trades: the last session of the reported window, where the position is valued",
    "Mark price": "Open trades: close on the mark date",
    "Holding days": "Calendar days from the entry date to the exit date (or the mark date)",
    "Price return %": "Exit (or mark) price over entry price, minus 1, in percent. Before trading costs, which "
                      "are charged on the portfolio's turnover, not on a trade; no dividends unless the price "
                      "basis says so",
}


@dataclass(frozen=True)
class RunSpec:
    """What the run was, as the Backtest tab set it."""

    mode: str                    # "History from 2010" or "Live"
    universe: str                # e.g. "Nifty 500", "Nifty Total Market"
    benchmark: str
    first_fill: pd.Timestamp | None
    last_session: pd.Timestamp | None
    top_n: int
    rebal_freq: int
    buffer_n: int
    weight_method: str
    cost_bps: float
    stock_cap: float
    sector_cap: float
    weights: tuple[float, ...]
    liquidity_floor_cr: float
    price_basis: str
    has_industry_map: bool
    ema_period: int | None = None   # None: the engine's own default
    high_pct: float | None = None   # None: the engine's own default
    stats: dict[str, Any] = field(default_factory=dict)
    generated: str = ""          # IST time stamp, supplied by the caller


def _engine_default(name: str):
    """A run_backtest default the tab does not set, read from the engine itself."""
    return inspect.signature(run_backtest).parameters[name].default


def _pct(x: float, digits: int = 0) -> str:
    return f"{x * 100:.{digits}f}%"


def _clean(text: Any) -> str:
    """Drop the status emoji the tab puts in front of a reason."""
    return re.sub(r"^[^\w(#]+", "", str(text)).strip() if pd.notna(text) else ""


def _date(x: Any) -> str:
    stamp = pd.to_datetime(x, errors="coerce")
    return "" if pd.isna(stamp) else f"{stamp:%Y-%m-%d}"


def trades_table(closed_trades: pd.DataFrame) -> pd.DataFrame:
    """Every position the run held, one row each, with dates as YYYY-MM-DD."""
    if closed_trades is None or closed_trades.empty:
        return pd.DataFrame(columns=TRADE_COLUMNS)
    t = closed_trades.copy()
    for col in ("Sector", "Entry Signal Date", "Entry Rank", "Entry Weight %", "Exit Signal Date", "Exit Rank"):
        if col not in t.columns:
            t[col] = np.nan
    is_open = t["Status"].eq("Open")
    entry = pd.to_datetime(t["Entry Date"], format="%d %b %Y", errors="coerce")
    exit_ = pd.to_datetime(t["Exit Date"], format="%d %b %Y", errors="coerce")
    mark = pd.to_datetime(
        t["Exit Date"].astype(str).str.extract(r"mark (\d{1,2} \w{3} \d{4})")[0],
        format="%d %b %Y", errors="coerce")
    out = pd.DataFrame({
        "Status": t["Status"],
        "Symbol": t["Symbol"],
        "Sector": t["Sector"].fillna("").astype(str),
        "Entry signal date": t["Entry Signal Date"].map(_date),
        "Entry date": entry.map(_date),
        "Entry price": t["Entry Price"].round(4),
        "Entry rank": pd.to_numeric(t["Entry Rank"], errors="coerce"),
        "Entry weight %": pd.to_numeric(t["Entry Weight %"], errors="coerce").round(3),
        "Exit signal date": t["Exit Signal Date"].map(_date),
        "Exit date": exit_.where(~is_open).map(_date),
        "Exit price": t["Exit Price"].where(~is_open).round(4),
        "Exit rank": pd.to_numeric(t["Exit Rank"], errors="coerce"),
        "Reason for exit": t["Reason for Exit"].map(_clean),
        "Mark date": mark.where(is_open).map(_date),
        "Mark price": t["Exit Price"].where(is_open).round(4),
        "Holding days": t["Holding (Days)"],
        "Price return %": (pd.to_numeric(t["Return %"], errors="coerce") * 100).round(2),
    })
    out["_e"] = entry
    out = out.sort_values(["_e", "Symbol"], kind="stable").drop(columns="_e").reset_index(drop=True)
    out.insert(0, "Trade #", np.arange(1, len(out) + 1))
    for col in ("Entry rank", "Exit rank"):
        out[col] = out[col].astype("Int64")
    return out[TRADE_COLUMNS]


def rules_table(spec: RunSpec, trades: pd.DataFrame) -> pd.DataFrame:
    """Section, Item, Value, Note: the run's rules in the order a reader asks about them."""
    ema = int(spec.ema_period if spec.ema_period is not None else _engine_default("ema_period"))
    high = float(spec.high_pct if spec.high_pct is not None else _engine_default("high_pct"))
    s = spec.stats or {}
    horizons = list(MOMENTUM_WINDOWS)
    wsum = sum(spec.weights) or 1.0
    weights_txt = ", ".join(f"{m}M {_pct(w / wsum)}" for m, w in zip(horizons, spec.weights))
    monthly = spec.rebal_freq == 21
    rows: list[tuple[str, str, str, str]] = []

    def add(section: str, item: str, value: Any, note: str = "") -> None:
        rows.append((section, item, str(value), note))

    n_closed = int((trades["Status"] == "Closed").sum()) if len(trades) else 0
    n_open = int((trades["Status"] == "Open").sum()) if len(trades) else 0

    add("Run", "Strategy", "Momentum: composite score, top holdings, buffer zone",
        "The same engine as the Screener's ranking and the Portfolio page")
    add("Run", "Mode", spec.mode)
    add("Run", "Universe", spec.universe)
    add("Run", "Benchmark", spec.benchmark)
    add("Run", "First fill date", _date(spec.first_fill))
    add("Run", "Last session reported", _date(spec.last_session),
        "Only completed calendar months are reported; the month in progress is left out")
    add("Run", "Trades in trades file", f"{len(trades)}", f"{n_closed} closed, {n_open} still open")
    add("Run", "Generated (IST)", spec.generated)

    add("Timing", "Rebalance",
        "Monthly" if monthly else f"Every {spec.rebal_freq} trading sessions",
        "Signal on the last trading session of each calendar month" if monthly else
        "Signal on every Nth trading session")
    add("Timing", "Signal date (T)", "The signal session",
        "Every filter and score reads T and nothing later: no look-ahead")
    add("Timing", "Fill date", "T+1 close",
        "Buys and sells are both struck at the close of the session after the signal")
    add("Timing", "First day a position earns", "T+2",
        "It was bought at the T+1 close, so the T+1 session itself belongs to the previous holder")
    add("Timing", "Open positions", "Valued at the last reported session",
        "Not at today's price; they are the book the run ends with")

    pit, cur = int(s.get("pit_periods", 0) or 0), int(s.get("current_universe_periods", 0) or 0)
    if pit and not cur:
        add("Entry rules", "1. In the index on T", f"{spec.universe}, point in time",
            "Membership on the signal date, not today's list, for every rebalance")
    elif pit:
        add("Entry rules", "1. In the index on T", f"{spec.universe}, point in time where on record",
            f"{cur} of {pit + cur} rebalances used today's list instead (see Data)")
    elif cur:
        add("Entry rules", "1. In the index on T", f"{spec.universe}, today's list",
            "The membership history did not reach back, so no month was scored on the index as it stood (see Data)")
    else:
        add("Entry rules", "1. In the index on T", spec.universe, "Membership on the signal date")
    add("Entry rules", "2. Trend filter", f"Close above its {ema}-session EMA", "Evaluated on T")
    add("Entry rules", "3. 52-week-high filter", f"Close at least {_pct(high)} of the 252-session high", "Evaluated on T")
    add("Entry rules", "4. Liquidity floor",
        f"20-day average traded value of Rs {spec.liquidity_floor_cr:g} Cr or more" if spec.liquidity_floor_cr else "None",
        "On the value known at T" if spec.liquidity_floor_cr else "Switched off for this run")
    add("Entry rules", "5. Rank", "Composite momentum score, best first",
        f"Z-scored returns over {', '.join(str(m) + 'M' for m in horizons)} blended with weights {weights_txt}")
    add("Entry rules", "6. Select", f"Top {spec.top_n} by rank",
        "A stock already held keeps its place while it ranks inside the buffer (next row)")
    add("Entry rules", "Buffer zone", f"Top {spec.buffer_n} ({spec.buffer_n / spec.top_n:.1f}x holdings)",
        "Stops a rank wobble from selling and re-buying the same stock")
    if spec.has_industry_map:
        add("Entry rules", "Industry cap on names",
            f"At most {sector_slots(spec.top_n, spec.stock_cap, spec.sector_cap)} names per industry",
            f"What a {_pct(spec.sector_cap)} industry cap allows at {_pct(spec.stock_cap)} a stock; "
            "a full industry is skipped for the next-ranked name")
    add("Entry rules", "Two share lines of one company", "One slot",
        "A line already held keeps it; otherwise the better-ranked line takes it")

    add("Exit rules", "When", "At the next rebalance fill",
        "There is no stop-loss, profit target or intra-period exit in this backtest")
    add("Exit rules", "Reason: Rank Dropped", f"Ranked outside the top {spec.buffer_n}",
        "Still passes every filter, but has fallen past the buffer")
    add("Exit rules", "Reason: Trend Breakdown", f"Closed below its {ema}-session EMA on T")
    add("Exit rules", "Reason: Failed 52W High Filter", f"Closed below {_pct(high)} of its 52-week high on T")
    add("Exit rules", "Reason: Not in the index", "No longer in the index on T",
        "The row names the date")
    add("Exit rules", "Reason: Below the liquidity floor", "20-day average traded value under the floor on T"
        if spec.liquidity_floor_cr else "Not applicable: no floor in this run")
    add("Exit rules", "Reason: Rebalance Exit", "Any other change to the book",
        "Used only when none of the reasons above explains the sale")

    add("Sizing", "Weighting", spec.weight_method)
    add("Sizing", "Stock cap", _pct(spec.stock_cap, 1), "A hard limit: never raised")
    add("Sizing", "Industry cap", _pct(spec.sector_cap, 1) if spec.has_industry_map else "Not applied",
        "A hard limit: never raised" if spec.has_industry_map else "No industry map for this run")
    cash = float(s.get("cap_cash_max", 0.0) or 0.0)
    add("Sizing", "Cash", f"Up to {_pct(cash, 1)} of the book" if cash > 1e-6 else "None",
        "Weight the caps cannot place is held as cash at 0%")

    add("Costs", "Trading cost", f"{spec.cost_bps:g} bps per unit of turnover",
        "Turnover is half the sum of the weight changes at a rebalance, so establishing a book costs half of this")
    add("Costs", "Where it is charged", "On the portfolio return at each rebalance, not per trade",
        "Price return % in the trades file is before costs")
    add("Costs", "Closing book", "Not liquidated", "Its exit leg is never charged")

    add("Data", "Price basis", spec.price_basis)
    if s:
        add("Data", "Rebalances on point-in-time membership", f"{pit} of {pit + cur}",
            f"Point-in-time membership begins {s.get('pit_from')}" if cur and s.get("pit_from") else
            "Every rebalance used the index as it stood" if not cur else "")
        if cur:
            add("Data", "Rebalances on today's list", f"{cur} of {pit + cur}",
                "Index additions skew toward recent winners, so these months flatter the result by an amount this run cannot measure")
    for col in TRADE_COLUMNS:
        add("Columns in the trades file", col, COLUMN_NOTES[col])
    return pd.DataFrame(rows, columns=["Section", "Item", "Value", "Note"])


def export_zip(rules: pd.DataFrame, trades: pd.DataFrame) -> bytes:
    """The two CSV files in one ZIP. UTF-8 with a byte-order mark so Excel reads it."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("backtest_rules.csv", rules.to_csv(index=False).encode("utf-8-sig"))
        z.writestr("backtest_trades.csv", trades.to_csv(index=False).encode("utf-8-sig"))
    return buffer.getvalue()
