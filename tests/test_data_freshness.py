"""Footer must state how old each data source is, in trading days.

Market caps are served from a snapshot the daily sync commits. If that sync
fails, production would otherwise serve yesterday's figures with nothing on
screen saying so.
"""
from datetime import date

import pytest

from src.core import startup_metrics as metrics
from src.ui.components import data_freshness


def setup_function():
    metrics.reset_for_tests()


def _freshness(monkeypatch, today, **facts):
    for k, v in facts.items():
        metrics.note(k, v)
    import src.core.market_time as mt

    monkeypatch.setattr(mt, "ist_today", lambda: today)
    return {i["label"]: i for i in data_freshness()}


def test_same_day_data_is_not_stale(monkeypatch):
    got = _freshness(monkeypatch, date(2026, 8, 18), price_as_of="2026-08-18")
    assert got["Prices"]["stale"] is False
    assert got["Prices"]["behind"] == 0


def test_monday_showing_friday_is_current_not_stale(monkeypatch):
    """The whole reason for counting trading days rather than calendar days."""
    got = _freshness(monkeypatch, date(2026, 8, 17), mcap_as_of="2026-08-14")
    assert got["Market caps"]["behind"] == 1
    assert got["Market caps"]["stale"] is False


def test_a_source_several_trading_days_behind_is_stale(monkeypatch):
    got = _freshness(monkeypatch, date(2026, 8, 18), mcap_as_of="2026-08-11")
    assert got["Market caps"]["stale"] is True
    assert got["Market caps"]["behind"] >= 2


def test_very_old_data_is_stale_even_beyond_the_horizon(monkeypatch):
    got = _freshness(monkeypatch, date(2026, 8, 18), price_as_of="2026-01-05")
    assert got["Prices"]["stale"] is True
    assert got["Prices"]["behind"] is None


def test_delivery_tolerates_an_extra_day(monkeypatch):
    """Delivery publishes later than the rest, so one more day is normal."""
    got = _freshness(monkeypatch, date(2026, 8, 18), delivery_as_of="2026-08-14")
    assert got["Delivery"]["behind"] == 2
    assert got["Delivery"]["stale"] is False


def test_absent_source_is_simply_not_reported(monkeypatch):
    assert _freshness(monkeypatch, date(2026, 8, 18)) == {}


def test_unparseable_date_is_skipped_rather_than_raising(monkeypatch):
    assert _freshness(monkeypatch, date(2026, 8, 18), price_as_of="not-a-date") == {}


def test_every_source_is_reported_together(monkeypatch):
    got = _freshness(
        monkeypatch, date(2026, 8, 18),
        price_as_of="2026-08-18", mcap_as_of="2026-08-17", delivery_as_of="2026-08-17",
    )
    assert set(got) == {"Prices", "Market caps", "Delivery"}
    assert all(i["stale"] is False for i in got.values())


def test_cache_fresh_path_stamps_the_as_of_date(tmp_path, monkeypatch):
    """Exercise a real return path rather than scanning the source text.

    "Prices" was absent from the footer entirely because no code path ever
    wrote price_as_of -- the freshness bar looked healthy while silently
    omitting the source that matters most.
    """
    import pandas as pd

    from src.core import startup_metrics as metrics
    from src.loaders import price_loader

    idx = pd.bdate_range(end="2026-08-17", periods=4)
    cached = pd.DataFrame({"RELIANCE": [1.0, 2.0, 3.0, 4.0]}, index=idx)
    cache_file = tmp_path / "prices.parquet"
    cached.to_parquet(cache_file)

    monkeypatch.setattr(price_loader, "PRICES_FILE", str(cache_file))
    # Make the cache look current so the cache_fresh branch is taken.
    monkeypatch.setattr(price_loader, "ist_today", lambda: idx[-1].date())

    out = price_loader.fetch_price_history(["RELIANCE"])

    assert not out.empty
    facts = metrics.snapshot()["facts"]
    assert facts["price_path"] == "cache_fresh"
    assert facts["price_as_of"] == "2026-08-17"


