"""Both QA probes must drive the app's navigation through one implementation.

This repository has already paid for the alternative. Production QA spent from
20 Aug onward reporting the app broken over a "Multi-Strategy" tab that had
been deliberately deleted, because only one of the two places that knew about
tabs was updated. A check that fails for a reason nobody acts on stops being
read, which is worse than not having it.

The shell's move from `st.tabs` to `st.navigation(position="top")` changed the
DOM both probes drive — links and an overflow dropdown instead of tab controls
— which is exactly the kind of change that splits two copies apart.
"""
from __future__ import annotations

import ast
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
PROBES = ["scripts/production_qa.py", "scripts/cold_start_probe.py"]
NAV_MODULE = ROOT / "scripts" / "_streamlit_nav.py"


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_the_shared_navigator_exists_and_parses():
    assert NAV_MODULE.is_file()
    ast.parse(NAV_MODULE.read_text(encoding="utf-8"))


@pytest.mark.parametrize("probe", PROBES)
def test_each_probe_imports_the_shared_navigator(probe):
    assert "_streamlit_nav import" in _source(probe), (
        f"{probe} does not use the shared navigator, so it can drift"
    )


@pytest.mark.parametrize("probe", PROBES)
def test_no_probe_still_hardcodes_a_tab_role_click(probe):
    """`role="tab"` survives only inside the shared navigator's fallback."""
    assert 'get_by_role("tab"' not in _source(probe), (
        f"{probe} clicks role=tab directly; the app renders nav links now, and "
        f"the fallback belongs in scripts/_streamlit_nav.py"
    )


def test_the_navigator_handles_every_shape_the_shell_can_take():
    """Tabs, top nav, the overflow dropdown, and the sidebar."""
    src = NAV_MODULE.read_text(encoding="utf-8")
    for needle in ("stPageLink", "stTopNavLink", "stTopNavSection",
                   "stTopNavDropdownLink", "stSidebarNavLink",
                   'get_by_role("tab"'):
        assert needle in src, f"the navigator cannot drive {needle}"


def test_the_navigator_raises_rather_than_returning_a_false_negative():
    """An unreachable page is a finding, not something to retry past."""
    src = NAV_MODULE.read_text(encoding="utf-8")
    assert "raise LookupError" in src


def test_every_test_id_the_navigator_uses_exists_in_the_pinned_streamlit():
    """A selector must be verified against the frontend, not inferred.

    Run 301 waited out its entire 420-second readiness budget looking for
    `[data-testid="stTopNav"]`, reported a perfectly healthy app as state
    "unknown", and cost a full production run. That id does not exist: it came
    from a substring grep that matched the PREFIX of `stTopNavLink`.

    `streamlit` is pinned to an exact version precisely so a check like this is
    stable, so grep the installed frontend for every id the probes rely on.
    """
    import re

    import streamlit

    static = pathlib.Path(streamlit.__file__).parent / "static"
    if not static.is_dir():
        pytest.skip("no streamlit static bundle to check against")
    blob = "".join(
        f.read_text(encoding="utf-8", errors="ignore")
        for f in static.rglob("*.js")
    )
    assert blob, "streamlit frontend bundle is empty"

    src = NAV_MODULE.read_text(encoding="utf-8")
    ids = sorted(set(re.findall(r'data-testid="(st[A-Za-z]+)"', src)))
    assert ids, "no test ids found in the navigator"

    missing = [
        tid for tid in ids
        if f"`{tid}`" not in blob and f'"{tid}"' not in blob and f"'{tid}'" not in blob
    ]
    assert not missing, (
        f"these test ids do not exist in streamlit {streamlit.__version__}: "
        f"{missing} -- they were inferred rather than verified"
    )


def test_a_readiness_failure_reports_what_the_dom_does_contain():
    """"No navigation found" cannot tell a broken app from a wrong selector."""
    src = NAV_MODULE.read_text(encoding="utf-8")
    assert "def nav_diagnostics" in src
    qa = _source("scripts/production_qa.py")
    assert "nav_diagnostics" in qa, (
        "the probe records no evidence when the nav is missing, which is the "
        "one case where evidence decides whose defect it is"
    )


def test_readiness_is_not_pinned_to_stTabs_any_more():
    """Readiness means the app's nav rendered, whichever primitive draws it."""
    src = NAV_MODULE.read_text(encoding="utf-8")
    assert "stTabs" in src and "stTopNavLink" in src, (
        "nav_count must accept both shapes so the classifier survives the "
        "migration in either direction"
    )
    qa = _source("scripts/production_qa.py")
    assert 'count(\'[data-testid="stTabs"]\')' not in qa, (
        "production_qa still classifies readiness by stTabs alone"
    )


def test_the_navigator_does_not_reference_the_id_that_never_existed():
    assert 'data-testid="stTopNav"' not in NAV_MODULE.read_text(encoding="utf-8")
