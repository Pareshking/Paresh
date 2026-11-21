"""Swap evidence: buys against names sold, each against the market over the same sessions."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.engine import swap_evidence as sw


def test_buys_and_sold_names_are_measured_against_the_market_from_their_own_dates():
    idx = pd.bdate_range("2026-01-01", periods=120)
    market = pd.Series(100 * 1.001 ** np.arange(120), index=idx)                 # +0.1% a day
    up = pd.Series(100 * 1.002 ** np.arange(120), index=idx)                     # +0.2% a day
    flat = pd.Series(100.0, index=idx)
    px = pd.DataFrame({"UP": up, "FLAT": flat})
    ev = sw.evidence([("UP", idx[0])], [("FLAT", idx[0]), ("UP", idx[10])], px, market)
    assert ev.buys == 1 and ev.sold == 2
    m1 = 1.001 ** 21 - 1
    assert ev.buy_1m == pytest.approx(((1.002 ** 21 - 1) - m1) * 100)
    assert ev.sold_1m == pytest.approx((((0.0 - m1)) + ((1.002 ** 21 - 1) - m1)) / 2 * 100)
    assert ev.rebought == 0


def test_a_name_bought_back_within_two_months_is_counted():
    idx = pd.bdate_range("2026-01-01", periods=120)
    px = pd.DataFrame({"A": pd.Series(100.0, index=idx)})
    m = pd.Series(100.0, index=idx)
    ev = sw.evidence([("A", idx[40])], [("A", idx[5])], px, m)
    assert ev.rebought == 1
