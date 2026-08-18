"""Streamlit-safe production QA for Umiya V1.

Separates HTTP reachability from browser readiness and uses a persistent,
realistic Chromium context. A browser cold-start timeout is reported as a
production-session compatibility failure with diagnostics, not silently
converted to a pass.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import requests
from playwright.sync_api import sync_playwright

URL = os.getenv("UMIYA_PRODUCTION_URL", "https://paresh.streamlit.app/")
HEALTH_URL = URL.rstrip("/") + "/_stcore/health"
BROWSER_TIMEOUT = 240_000
TABS = [
    "Screener", "Qualified", "Sectors", "RRG", "Multi-Strategy", "Portfolio",
    "Delivery", "Watchlist", "Market Breadth", "Backtest", "Configuration", "Guide",
]
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


def http_probe(out: Path) -> dict:
    result = {}
    for name, target in (("app", URL), ("health", HEALTH_URL)):
        started = time.perf_counter()
        try:
            response = requests.get(target, timeout=30, allow_redirects=True)
            result[name] = {
                "status": response.status_code,
                "elapsed_s": round(time.perf_counter() - started, 2),
                "final_url": response.url,
                "bytes": len(response.content),
            }
        except Exception as exc:
            result[name] = {"error": repr(exc), "elapsed_s": round(time.perf_counter() - started, 2)}
    (out / "http_probe.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def main() -> None:
    out = Path("artifacts/production_website_qa_v2")
    out.mkdir(parents=True, exist_ok=True)
    failures: list[str] = []
    probe = http_probe(out)
    if probe.get("health", {}).get("status") != 200:
        failures.append(f"Streamlit health probe failed: {probe.get('health')}")

    browser_ready = False
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(out / "browser-profile"),
            headless=True,
            viewport={"width": 1920, "height": 1080},
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
            ),
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        page_errors: list[str] = []
        page.on("pageerror", lambda exc: page_errors.append(str(exc)))
        page.on("response", lambda r: page_errors.append(f"HTTP {r.status}: {r.url}") if r.status >= 500 else None)

        started = time.perf_counter()
        try:
            page.goto(URL, wait_until="domcontentloaded", timeout=BROWSER_TIMEOUT)
            page.get_by_text("Screener", exact=True).first.wait_for(state="visible", timeout=BROWSER_TIMEOUT)
            browser_ready = True
            (out / "browser_ready.txt").write_text(
                f"ready_after_s={time.perf_counter()-started:.1f}\n", encoding="utf-8"
            )

            for name, (width, height) in VIEWPORTS.items():
                page.set_viewport_size({"width": width, "height": height})
                page.wait_for_timeout(750)
                for tab_name in TABS:
                    locator = page.get_by_text(tab_name, exact=True).first
                    if not locator.is_visible():
                        failures.append(f"{name}: missing tab {tab_name}")
                        continue
                    try:
                        locator.click(timeout=15_000)
                        page.wait_for_timeout(750)
                        body = page.locator("body").inner_text(timeout=20)
                        for token in ("Traceback", "KeyError:", "ImportError:", "IndexError:", "TypeError:", "StreamlitAPIException"):
                            if token in body:
                                failures.append(f"{name}/{tab_name}: visible runtime token {token}")
                    except Exception as exc:
                        failures.append(f"{name}/{tab_name}: {exc}")
                overflow = page.evaluate("document.documentElement.scrollWidth-window.innerWidth")
                if width <= 600 and overflow > 24:
                    failures.append(f"{name}: horizontal overflow {overflow}px")
                page.screenshot(path=str(out / f"{name}.png"), full_page=False)
        except Exception as exc:
            (out / "browser_failure.txt").write_text(
                page.locator("body").inner_text(timeout=20) if page.locator("body").count() else repr(exc),
                encoding="utf-8",
            )
            failures.append(f"Browser production session did not reach Screener: {exc}")
        finally:
            (out / "browser_errors.txt").write_text("\n".join(page_errors), encoding="utf-8")
            context.close()

    summary = {
        "url": URL,
        "http_probe": probe,
        "browser_ready": browser_ready,
        "tabs_expected": len(TABS),
        "viewports_expected": len(VIEWPORTS),
        "failures": failures,
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
