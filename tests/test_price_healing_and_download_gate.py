"""The download gate (src/core/market_time) and the trading-day record.

The Yahoo price cache these used to guard, with its healing merge, full
refresh and phantom-session filters, was removed with yfinance on 13 Oct 2026
(TODO S10); its tests went with it. What stays is still live: the settle
window that any nightly download is timed against, and the record of NSE
trading days and closures (src/loaders/trading_days) the sync writes.
"""

from datetime import date, datetime

from src.core.market_time import (
    DOWNLOAD_SETTLES,
    INDIA_TZ,
    last_downloadable_session,
    session_is_complete,
    session_is_downloadable,
)


def _ist(y, m, d, hh, mm):
    return datetime(y, m, d, hh, mm, tzinfo=INDIA_TZ)


# ── The download gate ────────────────────────────────────────────────────────

def test_the_settle_window_is_the_close_plus_seven_hours():
    """15:30 IST + 7h. The constant is the contract, so pin it."""
    assert DOWNLOAD_SETTLES.hour == 22 and DOWNLOAD_SETTLES.minute == 30


def test_todays_bar_is_not_downloadable_before_the_market_even_opens():
    """The exact production case: 2026-09-16 at 06:43 IST."""
    assert not session_is_downloadable(
        date(2026, 9, 16), now=_ist(2026, 9, 16, 6, 43)
    )


def test_todays_bar_is_not_downloadable_during_the_session():
    assert not session_is_downloadable(
        date(2026, 9, 16), now=_ist(2026, 9, 16, 11, 0)
    )


def test_todays_bar_is_still_not_downloadable_just_after_the_close():
    """The bell is not the settle. Yahoo revises the Indian bar for hours."""
    assert not session_is_downloadable(
        date(2026, 9, 16), now=_ist(2026, 9, 16, 15, 45)
    )


def test_todays_bar_becomes_downloadable_after_the_settle_window():
    assert session_is_downloadable(
        date(2026, 9, 16), now=_ist(2026, 9, 16, 22, 31)
    )


def test_the_gate_is_strictly_stricter_than_the_freshness_gate():
    """Between 16:00 and 22:30 a row is 'complete' but not worth re-requesting.

    If these two ever collapse into each other, the gate has stopped doing
    anything and the pre-open download is back.
    """
    at_1700 = _ist(2026, 9, 16, 17, 0)
    assert session_is_complete(date(2026, 9, 16), now=at_1700)
    assert not session_is_downloadable(date(2026, 9, 16), now=at_1700)


def test_a_past_session_is_always_downloadable():
    assert session_is_downloadable(date(2026, 9, 15), now=_ist(2026, 9, 16, 6, 43))


def test_last_downloadable_session_skips_today_before_its_settle():
    """Wednesday pre-dawn: the newest settled bar is Tuesday's."""
    assert last_downloadable_session(now=_ist(2026, 9, 16, 6, 43)) == date(2026, 9, 15)


def test_last_downloadable_session_takes_today_once_it_settles():
    assert last_downloadable_session(now=_ist(2026, 9, 16, 23, 0)) == date(2026, 9, 16)


def test_last_downloadable_session_reaches_back_over_a_weekend():
    """Saturday and Sunday are never trading days, so Friday is the answer."""
    assert last_downloadable_session(now=_ist(2026, 9, 20, 10, 0)) == date(2026, 9, 18)


# ── The trading-day record ───────────────────────────────────────────────────

def test_the_record_only_ever_holds_confirmations(tmp_path):
    """Absence must never read as a closure -- NSE answers 403 when throttled,
    and six retries on 2026-09-14 never got past it. Reading that as 'holiday'
    would delete real sessions on a bad network day."""
    from src.loaders.trading_days import is_confirmed, load_confirmed, record_confirmed

    path = str(tmp_path / "days.json")
    record_confirmed({"2026-09-16"}, path)
    assert load_confirmed(path) == {"2026-09-16"}
    assert is_confirmed("2026-09-16", load_confirmed(path))
    # An unknown date is unknown, not closed.
    assert not is_confirmed("2026-09-14", load_confirmed(path))


