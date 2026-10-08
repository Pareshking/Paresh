"""Give freed memory back to the system after each page run.

Streamlit runs every rerun on a NEW thread, and glibc gives threads their own
malloc arenas. A backtest's ~170 MB working set is freed when it finishes, but
into whichever arena that thread used, and glibc keeps it there: the process
grew 70-130 MB with every History parameter change, though Python held under
1 MB between runs (measured 8 Oct 2026; five History runs in ONE thread stayed
flat at 296 MB). MALLOC_ARENA_MAX would prevent it but must be set before
Python starts, which Streamlit Cloud does not allow.

malloc_trim(0) returns the free pages of every arena to the system. Same app,
same clicks: 830 -> 514 MB resident after six History changes; four weight
changes 689 -> 963 MB without it, 538 -> 569 MB with it.

Linux with glibc only; anywhere else it does nothing and never raises.
"""

from __future__ import annotations

import ctypes
import ctypes.util
import time

_trim = None
_looked = False


def _malloc_trim():
    global _trim, _looked
    if not _looked:
        _looked = True
        try:
            name = ctypes.util.find_library("c")
            fn = getattr(ctypes.CDLL(name), "malloc_trim", None) if name else None
            if fn is not None:
                fn.argtypes = [ctypes.c_size_t]
                fn.restype = ctypes.c_int
            _trim = fn
        except OSError:
            _trim = None
    return _trim


def release_freed_memory() -> float | None:
    """Return freed heap pages to the OS; seconds taken, or None where unsupported."""
    fn = _malloc_trim()
    if fn is None:
        return None
    started = time.perf_counter()
    try:
        fn(0)
    except Exception:  # noqa: BLE001 - observation-grade helper, must never break a page
        return None
    return time.perf_counter() - started
