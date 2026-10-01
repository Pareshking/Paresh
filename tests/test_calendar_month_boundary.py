"""Regression contracts for calendar closure vs latest price availability."""

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from src.core.market_time import last_closed_calendar_period
from src.engine.backtester import completed_month_window
from src.engine.systems import backtest_months
from src.engine.track_record import INCEPTION, months_to_cover

ROOT = Path(__file__).resolve().parents[1]


IST = ZoneInfo("Asia/Kolkata")


def test_october_first_closes_september_even_when_prices_stop_on_september_30():
    now = datetime(2026, 10, 1, 12, 51, tzinfo=IST)
    assert last_closed_calendar_period(pd.Timestamp("2026-09-30"), now=now) == pd.Period(
        "2026-09", freq="M"
    )


def test_september_30_before_close_does_not_close_september():
    now = datetime(2026, 9, 30, 12, 51, tzinfo=IST)
    assert last_closed_calendar_period(pd.Timestamp("2026-09-30"), now=now) == pd.Period(
        "2026-08", freq="M"
    )


def test_september_30_after_settle_closes_september():
    now = datetime(2026, 9, 30, 16, 1, tzinfo=IST)
    assert last_closed_calendar_period(pd.Timestamp("2026-09-30"), now=now) == pd.Period(
        "2026-09", freq="M"
    )


def test_completed_backtest_window_includes_september_on_october_first():
    now = datetime(2026, 10, 1, 12, 51, tzinfo=IST)
    dates = pd.date_range("2026-01-01", "2026-09-30", freq="B")
    start, end = completed_month_window(dates, months=6, now=now)
    assert start == pd.Timestamp("2026-04-01")
    assert end == pd.Timestamp("2026-09-30")


def test_track_record_and_backtest_month_counts_include_closed_september():
    now = datetime(2026, 10, 1, 12, 51, tzinfo=IST)
    as_of = pd.Timestamp("2026-09-30")
    assert months_to_cover(as_of, INCEPTION, now=now) == 9
    assert backtest_months("750", as_of, now=now) == 9


def test_actions_source_anchors_rebalance_schedule_to_calendar_today():
    source = (ROOT / "src/ui/views/actions_view.py").read_text(encoding="utf-8")
    assert "calendar_today = pd.Timestamp(ist_now().date())" in source
    assert "check, fill = next_rebalance(calendar_today)" in source
