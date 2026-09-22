"""Manifest-pinned research/backtest consumer boundary for R2.

This adapter deliberately performs no ranking, pricing, universe selection, or
research logic. It resolves one explicit immutable revision through the R2
storage contract and returns the verified dataframe plus its exact pin.
"""
from __future__ import annotations

from dataclasses import dataclass
import re

import pandas as pd

from src.storage.reader import R2DatasetReader, R2DatasetRef


class R2ResearchConsumerError(ValueError):
    """A research run cannot be satisfied by the requested R2 revision."""


@dataclass(frozen=True)
class R2ResearchPin:
    dataset: str
    as_of: str
    revision_sha256: str


@dataclass(frozen=True)
class R2ResearchDataset:
    pin: R2ResearchPin
    ref: R2DatasetRef
    frame: pd.DataFrame


def read_pinned_dataset(
    reader: R2DatasetReader,
    *,
    pin: R2ResearchPin,
) -> R2ResearchDataset:
    """Read exactly the requested immutable revision.

    A research/backtest run must supply its dataset, evidence date, and
    revision SHA. This function never falls back to the mutable current
    pointer, because doing so would make a previously published run
    non-reproducible.
    """
    if not pin.dataset.strip():
        raise R2ResearchConsumerError("dataset must not be empty")
    if not pin.as_of:
        raise R2ResearchConsumerError("as_of must not be empty")
    try:
        pd.Timestamp(pin.as_of).normalize()
    except Exception as exc:
        raise R2ResearchConsumerError(f"invalid as_of date: {pin.as_of!r}") from exc
    if not re.fullmatch(r"[0-9a-f]{64}", pin.revision_sha256):
        raise R2ResearchConsumerError("revision_sha256 must be a lowercase 64-character SHA-256")
    try:
        ref = reader.resolve_revision(
            pin.dataset,
            pin.as_of,
            pin.revision_sha256,
        )
    except (FileNotFoundError, ValueError) as exc:
        raise R2ResearchConsumerError(str(exc)) from exc

    frame = reader.read_parquet(ref)
    return R2ResearchDataset(pin=pin, ref=ref, frame=frame)


def pin_from_ref(ref: R2DatasetRef) -> R2ResearchPin:
    """Convert a verified R2 reference into a serializable research pin."""
    return R2ResearchPin(
        dataset=ref.dataset,
        as_of=ref.as_of,
        revision_sha256=ref.revision_sha256,
    )
