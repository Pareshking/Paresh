"""Changed src/ or r2/ code is reloaded without restarting the process."""

import os
import time
import threading
import types

from src.core import code_reload as cr


def _module(name, path):
    m = types.ModuleType(name)
    m.__file__ = str(path)
    return m


def _fresh(monkeypatch):
    monkeypatch.setattr(cr, "_SEEN", {})


def test_unchanged_files_reload_nothing(tmp_path, monkeypatch):
    _fresh(monkeypatch)
    f = tmp_path / "menu.py"
    f.write_text("x = 1\n")
    mods = {"src.ui.menu": _module("src.ui.menu", f), "pandas": _module("pandas", f)}
    cr.mark_loaded(mods)
    assert cr.reload_if_changed(mods) == []
    assert "src.ui.menu" in mods


def test_a_changed_file_unloads_every_app_module_but_nothing_else(tmp_path, monkeypatch):
    """The #177 case: the file changed on disk after the module was imported."""
    _fresh(monkeypatch)
    menu, other = tmp_path / "menu.py", tmp_path / "other.py"
    menu.write_text("x = 1\n")
    other.write_text("y = 1\n")
    mods = {
        "src": _module("src", other),
        "src.ui.menu": _module("src.ui.menu", menu),
        "r2.consumers.r2_streamlit": _module("r2.consumers.r2_streamlit", other),
        "pandas": _module("pandas", other),
        cr.__name__: _module(cr.__name__, other),
    }
    cr.mark_loaded(mods)
    time.sleep(0.01)
    menu.write_text("x = 22\n")
    os.utime(menu, None)
    assert cr.reload_if_changed(mods) == [str(menu)]
    # Bare test modules cannot be reloaded in place, so they are dropped and
    # imported afresh; the reloader itself stays (its lock is held, its records
    # outlive the reload); other packages are never touched.
    assert set(mods) == {"pandas", cr.__name__}


def test_a_module_first_seen_after_its_file_changed_is_not_missed(tmp_path, monkeypatch):
    """Without mark_loaded, the first sighting recorded the NEW file (toy app: 'OLD MENU' forever)."""
    _fresh(monkeypatch)
    f = tmp_path / "menu.py"
    f.write_text("x = 1\n")
    mods = {"src.ui.menu": _module("src.ui.menu", f)}
    cr.mark_loaded(mods)              # right after the imports
    f.write_text("x = 222\n")         # the pull lands between runs
    assert cr.reload_if_changed(mods) == [str(f)]


def test_app_py_calls_the_reloader_before_and_after_its_imports():
    src = open("app.py", encoding="utf-8").read()
    first_src_import = src.index("from src.core import startup_metrics")
    assert src.index("reload_if_changed()") < first_src_import
    assert src.index("mark_loaded()") > src.rindex("from src.ui.views")


def test_app_py_declares_its_code_current_only_after_the_reload_check():
    """QA run 580: a push that only ADDED src/core/code_reload.py reloaded
    nothing, so loaded_revision kept naming the start build and QA reported
    a new, running file as stale."""
    src = open("app.py", encoding="utf-8").read()
    assert src.index("metrics.mark_code_current()") > src.index("mark_loaded()")


def test_mark_code_current_moves_loaded_revision_to_disk(monkeypatch):
    from src.core import startup_metrics as metrics

    monkeypatch.setattr(metrics, "LOADED_REVISION", "a" * 40)
    monkeypatch.setattr(metrics, "_revision", lambda: "b" * 40)
    assert metrics.snapshot()["loaded_revision"] == "a" * 40
    metrics.mark_code_current()
    assert metrics.snapshot()["loaded_revision"] == "b" * 40


def test_app_import_guard_serializes_reload_and_import_windows():
    """A second Streamlit script thread cannot enter while one run reloads/imports."""
    from src.core.code_reload import app_import_guard

    first_entered = threading.Event()
    release_first = threading.Event()
    second_entered = threading.Event()

    def first():
        with app_import_guard():
            first_entered.set()
            assert release_first.wait(timeout=2)

    def second():
        assert first_entered.wait(timeout=2)
        with app_import_guard():
            second_entered.set()

    t1 = threading.Thread(target=first)
    t2 = threading.Thread(target=second)
    t1.start()
    assert first_entered.wait(timeout=2)
    t2.start()
    assert not second_entered.wait(timeout=0.1)
    release_first.set()
    t1.join(timeout=2)
    t2.join(timeout=2)
    assert not t1.is_alive()
    assert not t2.is_alive()
    assert second_entered.is_set()



def _package(tmp_path, monkeypatch, name="zzreload"):
    """A real three-module package on sys.path, treated as app code: a imports b, b imports c."""
    import sys

    pkg = tmp_path / name
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "c.py").write_text("VALUE = 1\n")
    (pkg / "b.py").write_text(f"from {name}.c import VALUE\n\n\ndef get():\n    return VALUE\n")
    (pkg / "a.py").write_text(f"from {name} import b\nfrom {name}.c import VALUE as DIRECT\n\n\n"
                              "def f():\n    return b.get(), DIRECT\n")
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setattr(cr, "_PACKAGES", (name,))
    monkeypatch.setattr(cr, "_PREFIXES", (name + ".",))
    _fresh(monkeypatch)
    for m in [m for m in sys.modules if m == name or m.startswith(name + ".")]:
        monkeypatch.delitem(sys.modules, m)
    return pkg


def test_changed_code_is_reloaded_in_place_and_never_missing(tmp_path, monkeypatch):
    # Owner's log, 7 Oct 2026: dropping every app module from sys.modules made a
    # second session importing one at that moment fail with KeyError.
    import importlib
    import sys

    pkg = _package(tmp_path, monkeypatch)
    a = importlib.import_module("zzreload.a")
    assert a.f() == (1, 1)
    cr.mark_loaded()
    names = {m for m in sys.modules if m.startswith("zzreload")}
    time.sleep(0.01)
    (pkg / "c.py").write_text("VALUE = 2\n")
    os.utime(pkg / "c.py", None)
    assert cr.reload_if_changed() == [str(pkg / "c.py")]
    assert names <= set(sys.modules)                 # nothing was ever removed
    assert sys.modules["zzreload.a"] is a            # the same module object, updated
    assert a.f() == (2, 2)                           # b's and a's `from c import VALUE` rebound


def test_a_session_importing_during_a_reload_never_sees_a_missing_module(tmp_path, monkeypatch):
    import importlib
    import sys

    pkg = _package(tmp_path, monkeypatch, name="zzreload2")
    importlib.import_module("zzreload2.a")
    cr.mark_loaded()
    errors, stop = [], threading.Event()

    def importer():
        while not stop.is_set():
            try:
                importlib.import_module("zzreload2.b")
                assert "zzreload2.c" in sys.modules
            except Exception as exc:  # noqa: BLE001
                errors.append(repr(exc))

    t = threading.Thread(target=importer)
    t.start()
    try:
        for i in range(20):
            time.sleep(0.005)
            (pkg / "c.py").write_text(f"VALUE = {i + 10}\n")
            os.utime(pkg / "c.py", None)
            cr.reload_if_changed()
            cr.mark_loaded()
    finally:
        stop.set()
        t.join()
    assert errors == []
