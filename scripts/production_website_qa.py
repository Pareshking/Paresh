"""Read-only production website QA for Umiya V1."""
from __future__ import annotations
import os
from pathlib import Path
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError, sync_playwright
PRODUCTION_URL = os.getenv("UMIYA_PRODUCTION_URL", "https://paresh.streamlit.app/")
VIEWPORTS = {"desktop_1920x1080": (1920,1080), "desktop_1440x900": (1440,900), "desktop_1366x768": (1366,768), "desktop_1280x800": (1280,800), "desktop_1024x768": (1024,768), "mobile_390x844": (390,844), "mobile_375x812": (375,812), "mobile_360x800": (360,800)}
EXPECTED_TABS = ["Screener","Qualified","Sectors","RRG","Multi-Strategy","Portfolio","Delivery","Watchlist","Market Breadth","Backtest","Configuration","Guide"]
MUTATING_BUTTONS = {"Sync NSE CSVs", "Purge Cache"}

def _assert_no_runtime_errors(page: Page, errors: list[str]) -> None:
    body = page.locator("body").inner_text(timeout=20)
    for token in ("Traceback", "KeyError:", "ImportError:", "IndexError:", "TypeError:"):
        if token in body: errors.append(f"Visible runtime token: {token}")
    if page.locator("text=StreamlitAPIException").count(): errors.append("Visible StreamlitAPIException")

def _find_tabs(page: Page):
    semantic = page.get_by_role("tab")
    return semantic if semantic.count() else page.locator('[data-baseweb="tab"]')

def _audit_view(page: Page, tab_name: str, errors: list[str]) -> None:
    _assert_no_runtime_errors(page, errors)
    if not page.locator("body").inner_text(timeout=20).strip(): errors.append(f"Blank page after opening tab {tab_name}")
    for locator_name, locator in (("select",page.locator("select")),("checkbox",page.locator('input[type="checkbox"]')),("radio",page.locator('input[type="radio"]')),("slider",page.locator('input[type="range"]'))):
        if locator.count(): print(f"  {tab_name}: {locator_name}s={locator.count()}")
    buttons = page.get_by_role("button")
    for i in range(buttons.count()):
        button = buttons.nth(i)
        if not button.is_visible(): continue
        name = (button.get_attribute("aria-label") or button.inner_text()).strip()
        if not name: errors.append(f"Unnamed visible button on {tab_name}")
        elif name not in MUTATING_BUTTONS and not button.is_disabled() and "download" in name.lower():
            try:
                with page.expect_download(timeout=10): button.click()
            except Exception as exc: errors.append(f"Download failed on {tab_name} [{name}]: {exc}")

def main() -> None:
    output = Path("artifacts/production_website_qa"); output.mkdir(parents=True, exist_ok=True); failures=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        try:
            for viewport_name,(width,height) in VIEWPORTS.items():
                print(f"\n=== {viewport_name} ==="); page=browser.new_page(viewport={"width":width,"height":height}); browser_errors=[]; response_errors=[]
                page.on("pageerror", lambda exc: browser_errors.append(f"pageerror: {exc}"))
                page.on("console", lambda msg: browser_errors.append(f"console error: {msg.text}") if msg.type=="error" else None)
                page.on("response", lambda response: response_errors.append(f"HTTP {response.status}: {response.url}") if response.status>=400 else None)
                try:
                    page.goto(PRODUCTION_URL, wait_until="domcontentloaded", timeout=180_000)
                    try: page.get_by_text("Screener", exact=True).first.wait_for(state="visible", timeout=180_000)
                    except PlaywrightTimeoutError:
                        (output/f"{viewport_name}_failure.txt").write_text(page.locator("body").inner_text(timeout=20),encoding="utf-8"); failures.append(f"{viewport_name}: application did not expose Screener within 180s"); continue
                    tabs=_find_tabs(page); names=[tabs.nth(i).inner_text().strip() for i in range(tabs.count())]; print("tabs:",names)
                    if names!=EXPECTED_TABS: failures.append(f"{viewport_name}: tabs={names!r}, expected={EXPECTED_TABS!r}")
                    for tab_name in EXPECTED_TABS:
                        tab=page.get_by_text(tab_name, exact=True).first
                        if not tab.count() or not tab.is_visible(): failures.append(f"{viewport_name}: missing visible tab {tab_name}"); continue
                        tab.click(); page.wait_for_timeout(750); _audit_view(page,tab_name,browser_errors)
                    overflow=page.evaluate("document.documentElement.scrollWidth-window.innerWidth"); print(f"  horizontal_overflow={overflow}px")
                    if width<=600 and overflow>24: failures.append(f"{viewport_name}: horizontal overflow {overflow}px")
                    page.screenshot(path=str(output/f"{viewport_name}.png"),full_page=False)
                except Exception as exc: failures.append(f"{viewport_name}: browser failure: {exc}")
                finally:
                    failures.extend(f"{viewport_name}: {e}" for e in browser_errors)
                    if response_errors: (output/f"{viewport_name}_http_errors.txt").write_text("\n".join(response_errors),encoding="utf-8")
                    page.close()
        finally: browser.close()
    if failures:
        print("\nPRODUCTION_WEBSITE_QA=FAIL"); [print("-",f) for f in failures]; raise SystemExit(1)
    print("\nPRODUCTION_WEBSITE_QA=PASS"); print(f"URL={PRODUCTION_URL}"); print(f"viewports_tested={len(VIEWPORTS)}"); print(f"tabs_tested={len(EXPECTED_TABS)}")
if __name__=="__main__": main()
