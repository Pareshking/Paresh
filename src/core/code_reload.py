"""Pick up changed app code in a long-running Streamlit process.

Streamlit re-executes app.py on every rerun, but modules it has already
imported (everything under src/ and r2/) stay as they were loaded until the
process restarts -- and Streamlit Cloud pulls a push WITHOUT restarting. On
2026-09-25 that left the #177 menu fix merged, on disk and not running until
someone pressed Reboot.

app.py calls reload_if_changed() before its other imports and mark_loaded()
after them. It compares the file behind every loaded src/ and r2/ module with
what it was when the module was loaded;
if any changed, it drops all of them from sys.modules, so the imports that
follow load the current code. This is what Streamlit's own file watcher does
on a change, done here because on Cloud it evidently does not.

A day with no code change (the daily data commit touches only data/) finds
nothing changed and costs one os.stat per loaded module. st.cache_data entries
survive a reload: they are keyed by each function's source, not by the
module object.
"""

from __future__ import annotations

import os
import sys
import threading

_PACKAGES = ("src", "r2")
_PREFIXES = tuple(p + "." for p in _PACKAGES)

# path -> (mtime_ns, size) as first seen after the module was loaded.
_SEEN: dict[str, tuple[int, int]] = {}
_LOCK = threading.Lock()


def _is_app_module(name: str) -> bool:
    # This module stays loaded: it holds the record of what was seen.
    if name == __name__:
        return False
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
        # importers hold references to its old objects.
        for name in [n for n in mods if _is_app_module(n)]:
            mods.pop(name, None)
        _SEEN.clear()  # re-recorded from the fresh imports on the next run
        return sorted(changed)
