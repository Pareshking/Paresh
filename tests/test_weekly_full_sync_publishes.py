"""The weekly full sync is the only path that can UN-freeze settled history.

Everything else in this pipeline is append-only. The daily job tops the cache
up from its last date forward, so a close the vendor backfills later and a
split it restates weeks after the fact are both invisible to it. FORCE_FULL
re-downloads the whole window, which is the one mechanism that sees either.

It rebuilt all of that and published none of it:

  * it restored and saved under `price-cache-*` while the daily job used
    `price-data-*`, so the two never saw each other's work;
  * its key was hashFiles('src/**/*.py'), which changes only when the SOURCE
    changes -- and actions/cache skips the save outright on an existing key, so
    most weeks it threw away the history it had just rebuilt (the same defect
    the daily workflow documents and fixed);
  * it had no publish step at all, so the release asset production seeds from
    was still written only by the append-only daily job.

The result was a healing path that ran every Friday and healed nothing. None of
that is visible from the application's tests, and all of it is cheap to assert.
"""

import pathlib

import pytest

yaml = pytest.importorskip("yaml")

ROOT = pathlib.Path(__file__).resolve().parents[1]
WEEKLY = ROOT / ".github/workflows/weekly_full_sync.yml"
DAILY = ROOT / ".github/workflows/daily_sync.yml"


@pytest.fixture(scope="module")
def job():
    return yaml.safe_load(WEEKLY.read_text(encoding="utf-8"))["jobs"]["full-sync"]


@pytest.fixture(scope="module")
def steps(job):
    return job["steps"]


def _cache_step(steps, kind):
    for step in steps:
        if kind in str(step.get("uses", "")):
            return step
    pytest.fail(f"the weekly sync no longer has a cache {kind} step")


def test_no_step_declares_both_uses_and_run(steps):
    """GitHub rejects the whole workflow. It cost the daily job 200 runs."""
    for step in steps:
        assert not ("uses" in step and "run" in step), (
            f"step {step.get('name')!r} declares both uses and run"
        )


def test_it_still_forces_a_full_refresh(steps):
    """Without FORCE_FULL this job is just a slower daily sync."""
    assert any(
        str(s.get("env", {}).get("FORCE_FULL", "")).lower() == "true" for s in steps
    ), "the weekly sync no longer forces a full re-download"


def test_it_shares_the_daily_jobs_cache_namespace(steps):
    """Two namespaces meant the full refresh landed where nothing read it."""
    daily = yaml.safe_load(DAILY.read_text(encoding="utf-8"))["jobs"]["sync"]["steps"]
    daily_key = _cache_step(daily, "restore")["with"]["key"]
    weekly_key = _cache_step(steps, "restore")["with"]["key"]
    prefix = daily_key.split("-${{")[0]
    assert weekly_key.startswith(prefix), (
        f"weekly key {weekly_key!r} is not in the daily job's {prefix!r} namespace"
    )


def test_the_cache_key_changes_every_run(steps):
    """actions/cache entries are immutable; a constant key never saves again."""
    key = _cache_step(steps, "save")["with"]["key"]
    assert "github.run_id" in key or "github.sha" in key, (
        f"cache key {key!r} is constant, so the refresh cannot be written back"
    )


def test_it_publishes_the_snapshot_production_actually_reads(steps):
    """The step whose absence made the whole job pointless."""
    uploads = [
        s for s in steps
        if "gh release upload" in str(s.get("run", ""))
        and "prices.parquet" in str(s.get("run", ""))
    ]
    assert uploads, (
        "the weekly full refresh never reaches production: nothing uploads "
        "prices.parquet to the data-latest release"
    )


def test_publishing_is_permitted(job, steps):
    """A release upload needs contents: write. It declared contents: read."""
    perms = job.get("permissions") or {}
    assert perms.get("contents") == "write", (
        f"contents: {perms.get('contents')!r} cannot upload a release asset"
    )


def test_a_full_refresh_rescans_for_corporate_actions(steps):
    """A full re-download is exactly when a vendor restatement lands."""
    assert any(
        "check_corporate_actions" in str(s.get("run", "")) for s in steps
    ), "a full refresh should re-scan; a restated split must stop being flagged"
