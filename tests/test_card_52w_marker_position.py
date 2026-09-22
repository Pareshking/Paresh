import pandas as pd

from src.ui.views.ranking_view import _attach_52w_range


def test_20_percent_from_52w_high_marker_is_80_percent_of_displayed_range():
    view = pd.DataFrame(
        [{"Symbol": "CASTROLIND", "52W High": 204.0, "CMP": 194.0}]
    )
    low_prices = pd.DataFrame(
        {"CASTROLIND": [174.0, 194.0, 204.0]}
    )

    out = _attach_52w_range(view, high_prices=None, low_prices=low_prices)

    assert out.at[0, "_52W Low"] == 174.0
    assert out.at[0, "_52W High"] == 204.0
    assert out.at[0, "_52W Position"] == (194.0 - 174.0) / (204.0 - 174.0) * 100.0
    assert out.at[0, "_52W 20% Marker"] == 80.0


def test_marker_stays_at_80_percent_for_a_wide_price_range():
    view = pd.DataFrame(
        [{"Symbol": "PWL", "52W High": 155.0, "CMP": 135.0}]
    )
    low_prices = pd.DataFrame(
        {"PWL": [80.0, 112.0, 135.0, 155.0]}
    )

    out = _attach_52w_range(view, high_prices=None, low_prices=low_prices)

    assert out.at[0, "_52W 20% Marker"] == 80.0
