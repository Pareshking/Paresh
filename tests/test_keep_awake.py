"""S202 (owner, 23 Nov 2026): the app is kept awake by a light visit every 4 hours; the full
Production QA runs on each push to main and once a day."""
from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WF = ROOT / ".github" / "workflows"


def _wf(name):
    yaml = pytest.importorskip("yaml")
    doc = yaml.safe_load((WF / name).read_text(encoding="utf-8"))
    return doc, doc.get("on", doc.get(True))


def test_the_keep_awake_visit_runs_well_inside_streamlits_12_hours():
    doc, on = _wf("keep_awake.yml")
    (cron,) = [c["cron"] for c in on["schedule"]]
    hours = cron.split()[1]
    assert hours == "*/4", cron        # three chances inside 12 h when GitHub skips a slot
    steps = doc["jobs"]["visit"]["steps"]
    assert any("keep_awake.py" in str(s.get("run", "")) for s in steps)
    assert not any("playwright install" in str(s.get("run", "")) for s in steps)   # the runner's Chrome


def test_production_qa_runs_on_push_and_once_a_day():
    _, on = _wf("v1-production-qa.yml")
    assert "push" in on
    (cron,) = [c["cron"] for c in on["schedule"]]
    minute, hour = cron.split()[:2]
    assert minute.isdigit() and hour.isdigit(), cron


def test_the_visit_wakes_a_sleeping_app_and_fails_when_it_cannot():
    src = (ROOT / "scripts" / "keep_awake.py").read_text(encoding="utf-8")
    assert "get this app back up" in src and "return 1" in src and 'channel=' in src
