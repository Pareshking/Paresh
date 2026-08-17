import numpy as np
import pandas as pd

from src.engine.momentum import clean_holidays


def test_holiday_cleanup_never_empties_sparse_price_history():
    index = pd.date_range("2026-01-01", periods=3, freq="D")
    prices = pd.DataFrame(
        np.nan,
        index=index,
        columns=["AAA", "BBB", "CCC", "DDD", "EEE"],
    )
    prices.iloc[-1, 0] = 100.0

    cleaned = clean_holidays(prices)

    assert not cleaned.empty
    assert cleaned.index.equals(prices.index)
