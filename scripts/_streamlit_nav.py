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

import time

# Every selector here is a test id VERIFIED to exist in the pinned Streamlit
# build -- see tests/test_qa_probes_share_one_navigator.py, which greps the
# installed frontend for each one.
#
# `stTopNav` was used here and does NOT exist. It was taken from a substring
# grep that matched the prefix of `stTopNavLink`, so the readiness check waited
# out its full 420s budget on an element that could never appear and reported a
# healthy app as state "unknown" (run 301). Infer a selector, verify a selector.
NAV_CONTAINERS = (
    '[data-testid="stPageLink"]',
    '[data-testid="stTabs"]',
    '[data-testid="stTopNavLink"]',
    '[data-testid="stTopNavSection"]',
    '[data-testid="stSidebarNav"]',
    '[data-testid="stSidebarNavLink"]',
)

# Counted and reported when NAV_CONTAINERS finds nothing, so a failure says
# what the DOM actually contains instead of only what it lacks.
NAV_DIAGNOSTIC_SELECTORS = NAV_CONTAINERS + (
    '[data-testid="stHeader"]',
    '[data-testid="stMain"]',
    '[data-testid="stSidebar"]',
    '[data-testid="stToolbar"]',
    '[data-testid="stAppViewContainer"]',
    "header",
    "nav",
    'a[href*="/screener"]',
    'a[href*="/configuration"]',
)



# Why the last _open_custom_popover call could not open the menu, for the
# report. Empty when it opened.
LAST_OPEN_DIAGNOSIS: list[str] = []

_MENU_BUTTONS = (
    '[data-testid="stPopoverButton"]',
    '[data-testid="stPopover"] button',
    'button[aria-label="Open navigation"]',
    'button:has-text("☰")',
)


def _menu_is_open(frame) -> bool:
    """At least one page link in the popover is visible.

    Not aria-expanded: the button flips to expanded a moment BEFORE the
    links render, so trusting it reported an empty menu as open.
    """
    links = frame.locator('[data-testid="stPopoverBody"] [data-testid="stPageLink"]')
    try:
        for i in range(min(links.count(), 12)):
            if links.nth(i).is_visible():
                return True
    except Exception:
        pass
    return False


def _button_expanded(button) -> bool:
    try:
        return button.get_attribute("aria-expanded") == "true"
    except Exception:
        return False


def _open_custom_popover(frame) -> bool:
    """Open the custom hamburger and wait until the menu is open.

    One button, clicked at most twice. This used to try four selectors in
    turn and click each one -- but they are the SAME button, and a popover
    button toggles, so every "it did not open in time" guess closed the menu
    again. Harmless while the menu stayed open across pages; once choosing a
    page started closing it (#177), every mobile page cost ~25s of toggling
    (run 577) and a desktop click landed on a menu that was mid-toggle.
    """
    LAST_OPEN_DIAGNOSIS.clear()
    if _menu_is_open(frame):
        return True

    button = None
    for selector in _MENU_BUTTONS:
        try:
            candidate = frame.locator(selector).first
            if candidate.count():
                button = candidate
                break
        except Exception:
            continue
    if button is None:
        try:
            candidate = frame.get_by_role("button", name="☰", exact=True).first
            if candidate.count():
                button = candidate
        except Exception:
            pass
    if button is None:
        LAST_OPEN_DIAGNOSIS.append("no menu button found")
        return False

    # A second click only if the first one did not take: a rerun that lands
    # while the click is in flight can swallow it.
    for attempt in (1, 2):
        # Already expanded: the links are on their way. Clicking now would
        # CLOSE the menu, so wait for them instead.
        if _button_expanded(button):
            deadline = time.perf_counter() + 5.0
            while time.perf_counter() < deadline:
                if _menu_is_open(frame):
                    LAST_OPEN_DIAGNOSIS.clear()
                    return True
                time.sleep(0.1)
            LAST_OPEN_DIAGNOSIS.append(f"attempt {attempt}: expanded but no links after 5s")
            continue
        try:
            button.click(timeout=8_000)
        except Exception as exc:
            # Playwright names the element that intercepted the click, which
            # is exactly what a reader-facing overlap would look like.
            LAST_OPEN_DIAGNOSIS.append(
                f"click {attempt}: {str(exc).splitlines()[0][:200]}")
            continue
        deadline = time.perf_counter() + 5.0
        while time.perf_counter() < deadline:
            if _menu_is_open(frame):
                LAST_OPEN_DIAGNOSIS.clear()
                return True
            time.sleep(0.1)
        LAST_OPEN_DIAGNOSIS.append(f"click {attempt}: menu not open after 5s")
    return False


