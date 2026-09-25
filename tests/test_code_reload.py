"""Changed src/ or r2/ code is reloaded without restarting the process."""

import os
import time
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
    assert set(mods) == {"pandas", cr.__name__}  # app code gone; libraries and the reloader stay


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
