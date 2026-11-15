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
