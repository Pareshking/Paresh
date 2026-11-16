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


def use_system_arrow_pool() -> str | None:
    """Make pyarrow allocate with malloc instead of its bundled mimalloc.

    TODO S64, measured 13 Oct 2026 (4 concurrent sessions, 3 runs each way):
    Portfolio peaks 960 / 1,000 / 1,001 MB with mimalloc, 877 / 895 / 929 MB
    with the system pool; Backtest 910 / 936 / 858 vs 819 / 801 / 840 MB. Every
    system run is under every mimalloc run. Memory freed by the system pool
    also goes back to the OS with release_freed_memory(). Streamlit Cloud
    cannot set ARROW_DEFAULT_MEMORY_POOL before Python starts, so this is
    called at app import. Returns the pool's backend name, or None if pyarrow
    refused (never raises).
    """
    try:
        import pyarrow as pa

        pa.set_memory_pool(pa.system_memory_pool())
        return pa.default_memory_pool().backend_name
    except Exception:  # noqa: BLE001 - an allocator choice must never break the app
        return None


# --- Large blocks go straight back to the system (16 Nov 2026, S141) ----------
#
# glibc serves a block of at least M_MMAP_THRESHOLD bytes with its own mmap,
# which free() hands straight back to the system. The threshold starts at
# 128 KiB but RISES to the size of every such block that is freed, up to
# 32 MiB, so after the first large DataFrame is dropped every later block up
# to that size is carved out of a thread's arena instead -- and Streamlit
# runs each rerun on a new thread, with up to 8 arenas per CPU. Freed there,
# the pages stay resident: that was the growth between pulls (S61).
#
# Measured 16 Nov against the production store revision (f7abe4...), six
# cycles of Dashboard, Portfolio, Backtest and History in two sessions with
# every cache expiring between cycles, both runs side by side: resident after
# each cycle 966 / 1147 / 1134 / 1117 / 1271 / 1286 MB unchanged, 756 / 775 /
# 785 / 795 / 802 / 799 MB with the threshold fixed at 1 MiB. Python held the
# same 448 MB of frames in both; each cycle took 71 s in both. Capping the
# arenas (MALLOC_ARENA_MAX=2) gives the same result but must be set before
# Python starts, which Streamlit Cloud does not allow; this option can be set
# at any time, because the threshold is shared by every arena.

M_MMAP_THRESHOLD = -3
MMAP_THRESHOLD_BYTES = 1 << 20


def fix_mmap_threshold(nbytes: int = MMAP_THRESHOLD_BYTES) -> bool:
    """Fix glibc's mmap threshold (no dynamic rise). True if glibc accepted it; never raises."""
    try:
        name = ctypes.util.find_library("c")
        fn = getattr(ctypes.CDLL(name), "mallopt", None) if name else None
        if fn is None:
            return False
        fn.argtypes = [ctypes.c_int, ctypes.c_int]
        fn.restype = ctypes.c_int
        return fn(M_MMAP_THRESHOLD, int(nbytes)) == 1
    except Exception:  # noqa: BLE001 - an allocator choice must never break the app
        return False


# --- A pull must not stack a second copy of every cache (15 Nov 2026) --------
#
# Streamlit Cloud pulls each push into the RUNNING process ("Updated app!") and
# never restarts it. code_reload swaps the src/ modules for the new code, but
# every st.cache_resource / st.cache_data entry and every module-level memo the
# old modules filled stays alive: the old price frames are still referenced by
# the caches, and the new code builds its own beside them. The owner's log of
# 15 Nov: 57 such pulls against 2 real restarts, resident memory after each pull
# climbing 1,093 -> 1,432 -> 1,514 -> ... -> ~2,450 MB, a peak of 2,874 MB at
# 10:42 UTC, and Streamlit restricting the app for memory at 11:24, two minutes
# after the sixth push of the day. Only a restart brought it back to ~180 MB.
#
# So the first run on a new revision drops every cache before anything is
# rebuilt. The next visitor pays one cold load (about 8 s for the price frames
# in the same log); the process stops growing with every push.

_REVISION_ATTR = "_umiya_served_revision"   # on `sys`: it must outlive code_reload


def revision_changed(revision: str | None, holder=None) -> bool:
    """True once per new deployed revision, after the first one this process saw.

    The served revision is kept as an attribute of `sys`, not in a module of
    ours: code_reload drops and re-imports every src/ module on a pull,
    including this one, so module state would be forgotten exactly when it is
    needed. None (revision unknown) never triggers a clear.
    """
    import sys

    box = sys if holder is None else holder
    if not revision:
        return False
    before = getattr(box, _REVISION_ATTR, None)
    setattr(box, _REVISION_ATTR, revision)
    return before is not None and before != revision


