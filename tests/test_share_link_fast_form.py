"""The Share button gives the link that skips Streamlit Cloud's wrapper (20 Nov 2026).

Measured on a fresh browser: the wrapper (/?stock=X) took 10.3 s to a ready
home page, the app's own mount (/~/+/) 3.1-3.5 s.
"""
from pathlib import Path

from src.ui.views.stock_view import _share_url

ROOT = Path(__file__).resolve().parents[1]


def test_cloud_link_uses_the_mount():
    assert _share_url("WELCORP", "https://paresh.streamlit.app/~/+/screener?stock=WELCORP") == \
        "https://paresh.streamlit.app/~/+/screener?stock=WELCORP"


def test_cloud_link_without_mount_in_address_still_gets_it():
    assert _share_url("M&M", "https://paresh.streamlit.app/sectors") == \
        "https://paresh.streamlit.app/~/+/screener?stock=M%26M"


def test_local_link_has_no_mount():
    assert _share_url("TCS", "http://localhost:8501/screener") == "http://localhost:8501/screener?stock=TCS"


def test_unknown_address_gives_relative_link():
    assert _share_url("TCS", "") == "/screener?stock=TCS"


def test_production_qa_opens_the_share_form_and_fails_without_it():
    src = (ROOT / "scripts" / "production_qa.py").read_text(encoding="utf-8")
    assert '"mounted_screener": f"{URL}~/+/screener?stock={DEEP_LINK_SYMBOL}"' in src
    assert 'get("mounted_screener", {})' in src
