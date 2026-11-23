"""S193 item K: links (owner, 23 Nov 2026: "Approved"; docs/archive/S193_ITEM_K_2026-11-23.md).

F2: Sectors linked to `dashboard#s-size`. /dashboard is a redirect, which dropped the `#` and put a step in
the history, so Back looped. A link built with `page_href` names a page, never a redirect. The section is
drawn after the browser has tried the `#`; the chart kit scrolls the host to it once it exists.
The crawler (scripts/link_crawl.mjs) runs in CI and fails on a dead link, a lost ?sys=, a missing section
or a Back that does not return.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")


def _pages_and_redirects() -> tuple[set[str], set[str]]:
    pages = set(re.findall(r'st\.Page\(_page_\w+, title="[^"]+", url_path="([^"]+)"\)', APP))
    moved = next(n for n in ast.walk(ast.parse(APP)) if isinstance(n, ast.Assign)
                 and any(getattr(t, "id", "") == "_MOVED" for t in n.targets))
    return pages, {k.value for k in moved.value.keys}


def test_page_href_never_names_a_redirect():
    pages, moved = _pages_and_redirects()
    assert {"actions", "market", "sectors"} <= pages and {"dashboard", "home", "breadth"} <= moved
    used = set()
    for f in [ROOT / "app.py", *(ROOT / "src").rglob("*.py")]:
        used |= {(f.name, m) for m in re.findall(r'page_href\("([^"]*)"\)', f.read_text(encoding="utf-8"))}
    assert used, "the guard lost its target"
    bad = {(f, p) for f, p in used if p.split("?")[0] in moved or (p not in pages and p != "./")}
    assert not bad, f"page_href with a redirect or an unknown page (the Dashboard is './'): {sorted(bad)}"


def test_sectors_links_to_the_dashboards_size_section_directly():
    src = (ROOT / "src" / "ui" / "views" / "sector_view.py").read_text(encoding="utf-8")
    assert 'page_href("./")}#s-size' in src and 'page_href("dashboard")' not in src


def test_the_kit_scrolls_to_a_section_drawn_after_load():
    js = (ROOT / "static" / "dash_charts.js").read_text(encoding="utf-8")
    assert "host.location.hash" in js and "scrollIntoView" in js and "__dcHash" in js


def test_the_crawler_runs_in_ci_after_the_layout_step():
    wf = (ROOT / ".github" / "workflows" / "v1-full-validation.yml").read_text(encoding="utf-8")
    assert (ROOT / "scripts" / "link_crawl.mjs").exists()
    assert wf.index("scripts/link_crawl.mjs") > wf.index("chart_hover_audit.mjs")
