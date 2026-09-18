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


def test_a_totally_failed_refresh_leaves_the_cache_untouched(tmp_path, monkeypatch):
    """The other half of the question: what if the refresh gets NOTHING?

    This one was already safe, and it is worth pinning so it stays that way.
    fetch_price_history returns an empty frame BEFORE any write when every
    batch comes back empty, so the cache on disk is never opened -- and
    sync_data republishes from the FILE, not from the returned frame, so a
    dead Friday republishes last week's good snapshot rather than nothing.

    The dangerous case was never total failure. It was partial success, which
    looks identical to a good fetch from the outside.
    """
    from src.loaders import price_loader

    idx = pd.date_range("2026-09-01", "2026-09-15", freq="B")
    cached = _frame(["AAA", "BBB"], idx, 100.0)
    path = tmp_path / "prices.parquet"
    cached.to_parquet(path)
    before = path.read_bytes()

    monkeypatch.setattr(price_loader, "PRICES_FILE", str(path))
    monkeypatch.setattr(price_loader.yf, "download", lambda *a, **k: pd.DataFrame())
    monkeypatch.setattr(price_loader.time, "sleep", lambda *_: None)

    out = price_loader.fetch_price_history(["AAA", "BBB"], period="2y", force_refresh=True)
    assert out.empty, "a failed refresh should report empty, not invent data"
    assert path.read_bytes() == before, "a failed refresh overwrote the cache"

    survived = pd.read_parquet(path)
    assert list(survived.columns) == ["AAA", "BBB"] and survived.notna().all().all()


# ── An in-progress session must never reach the cache ────────────────────────
#
# The cache is assumed settled by everything downstream: the download gate
# compares its last date against the last settled session, the precomputed
# ranking fingerprints the frame and expects the same bytes tomorrow, and
# "price as of" on the page is a claim about a CLOSE.
#
# heal_days is what broke that. A healing run skips the download gate on
# purpose -- it is reaching BACKWARD for sessions already held -- and nothing
# stopped the same request also reaching forward into a session that had barely
# opened. Dispatched by hand at 09:10 IST on 2026-09-16, the nightly job wrote
# a row where 587 of 750 symbols had printed and 163 had not, and the
# precompute published a 587-row ranking from it. The frame and the table
# agreed with each other, so the contract had nothing to object to.

def test_an_in_progress_session_is_dropped(monkeypatch):
    from src.loaders import price_loader

    idx = pd.date_range("2026-09-14", "2026-09-16", freq="B")
    frame = _frame(["AAA"], idx, 100.0)
    # 09:10 IST on the 16th: the session has opened but is nowhere near settled.
    monkeypatch.setattr(
        price_loader, "session_is_complete",
        lambda d, **k: d < date(2026, 9, 16),
    )
    out = price_loader._drop_unsettled_rows(frame)
    assert pd.Timestamp("2026-09-16") not in out.index, (
        "an in-progress session survived into the cache"
    )
    assert pd.Timestamp("2026-09-15") in out.index, "a settled session was dropped"


def test_a_healing_run_cannot_write_an_unsettled_session(tmp_path, monkeypatch):
    """The whole path, not just the helper: heal_days must not smuggle one in."""
    from src.loaders import price_loader

    idx = pd.date_range("2026-09-01", "2026-09-15", freq="B")
    cached = _frame(["AAA", "BBB"], idx, 100.0)
    path = tmp_path / "prices.parquet"
    cached.to_parquet(path)
    monkeypatch.setattr(price_loader, "PRICES_FILE", str(path))

    # The vendor answers with the healed window PLUS a half-formed today.
    today = pd.Timestamp("2026-09-16")
    fresh = _frame(["AAA", "BBB"], idx.append(pd.DatetimeIndex([today])), 100.0)
    fresh.loc[today, "BBB"] = np.nan            # 1 of 2 symbols has not printed

    monkeypatch.setattr(price_loader.yf, "download", lambda *a, **k: fresh)
    monkeypatch.setattr(price_loader, "_cache_is_current", lambda d: False)
    monkeypatch.setattr(price_loader, "_recover_stale_cache", lambda *a, **k: None)
    monkeypatch.setattr(
        price_loader, "session_is_complete",
        lambda d, **k: d < date(2026, 9, 16),
    )

    out = price_loader.fetch_price_history(["AAA", "BBB"], period="2y", heal_days=45)
    assert today not in out.index, (
        "a healing run wrote an in-progress session; this is what produced the "
        "587-row ranking on 2026-09-16"
    )
    assert out.notna().all().all(), "the settled history was disturbed"


def test_a_settled_session_is_kept(monkeypatch):
    """The guard must not eat real data once the bar has settled."""
    from src.loaders import price_loader

    idx = pd.date_range("2026-09-14", "2026-09-16", freq="B")
    frame = _frame(["AAA"], idx, 100.0)
    monkeypatch.setattr(price_loader, "session_is_complete", lambda d, **k: True)
    out = price_loader._drop_unsettled_rows(frame)
    assert len(out) == len(frame)


