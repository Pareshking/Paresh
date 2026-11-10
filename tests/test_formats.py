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


def test_no_view_prints_a_negative_zero_or_an_ascii_hyphen():
    """The house rule, held where it is actually used (duplicate audit,
    10 Nov 2026).

    src/ui/formats.py says a value is rounded before it is signed, so nothing
    reads "−0.0%", and that a minus is U+2212. Eight places formatted percents
    their own way; three signed the UNROUNDED value, so −0.04% printed
    "−0.0%", and the stock page printed an ASCII hyphen. They go through
    formats now, and these are the two properties that matter.
    """
    from src.ui import formats as fmt
    from src.ui import screener_table
    from src.ui.views import qualified_view, sector_view, stock_view

    tiny = -0.0004          # −0.04% as a fraction: rounds to zero
    assert fmt.pct(tiny) == "0.0%"
    assert qualified_view._pct(tiny) == "0.0%"
    assert sector_view._pct(tiny) == "0.0%"
    assert screener_table._signed(tiny * 100) == "0.0"

    # The stock page takes percent units, not a fraction.
    for v in (-0.04, -12.4, 0.0):
        out = stock_view._pct(v)
        assert "-" not in out, f"ASCII hyphen in {out!r}"
    assert stock_view._pct(-0.04) == "0.0%"
    assert stock_view._pct(-12.4) == "−12.4%"
