"""The long NSE price file the 2010+ backtest runs on, read from the data-latest release.

scripts/build_nse_long_prices.py writes it from R2's NSE bhavcopy (2008 to date)
and nse_long_prices.yml uploads it weekly:

    nse_long_close.parquet   closes adjusted for splits, bonuses, consolidations
                             and demergers (price-confirmed), renames joined;
                             no dividends, no rights issues
    nse_long_value.parquet   traded value per session, Rs crore
    nse_long_report.json     what the build found

The files are cached in DATA_DIR and fetched again after CACHE_TTL_S. Never
raises: anything unreachable returns None and the page says so.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
import time
from pathlib import Path

import pandas as pd
import requests

from src.core.config import DATA_DIR, NSE_LONG_BASE_URL

logger = logging.getLogger(__name__)

CLOSE_FILE = "nse_long_close.parquet"
VALUE_FILE = "nse_long_value.parquet"
REPORT_FILE = "nse_long_report.json"
CACHE_TTL_S = 24 * 3600
TIMEOUT_S = 120


def _fetch(name: str, base: str, cache: Path) -> Path | None:
    """The asset on disk: the cached copy while fresh, else downloaded; None if unreachable."""
    path = cache / name
    if path.exists() and time.time() - path.stat().st_mtime < CACHE_TTL_S:
        return path
    resp = None
    try:
        resp = requests.get(f"{base}/{name}", timeout=TIMEOUT_S, stream=True)
        if resp.status_code != 200:
            logger.info("Long NSE file %s unavailable (HTTP %s).", name, resp.status_code)
            return path if path.exists() else None
        cache.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=cache, suffix=".part")
        with os.fdopen(fd, "wb") as fh:
            for chunk in resp.iter_content(chunk_size=1 << 18):
                fh.write(chunk)
        os.replace(tmp, path)
        return path
    except Exception as exc:  # noqa: BLE001  a stale copy beats none
        logger.info("Long NSE file %s fetch failed (%s).", name, type(exc).__name__)
        return path if path.exists() else None
    finally:
        if resp is not None:
            resp.close()


def load(base: str = NSE_LONG_BASE_URL, cache: Path | str = DATA_DIR
         ) -> tuple[pd.DataFrame, pd.DataFrame, dict] | None:
    """(adjusted closes, traded value in Rs Cr, build report), or None if unavailable."""
    cache = Path(cache)
    paths = [_fetch(n, base, cache) for n in (CLOSE_FILE, VALUE_FILE, REPORT_FILE)]
    if any(p is None for p in paths):
        return None
    try:
        close = pd.read_parquet(paths[0])
        value = pd.read_parquet(paths[1])
        report = json.loads(paths[2].read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        logger.info("Long NSE file unreadable (%s).", type(exc).__name__)
        return None
    close.index = pd.DatetimeIndex(close.index)
    value.index = pd.DatetimeIndex(value.index)
    if close.empty:
        return None
    # float32 as stored: 16 years x 1,400 names is ~27 MB a field, not 54.
    return close.astype("float32"), value.astype("float32"), report


def average_value(value: pd.DataFrame) -> pd.DataFrame:
    """Trailing average traded value in Rs crore: the input liquidity.passes() reads."""
    from src.engine import liquidity

    return value.rolling(liquidity.WINDOW, min_periods=liquidity.MIN_SESSIONS).mean()
