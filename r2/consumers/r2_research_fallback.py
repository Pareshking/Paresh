"""Explicit, opt-in R2 research fallback boundary.

R2 is always attempted first. A local/release artifact is used only when the
caller explicitly supplies a fallback path. The fallback is never silently
written back to R2 and its provenance is returned to the caller.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hashlib
import pandas as pd

from r2.consumers.r2_research import R2ResearchDataset, R2ResearchPin, read_pinned_dataset
from src.storage.reader import R2DatasetReader


class R2ResearchFallbackError(ValueError):
    """Neither the pinned R2 revision nor the explicitly allowed fallback works."""


@dataclass(frozen=True)
class R2ResearchRead:
    frame: pd.DataFrame
    source: str
    pin: R2ResearchPin | None
    sha256: str


def _file_sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_with_explicit_fallback(
    reader: R2DatasetReader,
    *,
    pin: R2ResearchPin,
    fallback_path: str | None = None,
) -> R2ResearchRead:
    """Use exact R2 first; fallback only when the caller explicitly opts in."""
    try:
        data: R2ResearchDataset = read_pinned_dataset(reader, pin=pin)
        return R2ResearchRead(
            frame=data.frame,
            source="r2",
            pin=pin,
            sha256=pin.revision_sha256,
        )
    except Exception as r2_error:
        if not fallback_path:
            raise R2ResearchFallbackError(
                f"pinned R2 read failed and no fallback was authorized: {r2_error}"
            ) from r2_error

        path = Path(fallback_path)
        if not path.is_file():
            raise R2ResearchFallbackError(
                f"authorized fallback artifact does not exist: {path}"
            ) from r2_error
        try:
            frame = pd.read_parquet(path)
        except Exception as fallback_error:
            raise R2ResearchFallbackError(
                f"authorized fallback artifact is unreadable: {path}"
            ) from fallback_error
        return R2ResearchRead(
            frame=frame,
            source=f"fallback:{path}",
            pin=None,
            sha256=_file_sha(path),
        )