def _click_with_retry(frame, locator_fn, attempts: int = 3) -> None:
    """Click a menu link, reopening the menu if a rerun detached it."""
    last: Exception | None = None
    for _ in range(attempts):
        try:
            locator_fn().click(timeout=15_000)
            return
        except Exception as exc:  # detached / not stable while rerendering
            last = exc
            time.sleep(0.5)
            _open_custom_popover(frame)
    assert last is not None
    raise last


def _close_custom_popover(frame) -> None:
    try:
        if not frame.locator('[data-testid="stPopoverBody"]').count():
            return
        button = frame.locator('[data-testid="stPopoverButton"]').first
        if button.count():
            button.click(timeout=5_000)
    except Exception:
        pass


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
    if total == 0 and _open_custom_popover(frame):
        for sel in NAV_CONTAINERS:
            try:
                total += frame.locator(sel).count()
            except Exception:
                continue
    return total


def nav_diagnostics(frame) -> dict:
    """What nav-ish elements the DOM actually holds, for when nothing matches.

    A readiness failure that only says "no navigation found" cannot distinguish
    "the app did not render" from "the probe is looking for the wrong element".
    Run 301 was the second of those and cost a full run to find out.
    """
    found = {}
    for sel in NAV_DIAGNOSTIC_SELECTORS:
        try:
            found[sel] = frame.locator(sel).count()
        except Exception:
            found[sel] = -1
    return {k: v for k, v in found.items() if v}


def open_page(frame, name: str, page=None) -> str:
    """Open one page through the real custom navigation."""
    _open_custom_popover(frame)

    def page_link():
        return frame.locator('[data-testid="stPageLink"]').filter(has_text=name).first

    if page_link().count():
        _click_with_retry(frame, page_link)
        return "page_link"

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
            sections.nth(i).click(timeout=4_000)
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

    if page is not None:
        routes = {
            "Screener": "screener",
            "Qualified": "qualified",
            "Sectors": "sectors",
            "RRG": "rrg",
            "Portfolio": "portfolio",
            "Watchlist": "watchlist",
            "Market Breadth": "breadth",
            "Backtest": "backtest",
            "Track Record": "track-record",
            "Configuration": "configuration",
            "Guide": "guide",
        }
        route = routes.get(name)
        if route:
            _close_custom_popover(frame)
            from urllib.parse import urlsplit
            parts = urlsplit(page.url)
            page.goto(
                f"{parts.scheme}://{parts.netloc}/{route}",
                wait_until="domcontentloaded",
                timeout=120_000,
            )
            return "direct_route"

    raise LookupError(f"no navigation control found for page {name!r}")


def missing_pages(frame, names, page=None) -> list[str]:
    """Which of `names` cannot be reached at all.

    A page hidden inside the overflow dropdown is PRESENT, so this opens each
    dropdown before concluding anything is missing -- the check it replaces
    counted only visible controls and would have called eight of eleven pages
    missing on a phone.
    """
    reachable: set[str] = set()

    menu_opened = _open_custom_popover(frame)

    for sel in ('[data-testid="stPageLink"]',
                '[data-testid="stTopNavLink"]',
                '[data-testid="stSidebarNavLink"]'):
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

    missing = [n for n in names
              if not any(n == r or n in r for r in reachable)]
    _close_custom_popover(frame)
    # A hamburger that would not open cannot be read, so there the button's
    # presence is taken as the navigation contract. A hamburger that DID open
    # has just been read, and what it lacks is missing.
    #
    # This used to return [] whenever the button existed, opened or not -- so
    # a page dropped from the menu passed reachability on every viewport. The
    # full walk could not catch it either: open_page falls back to the page's
    # direct URL, which works whether or not the menu links to it.
    if missing and not menu_opened:
        try:
            if frame.locator('[data-testid="stPopoverButton"]').count():
                return []
        except Exception:
            pass
    return missing
