"""Every ticker link must open the stock page in place, not in a new tab.

Measured against the live app on 2026-09-11. The Screener's card ticker was:

    {'selector': 'a.sq-sym', 'frame_url': 'https://paresh.streamlit.app/~/+/',
     'in_component_iframe': False, 'href': '?stock=WELCORP',
     'target': '_blank'}

Nothing in this repository asked for `_blank` -- Streamlit's markdown renderer
applies it to any anchor that does not say otherwise. Two consequences, and the
second is the one that was reported:

1. Every ticker click opened a NEW TAB.
2. The href is RELATIVE, so in the new tab it resolved against the document it
   came from -- the app, which Streamlit Community Cloud mounts at /~/+/ --
   producing `paresh.streamlit.app/~/+/?stock=WELCORP`. The original tab kept
   the clean URL, which is why the probe saw the current page never navigate.

The Sectors tab already set `target="_self"` and behaved correctly. So the same
action, clicking a ticker, behaved two different ways depending on which view
you were in. That is a defect rather than a preference, and this test keeps the
two in step -- Streamlit's default will silently reapply otherwise.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCES = sorted((ROOT / "src").rglob("*.py"))

# The anchor opening a stock page, wherever it is built.
STOCK_ANCHOR = re.compile(r"""<a\s+href=(?:"|')\?stock=""")


def _anchor_lines():
    for path in SOURCES:
        for lineno, line in enumerate(path.read_text().splitlines(), start=1):
            if STOCK_ANCHOR.search(line):
                yield path, lineno, line


def test_the_app_still_builds_stock_anchors_somewhere():
    found = list(_anchor_lines())
    assert found, "no ?stock= anchors found; this guard has lost its target"
    assert len(found) >= 2, f"expected several ticker links, found {len(found)}"


# The table's ticker is the ONE anchor that must not say target="_self", and
# the reason is the sandbox rather than taste. Streamlit mounts that table in an
# iframe with no allow-top-navigation, so "_self" would navigate the little
# table frame INTO ITSELF rather than opening the stock page. Its click is
# intercepted in JS and a script injected into the parent document instead; the
# href exists only so middle-click and "copy link address" still behave.
# tests/test_stock_page_and_navigation.py pins that mechanism, and it caught
# this test's first version trying to "fix" it.
SANDBOXED_TABLE_ANCHOR = "theme.py"


def _in_app_document(path) -> bool:
    return path.name != SANDBOXED_TABLE_ANCHOR


@pytest.mark.parametrize(
    "case", [c for c in _anchor_lines() if _in_app_document(c[0])],
    ids=lambda c: f"{c[0].name}:{c[1]}" if isinstance(c, tuple) else str(c),
)
def test_every_stock_anchor_opens_in_place(case):
    path, lineno, line = case
    # The attribute may sit on the next fragment of an implicitly concatenated
    # f-string, so check a small window rather than the one line.
    src = path.read_text().splitlines()
    window = " ".join(src[max(0, lineno - 1):lineno + 2])
    assert 'target="_self"' in window, (
        f'{path.name}:{lineno} builds a ?stock= link without target="_self". '
        f"Streamlit defaults such anchors to _blank, which opens a new tab and "
        f"resolves the relative href against the app's mount path -- the "
        f"/~/+/?stock=SYM URL that was reported. Line: {line.strip()[:120]}"
    )


def test_the_sandboxed_table_anchor_stays_free_of_a_target():
    """It navigates by script injection; a target would break or mislead."""
    src = (ROOT / "src" / "ui" / "theme.py").read_text()
    for path, lineno, line in _anchor_lines():
        if path.name != SANDBOXED_TABLE_ANCHOR:
            continue
        window = " ".join(src.splitlines()[max(0, lineno - 1):lineno + 2])
        assert "target=" not in window, (
            f"theme.py:{lineno} gives the sandboxed table ticker a target; it "
            f"cannot navigate anything but itself, and its click is handled in "
            f"JS by injecting into the parent document"
        )


def test_no_stock_anchor_asks_for_a_new_tab_explicitly():
    for path, lineno, line in _anchor_lines():
        src = path.read_text().splitlines()
        window = " ".join(src[max(0, lineno - 1):lineno + 2])
        assert 'target="_blank"' not in window, (
            f"{path.name}:{lineno} opens the stock page in a new tab"
        )
