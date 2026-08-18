"""Measure a genuine Umiya V1 cold start in production.

A cold start is not "the app after a deploy" — it is the first session to
reach a container whose /tmp cache is empty, because that session is the one
that pays for the full 752-symbol download. This probe therefore does not
assume coldness from the fact that a deploy happened; it reads the cache
snapshot the application records before any fetch runs and refuses to report
a cold measurement unless the container actually was cold.

Two clocks are combined:

* Browser-side, measured here: when the app became reachable, when the
  Streamlit shell appeared, when the Screener UI first became usable, and
  when the page became fully interactive.
* Process-side, recorded by src/core/startup_metrics and published in a
  hidden element: per-stage durations (universe, price history, market caps,
  quant engine, delivery) and the fetch counters (Yahoo batches, individual
  retries, market-cap fallback and sequential retries, missing symbols).

The process-side numbers survive across sessions, so the real cold-start cost
is still readable even if something else connected to the container first.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import requests
from playwright.sync_api import sync_playwright

URL = os.getenv("UMIYA_PRODUCTION_URL", "https://paresh.streamlit.app/").rstrip("/") + "/"
OUT = Path(os.getenv("UMIYA_PROBE_OUT", "artifacts/cold_start_probe"))
METRICS_ID = "umiya-startup-metrics"

# How long to keep waiting for the app to answer at all after a redeploy.
REACHABLE_TIMEOUT_S = int(os.getenv("UMIYA_REACHABLE_TIMEOUT_S", "600"))
# How long a cold pipeline is allowed to run before we stop and report it.
READY_BUDGET_S = int(os.getenv("UMIYA_READY_BUDGET_S", "1500"))
POLL_S = 5
TABS = [
    "Screener", "Qualified", "Sectors", "RRG", "Multi-Strategy", "Portfolio",
    "Delivery", "Watchlist", "Market Breadth", "Backtest", "Configuration", "Guide",
]


def wait_until_reachable(session: requests.Session) -> dict:
    """Poll until the app host answers, recording the outage window."""
    started = time.monotonic()
    first_error = None
    attempts = 0
    while time.monotonic() - started < REACHABLE_TIMEOUT_S:
        attempts += 1
        try:
            r = session.get(URL, timeout=30, allow_redirects=True)
            if r.status_code == 200:
                return {
                    "reachable": True,
                    "waited_s": round(time.monotonic() - started, 1),
                    "attempts": attempts,
                    "first_error": first_error,
                }
            first_error = first_error or f"HTTP {r.status_code}"
        except Exception as exc:
            first_error = first_error or f"{type(exc).__name__}: {str(exc)[:120]}"
        time.sleep(POLL_S)
    return {
        "reachable": False,
        "waited_s": round(time.monotonic() - started, 1),
        "attempts": attempts,
        "first_error": first_error,
    }


def app_frame(page):
    for frame in page.frames:
        try:
            if frame.locator('[data-testid="stApp"]').count() > 0:
                return frame
        except Exception:
            continue
    return page.main_frame


def read_metrics(page) -> dict | None:
    """Read the process-side telemetry from whichever frame carries it."""
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
    report: dict = {
        "url": URL,
        "probe_started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "ready_budget_s": READY_BUDGET_S,
    }

    session = requests.Session()
    session.headers["User-Agent"] = (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
    )
    report["reachability"] = reach = wait_until_reachable(session)
    print("reachability:", json.dumps(reach), flush=True)
    if not reach["reachable"]:
        report["verdict"] = "UNREACHABLE"
        (OUT / "cold_start.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        raise SystemExit(1)

    marks: dict[str, float] = {}
    timeline: list[dict] = []

    with sync_playwright() as p:
        launch = {"headless": True, "args": ["--no-sandbox"]}
        exe = os.getenv("UMIYA_CHROMIUM_PATH")
        if exe:
            launch["executable_path"] = exe
        browser = p.chromium.launch(**launch)
        context = browser.new_context(viewport={"width": 1920, "height": 1080})
        page = context.new_page()

        t0 = time.monotonic()
        page.goto(URL, wait_until="domcontentloaded", timeout=180_000)
        marks["navigation_complete_s"] = round(time.monotonic() - t0, 1)

        deadline = time.monotonic() + READY_BUDGET_S
        metrics_blob = None
        while time.monotonic() < deadline:
            elapsed = round(time.monotonic() - t0, 1)
            frame = app_frame(page)
            try:
                n_app = frame.locator('[data-testid="stApp"]').count()
                n_tabs = frame.locator('[data-testid="stTabs"]').count()
                n_spin = frame.locator('[data-testid="stSpinner"]').count()
                n_exc = frame.locator('[data-testid="stException"]').count()
            except Exception:
                n_app = n_tabs = n_spin = n_exc = 0

            if n_app and "app_shell_s" not in marks:
                marks["app_shell_s"] = elapsed
            if n_spin and "pipeline_running_first_seen_s" not in marks:
                marks["pipeline_running_first_seen_s"] = elapsed
            if n_tabs and "screener_ui_usable_s" not in marks:
                marks["screener_ui_usable_s"] = elapsed

            timeline.append({
                "t_s": elapsed, "stApp": n_app, "stTabs": n_tabs,
                "stSpinner": n_spin, "stException": n_exc,
            })
            print(json.dumps(timeline[-1]), flush=True)

            if n_exc:
                marks["exception_s"] = elapsed
                break
            if n_tabs:
                break
            time.sleep(POLL_S)

        # Fully interactive: every tab control present and a real tab switch
        # completes and repaints.
        if "screener_ui_usable_s" in marks:
            frame = app_frame(page)
            missing_tabs = []
            for name in TABS:
                loc = frame.get_by_role("tab", name=name, exact=True)
                if loc.count() == 0:
                    missing_tabs.append(name)
            report["tabs_missing"] = missing_tabs
            try:
                frame.get_by_role("tab", name="Sectors", exact=True).first.click(timeout=30_000)
                frame.wait_for_timeout(1200)
                frame.get_by_role("tab", name="Screener", exact=True).first.click(timeout=30_000)
                frame.wait_for_timeout(800)
                marks["fully_interactive_s"] = round(time.monotonic() - t0, 1)
            except Exception as exc:
                report["interaction_error"] = f"{type(exc).__name__}: {str(exc)[:160]}"

        # Delivery is loaded inside its own tab during the first script run, so
        # its stage timing is already recorded by the time the tabs exist.
        metrics_blob = read_metrics(page)
        try:
            page.screenshot(path=str(OUT / "cold_start_final.png"))
        except Exception:
            pass
        context.close()
        browser.close()

    report["browser_marks_s"] = marks
    report["timeline"] = timeline
    report["app_metrics"] = metrics_blob

    facts = (metrics_blob or {}).get("facts", {})
    stages = (metrics_blob or {}).get("stages", {})
    counters = (metrics_blob or {}).get("counters", {})
    cold = facts.get("cold_container")
    report["cold_container"] = cold

    if metrics_blob is None:
        report["verdict"] = "NO_TELEMETRY"
    elif cold is True:
        report["verdict"] = "COLD_MEASUREMENT"
    elif cold is False:
        report["verdict"] = "WARM_CONTAINER_NOT_A_COLD_MEASUREMENT"
    else:
        report["verdict"] = "INDETERMINATE"

    (OUT / "cold_start.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("\n============== COLD START MEASUREMENT ==============", flush=True)
    print(f"verdict                     : {report['verdict']}", flush=True)
    print(f"cold container (cache empty): {cold}", flush=True)
    if metrics_blob:
        print(f"module import (UTC)         : {metrics_blob.get('module_import_utc')}", flush=True)
        print(f"module age at read          : {metrics_blob.get('uptime_s')}s", flush=True)
        print(f"process identity            : {json.dumps(metrics_blob.get('process'))}", flush=True)
        print(f"cache at startup            : {json.dumps(facts.get('cache_at_startup'))}", flush=True)
    print("\n-- browser-observed --", flush=True)
    for k in ("navigation_complete_s", "app_shell_s", "pipeline_running_first_seen_s",
              "screener_ui_usable_s", "fully_interactive_s", "exception_s"):
        if k in marks:
            print(f"  {k:<32}: {marks[k]}s", flush=True)
    print("\n-- application stages --", flush=True)
    for name in ("universe", "price_history", "extract_ohlcv", "market_caps",
                 "market_regime", "quant_engine", "data_pipeline_total", "delivery"):
        s = stages.get(name)
        if s:
            print(f"  {name:<22} start {s['started_at_s']:>8.1f}s  "
                  f"dur {s['duration_s']:>8.1f}s", flush=True)
    print("\n-- fetch counters --", flush=True)
    for k in sorted(counters):
        print(f"  {k:<36}: {counters[k]:g}", flush=True)
    if not counters:
        print("  (none - nothing was fetched or computed in this process)", flush=True)
    memo_misses = {k: v for k, v in counters.items() if k.startswith("memo_miss")}
    if not memo_misses:
        print("  NOTE: no memo misses, so Streamlit served every cached call "
              "from a warm cache - these timings are not a cold pipeline.",
              flush=True)
    print("\n-- coverage --", flush=True)
    for k in ("universe_symbols", "price_path", "price_symbols_requested",
              "price_missing_after_batches", "price_series_returned",
              "mcap_path", "mcap_symbols_requested", "mcap_symbols_resolved",
              "mcap_symbols_missing", "mcap_yfinance_fallback_symbols",
              "mcap_threaded_requested", "mcap_threaded_failed",
              "script_run_completed_at_s"):
        if k in facts:
            print(f"  {k:<32}: {facts[k]}", flush=True)
    if report.get("tabs_missing"):
        print(f"\n  MISSING TABS: {report['tabs_missing']}", flush=True)
    print("====================================================", flush=True)

    if report["verdict"] in ("NO_TELEMETRY", "INDETERMINATE"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
