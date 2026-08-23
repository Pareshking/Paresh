"""Two ways the desk told the reader something untrue about its own data.

Both surfaced from the same screenshot: on Sunday 23 Aug the footer read
"Prices: 21 Aug · today". The DATE was right -- Friday 21 Aug was the most
recent session, the weekend has no data to fetch -- but "today" was not, and it
read as a broken pipeline. Chasing it turned up a second, real problem behind
it: the daily sync had been committing yesterday's market caps every day.
"""
from datetime import date

import pytest

from src.core import startup_metrics as metrics
from src.ui import components


def setup_function():
    metrics.reset_for_tests()


def _items(monkeypatch, today, **facts):
    for k, v in facts.items():
        metrics.note(k, v)
    import src.core.market_time as mt

    monkeypatch.setattr(mt, "ist_today", lambda: today)
    return {i["label"]: i for i in components.data_freshness()}


# ── "today" means today, not "the latest session" ───────────────────────────

SUNDAY = date(2026, 8, 23)
FRIDAY = date(2026, 8, 21)


def test_friday_data_read_on_sunday_is_current_but_not_today(monkeypatch):
    got = _items(monkeypatch, SUNDAY, price_as_of=FRIDAY.isoformat())["Prices"]
    assert got["behind"] == 0, "Friday is the most recent trading day"
    assert got["stale"] is False
    assert got["is_today"] is False


def test_same_day_data_really_is_today(monkeypatch):
    tuesday = date(2026, 8, 18)
    got = _items(monkeypatch, tuesday, price_as_of=tuesday.isoformat())["Prices"]
    assert got["behind"] == 0
    assert got["is_today"] is True


def _ribbon(monkeypatch, items) -> str:
    captured = []
    monkeypatch.setattr(components, "data_freshness", lambda: items)
    monkeypatch.setattr(components.st, "markdown", lambda *a, **k: captured.append(a[0]))
    components.render_freshness_ribbon()
    return captured[0]


def test_the_ribbon_does_not_call_a_weekend_reading_today(monkeypatch):
    html = _ribbon(monkeypatch, [
        {"label": "Prices", "as_of": "21 Aug", "behind": 0, "is_today": False,
         "stale": False, "source": None},
    ])
    assert "latest session" in html
    assert "today" not in html


def test_the_ribbon_still_says_today_when_it_is(monkeypatch):
    html = _ribbon(monkeypatch, [
        {"label": "Prices", "as_of": "18 Aug", "behind": 0, "is_today": True,
         "stale": False, "source": None},
    ])
    assert "today" in html
    assert "0 trading days" not in html


def test_a_reading_behind_the_latest_session_still_counts_days(monkeypatch):
    html = _ribbon(monkeypatch, [
        {"label": "Market caps", "as_of": "14 Aug", "behind": 3, "is_today": False,
         "stale": True, "source": None},
    ])
    assert "3 trading days behind" in html


# ── The daily sync must actually refresh what it commits ────────────────────

def test_the_daily_sync_does_not_reuse_the_market_cap_cache():
    """_is_mcap_cache_fresh() accepts a 30-hour-old cache and this job runs
    every 24, so honouring it meant committing yesterday's caps forever."""
    import ast
    import pathlib

    src = (pathlib.Path(__file__).resolve().parents[1] / "scripts/sync_data.py").read_text()
    tree = ast.parse(src)
    calls = [
        n for n in ast.walk(tree)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Name)
        and n.func.id == "fetch_market_caps"
    ]
    assert len(calls) == 1, "expected exactly one market-cap fetch in the sync"
    kw = {k.arg: k.value for k in calls[0].keywords}
    assert "force_refresh" in kw
    assert isinstance(kw["force_refresh"], ast.Constant)
    assert kw["force_refresh"].value is True


def test_prices_stay_incremental():
    """A daily full 2y re-download would be slow and rude; only the weekly
    FORCE_FULL run should do that."""
    import pathlib

    src = (pathlib.Path(__file__).resolve().parents[1] / "scripts/sync_data.py").read_text()
    assert "fetch_price_history(symbols, period=\"2y\", force_refresh=FORCE_FULL)" in src


# ── The cache window must sit below the sync cadence ────────────────────────

def test_the_cache_window_is_shorter_than_the_daily_cadence():
    """At 30 hours against a 24-hour job, a cache written on one nightly run
    was still 'fresh' on the next, so the snapshot could never refresh."""
    from src.loaders.mcap_loader import MCAP_CACHE_MAX_AGE_S

    assert MCAP_CACHE_MAX_AGE_S < 24 * 3600, "must expire before the next run"
    # Enough slack for a late run: GitHub has been firing this cron ~28 min behind.
    assert MCAP_CACHE_MAX_AGE_S >= 20 * 3600, "must survive a same-day app restart"
    assert MCAP_CACHE_MAX_AGE_S == 22 * 3600


@pytest.mark.parametrize("age_hours,expected_fresh", [
    (0.5, True),    # minutes after a sync
    (12, True),     # same-day app restart
    (21.5, True),   # a late run, still inside the window
    (23, False),    # the next nightly run must see it as stale
    (30, False),    # what used to pass
])
def test_cache_freshness_by_age(monkeypatch, tmp_path, age_hours, expected_fresh):
    import datetime as _dt

    import pandas as pd

    from src.loaders import mcap_loader

    cache = tmp_path / "mcap_nse.parquet"
    pd.DataFrame({
        "Symbol": ["RELIANCE"],
        "MarketCap": [1.0],
        "TradeDate": ["2026-08-21"],
        "LastUpdated": [_dt.datetime.now() - _dt.timedelta(hours=age_hours)],
    }).to_parquet(cache)
    monkeypatch.setattr(mcap_loader, "MCAP_PR_FILE", str(cache))

    assert mcap_loader._is_mcap_cache_fresh() is expected_fresh
