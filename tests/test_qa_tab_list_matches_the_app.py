"""The QA scripts must expect the pages the app actually renders.

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
    """The page titles the app renders, in order.

    The app moved from `st.tabs([...])` to `st.navigation`/`st.Page` so that
    only the active page executes; both shapes are read here because the names
    are the app's public surface either way -- the probes click them by name --
    and a migration should not be able to silently drop the check. Whichever
    shape app.py uses, these titles and the probes' TABS lists must agree.
    """
    tree = ast.parse((ROOT / "app.py").read_text(encoding="utf-8"))

    pages = [
        kw.value.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "Page"
        for kw in node.keywords
        if kw.arg == "title"
        and isinstance(kw.value, ast.Constant)
        and isinstance(kw.value.value, str)
    ]
    if pages:
        return pages

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
    raise AssertionError(
        "app.py declares no st.Page(title=...) pages and no st.tabs([...]) call"
    )


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


def test_every_page_is_declared_with_an_explicit_title_and_url_path():
    """Order and naming are the probes' contract; url_path is the reader's.

    A page without an explicit `url_path` takes one derived from the function
    name, so renaming a private helper would change a shareable URL.
    """
    tree = ast.parse((ROOT / "app.py").read_text(encoding="utf-8"))
    pages = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "Page"
    ]
    if not pages:
        pytest.skip("app.py is not using st.navigation")
    missing = [
        ast.unparse(p)[:60] for p in pages
        if not {"title", "url_path"} <= {kw.arg for kw in p.keywords}
    ]
    assert not missing, f"pages missing title or url_path: {missing}"
    defaults = [p for p in pages
                if any(kw.arg == "default" for kw in p.keywords)]
    assert len(defaults) == 1, (
        f"exactly one page must be default=True; found {len(defaults)}"
    )


@pytest.mark.parametrize("script", QA_SCRIPTS)
def test_qa_script_expects_exactly_the_tabs_the_app_renders(script):
    assert _script_tabs(script) == _app_tabs()


@pytest.mark.parametrize("script", QA_SCRIPTS)
def test_no_qa_script_still_looks_for_a_removed_system(script):
    """Same guard as test_removed_systems_stay_removed, for the probes."""
    assert "Multi-Strategy" not in _script_tabs(script)
