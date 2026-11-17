"""A pull into the running app drops its caches and memos (owner's log, 15 Nov 2026).

Streamlit Cloud pulled 57 pushes into one process and restarted it twice;
resident memory after each pull rose to ~2,450 MB and the app was restricted
for memory at 11:24 UTC. Measured locally on 15 Nov, five pulls: 363 -> 499 MB
on main; with the caches cleared but the memos left, 379 -> 640 MB; with both,
363 -> 423 MB. Twelve pulls: main about +15 MB a pull, the fix about +7.
"""
import types
from collections import OrderedDict
from functools import lru_cache
from pathlib import Path

from src.core import memory

ROOT = Path(__file__).resolve().parents[1]


def test_a_revision_change_is_reported_once_and_never_for_the_first_or_an_unknown_one():
    box = types.SimpleNamespace()
    assert memory.revision_changed("a" * 40, box) is False        # the first this process saw
    assert memory.revision_changed("a" * 40, box) is False        # same revision, next rerun
    assert memory.revision_changed("b" * 40, box) is True         # a pull
    assert memory.revision_changed("b" * 40, box) is False        # once only
    assert memory.revision_changed(None, box) is False            # unknown never clears
    assert memory.revision_changed("b" * 40, box) is False


def test_the_frame_holding_memos_of_app_modules_are_emptied_and_others_left_alone():
    @lru_cache(maxsize=4)
    def holidays(x):
        return x

    holidays(1)
    app = types.ModuleType("src.loaders.fake")
    app._BASIS_MEMO = OrderedDict(k=("frame",))
    app._RUN_MEMO = [("frame",)]
    app._store_memo = {"at": 123.0, "frame": "big"}
    app.UNRELATED = {"keep": 1}
    holidays.__module__ = "src.loaders.fake"
    app.holidays = holidays
    other = types.ModuleType("pandas_fake")
    other._BASIS_MEMO = {"keep": 1}
    n = memory.clear_module_memos({"src.loaders.fake": app, "pandas_fake": other})
    assert n == 3
    assert not app._BASIS_MEMO and not app._RUN_MEMO
    assert app._store_memo == {"at": 0, "frame": None}           # keys kept: old code reads "nothing memoised"
    assert app.UNRELATED == {"keep": 1}
    assert holidays.cache_info().currsize == 0
    assert other._BASIS_MEMO == {"keep": 1}                       # not ours: untouched


def test_every_memo_the_list_names_still_exists_in_the_code():
    # A renamed memo would silently escape the clear and the leak would return.
    src = "\n".join(p.read_text(encoding="utf-8") for p in (ROOT / "src").rglob("*.py"))
    for name in memory._MEMO_NAMES:
        assert f"\n{name}" in src, name


def test_a_failing_clear_is_reported_and_does_not_stop_the_others():
    ran = []

    def bad():
        raise RuntimeError("x")

    out = memory.drop_caches_for_new_revision([bad, lambda: ran.append(1)])
    assert ran == [1] and out["errors"] and "after_mb" in out


def test_app_drops_memos_before_modules_and_caches_after_the_imports():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    memo = app.index("clear_module_memos(sys.modules)")
    pop = app.index("sys.modules.pop(_name, None)")
    imports = app.index("mark_loaded()  # the baseline")
    caches = app.index("_drop_caches([st.cache_data.clear, st.cache_resource.clear])")
    assert memo < pop < imports < caches


def test_the_memory_guard_fires_over_the_limit_and_at_most_every_fifteen_minutes():
    box = types.SimpleNamespace()
    assert memory.over_guard(box, now=0, rss_mb=1200, limit_mb=1800) is False
    assert memory.over_guard(box, now=10, rss_mb=1900, limit_mb=1800) is True
    assert memory.over_guard(box, now=100, rss_mb=1950, limit_mb=1800) is False      # too soon
    assert memory.over_guard(box, now=10 + memory.GUARD_EVERY_S, rss_mb=1950, limit_mb=1800) is True
    assert memory.over_guard(box, now=99999, rss_mb=None, limit_mb=1800) is False   # unknown never clears


def test_the_guard_uses_the_same_clear_as_a_pull():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "if _revision_pulled or _memory_guard:" in app
    assert app.count("if _revision_pulled or _memory_guard:") == 2   # modules dropped, then caches


def test_the_mmap_threshold_is_fixed_at_app_import():
    """S141: without it, freed frames stay resident in per-thread arenas."""
    import sys

    from src.core import memory

    if sys.platform.startswith("linux"):
        assert memory.fix_mmap_threshold() is True
    else:
        assert memory.fix_mmap_threshold() in (True, False)
    src = open("app.py", encoding="utf-8").read()
    head = src[:src.index("if not hasattr(_code_reload")]
    assert 'getattr(_memory, "fix_mmap_threshold", lambda: False)()' in head, \
        "must run before the first page builds any frame"


def test_a_freed_large_frame_goes_back_to_the_system():
    """With the threshold fixed, a 24 MB block freed under a survivor is not kept resident.

    Unfixed, freeing the 64 MB block raises glibc's threshold, the 24 MB block
    is carved from the thread's arena, and the small survivor above it stops
    the trim: 24 MB stays resident (measured 16 Nov). Fixed, it is 0.
    """
    import subprocess
    import sys

    import pytest

    from src.core import memory

    if memory.resident_mb() is None or not memory.fix_mmap_threshold():
        pytest.skip("needs Linux with glibc")
    # Its own process: resident memory inside the test run moves with every
    # other test's frames.
    out = subprocess.run([sys.executable, "-c", _FRAGMENT], capture_output=True,
                         text=True, timeout=120, check=True).stdout
    assert int(out.split()[-1]) < 8, out


_FRAGMENT = """
import threading
import numpy as np
from src.core import memory
assert memory.fix_mmap_threshold()
keep = []
def work():
    for _ in range(4):
        a = np.ones((8 << 20,))
        del a
        b = np.ones((3 << 20,))
        keep.append(np.ones(64))
        del b
before = memory.resident_mb()
t = threading.Thread(target=work)
t.start()
t.join()
print(memory.resident_mb() - before)
"""


def test_app_survives_a_pull_that_adds_a_memory_function():
    """17 Nov 2026: a pull left the old src.core.memory loaded, and app.py's top
    `from src.core.memory import fix_mmap_threshold` raised ImportError on every page.
    The head of app.py (up to the module drop) must run against a stale module."""
    import subprocess
    import sys

    src = open("app.py", encoding="utf-8").read()
    head = src[:src.index("def _new_revision_pulled(")]
    # Every `from src... import name` above the drop is the bug this guards against.
    import re
    assert not re.findall(r"^from src\.[\w.]+ import (?!code_reload|memory as)", head, re.M), \
        "import modules, not names, above the module drop"
    probe = (
        "import sys, types\n"
        "import src.core.memory as real\n"
        "stale = types.ModuleType('src.core.memory')\n"
        "stale.__file__ = real.__file__; stale.__spec__ = real.__spec__\n"
        "for n in ('release_freed_memory', 'use_system_arrow_pool'):\n"
        "    setattr(stale, n, getattr(real, n))\n"
        "sys.modules['src.core.memory'] = stale\n"
        "import src.core\n"
        "src.core.memory = stale\n"
        f"exec(compile({head!r}, 'app.py', 'exec'), {{'__name__': 'app_head'}})\n"
        "print('ok')\n"
    )
    out = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True, timeout=120)
    assert out.returncode == 0 and out.stdout.strip().endswith("ok"), out.stderr[-2000:]
