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


def fetch_screener_store(source_key: str):
    """(store, revision) for ``source_key``: the R2 pin when R2 is on, else HTTPS.

    R2: the current pointer is re-read at most hourly (_current_pin), but the
    file is downloaded only when that pointer names a revision not already in
    memory (_read_revision, keyed on the SHA). Until 16 Nov 2026 the whole read
    sat behind one ttl=3600 cache, so the same 8.8 MB revision was downloaded
    and parsed again every hour (15 times in 25 h in the production log), and
    every memo keyed on the store object's identity missed with it (TODO S141).
    """
    from r2.consumers import r2_streamlit

    if r2_streamlit.enabled():
        try:
            pin = _current_pin(source_key)
            frame = _read_revision(pin.dataset, pin.as_of, pin.revision_sha256)
        except Exception as exc:
            logger.error("Configured immutable Screener read failed: %s", type(exc).__name__)
            metrics.note("screener_store_fetch", f"r2_error_{type(exc).__name__}")
            raise RuntimeError("Configured immutable Screener read failed; refusing source fallback") from exc
        metrics.note("screener_store_source", "r2")
        metrics.note("screener_store_as_of", pin.as_of)
        metrics.note("screener_store_revision", pin.revision_sha256)
        return frame, pin.revision_sha256
    return _fetch_https_store(source_key)


# The freshness boundary: a new nightly revision is picked up within an hour,
# as before. Only the pointer (a few hundred bytes) is re-read.
@st.cache_resource(show_spinner=False, ttl=3600, max_entries=2)
def _current_pin(source_key: str):
    from r2.consumers import r2_streamlit

    return r2_streamlit.current_screener_pin()


# A resource, not data: the store is read-only here (from_screener takes
# cross-sections, which are new frames), so one copy serves every session
# instead of a 35 MB unpickle on every rerun. A revision is immutable, so no
# TTL: it stays until a newer revision pushes it out (two kept, so the
# sessions still on the previous one are not forced to re-download it).
@st.cache_resource(show_spinner=False, max_entries=2)
def _read_revision(dataset: str, as_of: str, revision_sha256: str) -> pd.DataFrame:
    from r2.consumers import r2_streamlit
    from r2.consumers.r2_research import R2ResearchPin

    frame = r2_streamlit.read_screener_revision(
        R2ResearchPin(dataset=dataset, as_of=as_of, revision_sha256=revision_sha256)
    )
    logger.info(
        "Screener ranking store: source=object_storage dataset=%s as_of=%s revision=%s",
        dataset,
        as_of,
        revision_sha256,
    )
    return frame


# The legacy HTTPS file has no revision to ask for, so the hour is still its
# freshness boundary.
@st.cache_resource(show_spinner=False, ttl=3600, max_entries=2)
def _fetch_https_store(source_key: str):
    from src.loaders import price_source as _ps

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
