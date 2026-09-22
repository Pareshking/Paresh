"""Explicit consumer boundary for historical R2 evidence.

This module is deliberately outside src/storage and outside the V1 runtime. The storage layer knows only
how to resolve and verify immutable R2 datasets. This module interprets the
published membership schema for stock-research consumers.

It does not replace the existing in-process membership engine and it does not
change any production/backtest data source. It is an opt-in, manifest-pinned
consumer path that can be validated before migration.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from src.storage.reader import R2DatasetReader, R2DatasetRef


class R2HistoricalConsumerError(ValueError):
    """Published R2 evidence cannot satisfy the consumer contract."""


MEMBERSHIP_DATASET = "indices/membership/nifty_total_market"


def _as_date(value: Any) -> pd.Timestamp:
    try:
        return pd.Timestamp(value).normalize()
    except Exception as exc:
        raise R2HistoricalConsumerError(f"invalid as_of date: {value!r}") from exc


def membership_from_frame(frame: pd.DataFrame, *, index: str, as_of: Any) -> set[str] | None:
    """Return members whose archived interval contains as_of; unknown coverage returns None."""
    required = {"index", "symbol", "effective_from", "effective_to", "source", "evidence_date"}
    missing = required - set(frame.columns)
    if missing:
        raise R2HistoricalConsumerError(f"membership dataset missing columns: {sorted(missing)}")
    target = _as_date(as_of)
    rows = frame.loc[frame["index"].astype(str) == str(index)].copy()
    if rows.empty:
        return None
    rows["symbol"] = rows["symbol"].astype(str).str.strip().str.upper()
    rows["effective_from"] = pd.to_datetime(rows["effective_from"], errors="coerce").dt.normalize()
    rows["effective_to"] = pd.to_datetime(rows["effective_to"], errors="coerce").dt.normalize()
    rows["evidence_date"] = pd.to_datetime(rows["evidence_date"], errors="coerce").dt.normalize()
    if rows[["effective_from", "evidence_date"]].isna().any().any():
        raise R2HistoricalConsumerError("membership contains invalid dates")
    if rows["symbol"].eq("").any():
        raise R2HistoricalConsumerError("membership contains an empty symbol")
    active = rows[(rows["effective_from"] <= target) & (rows["effective_to"].isna() | (rows["effective_to"] >= target))]
    if active.empty:
        # No interval covering the requested date is unknown historical coverage,
        # not an empty index. Never turn missing evidence into a valid empty universe.
        return None
    duplicates = active["symbol"][active["symbol"].duplicated()].tolist()
    if duplicates:
        raise R2HistoricalConsumerError("multiple active membership intervals: " + ", ".join(sorted(set(duplicates))))
    return set(active["symbol"])


def read_membership_as_of(reader: R2DatasetReader, *, as_of: Any, index: str = "nifty_total_market") -> tuple[R2DatasetRef, set[str] | None]:
    """Read the current manifest-pinned R2 membership revision and reconstruct members."""
    ref, frame = reader.read_current_parquet(MEMBERSHIP_DATASET)
    return ref, membership_from_frame(frame, index=index, as_of=as_of)
