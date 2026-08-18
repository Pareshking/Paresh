"""India-market time helpers.

Every "today" in this application is a question about an NSE trading day, so
it has to be answered in Asia/Kolkata rather than in the server's timezone.
Streamlit Cloud runs in UTC, 5h30m behind IST: between 18:30 and 24:00 UTC the
Indian date is already tomorrow. A naive datetime.now() therefore disagreed
with the IST-aware paths for five and a half hours of every day, and the two
notions of "today" sat in the same module in one case.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

INDIA_TZ = ZoneInfo("Asia/Kolkata")


def ist_now() -> datetime:
    """Current time in Indian market time, timezone-aware."""
    return datetime.now(INDIA_TZ)


def ist_today() -> date:
    """Today's date as the Indian market sees it."""
    return ist_now().date()


def recent_trading_days(
    count: int = 6,
    *,
    as_of: date | None = None,
    max_lookback_days: int = 21,
) -> list[date]:
    """Most recent candidate trading days, newest first, weekends excluded.

    Includes ``as_of`` itself, because a caller asking at 09:00 IST should
    still try today before falling back -- and if today's file is not
    published yet the caller simply moves to the next candidate.

    NSE holidays are deliberately NOT enumerated here. A hardcoded holiday
    calendar goes stale and then fails silently on exactly the day it matters.
    Callers instead walk this list and stop at the first date that actually
    returns data, so a holiday costs one failed lookup rather than a wrong
    answer. The calendar-day budget is wide enough to clear a multi-day
    festival cluster sitting next to a weekend (Diwali, Holi), which a
    seven-calendar-day window could not.
    """
    if count <= 0:
        return []
    cursor = as_of or ist_today()
    days: list[date] = []
    for offset in range(max_lookback_days):
        day = cursor - timedelta(days=offset)
        if day.weekday() >= 5:  # Saturday / Sunday are never trading days
            continue
        days.append(day)
        if len(days) >= count:
            break
    return days
