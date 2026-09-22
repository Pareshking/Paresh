"""Feature-flagged Streamlit historical reader boundary.

Disabled by default. When enabled, callers must provide an immutable R2 pin;
there is no implicit current-pointer fallback.
"""
from __future__ import annotations
import os
from r2.consumers.r2_research import R2ResearchPin, read_pinned_dataset
from src.storage.reader import R2DatasetReader

ENV_FLAG="R2_STREAMLIT_READER_ENABLED"

def enabled() -> bool:
    return os.getenv(ENV_FLAG,"0").strip().lower() in {"1","true","yes","on"}

def read_historical(reader:R2DatasetReader, *, pin:R2ResearchPin):
    if not enabled():
        raise RuntimeError(f"{ENV_FLAG} is disabled")
    return read_pinned_dataset(reader,pin=pin)
