"""The Market page lives at /market; /breadth, its address until 21 Nov 2026, redirects there.

Owner, 21 Nov 2026: "change the address from /breadth to /market with a redirect".
Checked in a browser the same day: /breadth -> /market, and /breadth?system=nano ->
/market?system=nano. This pins the source so a later edit cannot drop either half.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")


def test_market_page_is_served_at_market():
    assert 'st.Page(_page_market, title="Market", url_path="market")' in APP
    assert 'url_path="breadth"' not in APP


def test_old_address_redirects_to_market_with_its_query_string():
    assert '"breadth": "Breadth link"' in APP          # a redirect, not a page in the menu
    assert '"breadth": "Market"' in APP                # and where it lands
    assert "query_params=st.query_params.to_dict()" in APP


def test_no_link_or_probe_still_points_at_the_old_address():
    for rel in ("src/ui/views/market_questions_view.py", "src/ui/views/dashboard_home_view.py",
                "scripts/_streamlit_nav.py", ".github/workflows/v1-full-validation.yml"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert 'page_href("breadth")' not in text and "8501/breadth" not in text, rel
        assert '"Market": "breadth"' not in text, rel
