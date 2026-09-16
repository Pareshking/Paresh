"""The price cache must be able to CHANGE ITS MIND about settled history.

Two independent failures, both invisible from every other test in this suite,
both measured in the published production snapshot before this file existed.

THE GATE. The incremental path asked Yahoo for a session that had not happened
yet. Production logged it on 2026-09-16 at 06:43 IST -- two and a half hours
before the NSE open -- as a 25-second download of 750 tickers that returned
nothing: 499 rows in, 499 rows out. Every cold start before the open paid it.

THE HEAL. The same path is append-only. It asks from the last cached date
FORWARD, so a close the vendor backfills later is never requested again, and
the merge took the vendor's whole row on a duplicated date -- erasing cells the
cache already held when one ticker in the batch came back empty. The snapshot
carried 572 missing closes across 337 symbols from this, clustered on five
dates where 11-18% of the universe vanished at once.
"""

from datetime import date, datetime

import numpy as np
import pandas as pd
import pytest

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


# ── The gate as the loader uses it ───────────────────────────────────────────

def test_a_pre_open_cold_start_makes_no_network_call(tmp_path, monkeypatch):
    """The whole point: no yf.download before the session is downloadable."""
    from src.loaders import price_loader

    idx = pd.date_range("2026-09-01", "2026-09-15", freq="B")
    cached = pd.DataFrame({"AAA": np.linspace(100, 110, len(idx))}, index=idx)
    path = tmp_path / "prices.parquet"
    cached.to_parquet(path)
    monkeypatch.setattr(price_loader, "PRICES_FILE", str(path))

    called = []
    monkeypatch.setattr(
        price_loader.yf, "download",
        lambda *a, **k: called.append(1) or pd.DataFrame(),
    )
    # 06:43 IST on the 16th, exactly as production logged it.
    monkeypatch.setattr(
        price_loader, "last_downloadable_session", lambda: date(2026, 9, 15)
    )
    monkeypatch.setattr(price_loader, "_cache_is_current", lambda d: False)

    out = price_loader.fetch_price_history(["AAA"], period="2y")
    assert not called, "asked the vendor for a session that has not settled"
    assert len(out) == len(cached)


def test_a_healing_run_ignores_the_gate(tmp_path, monkeypatch):
    """heal_days is not chasing the newest bar; it is re-reading old ones."""
    from src.loaders import price_loader

    idx = pd.date_range("2026-09-01", "2026-09-15", freq="B")
    cached = pd.DataFrame({"AAA": np.linspace(100, 110, len(idx))}, index=idx)
    path = tmp_path / "prices.parquet"
    cached.to_parquet(path)
    monkeypatch.setattr(price_loader, "PRICES_FILE", str(path))

    called = []

    def _dl(*a, **k):
        called.append(k.get("start"))
        return pd.DataFrame()

    monkeypatch.setattr(price_loader.yf, "download", _dl)
    monkeypatch.setattr(
        price_loader, "last_downloadable_session", lambda: date(2026, 9, 15)
    )
    monkeypatch.setattr(price_loader, "_cache_is_current", lambda d: False)
    monkeypatch.setattr(price_loader, "_recover_stale_cache", lambda *a, **k: None)

    price_loader.fetch_price_history(["AAA"], period="2y", heal_days=45)
    assert called, "a healing run must still reach the vendor"
    assert pd.Timestamp(called[0]) <= pd.Timestamp("2026-08-01"), (
        f"heal_days=45 should reach back ~45 days, asked from {called[0]}"
    )


# ── The healing merge ────────────────────────────────────────────────────────

def _run_merge(monkeypatch, tmp_path, cached, new_data, **kw):
    from src.loaders import price_loader

    path = tmp_path / "prices.parquet"
    cached.to_parquet(path)
    monkeypatch.setattr(price_loader, "PRICES_FILE", str(path))
    monkeypatch.setattr(price_loader.yf, "download", lambda *a, **k: new_data)
    monkeypatch.setattr(price_loader, "_cache_is_current", lambda d: False)
    monkeypatch.setattr(
        price_loader, "last_downloadable_session", lambda: date(2030, 1, 1)
    )
    return price_loader.fetch_price_history(list(cached.columns), **kw)


def test_a_backfilled_close_reaches_the_cache(tmp_path, monkeypatch):
    """The user's case: a close missing on the 10th, filled in by the vendor later.

    Append-only, this could never land -- the top-up asked from the 15th
    forward and the 10th was never requested again.
    """
    idx = pd.date_range("2026-09-08", "2026-09-15", freq="B")
    cached = pd.DataFrame({"AAA": [100.0, 101.0, np.nan, 103.0, 104.0, 105.0]}, index=idx)
    assert cached["AAA"].isna().sum() == 1

    new_data = pd.DataFrame({"AAA": [100.0, 101.0, 102.5, 103.0, 104.0, 105.0]}, index=idx)
    out = _run_merge(monkeypatch, tmp_path, cached, new_data, heal_days=45)

    assert out["AAA"].isna().sum() == 0, "the hole survived a healing run"
    assert out.loc[pd.Timestamp("2026-09-10"), "AAA"] == pytest.approx(102.5)


def test_a_vendor_hole_never_erases_a_close_the_cache_already_had(tmp_path, monkeypatch):
    """The bug that CREATED the 572 gaps.

    keep="last" on a duplicated date takes the vendor's entire row. One
    rate-limited ticker therefore deleted good history, and the append-only
    path guaranteed nobody would ever ask for it again.
    """
    idx = pd.date_range("2026-09-08", "2026-09-15", freq="B")
    cached = pd.DataFrame({"AAA": [100.0, 101.0, 102.0, 103.0, 104.0, 105.0]}, index=idx)
    # The vendor answers the overlap with nothing for AAA.
    new_data = pd.DataFrame({"AAA": [np.nan] * len(idx)}, index=idx)

    out = _run_merge(monkeypatch, tmp_path, cached, new_data, heal_days=45)
    assert out["AAA"].isna().sum() == 0, "a vendor blank erased a cached close"
    assert out.loc[pd.Timestamp("2026-09-10"), "AAA"] == pytest.approx(102.0)


