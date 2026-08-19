"""Guards on the daily sync workflow file.

This file has failed silently twice in ways nothing else could catch. Once a
step declared both `uses` and `run`, which is invalid, so GitHub rejected the
workflow on every push and the nightly schedule never fired -- 200 consecutive
failed runs. Then the price cache key never changed, so the cache was written
once and never again.

Neither is visible from the application's tests, and both only show up in a log
nobody reads. They are cheap to assert here.
"""
import pathlib

import pytest

yaml = pytest.importorskip("yaml")

WORKFLOW = pathlib.Path(__file__).resolve().parents[1] / ".github/workflows/daily_sync.yml"


@pytest.fixture(scope="module")
def steps():
    spec = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    return spec["jobs"]["sync"]["steps"]


def _cache_steps(steps):
    return [s for s in steps if str(s.get("uses", "")).startswith("actions/cache")]


def _cache_step(steps, kind="restore"):
    for step in _cache_steps(steps):
        if kind in str(step.get("uses", "")):
            return step
    pytest.fail(f"the workflow no longer has a price cache {kind} step")


def test_no_step_declares_both_uses_and_run(steps):
    """The mistake that cost 200 runs. GitHub rejects the whole workflow."""
    for step in steps:
        assert not ("uses" in step and "run" in step), (
            f"step {step.get('name')!r} declares both uses and run"
        )


def test_the_price_cache_key_changes_every_run(steps):
    """actions/cache entries are immutable.

    A constant key means the very first run writes the cache and every run
    after it logs "Cache hit occurred on the primary key ..., not saving
    cache" and throws its updated copy away. The cached history then ages one
    day per day while the incremental top-up grows to match.
    """
    key = _cache_step(steps)["with"]["key"]
    assert "github.run_id" in key or "github.sha" in key, (
        f"cache key {key!r} is constant, so the cache can never be rewritten"
    )


def test_the_cache_still_falls_back_to_the_newest_previous_entry(steps):
    """A rotating key hits nothing on its own; restore-keys is what saves it.

    Without a prefix fallback, every run would start from an empty cache and
    re-download two years of history -- strictly worse than the bug being
    fixed.
    """
    restore = _cache_step(steps)["with"]["restore-keys"]
    prefixes = [line.strip() for line in str(restore).splitlines() if line.strip()]
    key = _cache_step(steps)["with"]["key"]

    assert prefixes, "a rotating key with no restore-keys never restores anything"
    assert any(key.startswith(p) for p in prefixes), (
        f"none of the restore-keys {prefixes} is a prefix of the key {key!r}"
    )


def test_the_snapshot_is_published_after_the_sync_runs(steps):
    """Order matters: the upload reads a file the sync step writes."""
    names = [str(s.get("name", "")) for s in steps]
    sync = next(i for i, n in enumerate(names) if "Market Sync" in n)
    publish = next(i for i, n in enumerate(names) if "Publish price snapshot" in n)
    assert sync < publish


def test_the_save_step_writes_the_key_the_restore_step_asked_for():
    """Where the rotation was almost missed.

    The workflow has TWO cache steps, and only the restore one was updated at
    first. A save pinned to the old constant key would have gone on skipping
    exactly as before, so the rotation would have changed nothing at all.
    """
    spec = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    steps = spec["jobs"]["sync"]["steps"]

    restore = _cache_step(steps, "restore")["with"]["key"]
    save = _cache_step(steps, "save")["with"]["key"]

    assert save == restore, "the save writes a different key than the restore reads"


def test_the_cache_is_saved_even_when_the_sync_fails():
    """A run that dies after the download still holds history worth keeping."""
    spec = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    steps = spec["jobs"]["sync"]["steps"]
    assert _cache_step(steps, "save").get("if") == "always()"