# ── An exchange holiday the vendor answered for anyway is not a session ──────
#
# clean_holidays drops a row only when more than 70% of the universe is NaN --
# a genuine exchange-wide blank. A holiday where Yahoo answers for 460 of 750
# symbols sits at 39% NaN and sails through, and the engine then scores a
# one-day move INTO a day nobody traded and another back out of it.
#
# 2026-09-14 was an NSE holiday and is exactly that. It arrived through the
# healing path: the incremental top-up had skipped it (the cache jumped 09-11
# to 09-15, and being append-only it could never revisit) so the accident of
# that bug was hiding this one. Re-requesting 45 days of settled history found
# the row Yahoo was offering and merged it in, and the published snapshot and
# the precomputed ranking both carried it.
#
# Measured on the live 500-session frame, the separation is not marginal:
#   2026-09-14 (holiday)        61.3%   alone in its band
#   2026-07-20 (thinnest real)  82.0%
#   496 of 500 sessions         >82%
#   oldest rows                 90.3%   (a tenth of the universe not yet listed)

def _session(n_have, n_total=750):
    import numpy as _np
    vals = [100.0] * n_have + [_np.nan] * (n_total - n_have)
    return {f"S{i}": vals[i] for i in range(n_total)}


def test_a_holiday_the_vendor_answered_for_is_dropped():
    from src.loaders.price_loader import _drop_phantom_sessions

    idx = pd.to_datetime(["2026-09-11", "2026-09-14", "2026-09-15"])
    frame = pd.DataFrame(
        [_session(750), _session(460), _session(750)], index=idx
    )
    out = _drop_phantom_sessions(frame)
    assert pd.Timestamp("2026-09-14") not in out.index, (
        "the holiday survived; the engine will score a move into a day nobody traded"
    )
    assert len(out) == 2


def test_a_thin_but_real_session_is_kept():
    """2026-07-20 at 82% is a real trading day with a partial vendor fetch.

    Dropping it would throw away 615 genuine closes to avoid 135 gaps, which
    is the wrong trade and the opposite of what the healing path is for.
    """
    from src.loaders.price_loader import _drop_phantom_sessions

    idx = pd.to_datetime(["2026-07-17", "2026-07-20", "2026-07-21"])
    frame = pd.DataFrame(
        [_session(750), _session(615), _session(750)], index=idx
    )
    out = _drop_phantom_sessions(frame)
    assert len(out) == 3, "a real trading day was discarded as a holiday"


def test_the_oldest_rows_of_the_window_are_kept():
    """They read low only because part of today's universe had not listed."""
    from src.loaders.price_loader import _drop_phantom_sessions

    idx = pd.to_datetime(["2024-09-16", "2024-09-17"])
    frame = pd.DataFrame([_session(677), _session(677)], index=idx)
    assert len(_drop_phantom_sessions(frame)) == 2


def test_a_narrow_frame_is_left_alone():
    """The threshold is a claim about a universe, not about two columns."""
    from src.loaders.price_loader import _drop_phantom_sessions

    idx = pd.to_datetime(["2026-09-14", "2026-09-15"])
    frame = pd.DataFrame({"AAA": [np.nan, 1.0], "BBB": [np.nan, 2.0]}, index=idx)
    assert len(_drop_phantom_sessions(frame)) == 2


def test_the_live_frame_loses_exactly_the_holiday():
    """The real separation, pinned: everything kept clears 82%."""
    from src.loaders.price_loader import MIN_SESSION_COVERAGE

    assert 0.65 <= MIN_SESSION_COVERAGE <= 0.80, (
        f"MIN_SESSION_COVERAGE={MIN_SESSION_COVERAGE} no longer sits between the "
        "61.3% holiday and the 82.0% thinnest real session"
    )


# ── The exchange outranks the coverage guess ─────────────────────────────────
#
# Counting how much of the universe has a price CANNOT tell a holiday from a
# vendor that has not finished publishing. The same two dates, measured a day
# apart, prove no threshold can:
#
#                        2026-09-16 (traded)   2026-09-14 (holiday)
#   during the sync              20%                   61%
#   a day later                  63%                   86%
#
# On 2026-09-16 a 70% floor dropped the real session. By 2026-09-17 the same
# floor would keep the holiday and drop the real session again. Yahoo backfills
# a closed day as readily as an open one.
#
# NSE settles it, and the job ALREADY ASKS -- it downloaded the bhavcopy FOR
# 2026-09-16 three seconds after dropping that session at 20% coverage.

def test_a_session_nse_confirmed_is_never_dropped(monkeypatch):
    """2026-09-16: 20% coverage, but NSE published a bhavcopy for it."""
    from src.loaders import price_loader

    monkeypatch.setattr(
        price_loader, "load_confirmed", lambda: {"2026-09-16"}, raising=False
    )
    import src.loaders.trading_days as td
    monkeypatch.setattr(td, "load_confirmed", lambda path=None: {"2026-09-16"})

    idx = pd.to_datetime(["2026-09-15", "2026-09-16"])
    frame = pd.DataFrame([_session(750), _session(150)], index=idx)   # 100%, 20%
    out = price_loader._drop_phantom_sessions(frame)
    assert pd.Timestamp("2026-09-16") in out.index, (
        "a session NSE confirmed as a trading day was deleted on vendor coverage"
    )


