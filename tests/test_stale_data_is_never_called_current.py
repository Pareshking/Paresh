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
"""
from datetime import date, datetime

import numpy as np
import pandas as pd
import pytest

from src.core import startup_metrics as metrics
from src.core.market_time import INDIA_TZ, session_is_complete
from src.loaders import price_loader, price_store
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


# ── The cache must keep refreshing while the session is open ─────────────────

def _freeze_cache_currency(monkeypatch, behind, complete):
    monkeypatch.setattr(price_loader, "trading_days_behind", lambda *_, **__: behind)
    monkeypatch.setattr(price_loader, "session_is_complete", lambda *_, **__: complete)


def test_an_open_session_does_not_make_the_cache_current(monkeypatch):
    _freeze_cache_currency(monkeypatch, behind=0, complete=False)
    assert price_loader._cache_is_current(date(2026, 8, 28)) is False


def test_a_closed_latest_session_makes_the_cache_current(monkeypatch):
    _freeze_cache_currency(monkeypatch, behind=0, complete=True)
    assert price_loader._cache_is_current(date(2026, 8, 28)) is True


def test_an_older_session_is_never_current(monkeypatch):
    _freeze_cache_currency(monkeypatch, behind=3, complete=True)
    assert price_loader._cache_is_current(date(2026, 8, 25)) is False


def test_a_cache_beyond_the_horizon_is_never_current(monkeypatch):
    _freeze_cache_currency(monkeypatch, behind=None, complete=True)
    assert price_loader._cache_is_current(date(2025, 1, 6)) is False


def test_an_open_session_is_re_requested_from_its_own_date(tmp_path, monkeypatch):
    """The partial row must be REPLACED, not skipped.

    Asking Yahoo from the day AFTER the last cached session is what froze the
    price: today's row was already there, so the only date that could have
    updated it was excluded from every later request.
    """
    idx = pd.bdate_range(end="2026-08-28", periods=4)
    cache_file = tmp_path / "prices.parquet"
    pd.DataFrame({"RELIANCE": [1.0, 2.0, 3.0, 4.0]}, index=idx).to_parquet(cache_file)

    monkeypatch.setattr(price_loader, "PRICES_FILE", str(cache_file))
    _freeze_cache_currency(monkeypatch, behind=0, complete=False)

    asked = {}

    def _fake_download(tickers, start, **kwargs):
        asked["start"] = start
        return pd.DataFrame()

    monkeypatch.setattr(price_loader.yf, "download", _fake_download)
    monkeypatch.setattr(price_loader, "_recover_stale_cache", lambda *a, **k: None)

    price_loader.fetch_price_history(["RELIANCE"])
    assert asked["start"] == "2026-08-28"


def test_a_closed_session_is_topped_up_from_the_next_day(tmp_path, monkeypatch):
    idx = pd.bdate_range(end="2026-08-28", periods=4)
    cache_file = tmp_path / "prices.parquet"
    pd.DataFrame({"RELIANCE": [1.0, 2.0, 3.0, 4.0]}, index=idx).to_parquet(cache_file)

    monkeypatch.setattr(price_loader, "PRICES_FILE", str(cache_file))
    # Settled, but no longer the latest session -- so a top-up is due.
    _freeze_cache_currency(monkeypatch, behind=1, complete=True)

    asked = {}

    def _fake_download(tickers, start, **kwargs):
        asked["start"] = start
        return pd.DataFrame()

    monkeypatch.setattr(price_loader.yf, "download", _fake_download)
    monkeypatch.setattr(price_loader, "_recover_stale_cache", lambda *a, **k: None)

    price_loader.fetch_price_history(["RELIANCE"])
    # The next CALENDAR day. yfinance's start is a calendar bound, so there is
    # nothing to gain by skipping the weekend -- only a trading calendar to get
    # wrong.
    assert asked["start"] == "2026-08-29"


# ── A future-dated row must not pin the cache forever ────────────────────────

def test_rows_dated_after_today_are_discarded(monkeypatch):
    monkeypatch.setattr(price_loader, "ist_today", lambda: date(2026, 8, 28))
    idx = pd.DatetimeIndex(["2026-08-26", "2026-08-27", "2026-08-28", "2026-09-04"])
    out = price_loader._drop_future_rows(pd.DataFrame({"A": [1.0] * 4}, index=idx))

    assert list(out.index) == list(pd.DatetimeIndex(idx[:3]))
    assert metrics.snapshot()["facts"]["price_future_rows_dropped"] == 1


def test_an_ordinary_frame_passes_through_untouched(monkeypatch):
    monkeypatch.setattr(price_loader, "ist_today", lambda: date(2026, 8, 28))
    frame = pd.DataFrame({"A": [1.0, 2.0]}, index=pd.bdate_range(end="2026-08-28", periods=2))
    assert price_loader._drop_future_rows(frame) is frame


# ── Snapshot recovery, and its restraint ─────────────────────────────────────

def _serve_snapshot(monkeypatch, frame):
    import io

    buf = io.BytesIO()
    frame.to_parquet(buf, compression="zstd")
    payload = buf.getvalue()

    class _Resp:
        status_code = 200

        def iter_content(self, chunk_size=1):
            yield payload

    monkeypatch.setattr(price_store.requests, "get", lambda url, **kw: _Resp())
    monkeypatch.setattr(price_store, "MIN_PLAUSIBLE_BYTES", 100)


def _frame(end, rows=6):
    idx = pd.bdate_range(end=end, periods=rows)
    return pd.DataFrame(
        np.arange(float(rows * 2)).reshape(rows, 2), index=idx, columns=["A", "B"]
    )


def test_a_newer_snapshot_is_adopted(tmp_path, monkeypatch):
    cache_file = tmp_path / "prices.parquet"
    cache_file.write_bytes(b"stale")
    monkeypatch.setattr(price_store, "PRICES_FILE", str(cache_file))
    _serve_snapshot(monkeypatch, _frame("2026-08-28"))

    got = price_store.snapshot_frame_if_newer(date(2026, 8, 21), "http://x")

    assert got is not None
    assert pd.Timestamp(got.index[-1]).date() == date(2026, 8, 28)
    assert pd.read_parquet(cache_file).equals(got)
    assert metrics.snapshot()["facts"]["price_recovery"] == "recovered_from_snapshot"


def test_a_snapshot_no_newer_than_the_cache_is_left_alone(tmp_path, monkeypatch):
    """Adopting an equal snapshot would discard a top-up Yahoo did deliver."""
    cache_file = tmp_path / "prices.parquet"
    cache_file.write_bytes(b"do not touch")
    monkeypatch.setattr(price_store, "PRICES_FILE", str(cache_file))
    _serve_snapshot(monkeypatch, _frame("2026-08-28"))

    assert price_store.snapshot_frame_if_newer(date(2026, 8, 28), "http://x") is None
    assert cache_file.read_bytes() == b"do not touch"
    assert metrics.snapshot()["facts"]["price_recovery"] == "snapshot_not_newer"


def test_a_rejected_snapshot_leaves_no_temporary_file(tmp_path, monkeypatch):
    cache_file = tmp_path / "prices.parquet"
    monkeypatch.setattr(price_store, "PRICES_FILE", str(cache_file))
    _serve_snapshot(monkeypatch, _frame("2026-08-28"))

    price_store.snapshot_frame_if_newer(date(2026, 8, 28), "http://x")
    assert list(tmp_path.glob("*.parquet")) == []


def test_recovery_is_not_attempted_one_day_behind(monkeypatch):
    """A morning before the session has produced anything is not an outage.

    Reaching for a ten-megabyte snapshot there would spend the bandwidth to be
    told what the cache already knows, every hour of every trading day.
    """
    monkeypatch.setattr(price_loader, "trading_days_behind", lambda *_, **__: 1)

    def _must_not_run(*_, **__):  # pragma: no cover - the assertion is that it does not
        raise AssertionError("the snapshot was fetched one trading day behind")

    monkeypatch.setattr(price_store, "snapshot_frame_if_newer", _must_not_run)
    assert price_loader._recover_stale_cache(pd.DataFrame(), date(2026, 8, 28)) is None


def test_a_failed_recovery_reports_itself_rather_than_going_quiet(monkeypatch):
    """"No new price data" in a log file is not a signal anyone sees."""
    monkeypatch.setattr(price_loader, "trading_days_behind", lambda *_, **__: 6)
    monkeypatch.setattr(price_store, "snapshot_frame_if_newer", lambda *a, **k: None)

    assert price_loader._recover_stale_cache(pd.DataFrame(), date(2026, 8, 21)) is None
    assert metrics.snapshot()["facts"]["price_path"] == "cache_stale_unrecovered"


# ── The header must date the DATA, not the clock ─────────────────────────────

def _header(monkeypatch, today, **facts):
    for k, v in facts.items():
        metrics.note(k, v)
    import src.core.market_time as mt

    monkeypatch.setattr(mt, "ist_today", lambda: today)
    return components.header_as_of()


def test_the_header_shows_the_price_date_not_the_wall_clock(monkeypatch):
    text, _ = _header(monkeypatch, date(2026, 8, 31), price_as_of="2026-08-21")
    assert "21 Aug 2026" in text
    assert "31 Aug" not in text


def test_a_stale_header_is_flagged_amber_and_counts_the_days(monkeypatch):
    text, color = _header(monkeypatch, date(2026, 8, 31), price_as_of="2026-08-21")
    assert color == "#d97706"
    assert "trading days behind" in text


def test_a_current_header_is_quiet(monkeypatch):
    text, color = _header(monkeypatch, date(2026, 8, 31), price_as_of="2026-08-28")
    assert color == "#64748b"
    assert "28 Aug 2026" in text


def test_an_unstamped_pipeline_admits_it_rather_than_inventing_a_date(monkeypatch):
    text, color = _header(monkeypatch, date(2026, 8, 31))
    assert text == "price date unknown"
    assert color == "#d97706"


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
