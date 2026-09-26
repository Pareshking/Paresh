"""Headless Streamlit smoke test: the landing page must show the ranking.

The old check asserted only that no exception or error element appeared, then
printed the number of st.tabs and st.dataframe elements -- both 0, because the
app uses neither (navigation is page links and segmented controls, tables are
HTML). A page that rendered its header and nothing else passed it.

This one asserts what a visitor needs to see: the navigation, the ranking in
both layouts, and the export. Run from the repo root:

    python scripts/headless_smoke.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / "app.py")
MIN_NAV_LINKS = 10    # 11 pages today
MIN_CARDS = 20        # the card grid shows 48
MIN_TABLE_ROWS = 500  # the table shows the full 750-name universe


def _fail(msg: str) -> None:
    raise SystemExit(f"HEADLESS_STREAMLIT_SMOKE=FAIL: {msg}")


def _check_clean(at: AppTest, stage: str) -> None:
    for exc in at.exception:
        print("STREAMLIT_EXCEPTION:", exc.value)
    for err in at.error:
        print("STREAMLIT_ERROR:", err.value)
    if at.exception or at.error:
        _fail(f"{stage}: exception or error element rendered")


def _startup_facts(at: AppTest) -> dict:
    for m in at.markdown:
        if "umiya-startup-metrics" in m.value:
            found = re.search(r">(\{.*\})<", m.value, re.S)
            if found:
                return json.loads(found.group(1)).get("facts", {})
    _fail("startup metrics block missing")
    return {}


def _elements(at: AppTest, kind: str) -> list:
    return [e for e in at.main if getattr(e, "type", "") == kind]


def main() -> int:
    at = AppTest.from_file(APP, default_timeout=900)
    at.run(timeout=900)
    _check_clean(at, "first load")

    facts = _startup_facts(at)
    if facts.get("script_outcome") != "ok":
        _fail(f"script_outcome={facts.get('script_outcome')!r}")

    nav = _elements(at, "page_link")
    print(f"Navigation links: {len(nav)}")
    if len(nav) < MIN_NAV_LINKS:
        _fail(f"{len(nav)} navigation links, expected at least {MIN_NAV_LINKS}")

    grids = [m.value for m in at.markdown if 'class="sq-grid"' in m.value]
    cards = grids[0].count('class="sq-sym"') if grids else 0
    print(f"Ranking cards: {cards}")
    if cards < MIN_CARDS:
        _fail(f"{cards} ranking cards, expected at least {MIN_CARDS}")

    downloads = [b.label for b in at.get("download_button")]
    if not any(label.startswith("Download Rankings CSV") for label in downloads):
        _fail(f"rankings export missing (download buttons: {downloads})")

    at.segmented_control(key="rank_view_mode").set_value("Table").run(timeout=900)
    _check_clean(at, "table view")
    frames = _elements(at, "iframe")
    rows = max((f.proto.srcdoc.count("<tr") - 1 for f in frames), default=0)
    print(f"Ranking table rows: {rows}")
    if rows < MIN_TABLE_ROWS:
        _fail(f"{rows} ranking table rows, expected at least {MIN_TABLE_ROWS}")

    print("HEADLESS_STREAMLIT_SMOKE=PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
