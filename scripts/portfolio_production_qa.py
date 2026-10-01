"""Focused production visual QA for the Portfolio page.

Runs after the general V1 production QA against the same deployed Streamlit app.
Captures the Portfolio page at the two viewports that matter most for the UX
review and records simple, deterministic contract checks:
- page renders without runtime exception
- canonical Portfolio history does not expose pre-inception 2022 records
- grouped Performance/Activity history navigation is present
- the canonical Current Book table is present
- mobile has no material horizontal overflow

This is intentionally a visual-evidence supplement, not a second accounting engine.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
from production_qa import URL, EXPECTED_SHA, app_frame, read_revision, read_state  # noqa: E402
from _streamlit_nav import _close_custom_popover, open_page  # noqa: E402

OUT = Path(os.getenv("UMIYA_QA_OUT", "artifacts/production_qa"))
OUT.mkdir(parents=True, exist_ok=True)

VIEWPORTS = {
    "portfolio_desktop_1280x800": (1280, 800),
    "portfolio_mobile_390x844": (390, 844),
}
READY_TIMEOUT_S = 420
POLL_S = 5


def wait_ready(page):
    deadline = time.perf_counter() + READY_TIMEOUT_S
    last = None
    while time.perf_counter() < deadline:
        frame = app_frame(page)
        state = read_state(page)
        last = state
        if state.get("state") == "ready":
            return frame, state
        if state.get("state") in {"app_exception", "app_data_init_failed"}:
            return frame, state
        time.sleep(POLL_S)
    return app_frame(page), last or {"state": "timeout"}


def main() -> int:
    report = {
        "url": URL,
        "expected_revision": EXPECTED_SHA[:7] if EXPECTED_SHA else "",
        "viewports": {},
        "failures": [],
    }

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        page = context.new_page()
        try:
            page.goto(URL, wait_until="domcontentloaded", timeout=120_000)
            frame, state = wait_ready(page)
            report["initial_state"] = state.get("state")
            if state.get("state") != "ready":
                report["failures"].append(
                    f"Portfolio visual QA could not reach ready state: {state.get('state')}"
                )
            else:
                served, reason = read_revision(page, wait_s=30)
                report["served_revision"] = (served or "unknown")[:7]
                report["revision_reason"] = reason
                if EXPECTED_SHA and served and not EXPECTED_SHA.startswith(
                    served.lower()[:7]
                ):
                    report["failures"].append(
                        f"Unexpected served revision {served[:7]} for {EXPECTED_SHA[:7]}"
                    )

                for name, (width, height) in VIEWPORTS.items():
                    page.set_viewport_size({"width": width, "height": height})
                    page.wait_for_timeout(500)
                    frame = app_frame(page)
                    try:
                        how = open_page(frame, "Portfolio", page)
                        # Navigation is a means to reach the page, not part of the page visual evidence.
                        # Close the hamburger after routing so mobile screenshots validate the Portfolio content itself.
                        _close_custom_popover(frame)
                        page.wait_for_timeout(300)
                    except Exception as exc:
                        report["failures"].append(
                            f"{name}: could not open Portfolio: "
                            f"{type(exc).__name__}: {exc}"
                        )
                        continue

                    deadline = time.perf_counter() + 180
                    while time.perf_counter() < deadline:
                        frame = app_frame(page)
                        body = frame.locator("body").inner_text(timeout=15_000)
                        body_folded = body.casefold()
                        spinner = frame.locator('[data-testid="stSpinner"]').count()
                        exception = frame.locator('[data-testid="stException"]').count()
                        if exception:
                            break
                        if not spinner and (
                            "current book" in body_folded or "portfolio value" in body_folded
                        ):
                            break
                        time.sleep(3)

                    frame = app_frame(page)
                    body = frame.locator("body").inner_text(timeout=15_000)
                    body_folded = body.casefold()
                    exception = frame.locator('[data-testid="stException"]').count()
                    overflow = page.evaluate(
                        "document.documentElement.scrollWidth - window.innerWidth"
                    )

                    checks = {
                        "opened_via": how,
                        "current_book_present": "current book" in body_folded,
                        "portfolio_value_present": "portfolio value" in body_folded,
                        "performance_group_present": "performance" in body_folded,
                        "activity_group_present": "activity" in body_folded,
                        "pre_inception_2022_visible": "2022" in body,
                        "runtime_exception": bool(exception),
                        "horizontal_overflow_px": overflow,
                        "body_chars": len(body),
                    }
                    report["viewports"][name] = checks

                    if not checks["current_book_present"]:
                        report["failures"].append(
                            f"{name}: Current Book is not visible"
                        )
                    if not checks["portfolio_value_present"]:
                        report["failures"].append(
                            f"{name}: Portfolio value KPI is not visible"
                        )
                    if not checks["performance_group_present"] or not checks[
                        "activity_group_present"
                    ]:
                        report["failures"].append(
                            f"{name}: grouped Performance/Activity navigation missing"
                        )
                    if checks["pre_inception_2022_visible"]:
                        report["failures"].append(
                            f"{name}: visible Portfolio content contains 2022"
                        )
                    if checks["runtime_exception"]:
                        report["failures"].append(
                            f"{name}: Streamlit runtime exception visible"
                        )
                    if width <= 600 and overflow > 24:
                        report["failures"].append(
                            f"{name}: horizontal overflow {overflow}px"
                        )

                    # Exercise the two history views that contain live MTD/calendar evidence.
                    try:
                        equity_control = frame.get_by_text("Equity", exact=True)
                        equity_control.click(timeout=10_000)
                        page.wait_for_timeout(700)
                        equity_body = app_frame(page).locator("body").inner_text(timeout=15_000)
                        equity_folded = equity_body.casefold()
                        equity_checks = {
                            "equity_mtd_strategy_present": "mtd · strategy" in equity_folded,
                            "equity_mtd_benchmark_present": "mtd · nifty 500" in equity_folded,
                            "equity_mtd_alpha_present": "mtd alpha" in equity_folded,
                            "cumulative_42pct_visible": "+42.4%" in equity_body,
                        }
                        checks.update(equity_checks)
                        if not equity_checks["equity_mtd_strategy_present"] or not equity_checks["equity_mtd_benchmark_present"] or not equity_checks["equity_mtd_alpha_present"]:
                            report["failures"].append(f"{name}: Equity view MTD summary is incomplete")
                        if equity_checks["cumulative_42pct_visible"]:
                            report["failures"].append(f"{name}: Equity view still exposes the old cumulative +42.4% headline")
                        page.screenshot(path=str(OUT / f"{name}_equity.png"), full_page=True)

                        frame = app_frame(page)
                        frame.get_by_text("Monthly", exact=True).click(timeout=10_000)
                        page.wait_for_timeout(700)
                        monthly_body = app_frame(page).locator("body").inner_text(timeout=15_000)
                        monthly_folded = monthly_body.casefold()
                        monthly_checks = {
                            "calendar_grid_present": "calendar grid" in monthly_folded,
                            "strategy_present": "strategy" in monthly_folded,
                            "nifty_500_present": "nifty 500" in monthly_folded,
                            "alpha_present": "alpha" in monthly_folded,
                            "mtd_present": "mtd" in monthly_folded,
                        }
                        checks.update(monthly_checks)
                        if not all(monthly_checks.values()):
                            report["failures"].append(f"{name}: Calendar grid MTD evidence is incomplete")
                        page.screenshot(path=str(OUT / f"{name}_monthly.png"), full_page=True)
                    except Exception as exc:
                        report["failures"].append(
                            f"{name}: could not exercise Equity/Monthly history views: "
                            f"{type(exc).__name__}: {exc}"
                        )

                    page.screenshot(
                        path=str(OUT / f"{name}.png"),
                        full_page=True,
                    )

        except Exception as exc:
            report["failures"].append(
                f"Portfolio visual QA browser error: {type(exc).__name__}: {exc}"
            )
        finally:
            try:
                (OUT / "portfolio_final_dom.html").write_text(
                    page.content(), encoding="utf-8"
                )
            except Exception:
                pass
            context.close()
            browser.close()

    (OUT / "portfolio_visual_qa.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, indent=2), flush=True)
    return 1 if report["failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
