"""NSE index levels (Nifty 50, Next 50, Midcap 150, Smallcap 250, Microcap 250)
from the R2 dataset the nightly `r2_nse_index_prices` job publishes.

Read through the dataset's current pointer, like the price store. Returns None
when R2 is not configured or the read fails: the dashboard then leaves the
size table out and says so, rather than showing figures it could not load.
"""
from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import streamlit as st

from src.core.logger import logger

DATASET = "indices/prices/research"
BENCHMARKS_FILE = Path(__file__).resolve().parents[2] / "data" / "benchmarks.csv"


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_index_levels() -> pd.DataFrame | None:
    # Local development without R2 credentials: point INDEX_LEVELS_FILE at a
    # copy of the published parquet. Never set on the deployed app.
    local = os.getenv("INDEX_LEVELS_FILE", "").strip()
    if local:
        try:
            return pd.read_parquet(local)
        except Exception as exc:
            logger.warning("INDEX_LEVELS_FILE unreadable: %s", type(exc).__name__)
            return None
    try:
        from src.storage.r2 import R2Archive, R2Config
        from src.storage.reader import R2DatasetReader

        reader = R2DatasetReader(R2Archive(R2Config.from_env()))
        frame = reader.read_parquet(reader.resolve_current(DATASET))
    except Exception as exc:  # not configured here, or the read failed
        logger.warning("Index levels unavailable from R2 (%s): %s", DATASET, type(exc).__name__)
        return None
    if frame is None or frame.empty or not {"date", "index", "close"} <= set(frame.columns):
        return None
    return frame


@st.cache_data(ttl=3600, show_spinner=False)
def nse_benchmarks() -> pd.DataFrame | None:
    """NSE's own daily Nifty 500 and Nifty 50 closes (data/benchmarks.csv)."""
    try:
        frame = pd.read_csv(BENCHMARKS_FILE, parse_dates=["date"]).set_index("date").sort_index()
    except Exception as exc:
        logger.warning("benchmarks.csv unreadable: %s", type(exc).__name__)
        return None
    return frame
