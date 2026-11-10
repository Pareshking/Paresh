"""An unconfigured R2 is decided locally, and the log line says how long it took.

`docs/TODO.md` S115 recorded "R2 index levels failing for 3 s" on the cold path,
read off the GAP between two log lines. It is not three seconds: `R2Config`
raises on missing keys before any client is constructed, so nothing is dialled
and nothing times out. These tests pin that -- no S3 client is built, no socket
is opened -- and that the warning now carries its own elapsed time, so the cost
is never again inferred from a gap (measured 10 Nov 2026: 0 ms in the app,
against a 4 s gap that belongs to the dashboard's own rendering before this is
reached).
"""
from __future__ import annotations

import logging

import pytest

from src.loaders import index_levels
from src.storage import r2 as r2_mod


@pytest.fixture(autouse=True)
def _no_credentials_and_no_local_file(monkeypatch):
    for key in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY",
                "R2_ENDPOINT", "R2_BUCKET", "INDEX_LEVELS_FILE"):
        monkeypatch.delenv(key, raising=False)
    index_levels.fetch_index_levels.clear()
    yield
    index_levels.fetch_index_levels.clear()


def test_no_client_is_constructed_when_the_keys_are_absent(monkeypatch):
    def _explode(*a, **k):  # pragma: no cover - the point is that it is not called
        raise AssertionError("an S3 client was constructed for an unconfigured R2")

    monkeypatch.setattr(r2_mod, "R2Archive", _explode)
    assert index_levels.fetch_index_levels() is None


def test_the_warning_reports_its_own_elapsed_time(caplog):
    with caplog.at_level(logging.WARNING, logger="nse_momentum"):
        assert index_levels.fetch_index_levels() is None
    line = next(r.getMessage() for r in caplog.records
                if "Index levels unavailable from R2" in r.getMessage())
    assert "R2ConfigurationError" in line
    assert line.endswith("ms"), line
