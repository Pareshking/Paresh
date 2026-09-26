"""Gap-filled share: missing days count only after a stock's first price."""
import numpy as np
import pandas as pd

from src.engine.momentum import compute_ffill_pct


def test_days_before_listing_are_not_gaps():
    idx = pd.bdate_range("2024-01-01", periods=10)
    df = pd.DataFrame({
        "OLD": np.arange(10.0),
        # Lists on day 4, then one missing session on day 7.
        "NEW": [np.nan] * 4 + [1.0, 1.0, 1.0, np.nan, 1.0, 1.0],
        "OTHER": np.arange(10.0),
    }, index=idx)
    got = compute_ffill_pct(df)
    assert got["OLD"] == 0.0
    assert got["NEW"] == round(1 / 6 * 100, 1)       # 1 gap in 6 listed days
