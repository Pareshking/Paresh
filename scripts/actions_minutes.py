"""GitHub Actions minutes for a window, per workflow (TODO S142; owner, 17 Nov 2026: measure before going private).

The 10-16 Nov baseline's method (2,299 a week): each completed run counts max(1, ceil(wall minutes)), wall time
being `updated_at - run_started_at`; a skipped or cancelled-before-start run counts 0. Wall time per run, so a run
whose jobs ran in parallel is undercounted: read the totals as a floor. Read-only; prints a table.

    python scripts/actions_minutes.py 2026-11-19T18:30:00Z 2026-11-26T18:30:00Z
"""

from __future__ import annotations

import math
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta, UTC

import requests

API = "https://api.github.com"


def _ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def run_minutes(run: dict) -> int:
    """The baseline's count for one run."""
    if run.get("status") != "completed" or run.get("conclusion") in ("skipped", None):
        return 0
    start, end = run.get("run_started_at"), run.get("updated_at")
    if not start or not end:
        return 0
    wall = (_ts(end) - _ts(start)).total_seconds() / 60
    return max(1, math.ceil(wall)) if wall > 0 else 1


def fetch(repo: str, start: datetime, end: datetime, token: str) -> list[dict]:
    """Every run created in [start, end), a few hours at a time (the API returns at most 1,000 per query)."""
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"})
    runs, t, step = {}, start, timedelta(hours=6)
    while t < end:
        u = min(t + step, end)
        rng = f"{t:%Y-%m-%dT%H:%M:%SZ}..{u - timedelta(seconds=1):%Y-%m-%dT%H:%M:%SZ}"
        page, got = 1, 0
        while True:
            r = s.get(f"{API}/repos/{repo}/actions/runs", params={"created": rng, "per_page": 100, "page": page},
                      timeout=60)
            r.raise_for_status()
            body = r.json()
            for run in body.get("workflow_runs", []):
                runs[run["id"]] = run
            got += len(body.get("workflow_runs", []))
            if len(body.get("workflow_runs", [])) < 100:
                break
            page += 1
        if body.get("total_count", 0) >= 1000:
            print(f"::warning::{rng} hit the API's 1,000-run cap; the total for it is a floor")
        t = u
    return list(runs.values())


def table(runs: list[dict]) -> tuple[dict, dict, int]:
    by_wf, by_event = defaultdict(lambda: [0, 0]), defaultdict(int)
    for run in runs:
        m = run_minutes(run)
        by_wf[run.get("name") or "?"][0] += m
        by_wf[run.get("name") or "?"][1] += 1
        by_event[run.get("event") or "?"] += m
    return by_wf, by_event, sum(v[0] for v in by_wf.values())


def main(argv: list[str]) -> int:
    start, end = _ts(argv[0]), _ts(argv[1])
    repo = os.environ.get("GITHUB_REPOSITORY", "Pareshking/Paresh")
    runs = fetch(repo, start.astimezone(UTC), end.astimezone(UTC), os.environ["GITHUB_TOKEN"])
    by_wf, by_event, total = table(runs)
    days = (end - start).total_seconds() / 86400
    print(f"Window {start:%Y-%m-%d %H:%M} to {end:%Y-%m-%d %H:%M} UTC ({days:.1f} days): {len(runs)} runs, "
          f"{total:,} minutes (per 30 days: ~{total * 30 / days:,.0f})")
    print("By event: " + "; ".join(f"{k} {v:,}" for k, v in sorted(by_event.items(), key=lambda kv: -kv[1])))
    print(f"{'Workflow':<60} {'Minutes':>8} {'Runs':>6}")
    for name, (m, n) in sorted(by_wf.items(), key=lambda kv: -kv[1][0]):
        print(f"{name[:60]:<60} {m:>8,} {n:>6}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
