"""Feature-flagged Streamlit R2 production reader.

Disabled by default. When enabled, Streamlit follows the latest validated
current pointer for the configured dataset. Each published revision remains
immutable and independently reproducible.
"""
from __future__ import annotations

import os

from r2.consumers.r2_research import R2ResearchPin, read_pinned_dataset
from src.storage.reader import R2DatasetReader
from src.storage.r2 import R2Archive, R2Config

ENV_FLAG = "R2_STREAMLIT_READER_ENABLED"
DATASET_ENV = "R2_STREAMLIT_DATASET"
DEFAULT_DATASET = "prices/screener"
# The adjusted 10-year Yahoo archive the daily sync republishes every night
# (prices_full.parquet). NOT prices/yahoo/raw: that is an unadjusted provenance
# capture from a one-off build (auto_adjust=False, no "Adj Close"), frozen at
# its build date. Serving it made every split outside the corporate-action log
# a phantom crash in the Backtest and Track Record, on prices that stopped
# moving on 2026-09-21.
DEEP_HISTORY_DATASET = "prices/yahoo"



def enabled() -> bool:
    return os.getenv(ENV_FLAG, "0").strip().lower() in {"1", "true", "yes", "on"}


def configured_dataset() -> str:
    dataset = os.getenv(DATASET_ENV, DEFAULT_DATASET).strip()
    if not dataset:
        raise RuntimeError(f"{DATASET_ENV} must not be empty")
    return dataset


def configuration_key() -> str:
    """Return the cache identity for the live R2 source configuration.

    The production source is deliberately the latest validated R2 pointer,
    not a manually maintained revision pin. Streamlit cache TTL still limits
    how long an already-loaded daily snapshot can remain in memory.
    """
    return "|".join([
        "r2" if enabled() else "screener",
        configured_dataset(),
        "current",
    ])


def read_configured_deep_history():
    """Read the current R2 Yahoo-origin deep-history snapshot.

    The production app uses this as the transport for its historical feed;
    Yahoo remains the upstream publisher, not a runtime network dependency.
    """
    if not enabled():
        raise RuntimeError(f"{ENV_FLAG} is disabled")
    reader = R2DatasetReader(R2Archive(R2Config.from_env()))
    ref = reader.resolve_current(DEEP_HISTORY_DATASET)
    frame = reader.read_parquet(ref)
    return frame, R2ResearchPin(
        dataset=ref.dataset,
        as_of=ref.as_of,
        revision_sha256=ref.revision_sha256,
    )


def read_historical(reader: R2DatasetReader, *, pin: R2ResearchPin | None = None):
    if not enabled():
        raise RuntimeError(f"{ENV_FLAG} is disabled")
    if pin is None:
        ref = reader.resolve_current(configured_dataset())
        pin = R2ResearchPin(
            dataset=ref.dataset,
            as_of=ref.as_of,
            revision_sha256=ref.revision_sha256,
        )
    return read_pinned_dataset(reader, pin=pin)


def read_configured_screener():
    if not enabled():
        raise RuntimeError(f"{ENV_FLAG} is disabled")
    reader = R2DatasetReader(R2Archive(R2Config.from_env()))
    dataset = configured_dataset()
    ref = reader.resolve_current(dataset)
    pin = R2ResearchPin(
        dataset=ref.dataset,
        as_of=ref.as_of,
        revision_sha256=ref.revision_sha256,
    )
    frame = reader.read_parquet(ref)
    return frame, pin
