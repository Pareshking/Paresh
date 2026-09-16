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


# ── When the vendor's daily bar is worth ASKING FOR ──────────────────────────
#
# SESSION_SETTLES above answers "is this row final?". This answers a different
# and more expensive question: "is there any point making the request at all?"
#
# They are not the same moment. NSE's bell is 15:30 IST, but Yahoo's daily bar
# for an Indian symbol keeps moving for hours afterwards -- the close is
# revised, the volume is restated, and on a corporate-action day the whole
# series is recomputed. Asking at 16:00 gets an answer; asking at 22:30 gets
# the RIGHT answer, and asking before the open gets nothing at all while still
# costing the full round trip.
#
# That last case is what this constant exists for. Production logged a
# 25-second download of 750 tickers at 06:43 IST on 2026-09-16 -- before the
# market had opened -- which returned no new rows, because the session it was
# asking about had not happened yet. The cache went in with 499 rows and came
# out with 499 rows, and every cold start before the open paid for it.
#
# 15:30 close + 7 hours. Deliberately generous: a late bar costs one stale
# session, an early fetch costs a wrong price on every page that quotes it.
DOWNLOAD_SETTLES = time(22, 30)


def session_is_downloadable(day: date, *, now: datetime | None = None) -> bool:
    """Is ``day``'s daily bar worth requesting from the vendor yet?

    Stricter than :func:`session_is_complete`, and for a different caller. That
    one guards how a row already in hand may be DESCRIBED; this one guards
    whether a network request is made at all.
    """
    reference = now or ist_now()
    today = reference.date()
    if day > today:
        return False
    if day < today:
        return True
    return reference.time() >= DOWNLOAD_SETTLES


def last_downloadable_session(*, now: datetime | None = None) -> date | None:
    """The newest session whose bar the vendor can be expected to have settled.

    Walks back from today over candidate trading days -- weekends are skipped
    by :func:`recent_trading_days`, holidays are not enumerated -- and returns
    the first one past its settle window. A caller whose cache already reaches
    this date has nothing to gain from a request.

    Returns None only if no candidate in the lookback window qualifies, which
    a caller should read as "cannot tell; behave as before".
    """
    reference = now or ist_now()
    for day in recent_trading_days(count=10, as_of=reference.date()):
        if session_is_downloadable(day, now=reference):
            return day
    return None
