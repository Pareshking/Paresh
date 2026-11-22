#!/usr/bin/env python3
"""Keep the live app awake: open its home page once in a real browser (S202).

Streamlit Community Cloud puts an app to sleep after 12 hours without traffic, and a
visit wakes it ("All apps without traffic for 12 hours go to sleep ... To keep your app
awake, simply visit your app", docs.streamlit.io, read 23 Nov 2026). Until 23 Nov 2026
the 6-hourly Production QA was the visit: 2-3.5 min of browser checks over 11 pages and
several viewports. This is one page load. On the sleep page it presses the wake button.

Exits 0 when the app's own page has rendered, 1 when it has not within the time
allowed (the scheduled-failure alert fires). Uses the runner's installed Chrome
(channel="chrome"), so nothing is downloaded.
"""
from __future__ import annotations

import os
import sys
import time

URL = os.getenv("UMIYA_PRODUCTION_URL", "https://paresh.streamlit.app/").rstrip("/") + "/"
ASLEEP = ("has gone to sleep", "get this app back up")
APP = '[data-testid="stAppViewContainer"]'
LIMIT_S = 240


def rendered(page) -> bool:
    return any(f.query_selector(APP) is not None for f in page.frames)


def asleep(page) -> bool:
    text = (page.content() or "").lower()
    return any(n in text for n in ASLEEP)


def main() -> int:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(channel=os.getenv("KEEP_AWAKE_CHANNEL", "chrome"))
        page = browser.new_page()
        page.goto(URL, wait_until="domcontentloaded", timeout=120_000)
        start, woke = time.monotonic(), False
        while time.monotonic() - start < LIMIT_S:
            if rendered(page):
                print(f"AWAKE {URL} after {time.monotonic() - start:.0f}s{' (woken from sleep)' if woke else ''}")
                browser.close()
                return 0
            if asleep(page) and not woke:
                print("The app was asleep; pressing the wake button.")
                page.get_by_role("button", name="get this app back up", exact=False).first.click()
                woke = True
            time.sleep(3)
        print(f"::error::{URL} did not render within {LIMIT_S}s (asleep={asleep(page)})")
        browser.close()
        return 1


if __name__ == "__main__":
    sys.exit(main())