def test_a_revised_close_still_wins_over_the_cached_one(tmp_path, monkeypatch):
    """Healing must not become stickiness: where the vendor HAS a value, it wins."""
    idx = pd.date_range("2026-09-08", "2026-09-15", freq="B")
    cached = pd.DataFrame({"AAA": [100.0, 101.0, 102.0, 103.0, 104.0, 105.0]}, index=idx)
    revised = cached.copy()
    revised.loc[pd.Timestamp("2026-09-15"), "AAA"] = 107.5

    out = _run_merge(monkeypatch, tmp_path, cached, revised, heal_days=45)
    assert out.loc[pd.Timestamp("2026-09-15"), "AAA"] == pytest.approx(107.5)


# ── A full refresh must not be able to LOSE history ──────────────────────────
#
# The FORCE_FULL path wrote straight over the cache, which made the widest
# download in the system the only one with no protection. A batch of 100 that
# comes back empty, or a ticker answering with some sessions missing, replaced
# good stored history with a worse copy and nothing noticed -- the retry loop
# only catches tickers absent ENTIRELY, and a partial series looks like a
# successful fetch.
#
# Survivable while the weekly run published nothing. Not survivable once it
# publishes the snapshot production seeds from: one bad Friday would hand every
# reader a thinner history than the one it replaced, and the append-only daily
# path could never fill it back in.

def _full_refresh(monkeypatch, tmp_path, cached, downloaded):
    from src.loaders import price_loader

    path = tmp_path / "prices.parquet"
    cached.to_parquet(path)
    monkeypatch.setattr(price_loader, "PRICES_FILE", str(path))
    monkeypatch.setattr(price_loader.yf, "download", lambda *a, **k: downloaded)
    monkeypatch.setattr(price_loader.time, "sleep", lambda *_: None)
    return price_loader.fetch_price_history(
        list(cached.columns), period="2y", force_refresh=True
    )


def _frame(cols, idx, value=100.0):
    return pd.DataFrame({c: [value] * len(idx) for c in cols}, index=idx)


def test_a_partial_full_refresh_keeps_the_sessions_it_did_not_return(tmp_path, monkeypatch):
    """The exact hazard: the vendor answers, but with holes."""
    idx = pd.date_range("2026-09-01", "2026-09-15", freq="B")
    cached = _frame(["AAA", "BBB"], idx, 100.0)

    holed = cached.copy()
    holed.loc[idx[3], "AAA"] = np.nan          # vendor dropped one session
    holed.loc[idx[5], "BBB"] = np.nan

    out = _full_refresh(monkeypatch, tmp_path, cached, holed)
    assert out.loc[idx[3], "AAA"] == pytest.approx(100.0), "a full refresh lost a session"
    assert out.loc[idx[5], "BBB"] == pytest.approx(100.0), "a full refresh lost a session"
    assert out.isna().sum().sum() == 0


def test_a_full_refresh_that_drops_a_ticker_keeps_its_history(tmp_path, monkeypatch):
    """A failed batch must not delete 100 symbols from the record."""
    idx = pd.date_range("2026-09-01", "2026-09-15", freq="B")
    cached = _frame(["AAA", "BBB"], idx, 100.0)
    only_one = cached[["AAA"]].copy()

    out = _full_refresh(monkeypatch, tmp_path, cached, only_one)
    assert "BBB" in out.columns, "a full refresh deleted a ticker it failed to fetch"
    assert out["BBB"].notna().all()


def test_a_restatement_still_wins_on_a_full_refresh(tmp_path, monkeypatch):
    """Merging must not become stickiness.

    Landing a vendor restatement is the entire purpose of a full refresh, so
    wherever the download HAS a value it must replace the cached one.
    """
    idx = pd.date_range("2026-09-01", "2026-09-15", freq="B")
    cached = _frame(["AAA"], idx, 300.0)
    restated = _frame(["AAA"], idx, 100.0)      # 1:3 split, adjusted by the vendor

    out = _full_refresh(monkeypatch, tmp_path, cached, restated)
    assert out["AAA"].tolist() == pytest.approx([100.0] * len(out)), (
        "the full refresh kept pre-restatement prices; restatements can no longer land"
    )


def test_a_full_refresh_that_reaches_further_back_keeps_the_extra_depth(tmp_path, monkeypatch):
    """A 10y refresh over a 2y cache must end up with 10y, not 2y."""
    short = pd.date_range("2026-09-01", "2026-09-15", freq="B")
    long = pd.date_range("2026-08-01", "2026-09-15", freq="B")
    cached = _frame(["AAA"], short, 100.0)
    deeper = _frame(["AAA"], long, 100.0)

    out = _full_refresh(monkeypatch, tmp_path, cached, deeper)
    assert len(out) == len(long), "the full refresh lost the depth it just fetched"


def test_the_shortfall_is_reported_not_silent(tmp_path, monkeypatch, caplog):
    """A thin refresh must say so; it is the only signal anyone would get."""
    import logging

    idx = pd.date_range("2026-09-01", "2026-09-15", freq="B")
    cached = _frame(["AAA", "BBB"], idx, 100.0)
    only_one = cached[["AAA"]].copy()

    with caplog.at_level(logging.WARNING):
        _full_refresh(monkeypatch, tmp_path, cached, only_one)
    assert any("thinner than the cache" in r.message for r in caplog.records), (
        "a full refresh came back short and logged nothing"
    )
