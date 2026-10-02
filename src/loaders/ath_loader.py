"""All-time highs, read from the snapshot the daily sync job commits.

A true all-time high needs a decade of prices; the screener pipeline runs on a
two-year window because every calendar-momentum pass walks that frame row by
row, so lengthening it multiplies the cold start rather than the storage.

The daily sync job on GitHub Actions has neither constraint -- nobody is
waiting on it -- so it computes the highs once a day from Screener's whole
store (about ten years of closes, the basis the ranking uses; no Yahoo since
2026-10-02) and commits one small row per symbol. Production reads that file
in milliseconds.

When the snapshot is missing the caller falls back to the high water mark of
whatever history is already in memory. That is NOT an all-time high, and the
loader says so rather than letting a two-year high be labelled as one.
"""

from __future__ import annotations

import os
import threading

import pandas as pd

from src.core import startup_metrics as metrics
from src.core.config import REPO_ATH_FILE
from src.core.logger import logger


# One engine build reads this file three times -- ath_series once and
# ath_date_series twice, at each of the two ATH sites in momentum.py -- and
# every read re-parsed the same 750-row CSV from disk.
#
# Keyed on the file's identity rather than just its path, so the daily sync
# rewriting the snapshot invalidates the entry instead of serving yesterday's
# highs for the life of the process. Lock because Streamlit serves concurrent
# sessions from one process; the worst a race costs is a duplicate read, but
# the dict must not be mutated from two threads at once.
_SNAPSHOT_CACHE: dict[tuple, pd.DataFrame] = {}
_SNAPSHOT_LOCK = threading.Lock()


def _file_identity(target: str) -> tuple:
    """(path, mtime, size), or (path,) when the file is not there."""
    try:
        st = os.stat(target)
        return (target, st.st_mtime_ns, st.st_size)
    except OSError:
        return (target,)


def clear_snapshot_cache() -> None:
    """For tests, and for any caller that rewrites the file in-process."""
    with _SNAPSHOT_LOCK:
        _SNAPSHOT_CACHE.clear()


def load_ath_snapshot(path: str | None = None) -> pd.DataFrame:
    """Per-symbol all-time highs, or an empty frame when unavailable.

    Columns: Symbol, ATH, ATHDate, AsOf. Never raises -- a missing or malformed
    snapshot degrades to the in-memory fallback rather than taking the app down.

    Memoised on the file's identity. Returns a COPY: callers set an index on
    the result, and handing out the cached frame would let one caller's
    set_index reshape what every later caller receives.
    """
    target = path or REPO_ATH_FILE
    key = _file_identity(target)
    with _SNAPSHOT_LOCK:
        hit = _SNAPSHOT_CACHE.get(key)
    if hit is not None:
        metrics.incr("ath_snapshot_cache_hit")
        return hit.copy()
    frame = _read_ath_snapshot(target)
    with _SNAPSHOT_LOCK:
        _SNAPSHOT_CACHE[key] = frame
        # The path only ever has one live identity; drop stale generations so
        # a long-running process does not accumulate old snapshots.
        for stale in [k for k in _SNAPSHOT_CACHE if k[0] == target and k != key]:
            del _SNAPSHOT_CACHE[stale]
    return frame.copy()


def _read_ath_snapshot(target: str) -> pd.DataFrame:
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


def ath_date_series(path: str | None = None) -> pd.Series:
    """When each all-time high was printed, indexed by symbol.

    Shown on hover over % ATH. Over a long window Yahoo's old NSE history
    carries bad ticks, and one spurious print sets a permanent phantom high; a
    stock reading -90% from a peak dated 2007 is a very different claim from
    one dated last month, and the reader should be able to tell them apart.
    """
    df = load_ath_snapshot(path)
    if df.empty or "ATHDate" not in df.columns:
        return pd.Series(dtype=object)
    return df.set_index("Symbol")["ATHDate"]


def build_ath_snapshot(symbols: list[str], store: pd.DataFrame | None = None) -> pd.DataFrame:
    """Per-symbol all-time highs from Screener's whole close history.

    Run by the daily sync job on GitHub Actions, never by the app.

    THE ADJUSTMENT BASIS MUST MATCH THE APP'S. The ranking now reads
    Screener's closes (split and bonus adjusted, not dividends), so the high
    is taken from the same series: a high on any other basis would put a stock
    that split 1:5 at ~80% below a high it never had. Screener carries closes
    only, so this is a closing high, over as far back as the store reaches
    (about ten years; weekly through 2023-24).

    `store` is the Screener store (columns (symbol, field)); None fetches the
    published one.
    """
    empty = pd.DataFrame(columns=["Symbol", "ATH", "ATHDate", "AsOf"])
    if store is None:  # pragma: no cover - exercised only against the network
        from src.loaders import price_source

        store = price_source.fetch_screener_store()
    if store is None or store.empty or not isinstance(store.columns, pd.MultiIndex):
        return empty
    try:
        closes = store.xs("Close", axis=1, level=-1)
    except Exception:  # noqa: BLE001
        return empty
    wanted = [s for s in dict.fromkeys(str(x).upper() for x in symbols) if s in closes.columns]
    closes = closes[wanted].apply(pd.to_numeric, errors="coerce")
    if closes.empty:
        return empty
    ath = closes.max()
    ath = ath[ath > 0].dropna()
    if ath.empty:
        return empty
    peak_date = closes[ath.index].idxmax()
    index = pd.DatetimeIndex(closes.index)
    logger.info("All-time highs from Screener: %d symbols, %d sessions, %s to %s",
                len(ath), len(index), index[0].date(), index[-1].date())
    return pd.DataFrame({
        "Symbol": ath.index,
        "ATH": ath.values,
        "ATHDate": [str(pd.Timestamp(d).date()) if pd.notna(d) else "" for d in peak_date.values],
        "AsOf": str(index[-1].date()),
    }).sort_values("Symbol").reset_index(drop=True)
