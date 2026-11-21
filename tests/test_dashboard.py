"""The dashboard home page (owner, 7 Nov 2026): its address, and the "On this page" line.

The old Dashboard (dashboard_view.py) was unreachable from 20 Nov and was deleted on
21 Nov 2026; the page is src/ui/views/dashboard_home_view.py (tests/test_dashboard_home_view.py)."""
from __future__ import annotations

from pathlib import Path

from src.ui import page_kit as kit

APP = Path(__file__).resolve().parents[1] / "app.py"


def test_dashboard_is_home_and_the_screener_keeps_an_address():
    src = APP.read_text(encoding="utf-8")
    assert 'st.Page(_page_dashboard, title="Dashboard", default=True)' in src
    # /home and /dashboard are redirects to it: the default page is served at "/"
    # only, and /home showed "Page not found" until 8 Nov.
    assert '"home": "Dashboard"' in src and '"dashboard": "Dashboard"' in src
    assert 'st.Page(_page_screener, title="Screener", url_path="screener")' in src


def test_the_on_this_page_line_links_each_section():
    """Owner, 8 Nov 2026: the Breadth page's "On this page" links (now kit.page_nav, on every page)."""
    out = kit.page_nav_html([("d-breadth", "Are most stocks taking part?"), ("s-db_risk", "Book at risk")])
    assert out.startswith('<nav class="qp-nav" aria-label="On this page">')
    assert '<a href="#d-breadth">Are most stocks taking part?</a>' in out and 'href="#s-db_risk"' in out
    assert kit.page_nav_html([]) == ""


