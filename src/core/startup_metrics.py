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

MODULE_IMPORT_MONOTONIC: float = time.monotonic()
# When THIS MODULE was imported. On Streamlit Cloud a deploy can reload changed
# modules into an already-running interpreter, so this is NOT proof that the
# process restarted -- see process_identity() for that.
MODULE_IMPORT_UTC: str = datetime.now(timezone.utc).isoformat(timespec="seconds")


def process_identity() -> dict:
    """Identify the OS process, so a module reload cannot be mistaken for a restart.

    A fresh import with a warm @st.cache_data is exactly what a redeploy into a
    surviving interpreter looks like, and it is indistinguishable from a cold
    process unless the PID and process start time are reported too.
    """
    info: dict[str, object] = {"pid": os.getpid()}
    try:
        with open("/proc/self/stat", "r", encoding="utf-8") as fh:
            fields = fh.read().rsplit(") ", 1)[-1].split()
        starttime_ticks = float(fields[19])
        clk = os.sysconf("SC_CLK_TCK")
        with open("/proc/uptime", "r", encoding="utf-8") as fh:
            system_uptime = float(fh.read().split()[0])
        info["process_age_s"] = round(system_uptime - starttime_ticks / clk, 1)
        info["system_uptime_s"] = round(system_uptime, 1)
    except Exception as exc:
        info["error"] = str(exc)[:120]
    return info

_stages: dict[str, dict] = {}
_counters: dict[str, float] = {}
_facts: dict[str, object] = {}


def _now() -> float:
    return time.monotonic()


def since_start() -> float:
    """Seconds elapsed since this module was imported."""
    return round(_now() - MODULE_IMPORT_MONOTONIC, 3)


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
            "module_import_utc": MODULE_IMPORT_UTC,
            "uptime_s": since_start(),
            "process": process_identity(),
            "stages": dict(_stages),
            "counters": dict(_counters),
            "facts": dict(_facts),
        }


def reset_for_tests() -> None:
    with _LOCK:
        _stages.clear()
        _counters.clear()
        _facts.clear()
