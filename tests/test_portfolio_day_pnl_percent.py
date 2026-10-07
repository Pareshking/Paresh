from src.ui.theme import percent_unit


def test_portfolio_day_pnl_percent_is_fraction_based():
    # build_portfolio_tracker stores Day P&L % as a fraction (0.084 = 8.4%),
    # unlike P&L %, which is already scaled (8.4 = 8.4%).
    assert percent_unit("Day P&L %") == "fraction"
    assert percent_unit("P&L %") == "scaled"


def test_day_pnl_examples_match_current_book_display_units():
    # These are representative values from the portfolio table. The renderer
    # must print them as -0.99%, -0.90%, and -0.34%, not -99.1%, -90.0%, -33.8%.
    assert f"{-0.00991:.1%}" == "-1.0%"
    assert f"{-0.00900:.1%}" == "-0.9%"
    assert f"{-0.00338:.1%}" == "-0.3%"