def drop_caches_for_new_revision(clear_fns) -> dict:
    """Run each cache clear, collect garbage, give pages back; resident MB before/after."""
    import gc

    def _rss_mb() -> int | None:
        try:
            with open("/proc/self/status", encoding="utf-8") as fh:
                for line in fh:
                    if line.startswith("VmRSS:"):
                        return int(line.split()[1]) // 1024
        except (OSError, ValueError, IndexError):
            return None
        return None

    before = _rss_mb()
    errors = []
    for fn in clear_fns:
        try:
            fn()
        except Exception as exc:  # noqa: BLE001 - a failed clear must not break the page
            errors.append(f"{getattr(fn, '__qualname__', fn)}: {type(exc).__name__}")
    gc.collect()
    release_freed_memory()
    return {"before_mb": before, "after_mb": _rss_mb(), "errors": errors}


# Module-level memos that hold frames. Streamlit's cache registry keeps every
# cached function object it has seen, and a function object keeps its module's
# globals, so an old module dropped from sys.modules is never collected -- nor
# is anything its memos hold. Measured 15 Nov 2026 (local app, five pulls): with
# the caches cleared but these memos left, resident memory still rose ~50 MB a
# pull. They are emptied in the OLD modules before those are dropped.
_MEMO_NAMES = ("_RUN_MEMO", "_SNAPSHOT_CACHE", "_BASIS_MEMO", "_DOWNLOAD_MEMO", "_store_memo")


def clear_module_memos(modules: dict) -> int:
    """Empty the frame-holding memos of every loaded src/ and r2/ module; how many were emptied.

    A dict that maps fixed keys to a value (``_store_memo = {"frame": ..., "at": ...}``)
    keeps its keys, set to None and 0, so old code still running in another
    session reads "nothing memoised" instead of raising KeyError.
    """
    emptied = 0
    for name, mod in list(modules.items()):
        if not (name in ("src", "r2") or name.startswith(("src.", "r2."))):
            continue
        g = getattr(mod, "__dict__", {})
        for memo in _MEMO_NAMES:
            box = g.get(memo)
            try:
                if isinstance(box, list):
                    box.clear()
                elif isinstance(box, dict) and memo == "_store_memo":
                    for k in list(box):
                        box[k] = 0 if k == "at" else None
                elif isinstance(box, dict):
                    box.clear()
                else:
                    continue
                emptied += 1
            except Exception:  # noqa: BLE001 - best effort; never break a page
                continue
        for obj in list(g.values()):
            clear = getattr(obj, "cache_clear", None)
            if callable(clear) and getattr(obj, "__module__", None) == name:
                try:
                    clear()
                except Exception:  # noqa: BLE001
                    pass
    return emptied


# --- A ceiling between pulls (16 Nov 2026) ----------------------------------
#
# The owner's log after the pull fix: every pull now frees 100-370 MB, but
# memory still climbs with use between pulls, 185 MB after the restart to
# 1,594 MB 24 hours later, mostly at the hourly cache expiries (16:35 1,129;
# 18:55 1,326; 05:05 1,454; 14:14 1,594). Not reproduced locally at that size
# (about +10 MB an expiry without production's R2 data), so the cause is not
# proven. Until it is, the same clear that a pull runs also runs when resident
# memory passes GUARD_MB, at most once per GUARD_EVERY_S. The ~2.7 GB limit is
# then never reached by this growth, and the log line says how much each clear
# freed, which is the evidence still missing.
GUARD_MB = 1800
GUARD_EVERY_S = 900
_GUARD_ATTR = "_umiya_memory_guard_at"


def resident_mb() -> int | None:
    try:
        with open("/proc/self/status", encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1]) // 1024
    except (OSError, ValueError, IndexError):
        return None
    return None


def over_guard(holder=None, now: float | None = None, rss_mb: int | None = None,
               limit_mb: int | None = None) -> bool:
    """True when resident memory is over the guard and the last guard clear is old enough."""
    import os
    import sys
    import time

    box = sys if holder is None else holder
    limit = limit_mb if limit_mb is not None else int(os.environ.get("UMIYA_MEMORY_GUARD_MB", GUARD_MB))
    rss = resident_mb() if rss_mb is None else rss_mb
    if rss is None or rss < limit:
        return False
    t = time.time() if now is None else now
    last = getattr(box, _GUARD_ATTR, None)
    if last is not None and t - last < GUARD_EVERY_S:
        return False
    setattr(box, _GUARD_ATTR, t)
    return True
