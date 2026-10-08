"""One heavy computation at a time, process-wide (TODO S65).

Streamlit runs every session's script on its own thread in one process, so
two readers starting backtests at once each hold a walk-forward's working set
together. The owner's call (8 Oct 2026): serialise them, and tell the reader
who waits rather than risk the container's memory limit.

`serialised` wraps the body of a computation. Put it UNDER @st.cache_data, so
the gate is taken only on a cache miss: a reader whose result is already
cached is never queued behind another reader's run. A sweep takes it once per
combination, so other readers interleave with a long sweep instead of waiting
for all of it.

`busy()` is a hint for the UI ("a backtest is running"), read without locking;
it can be stale by the time the caller acts, which only means the message
shows when no wait follows, or the wait comes without the message.
"""

from __future__ import annotations

import functools
import threading
import time

from src.core import startup_metrics as metrics

# Re-entrant: a gated computation that calls another (nested backtests) must
# not deadlock on its own thread.
_GATE = threading.RLock()
_running = 0
_count_lock = threading.Lock()


def busy() -> bool:
    return _running > 0


def serialised(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        global _running
        waited = time.perf_counter()
        with _GATE:
            waited = time.perf_counter() - waited
            if waited > 0.5:
                metrics.incr("compute_gate_waits")
                metrics.note("compute_gate_last_wait_s", round(waited, 2))
            with _count_lock:
                _running += 1
            try:
                return func(*args, **kwargs)
            finally:
                with _count_lock:
                    _running -= 1
    return wrapper
