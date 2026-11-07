"""House style for numbers (pre-launch audit F5/F6; owner 7 Nov 2026: lakh/crore)."""
from src.ui.formats import MINUS, indian_group, inr, pct, signed


def test_indian_grouping():
    assert indian_group(942) == "942"
    assert indian_group(2340) == "2,340"
    assert indian_group(126433) == "1,26,433"
    assert indian_group(2827942) == "28,27,942"
    assert indian_group(123456789) == "12,34,56,789"


def test_rupees_put_the_sign_before_the_symbol():
    assert inr(2827942) == "₹28,27,942"
    assert inr(-954) == f"{MINUS}₹954"
    assert inr(2340, 2) == "₹2,340.00"
    assert inr(553, plus=True) == "+₹553"
    assert inr(None) == "—" and inr(float("nan")) == "—"


def test_percentages_round_then_sign_with_a_true_minus():
    assert pct(0.0231) == "+2.3%"
    assert pct(-0.019) == f"{MINUS}1.9%"
    assert pct(-0.0004) == "0.0%"
    assert pct(14.5, fraction=False) == "+14.5%"
    assert signed(-0.04) == "0.0"
