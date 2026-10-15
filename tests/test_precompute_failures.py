"""A ranking that is not precomputed fails the daily sync and is not republished (S85)."""
import os

import pytest
import yaml

from scripts import sync_data
from src.core import config


@pytest.fixture
def cache(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "PRICES_FILE", str(tmp_path / "prices.parquet"))
    return tmp_path


def test_a_failure_drops_the_old_table_and_is_noted(cache):
    # 2026-10-14: the 13 Oct table, restored with the data cache, was uploaded again.
    (cache / config.RANKINGS_SNAPSHOT_ASSET).write_bytes(b"13 Oct")
    sync_data.record_precompute_failure("750", ValueError("Encountered all NA values"))
    assert not (cache / config.RANKINGS_SNAPSHOT_ASSET).exists()
    noted = (cache / sync_data.PRECOMPUTE_FAILURES).read_text().splitlines()
    assert noted == ["750: ValueError: Encountered all NA values"]


def test_each_system_is_noted_under_its_own_table(cache):
    (cache / "rankings_combined.parquet").write_bytes(b"old")
    (cache / config.RANKINGS_SNAPSHOT_ASSET).write_bytes(b"new")
    sync_data.record_precompute_failure("combined", ValueError("x"), "rankings_combined.parquet")
    assert not (cache / "rankings_combined.parquet").exists()
    assert (cache / config.RANKINGS_SNAPSHOT_ASSET).exists()          # the 750's table is kept
    assert (cache / sync_data.PRECOMPUTE_FAILURES).read_text().startswith("combined: ")


def test_a_new_run_starts_with_no_failures(cache):
    sync_data.record_precompute_failure("750", ValueError("x"))
    sync_data.clear_precompute_failures()
    assert not (cache / sync_data.PRECOMPUTE_FAILURES).exists()
    sync_data.clear_precompute_failures()                              # nothing to clear: no error


def test_the_daily_sync_fails_last_on_a_noted_failure():
    path = os.path.join(os.path.dirname(__file__), "..", ".github", "workflows", "daily_sync.yml")
    steps = yaml.safe_load(open(path))["jobs"]["sync"]["steps"]
    last = steps[-1]
    assert last["name"] == "Fail when a ranking was not precomputed"
    assert sync_data.PRECOMPUTE_FAILURES in last["run"] and "exit 1" in last["run"]
    assert "if" not in last                                            # runs only when the steps before it passed
