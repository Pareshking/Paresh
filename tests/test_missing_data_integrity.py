import numpy as np
import pandas as pd

from src.engine.momentum import clean_holidays
from src.loaders.price_loader import _clean_price_df

def test_security_specific_nan_is_not_forward_filled():
    idx = pd.bdate_range("2026-01-05", periods=4)
    raw = pd.DataFrame({"A": [100.0, np.nan, 110.0, 111.0]}, index=idx)
    cleaned = _clean_price_df(raw)
    assert pd.isna(cleaned.loc[idx[1], "A"])
    assert cleaned.loc[idx[2], "A"] == 110.0

def test_security_specific_nan_does_not_create_zero_return():
    idx = pd.bdate_range("2026-01-05", periods=4)
    raw = pd.DataFrame({"A": [100.0, np.nan, 110.0, 111.0]}, index=idx)
    returns = _clean_price_df(raw)["A"].pct_change(fill_method=None)
    assert pd.isna(returns.iloc[1])
    assert not np.isclose(returns.iloc[2], 0.0)

def test_exchange_wide_missing_date_is_removed():
    idx = pd.bdate_range("2026-01-05", periods=4)
    raw = pd.DataFrame(
        {f"S{i}": [100.0, np.nan, 102.0, 103.0] for i in range(10)},
        index=idx,
    )
    cleaned = clean_holidays(raw)
    assert idx[1] not in cleaned.index

def test_trailing_all_nan_rows_removed_but_internal_nan_survives():
    idx = pd.bdate_range("2026-01-05", periods=5)
    raw = pd.DataFrame({"A": [100.0, np.nan, 110.0, 111.0, np.nan]}, index=idx)
    cleaned = _clean_price_df(raw)
    assert idx[-1] not in cleaned.index
    assert pd.isna(cleaned.loc[idx[1], "A"])