def test_an_unconfirmed_thin_session_still_falls_to_the_floor(monkeypatch):
    """2026-09-14: NSE never answered (403), so the floor still applies."""
    from src.loaders import price_loader
    import src.loaders.trading_days as td

    monkeypatch.setattr(td, "load_confirmed", lambda path=None: {"2026-09-16"})

    idx = pd.to_datetime(["2026-09-14", "2026-09-16"])
    frame = pd.DataFrame([_session(460), _session(150)], index=idx)   # 61%, 20%
    out = price_loader._drop_phantom_sessions(frame)
    assert pd.Timestamp("2026-09-14") not in out.index, "the unconfirmed holiday survived"
    assert pd.Timestamp("2026-09-16") in out.index, "the confirmed session was dropped"


def test_an_empty_record_changes_nothing(monkeypatch):
    """Before the first confirmation lands, behaviour is exactly as before."""
    from src.loaders import price_loader
    import src.loaders.trading_days as td

    monkeypatch.setattr(td, "load_confirmed", lambda path=None: set())
    idx = pd.to_datetime(["2026-09-15", "2026-09-16"])
    frame = pd.DataFrame([_session(750), _session(150)], index=idx)
    out = price_loader._drop_phantom_sessions(frame)
    assert pd.Timestamp("2026-09-16") not in out.index


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

def test_a_recorded_holiday_is_dropped_at_any_coverage(monkeypatch):
    """The three coverages 2026-09-14 actually showed, one test each."""
    from src.loaders import price_loader
    import src.loaders.trading_days as td

    monkeypatch.setattr(td, "load_confirmed", lambda path=None: set())
    monkeypatch.setattr(td, "load_closed", lambda path=None: {"2026-09-14"})

    for n_have, pct in ((460, "61%"), (645, "86%"), (551, "73.5%")):
        idx = pd.to_datetime(["2026-09-11", "2026-09-14", "2026-09-15"])
        frame = pd.DataFrame(
            [_session(750), _session(n_have), _session(750)], index=idx
        )
        out = price_loader._drop_phantom_sessions(frame)
        assert pd.Timestamp("2026-09-14") not in out.index, (
            f"the recorded holiday survived at {pct} coverage"
        )
        assert len(out) == 2, "a real session was dropped alongside the holiday"


def test_a_recorded_holiday_is_dropped_even_at_full_coverage(monkeypatch):
    """Coverage is not consulted at all for a date on the closed record.

    The vendor reaching 100% on a holiday is the end state of backfill, not
    evidence of a session. Nothing about 750/750 makes the market have opened.
    """
    from src.loaders import price_loader
    import src.loaders.trading_days as td

    monkeypatch.setattr(td, "load_confirmed", lambda path=None: set())
    monkeypatch.setattr(td, "load_closed", lambda path=None: {"2026-09-14"})

    idx = pd.to_datetime(["2026-09-11", "2026-09-14", "2026-09-15"])
    frame = pd.DataFrame([_session(750)] * 3, index=idx)
    out = price_loader._drop_phantom_sessions(frame)
    assert pd.Timestamp("2026-09-14") not in out.index
    assert len(out) == 2


def test_a_closure_and_a_thin_real_session_are_handled_in_one_pass(monkeypatch):
    """Both halves of the record at once -- the case production actually hit.

    2026-09-17 sat at 20% and was dropped; 2026-09-14 sat at 73.5% and was
    kept. Exactly backwards, and both wrong in the same frame.
    """
    from src.loaders import price_loader
    import src.loaders.trading_days as td

    monkeypatch.setattr(td, "load_confirmed", lambda path=None: {"2026-09-17"})
    monkeypatch.setattr(td, "load_closed", lambda path=None: {"2026-09-14"})

    idx = pd.to_datetime(["2026-09-14", "2026-09-15", "2026-09-17"])
    frame = pd.DataFrame(
        [_session(551), _session(750), _session(150)], index=idx  # 73.5%, 100%, 20%
    )
    out = price_loader._drop_phantom_sessions(frame)
    assert pd.Timestamp("2026-09-14") not in out.index, "the holiday was kept again"
    assert pd.Timestamp("2026-09-17") in out.index, "the real session was dropped again"


def test_an_empty_closure_record_changes_nothing(monkeypatch):
    """With nothing recorded closed, the floor behaves exactly as before."""
    from src.loaders import price_loader
    import src.loaders.trading_days as td

    monkeypatch.setattr(td, "load_confirmed", lambda path=None: set())
    monkeypatch.setattr(td, "load_closed", lambda path=None: set())

    idx = pd.to_datetime(["2026-09-14", "2026-09-15"])
    frame = pd.DataFrame([_session(460), _session(750)], index=idx)
    out = price_loader._drop_phantom_sessions(frame)
    assert pd.Timestamp("2026-09-14") not in out.index   # 61%, below the floor
    assert pd.Timestamp("2026-09-15") in out.index


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
