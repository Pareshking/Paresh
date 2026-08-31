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

It is also the RECOVERY path. Seeding once per container was not enough: from
then on the cache could only advance through Yahoo, and Yahoo rate-limits the
shared Streamlit Cloud egress address. When that happened the loader logged
"no new price data" and returned the same frame for as long as the container
lived -- days of frozen prices, with the daily snapshot sitting one HTTPS GET
away carrying every session that was missing. snapshot_frame_if_newer is how
the loader gets out of that hole.
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


class _Snapshot:
    """A parsed snapshot plus the temporary file it was parsed from."""

    __slots__ = ("frame", "tmp_path", "size", "elapsed")

    def __init__(self, frame, tmp_path, size, elapsed):
        self.frame = frame
        self.tmp_path = tmp_path
        self.size = size
        self.elapsed = elapsed

    def adopt(self) -> bool:
        """Move the downloaded file into place as the cache. Atomic."""
        try:
            os.replace(self.tmp_path, PRICES_FILE)
            return True
        except OSError as exc:
            logger.warning("Could not adopt the price snapshot: %s", exc)
            self.discard()
            return False

    def discard(self) -> None:
        """Delete the download. For a snapshot that turned out not to be wanted."""
        try:
            if self.tmp_path and os.path.exists(self.tmp_path):
                os.unlink(self.tmp_path)
        except OSError:
            pass


def _last_session(frame: pd.DataFrame):
    """The last date a price frame carries, or None when it carries none."""
    try:
        return pd.Timestamp(frame.index[-1]).date()
    except Exception:
        return None


def _download_snapshot(url: str, fact: str):
    """Fetch and parse the published snapshot into memory.

    Returns the frame, or None on any failure -- and records WHICH failure
    under ``fact``, because "the snapshot did not help" has several very
    different causes (not published, refused, truncated, corrupt) that call for
    different responses from whoever reads the telemetry.

    The temporary file lands beside PRICES_FILE so the caller can adopt it with
    an atomic rename; it is always cleaned up, adopted or not.
    """
    started = time.perf_counter()
    tmp_path = None
    try:
        resp = requests.get(url, timeout=DOWNLOAD_TIMEOUT_S, stream=True)
        if resp.status_code != 200:
            logger.info(
                "Price snapshot unavailable (HTTP %s); falling back to a full "
                "download.", resp.status_code
            )
            metrics.note(fact, f"http_{resp.status_code}")
            return None

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
            logger.warning("Price snapshot was only %d bytes; ignoring it.", size)
            metrics.note(fact, "too_small")
            return None

        # Parse before adopting. A corrupt parquet must fail here, where the
        # consequence is a full download, and not later inside the engine.
        frame = pd.read_parquet(tmp_path)
        if frame.empty or len(frame.columns) == 0:
            metrics.note(fact, "empty_frame")
            return None

        elapsed = time.perf_counter() - started
        metrics.note("price_snapshot_mb", round(size / 1024**2, 1))
        metrics.note("price_snapshot_seconds", round(elapsed, 1))
        last = _last_session(frame)
        if last is not None:
            metrics.note("price_snapshot_last_session", str(last))
        logger.info(
            "Price snapshot fetched: %d rows, %d series, %.1f MB in %.1fs "
            "(last session %s)",
            len(frame), len(frame.columns), size / 1024**2, elapsed, last,
        )
        # Ownership of the file passes to the caller here, so the cleanup below
        # must stop seeing it -- otherwise the `finally` deletes the download
        # on its way out and every adopt() fails on a missing path.
        downloaded, tmp_path = tmp_path, None
        return _Snapshot(
            frame=frame, tmp_path=downloaded, size=size, elapsed=elapsed
        )

    except Exception as exc:
        logger.warning(
            "Price snapshot could not be used (%s: %s); falling back to a full "
            "download.", type(exc).__name__, exc
        )
        metrics.note(fact, f"error_{type(exc).__name__}")
        return None
    finally:
        # Only failures reach here still holding tmp_path; the success path
        # handed it to the caller and cleared it.
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


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

    snap = _download_snapshot(url or PRICE_SNAPSHOT_URL, "price_snapshot")
    if snap is None or not snap.adopt():
        return False

    metrics.note("price_snapshot", "seeded")
    logger.info(
        "Price cache seeded from snapshot: %d rows, %d series, %.1f MB in %.1fs",
        len(snap.frame), len(snap.frame.columns),
        snap.size / 1024**2, snap.elapsed,
    )
    return True


def snapshot_frame_if_newer(current_last, url: str | None = None):
    """Adopt the published snapshot when it carries sessions the cache lacks.

    The counterpart to seeding, for a container whose cache has fallen behind
    and cannot catch up: Yahoo refuses the host, so the incremental top-up
    returns nothing and the same frame is served indefinitely. The snapshot is
    rebuilt every trading evening by a job that Yahoo does answer, so it is the
    one source that can still move production forward.

    Returns the newer frame, having already written it over the cache, or None
    -- which covers every failure AND the ordinary case where the snapshot is
    no fresher than what is already on disk. A snapshot that is merely EQUAL is
    not adopted: overwriting a cache with the same sessions would throw away a
    top-up Yahoo did manage to deliver, in exchange for nothing.
    """
    snap = _download_snapshot(url or PRICE_SNAPSHOT_URL, "price_recovery")
    if snap is None:
        return None

    snap_last = _last_session(snap.frame)
    if snap_last is None or (current_last is not None and snap_last <= current_last):
        metrics.note("price_recovery", "snapshot_not_newer")
        logger.info(
            "Published snapshot ends %s, the cache already holds %s; keeping the "
            "cache.", snap_last, current_last,
        )
        snap.discard()
        return None

    if not snap.adopt():
        metrics.note("price_recovery", "adopt_failed")
        return None

    metrics.note("price_recovery", "recovered_from_snapshot")
    metrics.note("price_recovery_gained_sessions", str(snap_last))
    logger.warning(
        "Price cache recovered from the published snapshot: %s -> %s. Yahoo "
        "returned no new sessions, so the cache was stale.",
        current_last, snap_last,
    )
    return snap.frame
