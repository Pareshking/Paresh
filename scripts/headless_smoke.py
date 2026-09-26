"""Headless Streamlit smoke test: the landing page must show the ranking.

The old check asserted only that no exception or error element appeared, then
printed the number of st.tabs and st.dataframe elements -- both 0, because the
app uses neither (navigation is page links and segmented controls, tables are
HTML). A page that rendered its header and nothing else passed it.

This one asserts what a visitor needs to see: the navigation, the ranking in
both column sets, and the export. Run from the repo root:

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


def _open_stock(symbol: str, page_hash: str | None) -> tuple[AppTest, list[dict]]:
    """Run the app as a ?stock= link would open it; record query-param writes."""
    from streamlit.runtime.state import query_params as qp_mod

    sent: list[dict] = []
    original = qp_mod.QueryParams._send_query_param_msg

    def _spy(self):
        sent.append(dict(self._query_params))
        return original(self)

    qp_mod.QueryParams._send_query_param_msg = _spy
    try:
        at = AppTest.from_file(APP, default_timeout=900)
        at.query_params["stock"] = symbol
        if page_hash:
            at._page_hash = page_hash
        at.run(timeout=900)
    finally:
        qp_mod.QueryParams._send_query_param_msg = original
    return at, sent


def _check_stock_links(at: AppTest) -> None:
    """A ?stock= link opens the stock page from any page, and says so upward.

    On Streamlit Cloud the app runs in a frame, so a link navigates only that
    frame; the address bar follows only when the app writes st.query_params
    (Streamlit forwards the write to the host page). Checked separately: a
    card link on the Screener must write it (a redirect's own write would
    otherwise hide a missing one), and a link from Sectors must land on the
    stock page.
    """
    symbol = "RELIANCE"
    direct, sent = _open_stock(symbol, None)
    _check_clean(direct, "stock link on the Screener")
    print(f"Stock link on the Screener: address-bar writes={sent}")
    if {"stock": symbol} not in sent:
        _fail("the stock page never wrote ?stock= back, so the address bar cannot follow")

    sectors = [e for e in _elements(at, "page_link") if e.proto.label == "Sectors"]
    if not sectors:
        _fail("no Sectors link to start the stock-link check from")
    routed, _ = _open_stock(symbol, sectors[0].proto.page_script_hash)
    _check_clean(routed, "stock link from Sectors")
    reached = "← Back to screener" in [b.label for b in routed.button]
    print(f"Stock link from Sectors: reached the stock page={reached}")
    if not reached:
        _fail("a ?stock= link clicked on Sectors did not open the stock page")


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

    # One table now, for desktop and phone: every row of the universe is in
    # it, so column sorting sees all of them.
    frames = _elements(at, "iframe")
    rows = max((f.proto.srcdoc.count("<tr data-stock=") for f in frames), default=0)
    print(f"Ranking table rows: {rows}")
    if rows < MIN_TABLE_ROWS:
        _fail(f"{rows} ranking table rows, expected at least {MIN_TABLE_ROWS}")

    downloads = [b.label for b in at.get("download_button")]
    if not any(label.startswith("Export CSV") for label in downloads):
        _fail(f"rankings export missing (download buttons: {downloads})")

    # The research view is still one click away and still draws every row.
    at.segmented_control(key="rank_density_mode").set_value("Full Quant (35)").run(timeout=900)
    _check_clean(at, "Full Quant table")
    frames = _elements(at, "iframe")
    wide = max((f.proto.srcdoc.count('<tr class="screener-row"') for f in frames), default=0)
    print(f"Full Quant table rows: {wide}")
    if wide < MIN_TABLE_ROWS:
        _fail(f"{wide} Full Quant rows, expected at least {MIN_TABLE_ROWS}")

    _check_stock_links(at)

    print("HEADLESS_STREAMLIT_SMOKE=PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
