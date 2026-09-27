"""The liquidity floor: 20-day average traded value, known at the signal date only."""

import pandas as pd

from src.engine import liquidity


def _frames():
    idx = pd.bdate_range("2026-08-03", periods=40)
    close = pd.DataFrame({"BIG": 100.0, "SMALL": 10.0, "GONE": 50.0}, index=idx)
    vol = pd.DataFrame({"BIG": 1_000_000.0, "SMALL": 100_000.0, "GONE": float("nan")}, index=idx)
    vol.loc[idx[30]:, "SMALL"] = 10_000_000.0          # becomes liquid late
    return close, vol


def test_traded_value_is_a_20_day_average_in_crore():
    close, vol = _frames()
    tv = liquidity.traded_value_cr(close, vol)
    assert tv["BIG"].iloc[-1] == 10.0                  # 100 x 10 lakh = ₹10 Cr a day
    assert pd.isna(tv["BIG"].iloc[10])                 # under 15 sessions: unknown


def test_the_floor_uses_the_value_known_that_day_and_fails_the_unknown():
    close, vol = _frames()
    tv = liquidity.traded_value_cr(close, vol)
    cols = pd.Index(["BIG", "SMALL", "GONE", "NEW"])
    early = liquidity.passes(tv, cols, tv.index[25], 5)
    assert early.to_dict() == {"BIG": True, "SMALL": False, "GONE": False, "NEW": False}
    late = liquidity.passes(tv, cols, tv.index[-1], 5)
    assert late["SMALL"]                               # ₹10 Cr+ by the end


def test_off_or_without_data_applies_no_condition():
    close, vol = _frames()
    tv = liquidity.traded_value_cr(close, vol)
    assert liquidity.passes(tv, close.columns, tv.index[-1], 0) is None
    assert liquidity.passes(None, close.columns, tv.index[-1], 5) is None
    assert liquidity.traded_value_cr(close, None) is None
