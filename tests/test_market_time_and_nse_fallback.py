"""Trading-day resolution and NSE archive fallback behaviour."""
from datetime import date, datetime, timezone

import pytest

from src.core.market_time import INDIA_TZ, ist_today, recent_trading_days


def test_ist_date_can_differ_from_server_date():
    """The bug this guards: UTC is 5h30m behind IST.

    At 19:00 UTC the Indian date is already tomorrow, so a server-local
    "today" asks NSE for the wrong trading day for part of every day.
    """
    utc_evening = datetime(2026, 8, 18, 19, 0, tzinfo=timezone.utc)
    assert utc_evening.date() == date(2026, 8, 18)
    assert utc_evening.astimezone(INDIA_TZ).date() == date(2026, 8, 19)


def test_ist_today_is_a_date():
    assert isinstance(ist_today(), date)


def test_walk_includes_today_then_walks_back():
    days = recent_trading_days(3, as_of=date(2026, 8, 18))  # a Tuesday
    assert days[0] == date(2026, 8, 18)
    assert days == sorted(days, reverse=True), "newest first"


def test_walk_never_returns_a_weekend():
    for anchor in (date(2026, 8, 15), date(2026, 8, 16), date(2026, 8, 17)):
        assert all(d.weekday() < 5 for d in recent_trading_days(8, as_of=anchor))


def test_monday_falls_back_across_the_weekend_to_friday():
    days = recent_trading_days(2, as_of=date(2026, 8, 17))  # Monday
    assert days == [date(2026, 8, 17), date(2026, 8, 14)]


def test_window_clears_a_multi_day_holiday_cluster():
    """A seven-calendar-day window yielded only five candidates.

    A festival cluster adjacent to a weekend can consume several of those, so
    the walk must still reach a genuine trading day behind it.
    """
    days = recent_trading_days(6, as_of=date(2026, 11, 10))
    assert len(days) == 6
    assert days[-1] <= date(2026, 11, 3), "must reach past the cluster"


@pytest.mark.parametrize("count", [0, -1])
def test_non_positive_count_returns_nothing(count):
    assert recent_trading_days(count) == []


def test_count_is_honoured():
    assert len(recent_trading_days(4, as_of=date(2026, 8, 18))) == 4


class _Resp:
    def __init__(self, status): self.status_code = status; self.content = b""


def test_blocked_status_raises_rather_than_looking_like_a_missing_file(monkeypatch):
    """403 must be distinguishable from 404.

    A missing archive means "try an earlier day". A refusal means every
    earlier day is refused too, so continuing burns the remaining attempts --
    up to five sequential 15s requests on a cold start.
    """
    from src.loaders import mcap_loader

    for status in (401, 403, 429):
        monkeypatch.setattr(mcap_loader.requests, "get", lambda *a, **k: _Resp(status))
        with pytest.raises(mcap_loader._NSEBlocked):
            mcap_loader._fetch_mcap_from_pr_zip(date(2026, 8, 18))


def test_missing_archive_returns_empty_so_the_caller_walks_back(monkeypatch):
    from src.loaders import mcap_loader

    monkeypatch.setattr(mcap_loader.requests, "get", lambda *a, **k: _Resp(404))
    assert mcap_loader._fetch_mcap_from_pr_zip(date(2026, 8, 18)) == {}
