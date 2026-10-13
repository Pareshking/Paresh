"""The app must not present old numbers as current ones.

Production showed prices that were days behind under a header dating them
today. Four separate mechanisms had to line up for that, and each one is worth
holding in place independently:

* the header printed the SERVER CLOCK, which is true of nothing on the page;
* the price cache called itself fresh as soon as it held any row dated today,
  so the first fetch of the morning ended refreshing for the day;
* the quant engine's memo key ignored the values in that row, so the ranking
  stayed frozen even when the loader underneath it did refresh; and
* when Yahoo returned nothing -- its normal response to a rate-limited host --
  the loader served the same frame indefinitely rather than reaching for the
  snapshot that carried the missing sessions.

The Yahoo cache and its snapshot recovery were removed with the Yahoo download
(TODO S10, 13 Oct 2026); their tests went with them. The settle rule and the
header tests below are still live.
"""
from datetime import date, datetime, time

import pytest

from src.core import startup_metrics as metrics
from src.core.market_time import INDIA_TZ, session_is_complete
from src.ui import components


def setup_function():
    metrics.reset_for_tests()


def _ist(y, m, d, hh, mm):
    return datetime(y, m, d, hh, mm, tzinfo=INDIA_TZ)


# ── A session is not a close until it closes ─────────────────────────────────

def test_a_past_session_is_settled():
    assert session_is_complete(date(2026, 8, 27), now=_ist(2026, 8, 28, 9, 0))


def test_a_future_session_is_never_settled():
    assert not session_is_complete(date(2026, 8, 31), now=_ist(2026, 8, 28, 23, 0))


def test_todays_session_is_open_during_market_hours():
    """The whole point: 11:00 IST is a running quote, not a result."""
    assert not session_is_complete(date(2026, 8, 28), now=_ist(2026, 8, 28, 11, 0))


def test_todays_session_settles_after_the_close():
    assert session_is_complete(date(2026, 8, 28), now=_ist(2026, 8, 28, 16, 30))


# ── The header must date the DATA, not the clock ─────────────────────────────

def _header(monkeypatch, today, **facts):
    """The header pill every page draws (``_status_pill_html``)."""
    for k, v in facts.items():
        metrics.note(k, v)
    import src.core.market_time as mt

    monkeypatch.setattr(mt, "ist_today", lambda: today)
    # Prices are judged against the session due by now, so pin the time too.
    monkeypatch.setattr(mt, "ist_now", lambda: datetime.combine(today, time(12, 0), tzinfo=mt.INDIA_TZ))
    return components._status_pill_html()


def test_the_header_shows_the_price_date_not_the_wall_clock(monkeypatch):
    pill = _header(monkeypatch, date(2026, 8, 31), price_as_of="2026-08-21")
    assert "21 Aug" in pill
    assert "31 Aug" not in pill


def test_a_stale_header_is_flagged_amber_and_counts_the_days(monkeypatch):
    pill = _header(monkeypatch, date(2026, 8, 31), price_as_of="2026-08-21")
    assert "hdr-pill-warn" in pill and "Prices · " in pill
    # The ribbon counts them: 24-28 Aug and 31 Aug, six sessions not covered.
    prices = next(i for i in components.data_freshness() if i["label"] == "Prices")
    assert components.age_phrase(prices) == " · 6 trading days behind"


def test_a_current_header_is_quiet(monkeypatch):
    pill = _header(monkeypatch, date(2026, 8, 31), price_as_of="2026-08-28")
    assert "hdr-pill-warn" not in pill
    assert "Prices · closes of " in pill and "28 Aug" in pill


def test_an_unstamped_pipeline_admits_it_rather_than_inventing_a_date(monkeypatch):
    pill = _header(monkeypatch, date(2026, 8, 31), price_path="cache_fresh")
    assert "hdr-pill-warn" in pill
    assert "date unknown" in pill
    assert "31 Aug" not in pill


# ── Wording, shared by the header and the ribbon ─────────────────────────────

def test_an_open_session_is_not_described_as_a_finished_today(monkeypatch):
    item = {"behind": 0, "is_today": True, "date": date(2026, 8, 28)}
    import src.core.market_time as mt

    monkeypatch.setattr(mt, "ist_now", lambda: _ist(2026, 8, 28, 11, 0))
    assert components.age_phrase(item) == " · today, session open"


def test_a_settled_today_is_simply_today(monkeypatch):
    item = {"behind": 0, "is_today": True, "date": date(2026, 8, 28)}
    import src.core.market_time as mt

    monkeypatch.setattr(mt, "ist_now", lambda: _ist(2026, 8, 28, 17, 0))
    assert components.age_phrase(item) == " · today"


@pytest.mark.parametrize(
    "item, expected",
    [
        ({"behind": None}, " · stale"),
        ({"behind": 0, "is_today": False}, " · latest session"),
        ({"behind": 1}, " · 1 trading day behind"),
        ({"behind": 4}, " · 4 trading days behind"),
    ],
)
def test_the_remaining_ages_keep_their_wording(item, expected):
    assert components.age_phrase(item) == expected
