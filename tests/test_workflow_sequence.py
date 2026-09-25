"""The unattended jobs run in the order their data needs, and every one alerts.

GitHub starts scheduled jobs hours late (2-5 h measured on this repo), so two
cron times an hour apart say nothing about which finishes first. A job that
reads another job's output is chained to it with workflow_run instead.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

WORKFLOWS = Path(__file__).resolve().parents[1] / ".github" / "workflows"


def _load(name: str) -> dict:
    return yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))


def _on(doc: dict) -> dict:
    return doc.get(True) or doc.get("on") or {}


# consumer workflow -> the workflow whose output it reads
CHAINS = {
    "daily_sync.yml": "Screener daily price sync (overnight)",          # re-rank the new store
    "r2_observed_trading_sessions.yml": "Screener daily price sync (overnight)",
    "r2_ranking_archive.yml": "Daily NSE Momentum Data Sync",           # rankings.parquet
    "r2_market_cap_history.yml": "Daily NSE Momentum Data Sync",        # data/nse_market_caps.csv
    "r2-historical-evidence-bootstrap.yml": "Daily NSE Momentum Data Sync",
}


@pytest.mark.parametrize("consumer,upstream", sorted(CHAINS.items()))
def test_consumers_run_after_what_they_read_and_only_on_success(consumer, upstream):
    doc = _load(consumer)
    run = _on(doc).get("workflow_run") or {}
    assert run.get("workflows") == [upstream]
    assert run.get("types") == ["completed"]
    for job in doc["jobs"].values():
        assert "github.event.workflow_run.conclusion == 'success'" in str(job.get("if", ""))


def test_chained_upstreams_exist_by_name():
    names = {_load(p.name)["name"] for p in WORKFLOWS.glob("*.yml")}
    assert set(CHAINS.values()) <= names


def test_every_unattended_workflow_raises_the_failure_alert():
    alert = _load("scheduled_failure_alert.yml")
    watched = set(_on(alert)["workflow_run"]["workflows"])
    unattended = {
        _load(p.name)["name"]
        for p in WORKFLOWS.glob("*.yml")
        if p.name != "scheduled_failure_alert.yml"
        and ({"schedule", "workflow_run"} & set(_on(_load(p.name))))
    }
    assert unattended - watched == set()
    condition = alert["jobs"]["alert"]["if"]
    assert "'schedule'" in condition and "'workflow_run'" in condition


def test_the_sunday_retention_run_applies_its_own_plan_then_audits():
    """Owner, 2026-09-25: the weekly run deletes, not only plans."""
    doc = _load("r2_retention.yml")
    assert _on(doc)["schedule"]
    steps = {s.get("name"): s for s in doc["jobs"]["retention"]["steps"]}
    plan, apply, audit = steps["Plan (dry run)"], steps["Apply"], steps["Recovery audit after apply"]
    assert "RETENTION_DELETE_COUNT" in plan["run"] and "GITHUB_OUTPUT" in plan["run"]
    assert "github.event_name == 'schedule'" in apply["if"]
    assert "steps.plan.outputs.count != '0'" in apply["if"]
    assert "steps.plan.outputs.count" in apply["env"]["EXPECT"]
    assert "--expect-deletes" in apply["run"]
    assert audit["if"] == "${{ steps.apply.outcome == 'success' }}"