def test_the_record_is_append_only(tmp_path):
    """A date NSE confirmed once stays confirmed; nothing here removes one."""
    from src.loaders.trading_days import load_confirmed, record_confirmed

    path = str(tmp_path / "days.json")
    record_confirmed({"2026-09-15"}, path)
    added, total = record_confirmed({"2026-09-16"}, path)
    assert added == 1 and total == 2
    assert load_confirmed(path) == {"2026-09-15", "2026-09-16"}
    # Re-recording the same day is a no-op.
    assert record_confirmed({"2026-09-16"}, path) == (0, 2)


def test_an_unreadable_record_degrades_to_the_floor(tmp_path):
    from src.loaders.trading_days import load_confirmed

    bad = tmp_path / "days.json"
    bad.write_text("{not json")
    assert load_confirmed(str(bad)) == set()


def test_the_shipped_record_vouches_for_the_session_that_broke():
    """The live file must carry 2026-09-16, or tonight repeats the mistake."""
    from src.loaders.trading_days import load_confirmed

    days = load_confirmed()
    assert "2026-09-16" in days, (
        "2026-09-16 is not in the committed record; the nightly heal will drop "
        "that real session again at 63% coverage"
    )


# ── A recorded closure beats the floor in the other direction ────────────────
#
# The confirmations above rescue a real session the vendor was slow on. They
# cannot do the opposite, and 2026-09-14 needed the opposite. It was a holiday
# NSE never answered for (403, six retries), so it had no confirmation to lose
# -- it just had to stay under a threshold, and it would not:
#
#   during the sync 2026-09-16    61%   dropped
#   2026-09-17                    86%   KEPT
#   2026-09-18                  73.5%   KEPT
#
# Twice above the floor, once below, same day, same holiday. The 70% line is
# not the wrong number; there is no right number. So the calendar gets recorded
# as a fact and the floor stops being asked.


def test_nse_confirmation_outranks_a_closure_claim(tmp_path):
    """A bhavcopy beats anything else, so the two records can never disagree.

    Without this, one bad closure entry would silently delete real sessions
    forever -- the exact failure mode the confirmations-only rule exists to
    prevent, reintroduced through the other door.
    """
    from src.loaders.trading_days import (
        load_closed, load_confirmed, record_closed, record_confirmed,
    )

    path = str(tmp_path / "days.json")
    record_confirmed({"2026-09-16"}, path)
    added, _ = record_closed(["2026-09-16"], source="mistaken", path=path)
    assert added == 0, "a date NSE published a bhavcopy for was marked closed"
    assert load_closed(path) == set()
    assert load_confirmed(path) == {"2026-09-16"}


def test_the_two_records_survive_each_other(tmp_path):
    """Nightly confirmations must not wipe the closures, or vice versa.

    They share one file and the nightly job rewrites it on every new trading
    day, so a write that only knew about its own half would drop the other.
    """
    from src.loaders.trading_days import (
        load_closed, load_confirmed, record_closed, record_confirmed,
    )

    path = str(tmp_path / "days.json")
    record_closed(["2026-09-14"], source="user-confirmed holiday", path=path)
    record_confirmed({"2026-09-15", "2026-09-16"}, path)
    assert load_closed(path) == {"2026-09-14"}, "the nightly write erased the closure"
    assert load_confirmed(path) == {"2026-09-15", "2026-09-16"}

    record_closed(["2026-10-02"], source="Gandhi Jayanti", path=path)
    assert load_confirmed(path) == {"2026-09-15", "2026-09-16"}, (
        "recording a closure erased the confirmations"
    )
    assert load_closed(path) == {"2026-09-14", "2026-10-02"}


def test_the_source_of_every_closure_is_written_down(tmp_path):
    """A closure deletes history, so the file must say who established it."""
    import json
    from src.loaders.trading_days import record_closed

    path = str(tmp_path / "days.json")
    record_closed(["2026-09-14"], source="user-confirmed NSE holiday", path=path)
    payload = json.loads(open(path).read())
    assert payload["closed_days_source"]["2026-09-14"] == "user-confirmed NSE holiday"


def test_the_shipped_record_marks_the_holiday_that_keeps_returning():
    """The live file must carry 2026-09-14, or tonight repeats the mistake."""
    from src.loaders.trading_days import load_closed, load_confirmed

    closed = load_closed()
    assert "2026-09-14" in closed, (
        "2026-09-14 is not on the closed record; the nightly heal will pull "
        "the holiday back in at whatever coverage Yahoo happens to show"
    )
    assert not (closed & load_confirmed()), (
        "the committed record claims a date is both a trading day and a holiday"
    )
