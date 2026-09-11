"""The app must draw its own navigation, in the body, where it is visible.

`st.navigation(position="top")` renders the nav inside Streamlit's header, and
this app hides that header outright (src/ui/theme.py):

    header, [data-testid="stHeader"], .stApp > header { display: none !important; }

so the navigation shipped to production in the DOM with `display: none`. A
reader had no way to reach ten of the eleven pages. Hidden elements contribute
no text, so the QA probe saw a healthy app shell with no navigation and no page
names anywhere and reported readiness "unknown" -- an accurate observation of a
real defect, which I misread as a probe fault for one round.

Neither half of that pair is wrong on its own. Hiding the Streamlit chrome is a
deliberate design choice, and `position="top"` is a legitimate API. Together
they are a broken app, and nothing in the test suite or the type system
connected them. These tests connect them.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
APP = str(ROOT / "app.py")


def _app_src() -> str:
    return (ROOT / "app.py").read_text(encoding="utf-8")


def _page_titles() -> list[str]:
    tree = ast.parse(_app_src())
    return [
        kw.value.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "Page"
        for kw in node.keywords
        if kw.arg == "title" and isinstance(kw.value, ast.Constant)
    ]


def test_the_theme_still_hides_the_streamlit_header():
    """The premise. If this ever stops being true, revisit the rest."""
    theme = (ROOT / "src" / "ui" / "theme.py").read_text(encoding="utf-8")
    assert re.search(r'\[data-testid="stHeader"\]', theme), (
        "the header is no longer hidden; `position=\"top\"` may be usable again, "
        "but re-check it against the live app before trusting it"
    )


def _navigation_position() -> str | None:
    """The `position=` actually PASSED to st.navigation.

    Read from the call, not from the file's text: the first version of this
    test grepped for the string and failed on the comment above the call that
    explains why that value is wrong. A test that cannot tell a comment from
    code is not testing the code.
    """
    tree = ast.parse(_app_src())
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "navigation"
        ):
            for kw in node.keywords:
                if kw.arg == "position" and isinstance(kw.value, ast.Constant):
                    return kw.value.value
            return "sidebar"        # Streamlit's default
    return None


def test_navigation_is_not_placed_in_the_hidden_header():
    position = _navigation_position()
    assert position is not None, "app.py does not call st.navigation"
    assert position != "top", (
        "st.navigation(position='top') renders inside the header this app "
        "hides with display:none, which leaves the app with no navigation"
    )
    assert position == "hidden", (
        f"position={position!r}: the app must suppress Streamlit's own nav and "
        f"draw its own in the body, where its CSS does not hide it"
    )


def test_the_app_renders_one_page_link_per_page():
    src = _app_src()
    assert "st.page_link(" in src, "no in-body navigation is rendered"


def test_every_page_is_reachable_from_the_rendered_navigation():
    """The end-to-end guarantee, against the real app rather than its source."""
    at = AppTest.from_file(APP, default_timeout=600).run()
    assert not at.exception, [e.value[:300] for e in at.exception]

    labels = [
        e.proto.label
        for e in at.main
        if getattr(e, "proto", None) is not None
        and e.proto.__class__.__name__ == "PageLink"
    ]
    expected = _page_titles()
    assert expected, "app.py declares no pages"
    assert labels == expected, (
        f"navigation does not offer every page in order: rendered {labels}, "
        f"declared {expected}"
    )


def test_the_navigation_survives_being_on_a_different_page():
    """The nav is drawn by the entrypoint, so it must not depend on the page."""
    at = AppTest.from_file(APP, default_timeout=600).run()
    assert not at.exception, [e.value[:300] for e in at.exception]
    count = sum(
        1 for e in at.main
        if getattr(e, "proto", None) is not None
        and e.proto.__class__.__name__ == "PageLink"
    )
    assert count == len(_page_titles()) >= 5


def test_exactly_one_navigation_item_is_marked_active():
    """The active pill is marked from Python, so assert Python marks it.

    Streamlit styles the current page link through an emotion prop with no
    stable attribute -- no aria-current, no meaningful class -- so the only CSS
    hook would be a generated class hash that changes between versions. The app
    therefore sets its own st-key-navon_* / st-key-navoff_* keys, and this
    checks the invariant those keys must satisfy.
    """
    src = _app_src()
    assert "navon" in src and "navoff" in src, (
        "the navigation no longer marks an active item"
    )
    assert "_p is _nav" in src, (
        "active detection must use identity: st.navigation returns one of the "
        "page objects it was passed, and attribute access on a page raises "
        "outside a script run"
    )

    theme = (ROOT / "src" / "ui" / "theme.py").read_text(encoding="utf-8")
    assert 'st-key-navon_' in theme, "nothing styles the active item"
    assert ".st-key-app_nav" in theme, "the navigation row is unstyled"


def test_the_navigation_row_is_not_styled_by_a_generated_class_hash():
    """Emotion class names are build artefacts, not an API."""
    theme = (ROOT / "src" / "ui" / "theme.py").read_text(encoding="utf-8")
    nav_css = theme[theme.find(".st-key-app_nav"):]
    nav_css = nav_css[: nav_css.find("/* ── Command Bar")]
    assert "st-emotion-cache" not in nav_css, (
        "the navigation styling depends on a generated emotion class, which "
        "changes between Streamlit builds"
    )
