"""Pick up changed app code in a long-running Streamlit process.

Streamlit re-executes app.py on every rerun, but modules it has already
imported (everything under src/ and r2/) stay as they were loaded until the
process restarts -- and Streamlit Cloud pulls a push WITHOUT restarting. On
2026-09-25 that left the #177 menu fix merged, on disk and not running until
someone pressed Reboot.

app.py calls reload_if_changed() before its other imports and mark_loaded()
after them. It compares the file behind every loaded src/ and r2/ module with
what it was when the module was loaded;
if any changed, it reloads all of them in place (importlib.reload), so the
code that runs next is the current code and no module is ever missing from
sys.modules for a session importing it at the same moment. Streamlit's own
file watcher would do this on a change; on Cloud it evidently does not.

A day with no code change (the daily data commit touches only data/) finds
nothing changed and costs one os.stat per loaded module. st.cache_data entries
survive a reload: they are keyed by each function's source, not by the
module object.
"""

from __future__ import annotations

import importlib
import os
import sys
import threading
from contextlib import contextmanager

_PACKAGES = ("src", "r2")
_PREFIXES = tuple(p + "." for p in _PACKAGES)

# State other modules need to outlive a reload, keyed by its owner. A module
# dropped here is re-imported with fresh globals, while its st.cache_data
# results are served from the cache without running again -- so anything the
# cached function records as a side effect (which source served a file) would
# otherwise be lost for the life of the process.
PERSISTENT: dict[str, dict] = {}

# path -> (mtime_ns, size) as first seen after the module was loaded.
_SEEN: dict[str, tuple[int, int]] = {}
_LOCK = threading.RLock()


@contextmanager
def app_import_guard():
    """Serialize the reload + app-import window across Streamlit script threads.

    reload_if_changed() deliberately removes all application modules from
    sys.modules before app.py imports them again. That operation is safe only
    if no second script run can import from the same cache in between those
    two steps. Streamlit can execute multiple script threads concurrently, so
    app.py holds this re-entrant lock across the complete reload/import window.
    """
    with _LOCK:
        yield


def _is_app_module(name: str) -> bool:
    # Include this module too. Streamlit Cloud can keep code_reload.py itself
    # imported across a pull; excluding it would leave newly added helpers
    # (notably app_import_guard) stale forever until a full process restart.
    return name in _PACKAGES or name.startswith(_PREFIXES)


def _stamp(path: str) -> tuple[int, int] | None:
    try:
        st = os.stat(path)
    except OSError:
        return None
    return st.st_mtime_ns, st.st_size


def mark_loaded(modules: dict | None = None) -> None:
    """Record the files behind every app module loaded so far.

    Call it right after the imports. reload_if_changed() alone would first
    see a module on the NEXT run, after a pull may already have changed its
    file -- and record the new file as if it were the loaded one (the toy
    app that tested this reported "OLD MENU" forever).
    """
    mods = sys.modules if modules is None else modules
    with _LOCK:
        for name, mod in list(mods.items()):
            if _is_app_module(name):
                path = getattr(mod, "__file__", None)
                now = _stamp(path) if path else None
                if now is not None:
                    _SEEN.setdefault(path, now)


def reload_if_changed(modules: dict | None = None) -> list[str]:
    """Unload every app module if any of their files changed; return those files.

    `modules` is sys.modules unless a test passes its own.
    """
    mods = sys.modules if modules is None else modules
    with _LOCK:
        changed: list[str] = []
        for name, mod in list(mods.items()):
            if not _is_app_module(name):
                continue
            path = getattr(mod, "__file__", None)
            if not path:
                continue
            now = _stamp(path)
            if now is None:
                continue
            seen = _SEEN.setdefault(path, now)
            if now != seen:
                changed.append(path)
        if not changed:
            return []
        # All of them, not only the changed files: a changed module's
        # importers hold references to its old objects. In place (owner's log,
        # 7 Oct 2026): dropping them from sys.modules left a window in which a
        # second session importing an app module -- lazily, or in a worker
        # thread, outside app_import_guard -- found it missing and failed with
        # KeyError: 'src.core.logger', 'src.core.startup_metrics', 'src'. A
        # module reloaded in place is never missing. Two passes: sys.modules
        # lists a module before the modules it imports, so the second pass
        # rebinds every `from x import y` to the reloaded x. This module is
        # left alone: its lock is held right now, and its records must outlive
        # the reload. A module that cannot be reloaded (its file deleted, a
        # test's bare module) is dropped as before and imported afresh.
        names = [n for n in mods if _is_app_module(n) and n != __name__]
        failed: set[str] = set()
        for _pass in range(2):
            for name in names:
                mod = mods.get(name)
                if mod is None or name in failed:
                    continue
                try:
                    importlib.reload(mod)
                except Exception:  # noqa: BLE001  any reload error means a fresh import
                    failed.add(name)
        for name in failed:
            mods.pop(name, None)
        _SEEN.clear()  # re-recorded from the current files on the next run
        return sorted(changed)