def test_note_price_as_of_stamps_the_last_session(monkeypatch):
    import pandas as pd

    from src.core import startup_metrics as metrics
    from src.loaders.price_loader import _note_price_as_of

    idx = pd.bdate_range(end="2026-08-17", periods=5)
    _note_price_as_of(pd.DataFrame({"A": [1.0] * 5}, index=idx))
    assert metrics.snapshot()["facts"]["price_as_of"] == "2026-08-17"


def test_note_price_as_of_is_silent_on_an_empty_frame():
    import pandas as pd

    from src.loaders.price_loader import _note_price_as_of

    _note_price_as_of(pd.DataFrame())      # must not raise
    _note_price_as_of(None)                # must not raise


def test_prices_appear_in_the_footer_sources(monkeypatch):
    from src.ui import components

    monkeypatch.setattr(
        components, "_FRESHNESS_SOURCES", components._FRESHNESS_SOURCES
    )
    keys = [entry[0] for entry in components._FRESHNESS_SOURCES]
    assert "price_as_of" in keys
    assert "mcap_as_of" in keys
    assert "ath_as_of" in keys


# ── Every source in use gets a chip, dated or not ───────────────────────────

def _freshness_with(monkeypatch, facts):
    from src.core import startup_metrics as metrics
    from src.ui import components

    monkeypatch.setattr(metrics, "snapshot", lambda: {"facts": facts})
    return {i["label"]: i for i in components.data_freshness()}


def test_market_caps_appear_even_when_the_snapshot_carries_no_date(monkeypatch):
    """The committed snapshot predated AsOf stamping, so the chip vanished.

    A source silently missing from the freshness bar is the failure the bar
    exists to prevent -- the reader sees a clean row of dates and cannot tell
    that a source is being used undated.
    """
    items = _freshness_with(monkeypatch, {
        "price_as_of": "2026-08-18", "price_path": "cache_fresh",
        "mcap_path": "repo_snapshot",          # loaded, but no AsOf column
    })
    assert "Market caps" in items
    assert items["Market caps"]["as_of"] == "date unknown"
    assert items["Market caps"]["stale"] is True


def test_all_time_highs_are_reported_as_a_source(monkeypatch):
    items = _freshness_with(monkeypatch, {
        "ath_as_of": "2026-08-18", "ath_path": "repo_snapshot",
    })
    assert "All-time highs" in items
    assert items["All-time highs"]["as_of"] == "18 Aug"
    assert items["All-time highs"]["stale"] is False


def test_a_missing_ath_snapshot_says_the_column_is_not_all_time(monkeypatch):
    """The fallback is a two-year high; the ribbon must not imply otherwise."""
    items = _freshness_with(monkeypatch, {"ath_path": "absent"})
    assert "All-time highs" in items
    assert "not all-time" in items["All-time highs"]["as_of"]
    assert items["All-time highs"]["stale"] is True


def test_a_source_that_was_never_loaded_is_not_invented(monkeypatch):
    """No date and no loader report means the source is genuinely absent."""
    items = _freshness_with(monkeypatch, {"price_as_of": "2026-08-18"})
    assert "Market caps" not in items
    assert "Delivery" not in items


def test_all_four_sources_report_together(monkeypatch):
    items = _freshness_with(monkeypatch, {
        "price_as_of": "2026-08-18", "price_path": "cache_fresh",
        "mcap_as_of": "2026-08-18", "mcap_path": "repo_snapshot",
        "ath_as_of": "2026-08-18", "ath_path": "repo_snapshot",
        "delivery_as_of": "2026-08-18",
    })
    assert set(items) == {"Prices", "Market caps", "All-time highs", "Delivery"}
    assert all(not i["stale"] for i in items.values())
