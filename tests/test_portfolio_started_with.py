"""S193 A2 (23 Nov 2026): the Nifty 1000 Portfolio said "Started with ₹1,05,50,323" and a gain
of ₹0 beside "₹1 Cr put in": capital came from the equity's first point, which is today's value
until the first month is frozen. Capital is now the money put in."""
from pathlib import Path

from src.core.config import MODEL_BOOK_CAPITAL

SRC = Path(__file__).resolve().parents[1] / "src" / "ui" / "views" / "portfolio_page.py"


def test_capital_is_the_money_put_in_not_the_first_equity_point():
    text = SRC.read_text()
    assert "capital=float(MODEL_BOOK_CAPITAL)" in text
    assert 'capital=float(series.history["equity"].iloc[0])' not in text


def test_the_heading_names_the_same_money():
    assert MODEL_BOOK_CAPITAL == 10_000_000.0
    assert "₹1 Cr was put in" in SRC.read_text()


def test_the_index_line_never_names_a_date_after_the_prices():
    text = SRC.read_text()
    assert 'Nifty Total Market for {dshort(last)} not in yet' in text
    assert "min(pd.Timestamp(eq.index[-1]), pd.Timestamp(p.as_of))" in text
