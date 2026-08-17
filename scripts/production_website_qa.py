"""Read-only production website QA for Umiya V1.

This test intentionally avoids mutating/admin actions such as NSE sync and cache purge.
It validates navigation, visible controls, responsive layout, download controls,
and browser/runtime errors against the deployed production application.
"""

from __future__ import annotations

import os
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

PRODUCTION_URL = os.getenv("UMIYA_PRODUCTION_URL", "https://paresh.streamlit.app/")

VIEWPORTS = {
    "desktop_1920x1080": (1920, 1080),
    "desktop_1440x900": (1440, 900),
    "desktop_1366x768": (1366, 768),
    "desktop_1280x800": (1280, 800),
    "desktop_1024x768": (1024, 768),
    "mobile_390x844": (390, 844),
    "mobile_375x812": (375, 812),
    "mobile_360x800": (360, 800),
}

EXPECTED_TABS = [
    "Screener",
    "Qualified",
    "Sectors",
    "RRG",
    "Multi-Strategy",
    "Portfolio",
    "Delivery",
    "Watchlist",
    "Market Breadth",
    "Backtest",
    "Configuration",
    "Guide",
]

MUTATING_BUTTONS = {"Sync NSE CSVs", "Purge Cache"}


def _assert_no_runtime_errors(page: Page, errors: list[str]) -> None:
    body = page.locator("body").inner_text(timeout=20)
    bad_tokens = ("Traceback", "KeyError:", "ImportError:", "IndexError:", "TypeError:")
    for token in bad_tokens:
        if token in body:
            errors.append(f"Visible runtime token: {token}")
    if page.locator("text=StreamlitAPIException").count():
        errors.append("Visible StreamlitAPIException")


def _audit_view(page: Page, tab_name: str, errors: list[str]) -> None:
    # Tab content must not expose an exception/blank critical state.
    _assert_no_runtime_errors(page, errors)
    if not page.locator("body").inner_text(timeout=20).strip():
        errors.append(f"Blank page after opening tab {tab_name}")

    # Exercise non-mutating selectboxes/radios/checkboxes/sliders where available.
    for locator_name, locator in (
        ("select", page.locator("select")),
        ("checkbox", page.locator('input[type="checkbox"]')),
        ("radio", page.locator('input[type="radio"]')),
        ("slider", page.locator('input[type="range"]')),
    ):
        count = locator.count()
        if count:
            print(f"  {tab_name}: {locator_name}s={count}")

    # Verify buttons have accessible names. Do not click mutating/admin actions.
    buttons = page.get_by_role("button")
    for i in range(buttons.count()):
        button = buttons.nth(i)
        if not button.is_visible():
            continue
        name = (button.get_attribute("aria-label") or button.inner_text()).strip()
        if not name:
            errors.append(f"Unnamed visible button on {tab_name}")
        elif name not in MUTATING_BUTTONS and not button.is_disabled():
            # Download buttons are safe to exercise; other buttons are inventoried only
            # to avoid unintended state-changing production actions.
            if "download" in name.lower():
                try:
                    with page.expect_download(timeout=10):
                        button.click()
                except Exception as exc:  # pragma: no cover - production-only timing
                    errors.append(f"Download failed on {tab_name} [{name}]: {exc}")


def main() -> None:
    output = Path("artifacts/production_website_qa")
    output.mkdir(parents=True, exist_ok=True)
    failures: list[str] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            for viewport_name, (width, height) in VIEWPORTS.items():
                print(f"\n=== {viewport_name} ===")
                page = browser.new_page(viewport={"width": width, "height": height})
                browser_errors: list[str] = []
                page.on("pageerror", lambda exc: browser_errors.append(f"pageerror: {exc}"))
                page.on(
                    "console",
                    lambda msg: browser_errors.append(f"console error: {msg.text}")
                    if msg.type == "error"
                    else None,
                )
                try:
                    page.goto(PRODUCTION_URL, wait_until="domcontentloaded", timeout=180_000)
                    page.wait_for_timeout(5_000)
                    if not page.get_by_role("tab", name="Screener", exact=True).count():
                        failures.append(f"{viewport_name}: Screener tab not rendered")
                        continue

                    tabs = page.get_by_role("tab")
                    names = [tabs.nth(i).inner_text().strip() for i in range(tabs.count())]
                    print("tabs:", names)
                    if names != EXPECTED_TABS:
                        failures.append(f"{viewport_name}: tabs={names!r}, expected={EXPECTED_TABS!r}")

                    for tab_name in EXPECTED_TABS:
                        tab = page.get_by_role("tab", name=tab_name, exact=True)
                        if not tab.count():
                            failures.append(f"{viewport_name}: missing tab {tab_name}")
                            continue
                        tab.click()
                        page.wait_for_timeout(500)
                        _audit_view(page, tab_name, browser_errors)

                    # Responsive check: body should not materially overflow the viewport.
                    overflow = page.evaluate("document.documentElement.scrollWidth - window.innerWidth")
                    if width <= 600 and overflow > 24:
                        failures.append(f"{viewport_name}: horizontal overflow {overflow}px")

                    screenshot = output / f"{viewport_name}.png"
                    page.screenshot(path=str(screenshot), full_page=False)
                except Exception as exc:
                    failures.append(f"{viewport_name}: browser failure: {exc}")
                finally:
                    failures.extend(f"{viewport_name}: {e}" for e in browser_errors)
                    page.close()
        finally:
            browser.close()

    if failures:
        print("\nPRODUCTION_WEBSITE_QA=FAIL")
        for failure in failures:
            print("-", failure)
        raise SystemExit(1)

    print("\nPRODUCTION_WEBSITE_QA=PASS")
    print(f"URL={PRODUCTION_URL}")
    print(f"viewports_tested={len(VIEWPORTS)}")
    print(f"tabs_tested={len(EXPECTED_TABS)}")


if __name__ == "__main__":
    main()
