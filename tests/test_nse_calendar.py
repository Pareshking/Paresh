"""Days NSE cannot have traded: weekends, fixed holidays, its published list."""
from datetime import date

from src.loaders import nse_calendar as cal


def test_weekends_and_fixed_holidays_are_not_sessions():
    assert cal.not_a_session("2024-01-27") == "weekend"
    assert cal.not_a_session("2024-01-26") == "Republic Day"
    assert cal.not_a_session("2023-10-02") == "Mahatma Gandhi Jayanti"
    assert cal.not_a_session("2024-01-25") == ""


def test_announced_weekend_sessions_and_muhurat_are_sessions():
    assert cal.not_a_session("2020-02-01") == ""        # Budget Saturday
    assert cal.not_a_session("2023-11-12") == ""        # Muhurat Sunday
    assert cal.not_a_session("2026-11-08") == ""        # Diwali Laxmi Pujan*, a Muhurat evening


def test_nses_published_holidays_are_not_sessions():
    assert cal.not_a_session("2026-03-03") == "Holi"
    assert cal.impossible_sessions(["2026-03-02", "2026-03-03", "2026-03-04"]) == {date(2026, 3, 3): "Holi"}
