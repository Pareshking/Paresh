"""Umiya V1 production QA — evidence-first, Streamlit-aware.

Design principles (replaces the earlier timeout-escalation harness):

1. Reachability, bootstrap, and application readiness are three DIFFERENT
   questions. Each is probed and reported separately so a failure can be
   attributed to the application, the QA harness, or the infrastructure.

2. `/_stcore/health` is NOT a proof of application health on Streamlit
   Community Cloud: the edge serves the same SPA shell (HTTP 200) for every
   path. We record what the endpoint actually returned and only treat a
   literal ``ok`` body as a genuine Streamlit health signal.

3. Readiness is a STATE MACHINE over the real Streamlit DOM, not a single
   ``get_by_text("Screener")`` wait. The app has distinguishable terminal
   states (tabs rendered / st.error / st.exception) and one non-terminal
   state (spinner = data pipeline still running). Reporting *which* state the
   app is in is the whole point; "did not become visible in N seconds" is not
   a diagnosis and is never fixed by raising N.

4. The cold data pipeline is expensive, so exactly ONE application session is
   established and every viewport and tab is exercised against that warm
   session.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import requests
from playwright.sync_api import sync_playwright

URL = os.getenv("UMIYA_PRODUCTION_URL", "https://paresh.streamlit.app/").rstrip("/") + "/"
HEALTH_URL = URL.rstrip("/") + "/_stcore/health"
OUT = Path(os.getenv("UMIYA_QA_OUT", "artifacts/production_qa"))

# Budget for the cold data pipeline. This is a REPORTING horizon, not a pass
# condition: exceeding it is recorded as an application-performance finding
# with the state the app was actually in, never silently retried at a larger N.
READY_BUDGET_S = int(os.getenv("UMIYA_READY_BUDGET_S", "420"))
POLL_S = 10
METRICS_ID = "umiya-startup-metrics"
# Commit this run intends to test. The workflow passes github.sha; the app
# publishes the revision it is actually serving. Without this the probe can
# connect before Streamlit has swapped builds and report a good commit red --
# which is exactly what happened to c151597, whose QA started two seconds
# after the push.
EXPECTED_SHA = (os.getenv("UMIYA_EXPECTED_SHA") or "").strip().lower()
DEPLOY_WAIT_S = int(os.getenv("UMIYA_DEPLOY_WAIT_S", "300"))

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

RUNTIME_TOKENS = (
    "Traceback", "KeyError:", "ImportError:", "IndexError:", "TypeError:",
    "ValueError:", "AttributeError:", "StreamlitAPIException",
)
# Streamlit Cloud wrapper states that mean "we never got to the app at all".
CLOUD_STATES = {
    "asleep": ("has gone to sleep", "get this app back up"),
    "cloud_error": ("Error running app", "Oh no.", "connection error"),
    "not_found": ("You do not have access", "404", "page not found"),
    "login": ("Sign in to continue", "Continue with Google", "Sign in with"),
}


def classify(msg: str, kind: str) -> dict:
    """Every failure carries an explicit attribution class."""
    return {"kind": kind, "detail": msg}


def http_probe() -> dict:
    """HTTP reachability using a cookie-holding session.

    Streamlit Cloud bootstraps an anonymous viewer session via a redirect
    handshake that MINTS a cookie. A client that discards cookies between
    redirects sees an infinite redirect loop and misreports the app as down,
    so a Session (persistent cookie jar) is mandatory here.
    """
    session = requests.Session()
    session.headers["User-Agent"] = (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
    )
    result: dict = {}
    for name, target in (("app", URL), ("health", HEALTH_URL)):
        started = time.perf_counter()
        try:
            r = session.get(target, timeout=45, allow_redirects=True)
            body = r.text[:200]
            result[name] = {
                "status": r.status_code,
                "elapsed_s": round(time.perf_counter() - started, 2),
                "final_url": r.url,
                "bytes": len(r.content),
                "redirects": len(r.history),
                # A real Streamlit health endpoint answers with the literal
                # body "ok". Anything else here is the Cloud SPA shell and
                # says nothing about whether the Python app is alive.
                "is_streamlit_health_ok": body.strip().lower().startswith("ok"),
                "looks_like_spa_shell": "<!doctype html" in body.lower(),
            }
        except Exception as exc:
            result[name] = {
                "error": f"{type(exc).__name__}: {exc}",
                "elapsed_s": round(time.perf_counter() - started, 2),
            }
    return result


def read_revision(page) -> str | None:
    """Revision the running app reports, from its startup telemetry."""
    for frame in page.frames:
        try:
            node = frame.locator(f"#{METRICS_ID}")
            if node.count() == 0:
                continue
            raw = node.first.text_content(timeout=5_000)
            if raw:
                return (json.loads(raw) or {}).get("revision")
        except Exception:
            continue
    return None


def app_frame(page):
    """Return the frame that actually hosts the Streamlit app.

    Streamlit Community Cloud serves a wrapper SPA and mounts the app inside a
    nested iframe. Querying only the top-level frame finds an empty body no
    matter how long you wait, which is exactly how a healthy app gets
    misreported as "never rendered".
    """
    for frame in page.frames:
        try:
            if frame.locator('[data-testid="stApp"]').count() > 0:
                return frame
        except Exception:
            continue
    # Fall back to the largest non-blank frame, then the main frame.
    for frame in page.frames:
        try:
            if frame != page.main_frame and frame.locator("body").inner_text(
                    timeout=2_000).strip():
                return frame
        except Exception:
            continue
    return page.main_frame


def read_state(page) -> dict:
    """Classify what the browser is ACTUALLY showing right now."""
    frame = app_frame(page)
    frames_info = [f.url[:120] for f in page.frames]
    try:
        body = frame.locator("body").inner_text(timeout=10_000)
    except Exception as exc:
        return {"state": "dom_unreadable", "detail": str(exc)[:200],
                "frames": frames_info, "body": ""}

    def count(sel: str) -> int:
        try:
            return frame.locator(sel).count()
        except Exception:
            return 0

    st_exception = count('[data-testid="stException"]')
    st_tabs = count('[data-testid="stTabs"]')
    st_spinner = count('[data-testid="stSpinner"]')
    st_app = count('[data-testid="stApp"]')

    info = {
        "body_len": len(body),
        "stApp": st_app, "stTabs": st_tabs,
        "stSpinner": st_spinner, "stException": st_exception,
        "n_frames": len(page.frames),
        "frames": frames_info,
        "body_head": body[:300].replace("\n", " | "),
    }

    for label, needles in CLOUD_STATES.items():
        if any(n.lower() in body.lower() for n in needles):
            return {"state": f"cloud_{label}", **info}

    if st_exception:
        return {"state": "app_exception", **info}
    if "Failed to initialize market data" in body:
        return {"state": "app_data_init_failed", **info}
    if st_tabs:
        return {"state": "ready", **info}
    if st_spinner or "Loading market data" in body:
        return {"state": "pipeline_running", **info}
    if st_app and len(body.strip()) == 0:
        return {"state": "app_shell_blank", **info}
    return {"state": "unknown", **info}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    failures: list[dict] = []
    report: dict = {"url": URL, "ready_budget_s": READY_BUDGET_S}

    report["http_probe"] = probe = http_probe()
    print("HTTP probe:", json.dumps(probe, indent=2), flush=True)

    app_probe = probe.get("app", {})
    if app_probe.get("status") != 200:
        failures.append(classify(
            f"App URL did not return 200 over HTTP: {app_probe}", "INFRASTRUCTURE"))

    ws_events: list[str] = []
    console_errors: list[str] = []
    page_errors: list[str] = []
    bad_responses: list[str] = []
    timeline: list[dict] = []

    with sync_playwright() as p:
        launch: dict = {"headless": True, "args": ["--no-sandbox"]}
        exe = os.getenv("UMIYA_CHROMIUM_PATH")
        if exe:
            launch["executable_path"] = exe
        browser = p.chromium.launch(**launch)
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()
        page.on("websocket", lambda ws: ws_events.append(f"open {ws.url[:160]}"))
        page.on("console", lambda m: console_errors.append(f"[{m.type}] {m.text[:250]}")
                if m.type == "error" else None)
        page.on("pageerror", lambda e: page_errors.append(str(e)[:250]))
        page.on("response", lambda r: bad_responses.append(f"{r.status} {r.url[:160]}")
                if r.status >= 500 else None)

        state = {"state": "not_started"}
        started = time.perf_counter()
        try:
            page.goto(URL, wait_until="domcontentloaded", timeout=120_000)
            report["goto_s"] = round(time.perf_counter() - started, 1)
            report["url_after_goto"] = page.url

            # Poll the readiness state machine. We stop as soon as the app
            # reaches ANY terminal state -- ready or broken -- instead of
            # blindly waiting out the clock on a single selector.
            deadline = time.perf_counter() + READY_BUDGET_S
            while time.perf_counter() < deadline:
                state = read_state(page)
                sample = {"t_s": round(time.perf_counter() - started, 1), **state}
                timeline.append(sample)
                print(json.dumps({k: v for k, v in sample.items() if k != "body"})[:500],
                      flush=True)
                if state["state"] in ("ready", "app_exception", "app_data_init_failed"):
                    break
                if state["state"].startswith("cloud_"):
                    break
                time.sleep(POLL_S)

            report["ready_state"] = state["state"]
            report["ready_after_s"] = round(time.perf_counter() - started, 1)

            # Deploy correspondence. If the app is still serving the previous
            # commit, this run's result says nothing about the commit that
            # triggered it, so wait for the swap and record what happened
            # rather than reporting the new commit red.
            if state["state"] == "ready" and EXPECTED_SHA:
                deadline_dep = time.perf_counter() + DEPLOY_WAIT_S
                served = read_revision(page)
                while (
                    served
                    and not EXPECTED_SHA.startswith(served.lower()[:7])
                    and time.perf_counter() < deadline_dep
                ):
                    print(json.dumps({
                        "waiting_for_deploy": EXPECTED_SHA[:7],
                        "currently_served": served[:7],
                        "t_s": round(time.perf_counter() - started, 1),
                    }), flush=True)
                    time.sleep(POLL_S)
                    page.reload(wait_until="domcontentloaded", timeout=120_000)
                    for _ in range(int(READY_BUDGET_S / POLL_S)):
                        if read_state(page)["state"] == "ready":
                            break
                        time.sleep(POLL_S)
                    served = read_revision(page)

                report["expected_revision"] = EXPECTED_SHA[:7]
                report["served_revision"] = (served or "unknown")[:7]
                if served is None:
                    report["deploy_correspondence"] = "unverifiable"
                elif EXPECTED_SHA.startswith(served.lower()[:7]):
                    report["deploy_correspondence"] = "match"
                else:
                    report["deploy_correspondence"] = "mismatch"
                    failures.append(classify(
                        f"Tested build {served[:7]} but this run was triggered by "
                        f"{EXPECTED_SHA[:7]}; Streamlit had not finished swapping "
                        f"builds within {DEPLOY_WAIT_S}s. This result does not "
                        f"describe the triggering commit.",
                        "INFRASTRUCTURE"))

            if state["state"] == "ready":
                pass
            elif state["state"] == "pipeline_running":
                failures.append(classify(
                    f"Application still executing its data pipeline after "
                    f"{READY_BUDGET_S}s (spinner state). Python is running and the "
                    f"websocket is up, so this is an application COLD-START "
                    f"PERFORMANCE defect, not a QA timeout to be raised.",
                    "APPLICATION"))
            elif state["state"] in ("app_exception", "app_data_init_failed"):
                failures.append(classify(
                    f"Application reached a failed terminal state "
                    f"'{state['state']}': {state.get('body_head', '')}", "APPLICATION"))
            elif state["state"].startswith("cloud_"):
                failures.append(classify(
                    f"Never reached the application; Streamlit Cloud wrapper state "
                    f"'{state['state']}': {state.get('body_head', '')}", "INFRASTRUCTURE"))
            else:
                failures.append(classify(
                    f"Unclassified readiness state '{state['state']}': "
                    f"{state.get('body_head', '')}", "QA"))

            # Only exercise the UI against a genuinely ready warm session.
            if state["state"] == "ready":
                report["viewports"] = {}
                for name, (w, h) in VIEWPORTS.items():
                    page.set_viewport_size({"width": w, "height": h})
                    page.wait_for_timeout(600)
                    vp: dict = {"tabs": {}}
                    frame = app_frame(page)
                    for tab in TABS:
                        try:
                            loc = frame.get_by_role("tab", name=tab, exact=True).first
                            if loc.count() == 0:
                                loc = frame.get_by_text(tab, exact=True).first
                            if not loc.is_visible():
                                vp["tabs"][tab] = "not_visible"
                                failures.append(classify(
                                    f"{name}: tab '{tab}' not visible", "APPLICATION"))
                                continue
                            loc.click(timeout=20_000)
                            page.wait_for_timeout(900)
                            body = frame.locator("body").inner_text(timeout=10_000)
                            hits = [t for t in RUNTIME_TOKENS if t in body]
                            if frame.locator('[data-testid="stException"]').count():
                                hits.append("stException")
                            if hits:
                                vp["tabs"][tab] = f"runtime_error:{hits}"
                                failures.append(classify(
                                    f"{name}/{tab}: runtime error tokens {hits}",
                                    "APPLICATION"))
                            else:
                                vp["tabs"][tab] = "ok"
                        except Exception as exc:
                            vp["tabs"][tab] = f"error:{type(exc).__name__}"
                            failures.append(classify(
                                f"{name}/{tab}: {type(exc).__name__}: {exc}", "APPLICATION"))
                    overflow = page.evaluate(
                        "document.documentElement.scrollWidth - window.innerWidth")
                    vp["h_overflow_px"] = overflow
                    if w <= 600 and overflow > 24:
                        failures.append(classify(
                            f"{name}: horizontal overflow {overflow}px", "APPLICATION"))
                    page.screenshot(path=str(OUT / f"{name}.png"))
                    report["viewports"][name] = vp
        except Exception as exc:
            failures.append(classify(
                f"Browser session error: {type(exc).__name__}: {exc}", "QA"))
        finally:
            try:
                (OUT / "final_dom.html").write_text(page.content(), encoding="utf-8")
                page.screenshot(path=str(OUT / "final_state.png"))
            except Exception:
                pass
            context.close()
            browser.close()

    report["websockets"] = ws_events
    report["websocket_established"] = any("_stcore/stream" in e for e in ws_events)
    report["console_errors"] = console_errors[:40]
    report["page_errors"] = page_errors[:40]
    report["server_errors_5xx"] = bad_responses[:40]
    report["timeline"] = timeline
    report["failures"] = failures
    report["failure_classes"] = sorted({f["kind"] for f in failures})

    (OUT / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("\n================ PRODUCTION QA VERDICT ================", flush=True)
    print(f"readiness state       : {report.get('ready_state')}", flush=True)
    if EXPECTED_SHA:
        print(f"deploy correspondence : {report.get('deploy_correspondence')} "
              f"(expected {report.get('expected_revision')}, "
              f"served {report.get('served_revision')})", flush=True)
    print(f"time to that state    : {report.get('ready_after_s')}s", flush=True)
    print(f"websocket established : {report['websocket_established']}", flush=True)
    print(f"page errors           : {len(page_errors)}", flush=True)
    print(f"console errors        : {len(console_errors)}", flush=True)
    for c in console_errors[:5]:
        print(f"    {c}", flush=True)
    if timeline:
        print(f"frames at last sample : {timeline[-1].get('frames')}", flush=True)
    print(f"5xx responses         : {len(bad_responses)}", flush=True)
    for f in failures:
        print(f"  [{f['kind']}] {f['detail']}", flush=True)
    if not failures:
        print("  no failures", flush=True)
    print("======================================================", flush=True)

    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
