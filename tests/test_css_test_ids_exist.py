"""Every Streamlit test id our CSS names still exists in the installed Streamlit (26 Nov 2026).

Streamlit 1.65 renamed st.pills' and st.segmented_control's containers (`stPills`, `stSegmentedControl` ->
`stButtonGroup`), and ~45 lines of page.css went on matching nothing for weeks, unnoticed (owner, 26 Nov
2026: "No pill required": removed). A rule naming an id the frontend no longer emits fails here instead.
"""

import re
from pathlib import Path

import pytest
import streamlit

CSS = Path(__file__).resolve().parents[1] / "src" / "ui" / "page.css"
BUNDLE = Path(streamlit.__file__).parent / "static"


def _bundle_text() -> str:
    return "\n".join(p.read_text(encoding="utf-8", errors="ignore") for p in BUNDLE.rglob("*.js"))


def test_every_test_id_in_page_css_is_one_streamlit_emits():
    if not BUNDLE.is_dir():
        pytest.skip("Streamlit's frontend bundle is not installed")
    ids = sorted(set(re.findall(r'data-testid="([A-Za-z]+)"', CSS.read_text(encoding="utf-8"))))
    assert ids, "page.css names no test ids: the pattern is wrong"
    text = _bundle_text()
    dead = [i for i in ids if not re.search(rf"[`\"']{i}[`\"']", text)]
    assert not dead, f"page.css styles test ids Streamlit {streamlit.__version__} no longer emits: {dead}"
