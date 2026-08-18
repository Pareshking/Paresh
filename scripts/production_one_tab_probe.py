"""One-tab production probe for diagnosing Streamlit session/readiness behavior.

Frame note: Streamlit Community Cloud serves a wrapper page and mounts the
application inside a nested iframe. Reading the top-level frame therefore
reports an empty body, zero tabs and a Screener that never appears, however
long you wait. Every DOM read below goes through app_frame().
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

URL = os.getenv("UMIYA_PRODUCTION_URL", "https://paresh.streamlit.app/")
OUT = Path("artifacts/one_tab_probe")
METRICS_ID = "umiya-startup-metrics"


def app_frame(page):
    """Return the frame hosting the Streamlit app, not the Cloud wrapper."""
    for frame in page.frames:
        try:
            if frame.locator('[data-testid="stApp"]').count() > 0:
                return frame
        except Exception:
            continue
    return page.main_frame


def read_startup_metrics(page):
    """Read the app's own cold-start telemetry, if this build publishes it."""
    for frame in page.frames:
        try:
            node = frame.locator(f"#{METRICS_ID}")
            if node.count() == 0:
                continue
            raw = node.first.text_content(timeout=5_000)
            if raw:
                return json.loads(raw)
        except Exception:
            continue
    return None


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    events: list[dict] = []
    console_errors: list[str] = []
    page_errors: list[str] = []
    ws_events: list[str] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})

        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        page.on("pageerror", lambda exc: page_errors.append(str(exc)))
        page.on("websocket", lambda ws: (ws_events.append(f"OPEN {ws.url}"), ws.on("close", lambda: ws_events.append(f"CLOSE {ws.url}"))))

        def response(resp) -> None:
            if resp.request.resource_type in {"document", "xhr", "fetch", "websocket"} or resp.status >= 400:
                events.append({
                    "t": round(time.perf_counter() - t0, 3),
                    "status": resp.status,
                    "type": resp.request.resource_type,
                    "url": resp.url,
                })

        page.on("response", response)
        page.on("requestfailed", lambda req: events.append({
            "t": round(time.perf_counter() - t0, 3),
            "failed": req.url,
            "failure": req.failure,
        }))

        print(f"URL={URL}")
        print(f"T+0.000 navigation_start")
        nav_start = time.perf_counter()
        page.goto(URL, wait_until="domcontentloaded", timeout=120_000)
        print(f"T+{time.perf_counter()-t0:.3f} domcontentloaded")

        # Probe the actual Streamlit health endpoint from the same browser context.
        try:
            health = page.request.get(URL.rstrip("/") + "/_stcore/health", timeout=30_000)
            print(f"T+{time.perf_counter()-t0:.3f} health_status={health.status}")
        except Exception as exc:
            print(f"T+{time.perf_counter()-t0:.3f} health_error={exc}")

        # Poll for the first real application UI signal, but only for measurement.
        # No pass/fail threshold is imposed here.
        screener_time = None
        for _ in range(360):
            try:
                frame = app_frame(page)
                loc = frame.get_by_text("Screener", exact=True)
                if loc.count() and loc.first.is_visible():
                    screener_time = time.perf_counter() - t0
                    print(f"T+{screener_time:.3f} screener_visible")
                    break
            except Exception:
                pass
            page.wait_for_timeout(1000)

        frame = app_frame(page)
        frames_seen = [f.url for f in page.frames]
        print(f"T+{time.perf_counter()-t0:.3f} frames={frames_seen}")
        try:
            body = frame.locator("body").inner_text(timeout=10_000)
        except Exception:
            body = ""
        print(f"T+{time.perf_counter()-t0:.3f} body_chars={len(body)}")
        print(f"T+{time.perf_counter()-t0:.3f} tab_count={frame.get_by_role('tab').count()}")

        startup_metrics = read_startup_metrics(page)
        if startup_metrics:
            facts = startup_metrics.get("facts", {})
            print(f"T+{time.perf_counter()-t0:.3f} cold_container={facts.get('cold_container')} "
                  f"uptime={startup_metrics.get('uptime_s')}s")

        if screener_time is not None:
            try:
                frame.get_by_text("Screener", exact=True).first.click(timeout=10_000)
                page.wait_for_timeout(1000)
                print(f"T+{time.perf_counter()-t0:.3f} screener_clicked")
            except Exception as exc:
                print(f"T+{time.perf_counter()-t0:.3f} screener_click_error={exc}")

        nav = frame.evaluate("""() => ({
            navigation: performance.getEntriesByType('navigation').map(x => ({
                domContentLoaded: x.domContentLoadedEventEnd,
                load: x.loadEventEnd,
                responseEnd: x.responseEnd,
                duration: x.duration
            })),
            readyState: document.readyState,
            title: document.title,
            bodyChars: document.body ? document.body.innerText.length : 0
        })""")

        result = {
            "elapsed_seconds": round(time.perf_counter() - t0, 3),
            "screener_visible_seconds": None if screener_time is None else round(screener_time, 3),
            "frames": frames_seen,
            "startup_metrics": startup_metrics,
            "tab_count": frame.get_by_role("tab").count(),
            "navigation": nav,
            "websockets": ws_events,
            "console_errors": console_errors,
            "page_errors": page_errors,
            "events": events,
            "body_excerpt": body[:4000],
        }
        (OUT / "probe.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        page.screenshot(path=str(OUT / "final.png"), full_page=False)
        browser.close()

        print("=== PROBE RESULT ===")
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
