"""Canonical model-book adapter for Track Record, Portfolio and Actions.

The Track Record's pinned record replay is the source of truth for the current
model book. This module deliberately contains no ranking, selection or weighting
logic; it validates and exposes the already-computed record book to UI views.
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from src.engine.extra_universe import SYSTEM_750


REQUIRED_BOOK_COLUMNS = (
    "Symbol",
    "Entry Date",
    "Entry Price",
    "Price Now",
    "Weight %",
    "Rank at Entry",
    "Rank at Rebalance",
)


def current_book(
    adj_close: pd.DataFrame,
    benchmark_close: pd.Series | None,
    system: str = SYSTEM_750,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Return the Track Record's canonical current model book.

    record_run lives in the engine; Portfolio and Actions consume this adapter.

    The returned frame is a validated snapshot. It is not a new portfolio
    calculation.
    """
    from src.engine.model_record import record_run

    result = record_run(adj_close, benchmark_close, system)
    result = result or {}
    book = result.get("live_book", pd.DataFrame())

    if book is None or book.empty:
        return pd.DataFrame(columns=list(REQUIRED_BOOK_COLUMNS)), result

    book = book.copy()
    if "Symbol" not in book.columns:
        raise ValueError("Canonical Track Record book is missing Symbol")
    if book["Symbol"].duplicated().any():
        dupes = book.loc[book["Symbol"].duplicated(), "Symbol"].astype(str).tolist()
        raise ValueError(f"Canonical Track Record book has duplicate symbols: {dupes}")

    missing = [c for c in REQUIRED_BOOK_COLUMNS if c not in book.columns]
    if missing:
        raise ValueError(
            "Canonical Track Record book is missing required columns: "
            + ", ".join(missing)
        )

    book["Symbol"] = book["Symbol"].astype(str)
    return book.sort_values("Symbol").reset_index(drop=True), result
