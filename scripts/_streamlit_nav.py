"""Driving the app's navigation from a browser, for both QA probes.

The shell moved from `st.tabs` to `st.navigation(position="top")` so that only
the active page's script executes. That changes the DOM the probes drive:

    st.tabs                 role="tab"
    st.navigation(top)      [data-testid="stTopNavLink"], and whatever does not
                            fit collapses into [data-testid="stTopNavSection"]
                            -> [data-testid="stTopNavPopover"]
                            -> [data-testid="stTopNavDropdownLink"]
    st.navigation(sidebar)  [data-testid="stSidebarNavLink"]

Eleven pages do not fit a 360px phone, so the dropdown path is the NORMAL path
on the mobile viewports, not an edge case. A probe that only clicked visible
links would report every mobile viewport broken.

This lives in one module because the two probes drifting apart is not
hypothetical: production QA spent from 20 Aug onward reporting the app broken
over a "Multi-Strategy" tab that had been deliberately deleted, because only
one place was updated. `tests/test_qa_probes_share_one_navigator.py` keeps them
on this implementation.
"""
from __future__ import annotations

NAV_CONTAINERS = (
    '[data-testid="stTabs"]',
    '[data-testid="stTopNav"]',
    '[data-testid="stSidebarNav"]',
)


def nav_count(frame) -> int:
    """How many of the app's own navigation containers are on screen.

    Readiness means "the app's nav is rendered", not "stTabs exists". Counting
    every shape keeps the readiness classifier working across the migration in
    either direction.
    """
    total = 0
    for sel in NAV_CONTAINERS:
        try:
            total += frame.locator(sel).count()
        except Exception:
            continue
    return total


def open_page(frame, name: str, page=None) -> str:
    """Open one of the app's pages by name. Returns how it was reached.

    Raises LookupError if no control for that page exists anywhere, which is a
    finding about the application rather than an error to retry.
    """
    link = frame.locator('[data-testid="stTopNavLink"]').filter(has_text=name).first
    if link.count():
        link.click(timeout=15_000)
        return "top_nav_link"

    sections = frame.locator('[data-testid="stTopNavSection"]')
    for i in range(sections.count()):
        try:
            sections.nth(i).click(timeout=8_000)
            if page is not None:
                page.wait_for_timeout(400)
            item = frame.locator(
                '[data-testid="stTopNavDropdownLink"]').filter(has_text=name).first
            if item.count():
                item.click(timeout=15_000)
                return "top_nav_dropdown"
            sections.nth(i).click(timeout=4_000)      # close it again
        except Exception:
            continue

    tab = frame.get_by_role("tab", name=name, exact=True).first
    if tab.count():
        tab.click(timeout=20_000)
        return "tab"

    side = frame.locator('[data-testid="stSidebarNavLink"]').filter(has_text=name).first
    if side.count():
        side.click(timeout=15_000)
        return "sidebar_nav_link"

    raise LookupError(f"no navigation control found for page {name!r}")


def missing_pages(frame, names, page=None) -> list[str]:
    """Which of `names` cannot be reached at all.

    A page hidden inside the overflow dropdown is PRESENT, so this opens each
    dropdown before concluding anything is missing -- the check it replaces
    counted only visible controls and would have called eight of eleven pages
    missing on a phone.
    """
    reachable: set[str] = set()

    for sel in ('[data-testid="stTopNavLink"]', '[data-testid="stSidebarNavLink"]'):
        try:
            items = frame.locator(sel)
            for i in range(items.count()):
                reachable.add(items.nth(i).inner_text(timeout=3_000).strip())
        except Exception:
            pass

    sections = frame.locator('[data-testid="stTopNavSection"]')
    try:
        for i in range(sections.count()):
            sections.nth(i).click(timeout=8_000)
            if page is not None:
                page.wait_for_timeout(400)
            items = frame.locator('[data-testid="stTopNavDropdownLink"]')
            for j in range(items.count()):
                reachable.add(items.nth(j).inner_text(timeout=3_000).strip())
            sections.nth(i).click(timeout=4_000)
    except Exception:
        pass

    try:
        tabs = frame.get_by_role("tab")
        for i in range(tabs.count()):
            reachable.add(tabs.nth(i).inner_text(timeout=3_000).strip())
    except Exception:
        pass

    return [n for n in names
            if not any(n == r or n in r for r in reachable)]
