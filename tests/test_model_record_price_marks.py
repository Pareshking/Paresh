"""Canonical live-book marks use the same price basis as record_run()."""
import numpy as np
import pandas as pd

from src.engine.model_record import _attach_live_price_marks


def test_live_book_exposes_fill_and_previous_close_prices_from_canonical_frame():
    dates = pd.to_datetime(["2026-09-30", "2026-10-01"])
    prices = pd.DataFrame(
        {"AAA": [10.0, 11.0], "BBB": [20.0, np.nan]},
        index=dates,
    )
    book = pd.DataFrame({
        "Symbol": ["AAA", "BBB"],
        "Price Now": [11.0, 20.0],
    })

    marked = _attach_live_price_marks(
        book,
        prices,
        {"fill_date": pd.Timestamp("2026-10-01"), "as_of": pd.Timestamp("2026-10-01")},
    ).set_index("Symbol")

    assert marked.loc["AAA", "Last Fill Price"] == 11.0
    assert marked.loc["BBB", "Last Fill Price"] == 20.0
    assert marked.loc["AAA", "Previous Price"] == 10.0
    assert marked.loc["BBB", "Previous Price"] == 20.0
    assert marked.loc["AAA", "Last Fill Date"] == pd.Timestamp("2026-10-01")
    assert marked.loc["AAA", "Previous Price Date"] == pd.Timestamp("2026-09-30")
    assert marked.loc["AAA", "Price As Of"] == pd.Timestamp("2026-10-01")
