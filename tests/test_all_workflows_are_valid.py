"""Invariants every workflow must hold, not just the two sync jobs.

A step declaring both `uses` and `run` makes GitHub reject the WHOLE file; on
daily_sync.yml that silently cost 200 scheduled runs. The guard used to cover
two files by name; a new workflow got none of it.
"""
import pathlib
import re

import pytest

yaml = pytest.importorskip("yaml")

ROOT = pathlib.Path(__file__).resolve().parents[1]
WORKFLOWS = sorted((ROOT / ".github/workflows").glob("*.yml"))


def _load(path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_workflow_is_structurally_valid(path):
    wf = _load(path)
    assert wf.get("name"), "unnamed workflows cannot be watched by the failure alert"
    for job_id, job in wf["jobs"].items():
        assert "permissions" in wf or "permissions" in job, (
            f"{job_id}: declare least privilege explicitly"
        )
        assert "timeout-minutes" in job, f"{job_id}: a hung job would burn 6 hours"
        for step in job.get("steps", []):
            assert not ("uses" in step and "run" in step), (
                f"{job_id}/{step.get('name')!r} declares both uses and run"
            )


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_every_referenced_repo_file_exists(path):
    text = path.read_text(encoding="utf-8")
    refs = set(re.findall(r"(?<![\w*])(?:scripts|tests|src|r2|agent)/[\w/.\-]+\.(?:py|json|sh)\b", text))
    missing = sorted(r for r in refs if not (ROOT / r).exists())
    assert missing == []


def test_every_scheduled_workflow_is_watched_by_the_failure_alert():
    alert = _load(ROOT / ".github/workflows/scheduled_failure_alert.yml")
    watched = set((alert.get(True) or alert.get("on"))["workflow_run"]["workflows"])
    scheduled = {
        wf["name"]
        for wf in map(_load, WORKFLOWS)
        if isinstance(wf.get(True) or wf.get("on"), dict)
        and "schedule" in (wf.get(True) or wf.get("on"))
    }
    assert scheduled - watched == set()
