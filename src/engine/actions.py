"""What the strategy would do at the next rebalance, from today's ranking.

A preview, not a prediction: it runs the strategy's own selection
(backtester._select_holdings: keep a holding while it ranks inside the buffer,
then fill from the top of the qualified list) and its own weighting
(apply_caps on an equal-weight book) on today's closes. The real orders are
struck at the rebalance close, so a name can still move in or out before then.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from src.engine.backtester import _select_holdings
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
    sector_cap: float = 0.30,
    spare: int = 4,
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
    new_book = _select_holdings(full_ranked, known, top_n, buffer_n)
    sells = [s for s in known if s not in new_book]
    buys = [s for s in new_book if s not in known]
    holds = [s for s in known if s in new_book]
    in_book = set(new_book)
    nxt = [s for s in q.index if s not in in_book][:spare]

    sector_map = (rank_df.drop_duplicates("Symbol").set_index("Symbol")["Industry"].to_dict()
                  if "Industry" in rank_df.columns else {})
    weights = pd.Series(dtype=float)
    if new_book:
        equal = pd.Series(1.0 / len(new_book), index=new_book)
        weights = apply_caps(equal, sector_map, sector_cap=sector_cap, stock_cap=stock_cap)
    return Plan(sells=sells, buys=buys, holds=holds, next_in_line=nxt, weights=weights)


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
