"""The observed-session publication gate: daily recent year, long span, never shrinks."""
import pandas as pd

from scripts import check_observed_sessions as cos


def _archive(dates):
    d = pd.DatetimeIndex(dates)
    return pd.DataFrame({"date": d, "market": "NSE", "is_session": True})


def _healthy():
    weekly = pd.date_range("2016-09-23", "2025-07-01", freq="W-FRI")
    daily = pd.bdate_range("2025-07-04", "2026-09-24")
    return weekly.append(daily)


def test_a_healthy_archive_passes():
    assert cos.check(_archive(_healthy()), previous=None) == []


def test_the_2026_09_21_regression_is_caught():
    """The nightly store that replaced a 10-year download with one year."""
    one_year = pd.bdate_range("2025-09-18", "2026-09-21")
    previous = set(_healthy().strftime("%Y-%m-%d"))
    problems = cos.check(_archive(one_year), previous)
    assert any("missing" in p for p in problems)


def test_a_short_history_alone_is_not_a_problem():
    """Owner: short history is fine (listing dates, collection just begun)."""
    assert cos.check(_archive(pd.bdate_range("2025-09-18", "2026-09-24")), None) == []


def test_a_store_that_fell_back_to_weekly_fails_the_recent_year():
    weekly = pd.date_range("2016-09-23", "2026-09-24", freq="W-FRI")
    assert any("recent year must be daily" in p for p in cos.check(_archive(weekly), None))


def test_a_lost_session_is_named():
    dates = _healthy()
    previous = set(dates.strftime("%Y-%m-%d"))
    problems = cos.check(_archive(dates.delete(10)), previous)
    assert problems and dates[10].strftime("%Y-%m-%d") in problems[0]


def test_growth_is_fine():
    dates = _healthy()
    previous = set(dates[:-5].strftime("%Y-%m-%d"))
    assert cos.check(_archive(dates), previous) == []


def test_shape_problems_are_reported():
    frame = _archive(_healthy())
    frame.loc[3, "market"] = "BSE"
    frame.loc[4, "is_session"] = False
    problems = cos.check(frame, None)
    assert any("NSE" in p for p in problems) and any("session" in p for p in problems)
