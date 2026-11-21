"""The Portfolio page's figures, and tables that grow with the record (S151, owner 20 Nov 2026)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.engine import portfolio_report as pr


def _series(start, end, daily=0.0005, seed=1):
    idx = pd.bdate_range(start, end)
    r = np.random.default_rng(seed).normal(daily, 0.01, len(idx))
    return pd.Series(100 * np.cumprod(1 + r), index=idx)


def test_the_first_year_has_no_annualised_rows():
    b = _series("2025-12-31", "2026-11-19")
    labels = [r[0] for r in pr.periods(b, b, b, b.index[-1])]
    assert labels[:3] == ["Today", "1 week", "Month so far"]
    assert "FY 2026-27" in labels
    assert not any(lab.startswith(("1 year", "3 years", "A year")) for lab in labels)


def test_from_the_second_year_the_periods_add_themselves():
    b = _series("2025-12-31", "2031-06-30")
    labels = [r[0] for r in pr.periods(b, b, b, b.index[-1])]
    for lab in ("1 year", "3 years", "5 years", "Since start", "A year, since start"):
        assert lab in labels
    risk = [r.label for r in pr.risk(b, b * 1.01)]
    assert risk[0].startswith("Since") and "Last 12 months" in risk and "2027" in risk and "2031, so far" in risk


def test_drawdown_terms():
    v = pd.Series([100, 110, 99, 88, 95, 111, 105], index=pd.bdate_range("2026-01-01", periods=7), dtype=float)
    f = pr.falls(v)
    assert f.worst == pytest.approx(-20.0)            # 110 to 88
    assert f.peak == v.index[1] and f.low == v.index[3] and f.recovered == v.index[5]
    assert f.worst_day == pytest.approx((88 / 99 - 1) * 100)
    assert f.now == pytest.approx((105 / 111 - 1) * 100)
    assert pr.worst_month_end([1.0, -10.0, 5.0])[0] == pytest.approx(-10.0)


def test_calendar_rows_by_year_with_quarters():
    s = {"book": {pd.Period("2026-01", "M"): 10.0, pd.Period("2026-02", "M"): -10.0, pd.Period("2026-04", "M"): 5.0,
                  pd.Period("2027-01", "M"): 1.0}}
    cal = pr.calendar(s)
    assert sorted(cal) == [2026, 2027]
    q = cal[2026]["book"]["quarters"]
    assert q[0] == pytest.approx(-1.0) and q[1] == pytest.approx(5.0) and q[2] is None
    assert cal[2026]["book"]["year"] == pytest.approx((1.1 * 0.9 * 1.05 - 1) * 100)
    fy = pr.financial_years(s)
    assert [x[0] for x in fy] == ["FY 2025-26", "FY 2026-27"]


def test_open_trades_get_their_rank_signal_and_weight_from_the_rebalance_line():
    trades = pd.DataFrame([{"Symbol": "NEW", "Sector": None, "Entry Date": "02 Nov 2026", "Entry Price": 10.0,
                            "Entry Signal Date": None, "Entry Rank": np.nan, "Entry Weight %": np.nan,
                            "Exit Signal Date": None, "Exit Date": "Not exited (mark 19 Nov 2026)", "Exit Price": 11.0,
                            "Exit Rank": np.nan, "Return %": 0.1, "Holding (Days)": 17, "Reason for Exit": "🟢 Still held",
                            "Status": "Open"}])
    book = pd.DataFrame([{"Period": "02 Nov 2026 → 19 Nov 2026", "Action": "🟢 BUY (Entry)", "Symbol": "NEW",
                          "Weight %": 5.0, "Reason / Signal": "New Momentum Leader (Rank #11)"}])
    t = pr.trades_table(trades, book, pd.bdate_range("2026-10-26", "2026-11-19"), {"NEW": "Healthcare"})
    row = t.iloc[0]
    assert list(t.columns) == pr.TRADE_FIELDS
    assert row["Entry rank"] == 11 and row["Entry weight %"] == 5.0 and row["Industry"] == "Healthcare"
    assert row["Entry signal date"] == pd.Timestamp("2026-10-30") and row["Exit date"] is None


def test_an_index_a_session_behind_has_no_today_figure():
    # 21 Nov 2026: prices to 20 Nov, Nifty Total Market to 19 Nov; Today read the market at 0.0%.
    b = _series("2025-12-31", "2026-11-20")
    m = b.loc[:"2026-11-19"]
    row = dict((r[0], r[1:]) for r in pr.periods(b, m, m, b.index[-1]))
    assert row["Today"][0] is not None and row["Today"][1] is None and row["Today"][2] is None
    assert row["1 week"][1] is not None
