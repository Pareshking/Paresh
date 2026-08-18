"""Seed the price cache from the snapshot the daily sync publishes.

Streamlit Cloud wipes /tmp on every container restart, so production began each
cold start with no price history and re-downloaded two years of OHLCV for 750
symbols from Yahoo. That cost roughly 38 seconds and put a rate-limited third
party in the critical path -- which is precisely how the screener went down
twice on 2026-08-18, once when SBIN was throttled and once when TATAPOWER was.

The daily sync already fetches that history on GitHub Actions. It publishes the
result as a release asset, and this module pulls it down once into the empty
cache. Everything after that is the loader's existing behaviour: the cache is
either fresh, or its incremental path fetches only the sessions published since.

This is an ACCELERATOR, NOT A DEPENDENCY. Every failure path here returns False
and leaves the cache untouched, so an unreachable snapshot costs a slow cold
start rather than an outage.
"""

from __future__ import annotations

import os
import tempfile
import time

import pandas as pd
import requests

from src.core import startup_metrics as metrics
from src.core.config import PRICE_SNAPSHOT_URL, PRICES_FILE
from src.core.logger import logger

# Generous, because the alternative to waiting is a 38-second Yahoo download.
DOWNLOAD_TIMEOUT_S: int = int(os.getenv("UMIYA_SNAPSHOT_TIMEOUT_S", "60"))
# A truncated or HTML error page must never be written over the cache.
MIN_PLAUSIBLE_BYTES: int = 200_000


def seed_price_cache_from_snapshot(url: str | None = None) -> bool:
    """Populate an EMPTY price cache from the published snapshot.

    Returns True only when the cache was actually seeded. Never raises, and
    never overwrites a cache that already exists -- a cache on disk is either
    current or the loader knows how to top it up, and either way it is better
    than a network round trip.
    """
    if os.path.exists(PRICES_FILE):
        metrics.note("price_snapshot", "cache_present")
        return False

    target = url or PRICE_SNAPSHOT_URL
    started = time.perf_counter()
    tmp_path = None
    try:
        resp = requests.get(target, timeout=DOWNLOAD_TIMEOUT_S, stream=True)
        if resp.status_code != 200:
            logger.info(
                "Price snapshot unavailable (HTTP %s); falling back to a full "
                "download.", resp.status_code
            )
            metrics.note("price_snapshot", f"http_{resp.status_code}")
            return False

        os.makedirs(os.path.dirname(PRICES_FILE), exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(
            suffix=".parquet", dir=os.path.dirname(PRICES_FILE)
        )
        size = 0
        with os.fdopen(fd, "wb") as fh:
            for chunk in resp.iter_content(chunk_size=1 << 20):
                if chunk:
                    fh.write(chunk)
                    size += len(chunk)

        if size < MIN_PLAUSIBLE_BYTES:
            # A 404 page, a redirect body, or a truncated transfer. Writing it
            # over the cache would turn a slow start into a broken one.
            logger.warning(
                "Price snapshot was only %d bytes; ignoring it.", size
            )
            metrics.note("price_snapshot", "too_small")
            return False

        # Parse before adopting. A corrupt parquet must fail here, where the
        # consequence is a full download, and not later inside the engine.
        frame = pd.read_parquet(tmp_path)
        if frame.empty or len(frame.columns) == 0:
            metrics.note("price_snapshot", "empty_frame")
            return False

        os.replace(tmp_path, PRICES_FILE)
        tmp_path = None

        elapsed = time.perf_counter() - started
        metrics.note("price_snapshot", "seeded")
        metrics.note("price_snapshot_mb", round(size / 1024**2, 1))
        metrics.note("price_snapshot_seconds", round(elapsed, 1))
        try:
            metrics.note(
                "price_snapshot_last_session",
                str(pd.Timestamp(frame.index[-1]).date()),
            )
        except Exception:
            pass
        logger.info(
            "Price cache seeded from snapshot: %d rows, %d series, %.1f MB in %.1fs",
            len(frame), len(frame.columns), size / 1024**2, elapsed,
        )
        return True

    except Exception as exc:
        logger.warning(
            "Price snapshot could not be used (%s: %s); falling back to a full "
            "download.", type(exc).__name__, exc
        )
        metrics.note("price_snapshot", f"error_{type(exc).__name__}")
        return False
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
