"""Process-global cold-start telemetry.

Observation only. Nothing here changes what the application fetches, how it
retries, what it caches, or which symbols survive — it records when stages ran
and how many attempts they took, so a cold start can be measured from outside
the container instead of guessed at.

The recorder is process-global rather than session-scoped on purpose. The
expensive data pipeline runs once, on whichever session happens to connect to
a fresh container first, and every later session is served from
``@st.cache_data``. A session-scoped recorder would therefore report a warm
session's timings and miss the cold start entirely. Keeping the numbers on the
process means a probe that arrives second still reads the first run's real
cost.
"""

from __future__ import annotations

import os
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone

_LOCK = threading.Lock()

PROCESS_START_MONOTONIC: float = time.monotonic()
PROCESS_START_UTC: str = datetime.now(timezone.utc).isoformat(timespec="seconds")

_stages: dict[str, dict] = {}
_counters: dict[str, float] = {}
_facts: dict[str, object] = {}


def _now() -> float:
    return time.monotonic()


def since_start() -> float:
    """Seconds elapsed since this Python process started."""
    return round(_now() - PROCESS_START_MONOTONIC, 3)


@contextmanager
def stage(name: str):
    """Time a named startup stage.

    Only the FIRST execution is kept: that is the cold one. Later executions
    just bump ``repeats`` so a forced refresh is visible without overwriting
    the cold-start measurement.
    """
    started_at = since_start()
    t0 = _now()
    try:
        yield
    finally:
        duration = round(_now() - t0, 3)
        with _LOCK:
            existing = _stages.get(name)
            if existing is None:
                _stages[name] = {
                    "started_at_s": started_at,
                    "ended_at_s": round(started_at + duration, 3),
                    "duration_s": duration,
                    "repeats": 0,
                }
            else:
                existing["repeats"] += 1


def incr(key: str, n: float = 1) -> None:
    """Increment a counter (batches attempted, retries issued, and so on)."""
    with _LOCK:
        _counters[key] = _counters.get(key, 0) + n


def note(key: str, value) -> None:
    """Record a scalar fact (symbol counts, cache presence, ...)."""
    with _LOCK:
        _facts[key] = value


def record_cache_presence(paths: dict[str, str]) -> None:
    """Snapshot which cache files existed BEFORE any fetch ran.

    This is how "was this container genuinely cold?" is answered with evidence
    rather than assumed from the fact that a deploy happened.
    """
    present: dict[str, object] = {}
    for label, path in paths.items():
        try:
            exists = os.path.exists(path)
            present[label] = (
                {"exists": True, "bytes": os.path.getsize(path)} if exists
                else {"exists": False}
            )
        except OSError as exc:
            present[label] = {"error": str(exc)[:120]}
    with _LOCK:
        if "cache_at_startup" not in _facts:
            _facts["cache_at_startup"] = present
            _facts["cold_container"] = not any(
                isinstance(v, dict) and v.get("exists") for v in present.values()
            )


def snapshot() -> dict:
    """Everything recorded so far, safe to serialise."""
    with _LOCK:
        return {
            "process_start_utc": PROCESS_START_UTC,
            "uptime_s": since_start(),
            "stages": dict(_stages),
            "counters": dict(_counters),
            "facts": dict(_facts),
        }


def reset_for_tests() -> None:
    with _LOCK:
        _stages.clear()
        _counters.clear()
        _facts.clear()
