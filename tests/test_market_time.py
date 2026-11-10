

def test_muhurat_trading_on_a_sunday_is_a_trading_day_once_nse_confirms_it():
    """NSE held Muhurat trading on Sunday 8 Nov 2026: its archive serves a
    bhavcopy of 3,551 rows for the 8th and 404 for Saturday the 7th. The
    calendar skipped every weekend day outright, so the freshest prices the
    site had could not be placed and the footer called them stale (owner,
    9 Nov 2026)."""
    from datetime import date

    from src.core import market_time as mt

    sunday, monday = date(2026, 11, 8), date(2026, 11, 9)
    before = mt._WEEKEND_SESSIONS
    try:
        mt._WEEKEND_SESSIONS = frozenset()
        assert sunday not in mt.recent_trading_days(5, as_of=monday)
        assert mt.trading_days_behind(sunday, today=monday) is None

        mt._WEEKEND_SESSIONS = frozenset({"2026-11-08"})
        assert sunday in mt.recent_trading_days(5, as_of=monday)
        assert mt.trading_days_behind(sunday, today=monday) == 1
        # Saturday answered 404, so it is not a session and stays out.
        assert date(2026, 11, 7) not in mt.recent_trading_days(5, as_of=monday)
    finally:
        mt._WEEKEND_SESSIONS = before


def test_a_collector_may_offer_the_exchange_a_weekend_date():
    """The walk that would confirm a Muhurat session was the walk that skipped
    it. A collector asks the exchange anyway, so it offers weekend dates; a
    404 costs one request and settles the question."""
    from datetime import date

    from src.core import market_time as mt

    before = mt._WEEKEND_SESSIONS
    try:
        mt._WEEKEND_SESSIONS = frozenset()
        days = mt.recent_trading_days(4, as_of=date(2026, 11, 9), probe_weekends=True)
        assert date(2026, 11, 8) in days and date(2026, 11, 7) in days
    finally:
        mt._WEEKEND_SESSIONS = before


def test_a_published_holiday_is_not_counted_as_a_trading_day():
    """Slot 10, 10 Nov 2026: the ribbon read "9 Nov -- 1 trading day behind".

    10 Nov 2026 is Diwali-Balipratipada in NSE's own holiday master
    (data/reference/nse/holidays.csv), so 9 Nov was the latest session there
    was. recent_trading_days still offers the holiday -- only the exchange can
    prove a day was closed -- but the age of a figure must not count it.
    """
    from datetime import date

    from src.core.market_time import trading_days_behind

    holiday = date(2026, 11, 10)
    assert trading_days_behind(date(2026, 11, 9), today=holiday) == 0
    # 8 Nov is a Sunday NSE traded on (Muhurat), so it is a session, not a gap.
    assert trading_days_behind(date(2026, 11, 8), today=holiday) == 1
    assert trading_days_behind(date(2026, 11, 6), today=holiday) == 2
    # And from a day NSE did trade, yesterday's session is one day behind.
    assert trading_days_behind(date(2026, 11, 9), today=date(2026, 11, 11)) == 1


def test_the_holiday_calendar_can_only_shorten_the_count_never_void_it():
    """A wrong holiday file must not turn a real session into "age unknown".

    That is what the ribbon shows as stale, and it is the failure
    recent_trading_days keeps the calendar out of the walk to avoid, so as_of
    itself is never removed by the calendar.
    """
    from datetime import date

    from src.core.market_time import trading_days_behind

    # 10 Nov 2026 IS a published holiday. Asked for its own age, the answer is
    # still a number, not None.
    assert trading_days_behind(date(2026, 11, 10), today=date(2026, 11, 10)) == 0
