"""India-market time helpers.

Every "today" in this application is a question about an NSE trading day, so
it has to be answered in Asia/Kolkata rather than in the server's timezone.
Streamlit Cloud runs in UTC, 5h30m behind IST: between 18:30 and 24:00 UTC the
Indian date is already tomorrow. A naive datetime.now() therefore disagreed
with the IST-aware paths for five and a half hours of every day, and the two
notions of "today" sat in the same module in one case.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

INDIA_TZ = ZoneInfo("Asia/Kolkata")

# When a session's daily bar can be trusted as final. NSE's equity close is
# 15:30 IST; the extra half hour is slack for the data provider, whose daily
# bar settles a few minutes after the bell.
#
# Until then a row dated today is an IN-PROGRESS quote, not a close. Treating
# the two as the same thing is what let the price cache freeze at whatever
# minute a container first fetched it, while the page went on calling the
# number "today".
SESSION_SETTLES = time(16, 0)


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


def trading_days_behind(as_of: date, *, today: date | None = None, horizon: int = 30) -> int | None:
    """How many trading days old ``as_of`` is.

    0 means it is the most recent trading day, 1 the one before, and so on.
    Counting in trading days rather than calendar days is what makes the
    answer usable: a Monday showing Friday's figures is current, not stale,
    and a festival cluster must not read as a data outage.

    Returns None when ``as_of`` is not among the recent trading days at all --
    either far older than the horizon, or in the future.
    """
    days = recent_trading_days(horizon, as_of=today or ist_today(), max_lookback_days=horizon * 2)
    try:
        return days.index(as_of)
    except ValueError:
        return None


def session_is_complete(day: date, *, now: datetime | None = None) -> bool:
    """Has the trading session dated ``day`` finished producing its daily bar?

    Any past date is settled. A future date never is. Today's is settled only
    once the close is comfortably behind us -- before that, the row exists but
    its Close is the last traded price and still moving.

    This is the distinction the price cache needs. Its old freshness gate asked
    only "does the cache hold a row dated today?", so the FIRST fetch of the
    morning satisfied it and no later fetch ever ran: the screener served the
    09:20 price at 15:20 and the header dated it today, which is true of the
    row and false of the number.
    """
    reference = now or ist_now()
    today = reference.date()
    if day < today:
        return True
    if day > today:
        return False
    return reference.time() >= SESSION_SETTLES
