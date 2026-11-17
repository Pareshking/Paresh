#!/usr/bin/env python3
"""The failure alert's green path, as a scan three times a day (S141, 17 Nov 2026).

Until 17 Nov 2026 `scheduled_failure_alert.yml` ran a job after EVERY successful
scheduled or chained run of a watched workflow: 506 runs in the week of 10-16
Nov, each a few seconds but billed as a whole minute (219 minutes; owner: make
a reduction). Failures are still reported the moment they happen, by the same
workflow's `alert` job. What moved here is the other half:

  - a workflow whose latest unattended run succeeded gets its open
    "Scheduled workflow failing: <name>" issue commented and closed;
  - a successful run that printed `::warning::` annotations is reported on
    "Scheduled workflow warning: <name>" (once per run: a run already named on
    the issue is not reported again).

Only the LATEST unattended (schedule / workflow_run) run of each watched
workflow on main is read. Warnings on an earlier green run between two scans are
not reported; the next run of the same workflow prints the same warning if the
cause is still there.

    python scripts/alert_green_scan.py            # needs GH_TOKEN, GH_REPO
"""
from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALERT_WORKFLOW = ROOT / ".github" / "workflows" / "scheduled_failure_alert.yml"
UNATTENDED = ("schedule", "workflow_run")
LOOKBACK = dt.timedelta(days=8)   # covers the weekly workflows


def watched_names(path: Path = ALERT_WORKFLOW) -> list[str]:
    import yaml

    wf = yaml.safe_load(path.read_text(encoding="utf-8"))
    on = wf.get(True) or wf.get("on")
    return list(on["workflow_run"]["workflows"])


def latest_unattended(runs: list[dict], names: list[str]) -> dict[str, dict]:
    """Newest completed schedule/workflow_run run of each watched name."""
    out: dict[str, dict] = {}
    wanted = set(names)
    for run in runs:
        name = run.get("name")
        if name not in wanted or run.get("event") not in UNATTENDED:
            continue
        if run.get("status") != "completed" or run.get("head_branch") != "main":
            continue
        best = out.get(name)
        if best is None or run["created_at"] > best["created_at"]:
            out[name] = run
    return out


def _gh(*args: str, check: bool = True) -> str:
    done = subprocess.run(["gh", *args], capture_output=True, text=True)
    if check and done.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args[:3])}: {done.stderr.strip()[-300:]}")
    return done.stdout


def _runs(repo: str, since: dt.datetime) -> list[dict]:
    runs: list[dict] = []
    for page in range(1, 31):
        body = json.loads(_gh("api", f"repos/{repo}/actions/runs?branch=main&status=completed"
                                     f"&created=>={since:%Y-%m-%dT%H:%M:%SZ}&per_page=100&page={page}"))
        batch = body.get("workflow_runs", [])
        runs += batch
        if len(batch) < 100:
            break
    return runs


def _open_issue(repo: str, title: str) -> int | None:
    out = _gh("issue", "list", "--repo", repo, "--label", "scheduled-failure", "--state", "open",
              "--search", f'in:title "{title}"', "--json", "number,title")
    for row in json.loads(out or "[]"):
        if row["title"] == title:
            return int(row["number"])
    return None


def _warnings(repo: str, run_id: int) -> list[str]:
    jobs = json.loads(_gh("api", f"repos/{repo}/actions/runs/{run_id}/jobs?per_page=100"))
    found: set[str] = set()
    for job in jobs.get("jobs", []):
        out = _gh("api", f"repos/{repo}/check-runs/{job['id']}/annotations", check=False)
        try:
            rows = json.loads(out or "[]")
        except json.JSONDecodeError:
            print(f"could not read annotations of job {job['id']}")
            continue
        found |= {r["message"] for r in rows if r.get("annotation_level") == "warning" and r.get("message")}
    return sorted(found)


def _mentions(repo: str, number: int, url: str) -> bool:
    issue = json.loads(_gh("api", f"repos/{repo}/issues/{number}"))
    if url in (issue.get("body") or ""):
        return True
    comments = json.loads(_gh("api", f"repos/{repo}/issues/{number}/comments?per_page=100"))
    return any(url in (c.get("body") or "") for c in comments)


def main() -> int:
    repo = os.environ["GH_REPO"]
    _gh("label", "create", "scheduled-failure", "--repo", repo, "--color", "B60205",
        "--description", "A scheduled production workflow failed", check=False)
    names = watched_names()
    latest = latest_unattended(_runs(repo, dt.datetime.now(dt.timezone.utc) - LOOKBACK), names)
    for name in names:
        run = latest.get(name)
        if run is None:
            print(f"{name}: no unattended run in {LOOKBACK.days} days")
            continue
        if run.get("conclusion") != "success":
            print(f"{name}: latest unattended run {run.get('conclusion')} -- the alert job reports failures")
            continue
        url, sha, when = run["html_url"], run["head_sha"][:7], run["updated_at"]
        warns = _warnings(repo, int(run["id"]))
        if warns:
            title = f"Scheduled workflow warning: {name}"
            number = _open_issue(repo, title)
            if number is not None and _mentions(repo, number, url):
                print(f"{name}: {len(warns)} warning(s), already reported for this run")
            else:
                body = (f"**{name}** finished GREEN on `{sha}` at {when} with {len(warns)} warning "
                        f"annotation(s): {url}\n\n" + "\n".join(f"- {w}" for w in warns))
                if number is not None:
                    _gh("issue", "comment", str(number), "--repo", repo, "--body", body)
                else:
                    body += ("\n\nA warning here does not fail the job on purpose: the step log is the "
                             "deliverable (daily_sync.yml). Close this once the warnings stop.")
                    _gh("issue", "create", "--repo", repo, "--title", title,
                        "--label", "scheduled-failure", "--body", body)
                print(f"{name}: reported {len(warns)} warning(s)")
        number = _open_issue(repo, f"Scheduled workflow failing: {name}")
        if number is not None:
            _gh("issue", "comment", str(number), "--repo", repo, "--body",
                f"Recovered: **{name}** succeeded on `{sha}` at {when}: {url}")
            _gh("issue", "close", str(number), "--repo", repo, "--reason", "completed")
            print(f"{name}: recovered, closed #{number}")
        elif not warns:
            print(f"{name}: green")
    return 0


if __name__ == "__main__":
    sys.exit(main())
