"""The QA scripts must expect the tabs the app actually renders.

Production QA drove every viewport looking for a "Multi-Strategy" tab that was
deleted when the alternative ranking systems were removed. The tab was gone on
purpose; the probe's expectation was not updated with it, so the workflow
reported production broken on every run from 20 Aug onward -- for a tab nobody
wanted. A check that fails for a reason nobody acts on stops being read, which
is worse than not having it.

Parsed rather than imported: these scripts pull in playwright at module scope.
"""
import ast
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
QA_SCRIPTS = ["scripts/production_qa.py", "scripts/cold_start_probe.py"]


def _app_tabs() -> list[str]:
    """The labels passed to st.tabs([...]) in app.py."""
    tree = ast.parse((ROOT / "app.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "tabs"
            and node.args
            and isinstance(node.args[0], ast.List)
        ):
            return [
                e.value for e in node.args[0].elts
                if isinstance(e, ast.Constant) and isinstance(e.value, str)
            ]
    raise AssertionError("no st.tabs([...]) call found in app.py")


def _script_tabs(path: str) -> list[str]:
    tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "TABS" for t in node.targets
        ):
            return [
                e.value for e in node.value.elts
                if isinstance(e, ast.Constant) and isinstance(e.value, str)
            ]
    raise AssertionError(f"no TABS assignment found in {path}")


def test_the_app_still_declares_its_tabs_somewhere_we_can_read():
    tabs = _app_tabs()
    assert len(tabs) >= 5
    assert "Screener" in tabs


@pytest.mark.parametrize("script", QA_SCRIPTS)
def test_qa_script_expects_exactly_the_tabs_the_app_renders(script):
    assert _script_tabs(script) == _app_tabs()


@pytest.mark.parametrize("script", QA_SCRIPTS)
def test_no_qa_script_still_looks_for_a_removed_system(script):
    """Same guard as test_removed_systems_stay_removed, for the probes."""
    assert "Multi-Strategy" not in _script_tabs(script)
