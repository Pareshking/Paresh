"""/stock?stock=X lands on the stock page without "Page not found" (S193 item K, 23 Nov 2026).

/stock was not an address the app declared, so Streamlit showed its "Page not found" dialog
before the ?stock rule sent the reader to the Screener. It is a redirect now, like /breadth.
"""
from pathlib import Path

APP = (Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")


def test_stock_is_a_declared_redirect_to_the_screener():
    assert '"stock": "Stock link"' in APP      # a redirect, not a page in the menu
    assert '"stock": "Screener"' in APP        # and where it lands


def test_the_redirect_keeps_the_query_string():
    # _moved_page passes st.query_params on, so ?stock= (and ?sys=) reach the Screener.
    assert "query_params=st.query_params.to_dict()" in APP
