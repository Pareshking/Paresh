"""NSE's own daily Nifty 500 and Nifty 50 closes (data/benchmarks.csv).

The R2 index-level reader (`fetch_index_levels`, dataset indices/prices/research)
was read only by the old Dashboard and went with it on 21 Nov 2026; the size
indices now come from data/benchmark_indices.csv (src/loaders/benchmark_indices.py).
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from src.core.logger import logger

BENCHMARKS_FILE = Path(__file__).resolve().parents[2] / "data" / "benchmarks.csv"


@st.cache_data(ttl=3600, show_spinner=False)
def nse_benchmarks() -> pd.DataFrame | None:
    """NSE's own daily Nifty 500 and Nifty 50 closes (data/benchmarks.csv)."""
    try:
        frame = pd.read_csv(BENCHMARKS_FILE, parse_dates=["date"]).set_index("date").sort_index()
    except Exception as exc:
        logger.warning("benchmarks.csv unreadable: %s", type(exc).__name__)
        return None
    # A file cut off mid-row still parses, but its dates come back as strings,
    # and every consumer then compares a str with a Timestamp: the Dashboard,
    # Breadth and Sectors all died on `searchsorted` with "'<' not supported
    # between instances of 'str' and 'Timestamp'" (launch slot 5, 10 Nov 2026).
    # A file we cannot date is a file we cannot use, so say so once, here,
    # rather than in three views.
    if not isinstance(frame.index, pd.DatetimeIndex):
        logger.warning("benchmarks.csv has no usable dates (index is %s); treating it as absent.",
                       type(frame.index).__name__)
        return None
    return frame
