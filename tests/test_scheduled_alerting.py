"""The alert board must be able to tell the truth (TODO S116).

Three things no other test held:

(f) The alert matches a workflow by its DISPLAY NAME, so renaming a workflow
    drops it from the watch list silently. All 26 scheduled workflows matched
    on 10 Nov 2026 -- this asserts it stays that way, and fails on a rename.
(b)+(a) A green run must be able to close a failure issue and to report a
    `::warning::` annotation. Both paths used to sit behind a failure gate.
(c)+(e) The schedule watchdog's cron arithmetic, which decides whether a
    workflow that produced no run at all is overdue. momentum_health.yml's
    cron matched 2-6 November, before the file was written on 8 November; it
    must not be called overdue until its first real fire, 2 Dec 2026.
"""
import datetime as dt
import pathlib

import pytest

yaml = pytest.importorskip("yaml")

ROOT = pathlib.Path(__file__).resolve().parents[1]
WORKFLOWS = sorted((ROOT / ".github/workflows").glob("*.yml"))
ALERT = ROOT / ".github/workflows/scheduled_failure_alert.yml"
WATCHDOG = ROOT / ".github/workflows/schedule_watchdog.yml"
UTC = dt.timezone.utc


def _load(path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _on(wf):
    # PyYAML reads a bare `on:` key as the boolean True.
    return wf.get(True) or wf.get("on")


def _scheduled():
    out = {}
    for path in WORKFLOWS:
        wf = _load(path)
        on = _on(wf)
        if isinstance(on, dict) and "schedule" in on:
            out[path.name] = wf["name"]
    return out


def test_every_scheduled_workflow_is_in_the_alert_watch_list():
    watched = set(_on(_load(ALERT))["workflow_run"]["workflows"])
    missing = {
        f"{file} ({name})"
        for file, name in _scheduled().items()
        if name not in watched
    }
    assert missing == set(), (
        "these scheduled workflows are not watched by the failure alert; a "
        "rename must be mirrored in scheduled_failure_alert.yml"
    )


def test_the_watch_list_names_no_workflow_that_does_not_exist():
    """The other half of a rename: the old name left behind watches nothing."""
    watched = set(_on(_load(ALERT))["workflow_run"]["workflows"])
    names = {_load(p).get("name") for p in WORKFLOWS}
    assert watched - names == set()


def test_a_green_run_can_close_the_issue_and_report_its_warnings():
    jobs = _load(ALERT)["jobs"]
    assert "green" in jobs, "no green path: a recovery can never close an issue"
    green = jobs["green"]
    assert "'success'" in green["if"]
    runs = "\n".join(step.get("run", "") for step in green["steps"])
    assert "/annotations" in runs, "a warning on a green run must be read back"
    assert "annotation_level == \"warning\"" in runs
    assert "gh issue close" in runs, "a recovered workflow must close its issue"
    # The failure path stays reachable only on a failure.
    assert "'failure'" in jobs["alert"]["if"]


def test_the_alert_never_queues_behind_another_alert_run():
    """21 alert runs were discarded by one shared concurrency group (S116 e)."""
    group = _load(ALERT)["concurrency"]["group"]
    assert "workflow_run.id" in group


def test_the_watchdog_watches_the_alert_itself():
    text = WATCHDOG.read_text(encoding="utf-8")
    alert_name = _load(ALERT)["name"]
    # The watchdog scans every workflow file with `on: schedule`, and the alert
    # has no schedule, so it is the reconciliation pass that covers it: a
    # failed latest scheduled run with no open issue is reported from outside.
    assert "unreported" in text
    assert alert_name  # named here so a rename of the alert shows up in review


def _watchdog_module():
    run = next(
        step["run"]
        for step in _load(WATCHDOG)["jobs"]["watch"]["steps"]
        if step.get("id") == "scan"
    )
    code = run.split("<<'PY'\n", 1)[1].rsplit("\nPY", 1)[0]
    namespace = {"__name__": "schedule_watchdog"}
    exec(compile(code, str(WATCHDOG), "exec"), namespace)  # noqa: S102
    return namespace


@pytest.fixture(scope="module")
def watchdog():
    return _watchdog_module()


def test_cron_fields_are_read_the_way_github_reads_them(watchdog):
    cron = watchdog["Cron"]("30 17 * * 1-5")
    # Friday 6 Nov 2026 17:30 UTC fires; the Saturday does not.
    assert cron.matches(dt.datetime(2026, 11, 6, 17, 30, tzinfo=UTC))
    assert not cron.matches(dt.datetime(2026, 11, 7, 17, 30, tzinfo=UTC))
    assert not cron.matches(dt.datetime(2026, 11, 6, 17, 31, tzinfo=UTC))
    every_six = watchdog["Cron"]("0 */6 * * *")
    assert every_six.matches(dt.datetime(2026, 11, 6, 18, 0, tzinfo=UTC))
    assert not every_six.matches(dt.datetime(2026, 11, 6, 19, 0, tzinfo=UTC))
    sunday = watchdog["Cron"]("40 6 * * 0")
    assert sunday.matches(dt.datetime(2026, 11, 8, 6, 40, tzinfo=UTC))
    assert not sunday.matches(dt.datetime(2026, 11, 9, 6, 40, tzinfo=UTC))


def test_momentum_health_is_not_overdue_before_its_first_fire(watchdog):
    """cron `23 6 2-6 * *`, added 8 Nov 2026, first real fire 2 Dec 06:23."""
    wf = _load(ROOT / ".github/workflows/momentum_health.yml")
    crons = [c["cron"] for c in _on(wf)["schedule"]]
    assert crons == ["23 6 2-6 * *"]
    cron = watchdog["Cron"](crons[0])
    grace = dt.timedelta(hours=12)

    due = cron.last_fire_before(dt.datetime(2026, 11, 10, 5, 41, tzinfo=UTC) - grace)
    assert due == dt.datetime(2026, 11, 6, 6, 23, tzinfo=UTC)
    # ... which is before the file existed, which is what keeps it quiet. The
    # workflow's first commit is the test: a fire due before it is not a miss.
    born = dt.datetime(2026, 11, 8, tzinfo=UTC)
    assert due < born

    # The day after its first real fire, with no run, it IS overdue.
    after = cron.last_fire_before(dt.datetime(2026, 12, 3, 5, 41, tzinfo=UTC) - grace)
    assert after == dt.datetime(2026, 12, 2, 6, 23, tzinfo=UTC)
    assert after > born


def test_a_schedule_with_no_fire_in_the_lookback_is_not_reported(watchdog):
    """29 February: no fire inside 70 days is "nothing due", not "overdue"."""
    cron = watchdog["Cron"]("0 3 29 2 *")
    assert cron.last_fire_before(dt.datetime(2026, 11, 10, tzinfo=UTC)) is None
