"""Staleness audit, 21 Nov 2026 (S164): verdicts read today, not the last month-end.

On 20 Nov Breadth's trend verdict and the Dashboard's signal count read the
Nifty 500 at its 30 Oct close (3.1% below its 10-month average) while the
index stood about 6% above it. A rule may read completed months; a verdict
about today reads today and names the month-end reading beside it.
"""
from __future__ import annotations

import pandas as pd

from src.engine import market_questions as mq
from src.ui.views import dashboard_home_view as dh


def _series(month_end_values, today_value, today="2026-11-20"):
    idx = pd.date_range("2025-12-31", periods=len(month_end_values), freq="ME")
    s = pd.Series(month_end_values, index=idx, dtype=float)
    s.loc[pd.Timestamp("2026-11-03")] = month_end_values[-1]
    s.loc[pd.Timestamp(today)] = today_value
    return s.sort_index()


def test_today_reads_todays_close_and_the_month_end_reading_stays_the_month_end():
    s = _series([100.0] * 11, 120.0)           # Dec-Oct flat at 100, 20 Nov at 120
    when = s.index[-1]
    assert round(mq.ten_month_gap(s, when), 6) == 0.0                 # 30 Oct against Jan-Oct
    assert mq.last_month_end(s, when) == pd.Timestamp("2026-10-31")
    # Today against the last ten monthly closes, November at today's close: 120 / 102 - 1.
    assert round(mq.ten_month_today(s, when), 4) == round((120 / 102 - 1) * 100, 4)


def test_on_a_month_end_both_readings_agree():
    s = _series([100.0 + i for i in range(11)], 0.0)
    s = s[s.index <= pd.Timestamp("2026-10-31")]
    when = s.index[-1]
    assert abs(mq.ten_month_today(s, when) - mq.ten_month_gap(s, when)) < 1e-9


def test_the_trend_verdict_votes_on_today_and_names_the_month_end():
    idx = pd.bdate_range("2025-01-01", "2026-11-20")
    # Falling to 30 Oct, then a sharp November rally.
    vals = [100 - 0.02 * i for i in range(len(idx))]
    s = pd.Series(vals, index=idx)
    s.loc["2026-11-02":] = 140.0
    ans = mq.trend_answer(s, {}, None)
    ten = next(m for m in ans.measures if "10-month" in m.name)
    assert ten.now > 0 and ten.vote == mq.UP
    assert "month-end" in ten.rule and "−" in ten.rule


def test_the_sentence_gives_the_month_end_count_only_when_it_differs():
    rows = [{"like": 1.0, "like_me": 1.0}, {"like": 1.0, "like_me": -1.0}, {"like": -1.0, "like_me": -1.0}]
    assert dh._month_end_count(rows, 0.0) == (1, 2)       # worded by dash.mom.3 (S203)
    same = [{"like": 1.0, "like_me": 1.0}]
    assert dh._month_end_count(same, 0.0) is None
    assert dh._month_end_count(rows, None) is None
