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
    book = book.sort_values("Symbol").reset_index(drop=True)
    # The fill date and as-of travel with the book, so every page reads them from one
    # place. Actions' standing weights need the fill date; without it the 30 Nov plan
    # fell back to equal weight instead of the record's held weights (found 20 Nov 2026).
    meta = result.get("live_meta") or {}
    book.attrs["as_of"] = meta.get("as_of")
    book.attrs["fill_date"] = meta.get("fill_date")
    return book, result


def unpriced_note(record: dict[str, Any] | None) -> tuple[str, str] | None:
    """(head, body) naming the members a live book was formed without, or None (S175/S194 F4).

    The Nifty 1000's live book is formed from the members we hold a close for at
    each signal close; the monthly freeze refuses such a month, so the page says
    which members are missing instead of presenting the book as the index's.
    """
    gaps = (record or {}).get("unpriced") or {}
    if not gaps:
        return None
    from src.ui.formats import date as _date   # "30 Oct 2026", not "2026-10-30" (S173 rule 3)
    day, names = sorted(gaps.items())[-1]
    # S203 pf.err.3: the relative clause read as "members we hold".
    n = len(names)
    head = (f"This book was formed without {n} member{'s' if n != 1 else ''}: we have no close for "
            f"{'them' if n != 1 else 'it'} on {_date(day)}.")
    body = (", ".join(names[:12]) + (" and more" if len(names) > 12 else "")
            + ". Their prices are being collected; the month is frozen only once every member has a close.")
    return head, body
