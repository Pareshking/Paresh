"""The model book's plan for the next rebalance, one function for every page (S154).

The Dashboard's "What happens on 30 Nov" and Actions both show the plan; they
built it separately, and only Actions passed the record's held weights, hold cap
and buy size (found 20 Nov 2026). The lists agreed that day, the weights did not
have to. Both now call `model_plan`.
"""
from __future__ import annotations

import pandas as pd

from src.engine.actions import Plan, fixed_buy_weight, plan_rebalance, standing_weights
from src.engine.track_record import TRACK_RECORD_CONFIG


def model_plan(book: pd.DataFrame, record: dict | None, rank_df: pd.DataFrame, adj_close: pd.DataFrame,
               benchmark_close: pd.Series | None, system: str, check: pd.Timestamp) -> Plan:
    """What the record would do at `check` on today's closes: sells, buys, holds and the
    weights it strikes. Between the six-monthly resets the kept names keep their drift up
    to the hold cap and each buy gets the record's buy size (owner, 8 Nov 2026)."""
    from src.engine.backtester import _hold_cap_on
    from src.ui.views.actions_view import _book_equity

    cfg = TRACK_RECORD_CONFIG
    symbols = [] if book is None or book.empty else book["Symbol"].tolist()
    resets = tuple(cfg.get("weight_reset_months") or ())
    held = (_hold_cap_on(cfg.get("hold_cap"), cfg.get("hold_cap_from"), check)
            and pd.Timestamp(check).month not in resets)
    standing = standing_weights(book, adj_close) if held else None
    if held and standing is None:
        raise ValueError("The model book has no fill date, so its held weights cannot be read; "
                         "the plan would fall back to equal weight (current_book sets book.attrs['fill_date'])")
    buy_w = (fixed_buy_weight(_book_equity(book, record, rank_df, adj_close, benchmark_close, system),
                              resets, float(cfg.get("buy_size") or 0.05)) if held else None)
    return plan_rebalance(rank_df, symbols, top_n=int(cfg["top_n"]), buffer_n=int(cfg["buffer_n"]),
                          stock_cap=float(cfg["stock_cap"]), sector_cap=float(cfg["sector_cap"]),
                          standing=standing, hold_cap=cfg.get("hold_cap") if held else None, buy_weight=buy_w)
