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


# ── The two scheduled slots ──────────────────────────────────────────────────
#
# Yahoo publishes an Indian session over about a day and a half, largest names
# first. Measured on 2026-09-17: 20% of the universe ~10h after the close, 50%
# at ~15h, 100% at ~34h. The night slot therefore always ranks the PREVIOUS
# session, and the morning slot exists for recovery -- a second attempt when
# the night run is delayed, throttled or fails -- not for freshness.

@pytest.fixture(scope="module")
def spec():
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def _triggers(spec):
    # PyYAML parses a bare `on:` key as the boolean True, not the string "on".
    return spec.get("on") or spec.get(True)


def _crons(spec):
    return [entry["cron"] for entry in _triggers(spec)["schedule"]]


def test_both_scheduled_slots_are_present(spec):
    crons = _crons(spec)
    assert "30 17 * * 1-5" in crons, "the night slot is gone"
    assert "0 2 * * 2-6" in crons, "the morning recovery slot is gone"


def test_the_morning_slot_covers_the_day_after_every_session(spec):
    """Sessions run Mon-Fri, so the morning after runs Tue-SAT.

    Dropping Saturday would leave Friday's session -- still only half published
    on Saturday morning -- with no recovery attempt until Monday night.
    """
    dow = "0 2 * * 2-6".split()[-1]
    assert dow == "2-6", "the morning slot no longer covers Tue-Sat"
    crons = _crons(spec)
    assert "0 2 * * 2-6" in crons


def test_the_slots_land_where_they_are_meant_to_in_india():
    """Both are written in UTC; the market they serve is not.

    GitHub queues scheduled workflows on a best-effort basis and has run this
    repo consistently ~28 minutes late, which both slots are positioned for.
    """
    from datetime import datetime, timedelta, timezone

    IST = timezone(timedelta(hours=5, minutes=30))
    observed_delay = timedelta(minutes=28)

    def ist_hhmm(hour, minute):
        t = datetime(2026, 9, 22, hour, minute, tzinfo=timezone.utc) + observed_delay
        return t.astimezone(IST).strftime("%H:%M")

    assert ist_hhmm(17, 30) == "23:28", "the night slot drifted off 23:00 IST"
    assert ist_hhmm(2, 0) == "07:58", "the morning slot drifted off 08:00 IST"


def test_the_two_slots_cannot_run_over_each_other(spec):
    """Both write the same rotating cache and both commit to main.

    A second runner starting mid-commit would race the rebase-and-retry push.
    Queued, not cancelled: a run already fetching prices is worth finishing.
    """
    conc = spec.get("concurrency")
    assert conc, "two scheduled slots with no concurrency guard"
    assert conc.get("cancel-in-progress") is False, (
        "cancelling in progress would kill a run mid-fetch and lose its cache"
    )


def test_the_morning_run_actually_re_downloads(spec):
    """The download gate would otherwise make it a no-op.

    last_downloadable_session() is already past by 08:00 IST and the cache
    holds that session, so the incremental path would return the cache
    untouched. heal_days bypasses the gate deliberately, which is the only
    reason this slot fetches anything at all.
    """
    from src.core.config import PRICE_HEAL_DAYS

    assert PRICE_HEAL_DAYS > 0, (
        "with heal_days at 0 the morning slot returns the cache without asking "
        "the vendor for anything, and the second attempt is worthless"
    )
    src = (pathlib.Path(__file__).resolve().parents[1] / "scripts/sync_data.py").read_text()
    assert "heal_days=0 if FORCE_FULL else PRICE_HEAL_DAYS" in src, (
        "the daily sync no longer heals, so the morning slot cannot recover a "
        "session the night run missed"
    )
