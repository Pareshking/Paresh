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


def test_only_the_ranking_window_counts():
    # Two years of business days: a month-long hole 18 months ago, none since.
    idx = pd.bdate_range("2024-09-02", "2026-09-25")
    s = pd.Series(1.0, index=idx)
    s[(idx >= "2025-03-01") & (idx < "2025-04-01")] = np.nan
    df = pd.DataFrame({"OLDGAP": s, "OTHER": 1.0}, index=idx)
    assert compute_ffill_pct(df)["OLDGAP"] == 0.0
    # The same hole inside the last 12 months is counted.
    s2 = pd.Series(1.0, index=idx)
    s2[(idx >= "2026-03-01") & (idx < "2026-04-01")] = np.nan
    got = compute_ffill_pct(pd.DataFrame({"NEWGAP": s2, "OTHER": 1.0}, index=idx))["NEWGAP"]
    assert 7.0 < got < 10.0              # ~22 of ~260 sessions
