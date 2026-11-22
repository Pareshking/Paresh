#!/usr/bin/env python3
"""The owner's one-tap clean-up (owner, 15 Nov 2026: "Build the one-tap clean-up job").

    python scripts/owner_cleanup.py            # dry run: say what would go, delete nothing
    python scripts/owner_cleanup.py --delete   # delete what passes every check

Run by `.github/workflows/owner_cleanup.yml` (Actions -> "Owner clean-up" -> Run
workflow), because a cloud session can neither delete a branch (HTTP 403) nor
reach R2 nor touch a release asset (docs/PENDING_DELETIONS.md). GitHub's own
runner can do all three.

Three things, each re-checked at run time and skipped, not forced, when the
check fails:

1. Branches in .github/cleanup/branches.tsv: deleted only if the branch still
   points at the sha recorded there (nothing pushed since the list was made), no
   pull request is open on it, and its name matches no keep rule.
2. R2 `scratch/bse_bhavcopy_2026-10-03/`: deleted only if it holds exactly the
   23 objects / 1,221.8 MiB recorded on 10 Nov, every key under that prefix.
3. Release assets on `data-latest` (ASSETS): each deleted only if it still has
   the size and download count recorded when the owner approved it.
4. Actions artifacts named `v1-production-qa` that GitHub keeps for 90 days:
   the ones uploaded before `retention-days: 14` (#506, 10 Nov 2026), about
   953 / 994 MB on 16 Nov (owner, 17 Nov 2026: "Delete 953 old QA artifacts").
   An artifact is taken only if it expires more than 15 days after it was made,
   which no upload under the new setting does; more than ARTIFACT_MAX of them
   skips the step.

Before a delete run, the workflow bundles every listed branch into a 90-day
artifact (`unmerged-branches.bundle`), so work that never reached main can be
restored with `git clone` / `git fetch` from the bundle.

Nothing else is touched. The dry run prints the same plan the real run executes.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRANCH_LIST = ROOT / ".github" / "cleanup" / "branches.tsv"
REPO = "Pareshking/Paresh"

# Never deleted, whatever the list says (the keep rules of the retired BRANCH_CLEANUP_TODO.md; docs/PENDING_DELETIONS.md).
KEEP = ("main", "agent/*", "*stage4b*", "audit-backup-*", "archive/*",
        "fix/r2-membership-test-live-change")

R2_PREFIX = "scratch/bse_bhavcopy_2026-10-03/"
R2_OBJECTS = 23
R2_BYTES = int(1221.8 * 2**20)   # 1,221.8 MiB as measured on 10 Nov (r2_archive_inventory)
R2_BYTES_TOLERANCE = 0.01         # the 10 Nov figure was rounded to a tenth of a MiB

RELEASE_TAG = "data-latest"
# Each approved by the owner with its size and downloads at the time; a change skips it.
ASSETS = (
    {"name": "tmp_session_2026-10-03.zip", "size": 10_851_823, "downloads": 0},   # deleted 15 Nov (run 43674615797)
    {"name": "history_backtests.zip", "size": 3_311_385, "downloads": 3},         # deleted 15 Nov (run 43677526783)
    # Nothing reads it: nse_compare lost its --extra argument and its workflow never
    # downloads it (storage audit, 15 Nov; owner: "Delete whatever you decided").
    {"name": "prices_extra.parquet", "size": 7_001_785, "downloads": 10},
    # The frozen Yahoo-era snapshot of 1 Oct 2026; its last reader went in #604 (C6,
    # owner 22 Nov: "delete both"). nse_sample_check run 44998959937 passed without it.
    {"name": "prices.parquet", "size": 10_876_794, "downloads": 932},             # deleted 22 Nov (run 45002747120)
)


@dataclass(frozen=True)
class Step:
    what: str        # "branch" / "r2" / "asset" / "artifact"
    target: str
    action: str      # "delete" / "skip" / "gone"
    why: str


def kept(name: str) -> bool:
    return any(fnmatch.fnmatchcase(name, pat) for pat in KEEP)


def read_list(path: Path = BRANCH_LIST) -> list[tuple[str, str]]:
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        name, sha = line.split("\t")[:2]
        out.append((name.strip(), sha.strip()))
    return out


def plan_branches(listed: list[tuple[str, str]], tips: dict[str, str], open_heads: set[str]) -> list[Step]:
    steps = []
    for name, sha in listed:
        if kept(name):
            steps.append(Step("branch", name, "skip", "matches a keep rule"))
        elif name not in tips:
            steps.append(Step("branch", name, "gone", "already deleted"))
        elif name in open_heads:
            steps.append(Step("branch", name, "skip", "a pull request is open on it"))
        elif tips[name] != sha:
            steps.append(Step("branch", name, "skip", f"moved since the list: {sha[:7]} -> {tips[name][:7]}"))
        else:
            steps.append(Step("branch", name, "delete", f"tip {sha[:7]} as listed"))
    return steps


def plan_r2(objects: list[dict]) -> Step:
    if not objects:
        return Step("r2", R2_PREFIX, "gone", "no object under the prefix")
    stray = [o["Key"] for o in objects if not o["Key"].startswith(R2_PREFIX)]
    if stray:
        return Step("r2", R2_PREFIX, "skip", f"listing returned keys outside the prefix: {stray[:3]}")
    size = sum(int(o["Size"]) for o in objects)
    if len(objects) != R2_OBJECTS:
        return Step("r2", R2_PREFIX, "skip", f"{len(objects)} objects, expected {R2_OBJECTS}")
    if abs(size - R2_BYTES) > R2_BYTES * R2_BYTES_TOLERANCE:
        return Step("r2", R2_PREFIX, "skip", f"{size:,} bytes, expected about {R2_BYTES:,}")
    return Step("r2", R2_PREFIX, "delete", f"{len(objects)} objects, {size / 2**20:,.1f} MiB as recorded")


def plan_asset(assets: list[dict], want: dict) -> Step:
    match = [a for a in assets if a.get("name") == want["name"]]
    if not match:
        return Step("asset", want["name"], "gone", "not on the release")
    a = match[0]
    if int(a.get("size", -1)) != want["size"] or int(a.get("download_count", -1)) != want["downloads"]:
        return Step("asset", want["name"], "skip",
                    f"size {a.get('size')} / downloads {a.get('download_count')}, expected "
                    f"{want['size']} / {want['downloads']}")
    return Step("asset", want["name"], "delete", f"{want['size']:,} bytes, {want['downloads']} downloads as recorded")


ARTIFACT_NAME = "v1-production-qa"
ARTIFACT_LONG_LIFE_DAYS = 15   # the new uploads live 14 days; the old ones 90
ARTIFACT_MAX = 1100            # 953 on 16 Nov; more means the selection is wrong


def _days_kept(a: dict) -> float | None:
    from datetime import datetime

    try:
        made = datetime.fromisoformat(str(a["created_at"]).replace("Z", "+00:00"))
        ends = datetime.fromisoformat(str(a["expires_at"]).replace("Z", "+00:00"))
    except (KeyError, ValueError):
        return None
    return (ends - made).total_seconds() / 86400


def plan_artifacts(artifacts: list[dict]) -> tuple[Step, list[int]]:
    old = [a for a in artifacts
           if a.get("name") == ARTIFACT_NAME and not a.get("expired")
           and (_days_kept(a) or 0) > ARTIFACT_LONG_LIFE_DAYS]
    if not old:
        return Step("artifact", ARTIFACT_NAME, "gone", "no 90-day upload left"), []
    size = sum(int(a.get("size_in_bytes", 0)) for a in old)
    if len(old) > ARTIFACT_MAX:
        return Step("artifact", ARTIFACT_NAME, "skip", f"{len(old)} matched, more than {ARTIFACT_MAX}"), []
    return (Step("artifact", ARTIFACT_NAME, "delete",
                 f"{len(old)} uploads kept 90 days, {size / 2**20:,.1f} MiB"),
            [int(a["id"]) for a in old])


# --- The outside world (only on GitHub's runner) ------------------------------

def _run(cmd: list[str]) -> str:
    return subprocess.run(cmd, check=True, capture_output=True, text=True).stdout


def remote_tips() -> dict[str, str]:
    tips = {}
    for line in _run(["git", "ls-remote", "--heads", "origin"]).splitlines():
        sha, ref = line.split("\t")
        tips[ref.removeprefix("refs/heads/")] = sha
    return tips


def open_pr_heads() -> set[str]:
    heads, page = set(), 1
    while True:
        prs = json.loads(_run(["gh", "api", f"repos/{REPO}/pulls?state=open&per_page=100&page={page}"]))
        heads |= {p["head"]["ref"] for p in prs if p["head"]["repo"] and p["head"]["repo"]["full_name"] == REPO}
        if len(prs) < 100:
            return heads
        page += 1


def r2_client():
    import boto3
    return boto3.client("s3", endpoint_url=os.environ["R2_ENDPOINT"].rstrip("/"),
                        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
                        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"], region_name="auto")


def r2_objects(client, bucket: str) -> list[dict]:
    out, token = [], None
    while True:
        kw = {"Bucket": bucket, "Prefix": R2_PREFIX, **({"ContinuationToken": token} if token else {})}
        page = client.list_objects_v2(**kw)
        out += page.get("Contents", [])
        if not page.get("IsTruncated"):
            return out
        token = page["NextContinuationToken"]


def release_assets() -> list[dict]:
    rel = json.loads(_run(["gh", "api", f"repos/{REPO}/releases/tags/{RELEASE_TAG}"]))
    return rel.get("assets", [])


def artifacts() -> list[dict]:
    out = _run(["gh", "api", "--paginate", f"repos/{REPO}/actions/artifacts?name={ARTIFACT_NAME}&per_page=100",
                "--jq", ".artifacts[]"])
    return [json.loads(line) for line in out.splitlines() if line.strip()]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--delete", action="store_true", help="delete; without it nothing is removed")
    args = ap.parse_args(argv)

    steps = plan_branches(read_list(), remote_tips(), open_pr_heads())
    client, bucket, objects = None, os.environ.get("R2_BUCKET", ""), []
    if bucket:
        client = r2_client()
        objects = r2_objects(client, bucket)
        steps.append(plan_r2(objects))
    else:
        steps.append(Step("r2", R2_PREFIX, "skip", "no R2 credentials in this run"))
    assets = release_assets()
    steps += [plan_asset(assets, want) for want in ASSETS]
    art_step, art_ids = plan_artifacts(artifacts())
    steps.append(art_step)

    mode = "DELETING" if args.delete else "DRY RUN (nothing is deleted)"
    print(f"Owner clean-up: {mode}")
    for s in steps:
        print(f"{s.action:6} {s.what:6} {s.target}  ({s.why})")
    todo = [s for s in steps if s.action == "delete"]
    counts = {a: sum(s.action == a for s in steps) for a in ("delete", "skip", "gone")}
    print(f"\n{counts['delete']} to delete, {counts['skip']} skipped by a check, {counts['gone']} already gone")
    if not args.delete:
        return 0

    failed = 0
    for s in todo:
        try:
            if s.what == "branch":
                _run(["git", "push", "origin", "--delete", s.target])
            elif s.what == "r2":
                for i in range(0, len(objects), 1000):
                    client.delete_objects(Bucket=bucket, Delete={
                        "Objects": [{"Key": o["Key"]} for o in objects[i:i + 1000]], "Quiet": True})
            elif s.what == "asset":
                _run(["gh", "release", "delete-asset", RELEASE_TAG, s.target, "--repo", REPO, "--yes"])
            elif s.what == "artifact":
                gone = 0
                for art_id in art_ids:
                    try:
                        _run(["gh", "api", "-X", "DELETE", f"repos/{REPO}/actions/artifacts/{art_id}"])
                        gone += 1
                    except Exception as exc:   # noqa: BLE001 - count it, keep going
                        print(f"::warning::artifact {art_id}: {exc}")
                if gone != len(art_ids):
                    raise RuntimeError(f"{len(art_ids) - gone} of {len(art_ids)} artifacts not deleted")
            print(f"deleted {s.what} {s.target}")
        except Exception as exc:          # one failure must not stop the rest; report it
            failed += 1
            print(f"::error::could not delete {s.what} {s.target}: {exc}")
    print(f"\ndone: {len(todo) - failed} deleted, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
