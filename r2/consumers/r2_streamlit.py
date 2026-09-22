"""Feature-flagged Streamlit historical reader boundary.

Disabled by default. When enabled, callers must provide an immutable R2 pin;
there is no implicit current-pointer fallback.
"""
from __future__ import annotations
import os
import re
from r2.consumers.r2_research import R2ResearchPin, read_pinned_dataset
from src.storage.reader import R2DatasetReader

ENV_FLAG="R2_STREAMLIT_READER_ENABLED"
DATASET_ENV="R2_STREAMLIT_DATASET"
AS_OF_ENV="R2_STREAMLIT_AS_OF"
REVISION_ENV="R2_STREAMLIT_REVISION_SHA256"
DEFAULT_DATASET="prices/screener"

def enabled() -> bool:
    return os.getenv(ENV_FLAG,"0").strip().lower() in {"1","true","yes","on"}

def configured_pin() -> R2ResearchPin:
    dataset = os.getenv(DATASET_ENV, DEFAULT_DATASET).strip()
    as_of = os.getenv(AS_OF_ENV, "").strip()
    revision = os.getenv(REVISION_ENV, "").strip().lower()
    if not dataset:
        raise RuntimeError(f"{DATASET_ENV} must not be empty")
    if not as_of:
        raise RuntimeError(f"{AS_OF_ENV} is required when {ENV_FLAG} is enabled")
    if not re.fullmatch(r"[0-9a-f]{64}", revision):
        raise RuntimeError(f"{REVISION_ENV} must be a lowercase 64-character SHA-256")
    return R2ResearchPin(dataset=dataset, as_of=as_of, revision_sha256=revision)


def configuration_key() -> str:
    return "|".join([
        "r2" if enabled() else "screener",
        os.getenv(DATASET_ENV, DEFAULT_DATASET).strip(),
        os.getenv(AS_OF_ENV, "").strip(),
        os.getenv(REVISION_ENV, "").strip().lower(),
    ])


def read_historical(reader:R2DatasetReader, *, pin:R2ResearchPin | None = None):
    if not enabled():
        raise RuntimeError(f"{ENV_FLAG} is disabled")
    return read_pinned_dataset(reader, pin=pin or configured_pin())


def read_configured_screener():
    if not enabled():
        raise RuntimeError(f"{ENV_FLAG} is disabled")
    from src.storage.r2 import R2Archive, R2Config
    reader = R2DatasetReader(R2Archive(R2Config.from_env()))
    pin = configured_pin()
    dataset = read_pinned_dataset(reader, pin=pin)
    return dataset.frame, pin
