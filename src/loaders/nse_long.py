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

Where they come from (S142, owner 17 Nov 2026: "Yes weekly"): R2 first, the
same weekly build published as R2_DATASETS, each revision checked against its
SHA-256 by the reader; the release only when R2 is off or cannot serve them.
The release links stop working for the app if the repository goes private.
The value and report files are taken from the same build date as the closes
(as_of = the last session), so one read never mixes two weeks.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path

import pandas as pd
import requests

from src.core.config import DATA_DIR, NSE_LONG_BASE_URL
# The app's own logger: under getLogger(__name__) these lines never reached the
# Streamlit Cloud log (owner's log of 17 Nov 2026 had none), so whether the
# Backtest's long file came from R2 or the release could not be read there.
from src.core.logger import logger


CLOSE_FILE = "nse_long_close.parquet"
VALUE_FILE = "nse_long_value.parquet"
REPORT_FILE = "nse_long_report.json"
CACHE_TTL_S = 24 * 3600
TIMEOUT_S = 120

# nse_long_prices.yml publishes the three files here every Saturday; the report
# (JSON) as a one-row table, report_to_parquet(), because the R2 publisher reads
# parquet. Retention keeps the newest two dates (scripts/r2_retention.py).
R2_DATASETS = {
    CLOSE_FILE: "prices/nse_long_close",
    VALUE_FILE: "prices/nse_long_value",
    REPORT_FILE: "prices/nse_long_report",
}
REPORT_COLUMN = "report_json"


def report_to_parquet(report_json: Path | str, out: Path | str) -> Path:
    """The build report as a one-row parquet: as_of (its last session) and the JSON text."""
    text = Path(report_json).read_text(encoding="utf-8")
    last = json.loads(text).get("last_session")
    if not last:
        raise ValueError("the report has no last_session to date it by")
    out = Path(out)
    pd.DataFrame({"as_of": [str(last)], REPORT_COLUMN: [text]}).to_parquet(out, index=False)
    return out


def _report_text(parquet_bytes: bytes) -> bytes:
    from io import BytesIO

    frame = pd.read_parquet(BytesIO(parquet_bytes))
    return str(frame[REPORT_COLUMN].iloc[0]).encode("utf-8")


def _from_r2(name: str, cache: Path, as_of: str | None = None) -> tuple[Path | None, str | None]:
    """(cached path, as_of) of `name` read from R2, or (None, None) when R2 is off or fails."""
    try:
        from r2.consumers import r2_streamlit

        if not r2_streamlit.enabled():
            return None, None
        from src.storage.r2 import R2Archive, R2Config
        from src.storage.reader import R2DatasetReader

        reader = R2DatasetReader(R2Archive(R2Config.from_env()))
        ref = reader.resolve_current(R2_DATASETS[name], as_of=as_of)
        data = reader.read_bytes(ref)          # size and SHA-256 checked against the manifest
        if name == REPORT_FILE:
            data = _report_text(data)
        cache.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=cache, suffix=".part")
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        path = cache / name
        os.replace(tmp, path)
        logger.info("Long NSE file %s from R2 (as_of %s).", name, ref.as_of)
        return path, ref.as_of
    except Exception as exc:  # noqa: BLE001  the release is the fallback
        logger.info("Long NSE file %s not read from R2 (%s); trying the release.", name, type(exc).__name__)
        return None, None


def _fetch(name: str, base: str, cache: Path, as_of: str | None = None,
           try_r2: bool = True) -> Path | None:
    """The asset on disk: the cached copy while fresh, else R2, else the release; None if unreachable."""
    path = cache / name
    if path.exists() and time.time() - path.stat().st_mtime < CACHE_TTL_S:
        return path
    if try_r2:
        got, _ = _from_r2(name, cache, as_of)
        if got is not None:
            return got
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


def load(base: str = NSE_LONG_BASE_URL, cache: Path | str = DATA_DIR, *,
         with_value: bool = True) -> tuple[pd.DataFrame, pd.DataFrame | None, dict] | None:
    """(adjusted closes, traded value in Rs Cr, build report), or None if unavailable.

    with_value=False leaves the traded-value file (~24 MB) undownloaded and
    returns None in its place: it is read only when a liquidity floor is set,
    so the first open of the history tab fetches half as much (owner,
    2026-10-03: the file must not make the backtest load late).
    """
    cache = Path(cache)
    names = (CLOSE_FILE, REPORT_FILE) + ((VALUE_FILE,) if with_value else ())
    # The closes first; the other files from the same build date when they come from R2.
    close_path = cache / CLOSE_FILE
    as_of, tried = None, False
    if not (close_path.exists() and time.time() - close_path.stat().st_mtime < CACHE_TTL_S):
        _, as_of = _from_r2(CLOSE_FILE, cache)
        tried = True
    paths = {CLOSE_FILE: _fetch(CLOSE_FILE, base, cache, try_r2=not tried)}
    paths.update({n: _fetch(n, base, cache, as_of) for n in names if n != CLOSE_FILE})
    if any(p is None for p in paths.values()):
        return None
    try:
        close = pd.read_parquet(paths[CLOSE_FILE])
        report = json.loads(paths[REPORT_FILE].read_text(encoding="utf-8"))
        value = pd.read_parquet(paths[VALUE_FILE]) if with_value else None
    except Exception as exc:  # noqa: BLE001
        logger.info("Long NSE file unreadable (%s).", type(exc).__name__)
        return None
    close.index = pd.DatetimeIndex(close.index)
    if close.empty:
        return None
    if value is not None:
        value.index = pd.DatetimeIndex(value.index)
        value = value.astype("float32")
    # float32 as stored: 16 years x 1,400 names is ~27 MB a field, not 54.
    return close.astype("float32"), value, report


def load_value(base: str = NSE_LONG_BASE_URL, cache: Path | str = DATA_DIR) -> pd.DataFrame | None:
    """The traded-value file alone (Rs Cr), or None if unavailable."""
    path = _fetch(VALUE_FILE, base, Path(cache))
    if path is None:
        return None
    try:
        value = pd.read_parquet(path)
    except Exception as exc:  # noqa: BLE001
        logger.info("Long NSE value file unreadable (%s).", type(exc).__name__)
        return None
    value.index = pd.DatetimeIndex(value.index)
    return value.astype("float32")


def average_value(value: pd.DataFrame) -> pd.DataFrame:
    """Trailing average traded value in Rs crore: the input liquidity.passes() reads."""
    from src.engine import liquidity

    return value.rolling(liquidity.WINDOW, min_periods=liquidity.MIN_SESSIONS).mean()
