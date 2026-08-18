"""All-time highs, read from the snapshot the daily sync job commits.

A true all-time high needs a decade of prices; the screener pipeline runs on a
two-year window because every calendar-momentum pass walks that frame row by
row, so lengthening it multiplies the cold start rather than the storage.

The daily sync job on GitHub Actions has neither constraint -- nobody is
waiting on it, and NSE and Yahoo both answer it -- so it computes the highs
once a day from ATH_HISTORY_PERIOD of data and commits one small row per
symbol. Production reads that file in milliseconds.

When the snapshot is missing the caller falls back to the high water mark of
whatever history is already in memory. That is NOT an all-time high, and the
loader says so rather than letting a two-year high be labelled as one.
"""

from __future__ import annotations

import os

import pandas as pd

from src.core import startup_metrics as metrics
from src.core.config import REPO_ATH_FILE
from src.core.logger import logger


def load_ath_snapshot(path: str | None = None) -> pd.DataFrame:
    """Per-symbol all-time highs, or an empty frame when unavailable.

    Columns: Symbol, ATH, ATHDate, AsOf. Never raises -- a missing or malformed
    snapshot degrades to the in-memory fallback rather than taking the app down.
    """
    target = path or REPO_ATH_FILE
    if not os.path.exists(target):
        metrics.note("ath_path", "absent")
        return pd.DataFrame(columns=["Symbol", "ATH", "ATHDate", "AsOf"])
    try:
        df = pd.read_csv(target)
    except Exception as exc:
        logger.warning(f"All-time-high snapshot unreadable ({exc}); falling back.")
        metrics.note("ath_path", "unreadable")
        return pd.DataFrame(columns=["Symbol", "ATH", "ATHDate", "AsOf"])

    if "Symbol" not in df.columns or "ATH" not in df.columns:
        metrics.note("ath_path", "malformed")
        return pd.DataFrame(columns=["Symbol", "ATH", "ATHDate", "AsOf"])

    df["Symbol"] = df["Symbol"].astype(str).str.strip().str.upper()
    df["ATH"] = pd.to_numeric(df["ATH"], errors="coerce")
    df = df[df["ATH"] > 0].dropna(subset=["Symbol", "ATH"])

    metrics.note("ath_path", "repo_snapshot")
    metrics.note("ath_symbols", int(len(df)))
    if "AsOf" in df.columns and len(df):
        as_of = str(df["AsOf"].iloc[0] or "").strip()
        if as_of:
            metrics.note("ath_as_of", as_of)
    logger.info(f"All-time-high snapshot: {len(df)} symbols")
    return df


def ath_series(path: str | None = None) -> pd.Series:
    """All-time high per symbol, indexed by symbol."""
    df = load_ath_snapshot(path)
    if df.empty:
        return pd.Series(dtype=float)
    return df.set_index("Symbol")["ATH"]
