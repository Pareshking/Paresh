"""Prices in whole rupees, returns to one decimal, on the page only (S173; owner, 22 Nov 2026: "price etc, Moving
averages etc should be in round numbers, return only with Max one decimal values like 11.1% not 11.11%").
The rendered pages are checked by scripts/number_format_audit.mjs in CI; these pin the formatter and that no
order, export or stored value goes through it."""
from __future__ import annotations

import inspect

from src.ui import formats as fmt


def test_a_price_is_whole_rupees_with_indian_grouping():
    assert fmt.price(2905.9) == "₹2,906"
    assert fmt.price(1234567.4) == "₹12,34,567"
    assert fmt.price(100) == "₹100"


def test_a_price_below_a_hundred_is_whole_rupees_too():
    # Owner, 22 Nov 2026: whole rupees for every price and moving average, "including below ₹100".
    assert fmt.price(70.05) == "₹70" and fmt.price(99.6) == "₹100" and fmt.price(7.4) == "₹7"


def test_missing_and_negative_prices():
    assert fmt.price(None) == fmt.DASH and fmt.price(float("nan")) == fmt.DASH
    assert fmt.price(-954.4) == "−₹954"


def test_returns_carry_one_decimal_by_default():
    assert fmt.pct(0.1111) == "+11.1%" and fmt.pts(0.0833) == "+8.3 pts"


def test_the_order_basket_and_exports_never_use_a_display_formatter():
    # The Kite basket sends market orders (price 0) with quantities from exact prices; the CSV exports write the
    # frames as they are. A display formatter in any of them would put rounded figures into an order or a file.
    from src.engine import backtest_export
    from src.ui.views import actions_page, ranking_view
    for fn in (actions_page.basket, ranking_view._rankings_csv, backtest_export.export_zip):
        src = inspect.getsource(fn)
        assert not any(call in src for call in ("price(", "inr(", "pct(", "pts(", "signed(")), fn.__name__
    rows = actions_page.basket.__doc__
    assert rows and "Kite basket" in rows


def test_the_rankings_export_keeps_prices_to_the_paisa():
    # The page shows ₹70 and ₹1,235 (owner, 22 Nov 2026); the CSV keeps two decimals (owner, 28 Nov 2026, S236
    # F19: "With your recommendation"), which is every price NSE quotes: 1110.4000244140625 was a float's noise.
    import pandas as pd

    from src.ui.views import ranking_view

    out = ranking_view._rankings_csv("t", pd.DataFrame({"Symbol": ["A", "B"], "CMP": [70.05, 1110.4000244140625]})).decode()
    assert "70.05" in out and "1110.4\n" in out
    assert fmt.price(70.05) == "₹70" and fmt.price(1234.567) == "₹1,235"


def test_dates_read_day_month_year():
    import pandas as pd

    assert fmt.date("2026-11-13") == "13 Nov 2026" and fmt.date(pd.Timestamp("2026-11-20"), short=True) == "20 Nov"
    assert fmt.date("Nifty 50") == "Nifty 50" and fmt.date("148.5") == "148.5"
