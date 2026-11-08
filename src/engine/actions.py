"""What the strategy would do at the next rebalance, from today's ranking.

A preview, not a prediction: it runs the strategy's own selection
(backtester._select_holdings: keep a holding while it ranks inside the buffer,
then fill from the top of the qualified list) and its own weighting
(apply_caps on an equal-weight book) on today's closes. The real orders are
struck at the rebalance close, so a name can still move in or out before then.
"""
from __future__ import annotations

from collections import Counter

from dataclasses import dataclass, field

import pandas as pd

from src.engine.backtester import _select_holdings, sector_slots
from src.engine.exit_watch import qualified_ranks
from src.engine.portfolio import apply_caps


@dataclass
class Plan:
    sells: list[str]
    buys: list[str]
    holds: list[str]
    next_in_line: list[str]
    weights: pd.Series = field(default_factory=lambda: pd.Series(dtype=float))


def plan_rebalance(
    rank_df: pd.DataFrame,
    holdings: list[str],
    *,
    top_n: int = 20,
    buffer_n: int = 40,
    stock_cap: float = 0.05,
    sector_cap: float = 0.40,
    spare: int = 4,
    standing: pd.Series | None = None,
    hold_cap: float | None = None,
) -> Plan:
    """Sells, buys and holds if the rebalance were struck at today's close.

    `holdings` not in the ranking cannot be judged and are left out of the
    plan (the page lists them separately). Weights are the strategy's equal
    weight projected onto the stock and sector caps.
    """
    q = qualified_ranks(rank_df)
    # _select_holdings reads position in a best-first index; qualified_ranks is
    # already best first, so its index is the ranking.
    full_ranked = pd.Series(range(len(q), 0, -1), index=q.index, dtype=float)
    ranked = set(rank_df["Symbol"])
    known = [s for s in holdings if s in ranked]
    sector_map = (rank_df.drop_duplicates("Symbol").set_index("Symbol")["Industry"].to_dict()
                  if "Industry" in rank_df.columns else {})
    # The same hard industry limit the backtest's selection applies.
    slots = sector_slots(top_n, stock_cap, sector_cap) if sector_map else None
    new_book = _select_holdings(full_ranked, known, top_n, buffer_n,
                                sector_map=sector_map or None, max_per_sector=slots)
    sells = [s for s in known if s not in new_book]
    buys = [s for s in new_book if s not in known]
    holds = [s for s in known if s in new_book]
    in_book = set(new_book)
    filled = Counter(sector_map.get(s, "Other") for s in new_book)
    nxt = [s for s in q.index if s not in in_book
           and (slots is None or filled[sector_map.get(s, "Other")] < slots)][:spare]

    weights = pd.Series(dtype=float)
    if new_book:
        equal = pd.Series(1.0 / len(new_book), index=new_book)
        weights = apply_caps(equal, sector_map, sector_cap=sector_cap, stock_cap=stock_cap)
        # From the 30 Nov 2026 signal the record lets winners run to `hold_cap`
        # (owner, 8 Nov 2026): with the book as it stands, the plan strikes the
        # record's weights, so the Kite basket buys what the record buys (audit,
        # 8 Nov 2026: equal 5% here against freed money there).
        if hold_cap is not None and standing is not None:
            from src.engine.backtester import _let_winners_run
            weights = _let_winners_run(weights, standing, known, hold_cap,
                                       sector_map or None, sector_cap)
    return Plan(sells=sells, buys=buys, holds=holds, next_in_line=nxt, weights=weights)


def standing_weights(book: pd.DataFrame, prices: pd.DataFrame | None) -> pd.Series | None:
    """The model book as it stands today: each name's struck weight carried from
    the last fill by its price, cash at 0% (the record's `_drift_holdings`)."""
    fill = pd.to_datetime(book.attrs.get("fill_date"), errors="coerce")
    if book is None or book.empty or prices is None or prices.empty or pd.isna(fill):
        return None
    w = pd.to_numeric(book.set_index("Symbol")["Weight %"], errors="coerce").fillna(0.0) / 100.0
    px = prices.reindex(columns=w.index).ffill()
    at_fill, now = px.loc[:fill], px
    if at_fill.empty or now.empty:
        return None
    growth = (now.iloc[-1] / at_fill.iloc[-1]).where(lambda g: g.notna() & (g > 0), 1.0)
    value = w * growth
    total = float(value.sum()) + max(1.0 - float(w.sum()), 0.0)
    return value / total if total > 0 else None


def buy_orders(plan: Plan, rank_df: pd.DataFrame, capital: float) -> pd.DataFrame:
    """Zerodha Kite basket rows for the buys, sized at their target weight.

    Only the buys: the app does not know how many shares of a holding are
    owned, so a sell cannot be sized. The page says so beside the button.
    """
    price = pd.to_numeric(rank_df.drop_duplicates("Symbol").set_index("Symbol")["CMP"],
                          errors="coerce")
    rows = []
    for s in plan.buys:
        p = price.get(s)
        w = float(plan.weights.get(s, 0.0))
        if p is None or pd.isna(p) or p <= 0 or w <= 0:
            continue
        qty = int(capital * w // p)
        if qty > 0:
            rows.append({"Instrument": s, "Exchange": "NSE", "Order Type": "MARKET",
                         "Action": "BUY", "Quantity": qty, "Price": 0,
                         "ProductType": "CNC", "TriggerPrice": 0})
    return pd.DataFrame(rows)
