import numpy as np
import pandas as pd

from src.engine.momentum import clean_holidays

def test_market_holiday_is_removed_but_security_gap_is_preserved():
    idx = pd.bdate_range("2026-01-05", periods=6)
    prices = pd.DataFrame(
        {
            "A": [100, np.nan, 102, 103, 104, 105],
            "B": [100, np.nan, 102, 103, 104, 105],
            "C": [100, np.nan, 102, 103, 104, 105],
            "D": [100, np.nan, 102, 103, 104, 105],
            "E": [100, 101, 102, 103, 104, 105],
        },
        index=idx,
    )

    cleaned = clean_holidays(prices)
    assert idx[1] not in cleaned.index

    prices2 = prices.drop(index=idx[1]).copy()
    prices2.loc[idx[2], "A"] = np.nan
    cleaned2 = clean_holidays(prices2)
    assert pd.isna(cleaned2.loc[idx[2], "A"])

def test_security_gap_does_not_create_zero_or_bridged_return():
    idx = pd.bdate_range("2026-02-02", periods=4)
    prices = pd.DataFrame({"A": [100.0, 105.0, np.nan, 115.0]}, index=idx)
    cleaned = clean_holidays(prices)
    log_returns = np.log(cleaned / cleaned.shift(1))
    assert pd.isna(log_returns.loc[idx[2], "A"])
    # The observation after a gap must not be treated as a return from
    # the stale pre-gap price. It must remain undefined until a valid
    # prior observation exists.
    assert pd.isna(log_returns.loc[idx[3], "A"])
