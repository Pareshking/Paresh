"""S142's minutes count: the 10-16 Nov baseline's rule, per run."""

from scripts import actions_minutes as am


def _run(start, end, conclusion="success", status="completed", name="W", event="push"):
    return {"run_started_at": start, "updated_at": end, "conclusion": conclusion, "status": status,
            "name": name, "event": event}


def test_a_run_counts_its_wall_minutes_rounded_up_and_at_least_one():
    assert am.run_minutes(_run("2026-11-20T00:00:00Z", "2026-11-20T00:09:10Z")) == 10
    assert am.run_minutes(_run("2026-11-20T00:00:00Z", "2026-11-20T00:00:20Z")) == 1


def test_a_skipped_or_unfinished_run_counts_nothing():
    assert am.run_minutes(_run("2026-11-20T00:00:00Z", "2026-11-20T00:05:00Z", conclusion="skipped")) == 0
    assert am.run_minutes(_run("2026-11-20T00:00:00Z", "2026-11-20T00:05:00Z", status="in_progress",
                               conclusion=None)) == 0


def test_the_table_sums_per_workflow_and_event():
    runs = [_run("2026-11-20T00:00:00Z", "2026-11-20T00:02:30Z", name="A"),
            _run("2026-11-20T00:00:00Z", "2026-11-20T00:00:30Z", name="A", event="schedule"),
            _run("2026-11-20T00:00:00Z", "2026-11-20T00:04:00Z", name="B", conclusion="skipped")]
    by_wf, by_event, total = am.table(runs)
    assert by_wf["A"] == [4, 2] and by_wf["B"] == [0, 1] and total == 4
    assert by_event == {"push": 3, "schedule": 1}


def test_the_breakdown_splits_one_workflow_by_event_conclusion_and_branch():
    runs = [dict(_run("2026-11-20T00:00:00Z", "2026-11-20T00:02:30Z", name="A", event="pull_request"), head_branch="x"),
            dict(_run("2026-11-20T00:00:00Z", "2026-11-20T00:01:30Z", name="A", event="pull_request",
                      conclusion="cancelled"), head_branch="x"),
            dict(_run("2026-11-20T00:00:00Z", "2026-11-20T00:09:00Z", name="B"), head_branch="main")]
    by_kind, by_branch = am.breakdown(runs, "A")
    assert by_kind == {("pull_request", "success"): [3, 1], ("pull_request", "cancelled"): [2, 1]}
    assert by_branch == {"x": [5, 2]}
