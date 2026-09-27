"""Where the app gets its published data: R2 first, the release files second.

The nightly jobs publish three files the app starts from -- the ranking
table, the Screener price history and the two-year price snapshot -- to both
R2 and the GitHub release. R2 is the canonical archive (owner, 2026-09-27:
"the app should use R2"), so the app asks it first, through the same
manifest-checked reader every other consumer uses: the pointer names a
revision, the manifest names the object, and the object's size and SHA-256
must match before a byte is returned.

Anything short of that -- no keys configured, R2 unreachable, a failed
integrity check -- returns None and the caller goes on to the release file
exactly as before. Which one served each file is recorded in SOURCES and in
the startup metrics, and the page footer says so.

Keys come from the environment (Streamlit exports top-level secrets as
environment variables) or from an [r2] section in the Streamlit secrets, with
the names upper- or lower-case: R2_ACCOUNT_ID, R2_ACCESS_KEY_ID,
R2_SECRET_ACCESS_KEY, R2_ENDPOINT, R2_BUCKET.
"""

from __future__ import annotations

import os
import time
from typing import Any

from src.core import startup_metrics as metrics
from src.core import code_reload
from src.core.logger import logger

# Dataset each published file is archived under (the --dataset its workflow
# passes to scripts/r2_publish.py).
RANKINGS = "snapshots/rankings"
SCREENER_STORE = "prices/screener"
PRICE_SNAPSHOT = "app/prices_snapshot"

_KEYS = ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY",
         "R2_ENDPOINT", "R2_BUCKET")

# file label -> "r2" or "release", for the footer.
# Kept in code_reload.PERSISTENT: the loaders that fill it are cached, so after
# a code reload they are not run again and a fresh dict would stay empty.
# code_reload never reloads itself, so a running process can hold a copy older
# than this file: create PERSISTENT on it rather than importing the name
# (importing it took production down with an ImportError on 2026-09-27).
_PERSISTENT = code_reload.__dict__.setdefault("PERSISTENT", {})
SOURCES: dict[str, str] = _PERSISTENT.setdefault("app_source.SOURCES", {})


def _from_secrets() -> dict[str, str]:
    try:
        import streamlit as st

        secrets: Any = st.secrets
        section = secrets.get("r2") or secrets.get("R2") or {}
        out = {}
        for name in _KEYS:
            short = name[3:]  # ACCOUNT_ID ...
            for cand in (name, name.lower(), short, short.lower()):
                if cand in section:
                    out[name] = str(section[cand])
                    break
            else:
                if name in secrets:
                    out[name] = str(secrets[name])
        return out
    except Exception:
        return {}


def r2_config():
    """An R2Config from the environment or the Streamlit secrets, or None."""
    from src.storage.r2 import R2Config, R2ConfigurationError

    values = {k: os.getenv(k, "").strip() for k in _KEYS}
    if not all(values.values()):
        found = _from_secrets()
        values = {k: values[k] or found.get(k, "").strip() for k in _KEYS}
    if not all(values.values()):
        return None
    try:
        return R2Config.from_values({k[3:].lower(): v for k, v in values.items()})
    except R2ConfigurationError as exc:
        logger.warning("R2 keys present but unusable (%s); using release files.", exc)
        return None


def fetch_latest(dataset: str, label: str, *, archive=None) -> bytes | None:
    """The newest verified revision of `dataset`, or None. Never raises."""
    started = time.perf_counter()
    try:
        if archive is None:
            config = r2_config()
            if config is None:
                metrics.note(f"r2_{label}", "not_configured")
                return None
            from src.storage.r2 import R2Archive

            archive = R2Archive(config)
        from src.storage.reader import R2DatasetReader

        reader = R2DatasetReader(archive)
        ref = reader.resolve_current(dataset)
        body = reader.read_bytes(ref)
    except Exception as exc:
        logger.info("R2 %s unavailable (%s: %s); using the release file.",
                    label, type(exc).__name__, exc)
        metrics.note(f"r2_{label}", type(exc).__name__)
        return None
    metrics.note(f"r2_{label}", "ok")
    metrics.note(f"r2_{label}_as_of", ref.as_of)
    metrics.note(f"r2_{label}_s", round(time.perf_counter() - started, 2))
    return body


def record(label: str, source: str) -> None:
    SOURCES[label] = source
    metrics.note(f"source_{label}", source)


def summary() -> str:
    """'R2', 'release files', or a mix, for the footer."""
    kinds = set(SOURCES.values())
    if not kinds:
        return ""
    if kinds == {"r2"}:
        return "R2"
    if kinds == {"release"}:
        return "release files"
    return ", ".join(f"{k}: {'R2' if v == 'r2' else 'release'}" for k, v in sorted(SOURCES.items()))
