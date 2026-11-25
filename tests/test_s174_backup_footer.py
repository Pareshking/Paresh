"""S174 "1 a" (owner, 22 Nov 2026): when R2 cannot be reached the pages read the backup copy, the foot
line says so, and the date is red when that copy is more than one trading day old."""
from __future__ import annotations

import pytest

from src.loaders import app_source
from src.ui import formats as fmt


def _live():
    """The module the footer reads now: another test may have reloaded it."""
    from src.loaders import app_source as current
    return current


@pytest.fixture
def unreached():
    _live().UNREACHED.add("rankings")
    yield
    _live().UNREACHED.discard("rankings")


def test_a_normal_run_reads_as_before():
    assert not app_source.unreachable()
    assert fmt.data_to("2026-11-23") == "Data to 23 Nov 2026 · NSE"
    assert fmt.data_to_html("2026-11-23") == "Data to 23 Nov 2026 · NSE"


def test_the_backup_copy_is_named(unreached):
    assert fmt.data_to("2026-11-23").endswith(fmt.BACKUP_NOTE)
    assert "R2 could not be reached" in fmt.data_to(None)


def test_an_old_backup_copy_has_its_date_in_red(unreached):
    out = fmt.data_to_html("2026-10-01")
    assert '<span class="dh-down" style="color:var(--c-down)">1 Oct 2026</span>' in out


def test_a_current_backup_copy_keeps_its_date_plain(unreached, monkeypatch):
    import src.core.market_time as mt
    monkeypatch.setattr(mt, "trading_days_behind", lambda d, **k: 1)
    out = fmt.data_to_html("2026-11-23")
    assert "dh-down" not in out and out.startswith("Data to 23 Nov 2026 · NSE")


def test_a_failed_r2_read_is_counted_but_no_keys_is_not(monkeypatch):
    monkeypatch.setattr(app_source, "r2_config", lambda: None)
    assert app_source.fetch_latest("snapshots/rankings", "x_nokeys") is None
    assert "x_nokeys" not in app_source.UNREACHED

    class Broken:
        def __getattr__(self, name):
            raise ConnectionError("down")
    monkeypatch.setattr(app_source, "R2DatasetReader", lambda a: Broken())
    try:
        assert app_source.fetch_latest("snapshots/rankings", "x_down", archive=object()) is None
        assert "x_down" in app_source.UNREACHED
    finally:
        app_source.UNREACHED.discard("x_down")
