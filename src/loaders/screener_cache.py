"""The Screener store, read once per process and shared by every page.

app.py ranks from it and the Track Record comparison prices the other systems
from it. Until 2026-10-08 the comparison downloaded the store again through
price_source.fetch_screener_store(), which also bypassed the configured R2 pin
the app reads, so the two could price from different revisions (TODO S63).

Read-only: callers take cross-sections (from_screener), which are new frames.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.core import startup_metrics as metrics
from src.core.logger import logger


def configured() -> tuple[pd.DataFrame | None, str]:
    """(store, revision) for the app's configured source. May raise when R2 is configured and fails."""
    from r2.consumers import r2_streamlit

    result = fetch_screener_store(r2_streamlit.configuration_key())
    return result if result is not None else (None, "none")


# A resource, not data: the store is read-only here (from_screener takes
# cross-sections, which are new frames), so one copy serves every session
# instead of a 35 MB unpickle on every rerun. See _shared.
@st.cache_resource(show_spinner=False, ttl=3600, max_entries=2)
def fetch_screener_store(source_key: str):
    """Read Screener history, optionally from an immutable archive pin.

    The second return value is the source revision identity used to memoise
    shaping. For R2 it is the immutable SHA; for the legacy HTTPS path the
    existing one-hour cache TTL remains the freshness boundary.
    """
    from r2.consumers import r2_streamlit
    from src.loaders import price_source as _ps

    if r2_streamlit.enabled():
        try:
            frame, pin = r2_streamlit.read_configured_screener()
        except Exception as exc:
            logger.error("Configured immutable Screener read failed: %s", type(exc).__name__)
            metrics.note("screener_store_fetch", f"r2_error_{type(exc).__name__}")
            raise RuntimeError("Configured immutable Screener read failed; refusing source fallback") from exc
        metrics.note("screener_store_source", "r2")
        metrics.note("screener_store_as_of", pin.as_of)
        metrics.note("screener_store_revision", pin.revision_sha256)
        logger.info(
            "Screener ranking store: source=object_storage dataset=%s as_of=%s revision=%s",
            pin.dataset,
            pin.as_of,
            pin.revision_sha256,
        )
        return frame, pin.revision_sha256

    frame = _ps.fetch_screener_store()
    logger.info("Screener ranking store: source=published_screener_https")
    # The HTTPS file has no immutable revision, so derive one from its content.
    # A constant here let the shaped frames (_resolved_prices_shared) pair a re-fetched store with
    # the shape of the previous one for up to an hour (two independent TTLs).
    if frame is None:
        return None, "published_screener_https:none"
    digest = (
        int(pd.util.hash_pandas_object(frame, index=True).sum())
        + int(pd.util.hash_pandas_object(frame.columns.to_frame(index=False), index=False).sum())
    ) & 0xFFFFFFFFFFFFFFFF
    return frame, f"published_screener_https:{digest:016x}"
