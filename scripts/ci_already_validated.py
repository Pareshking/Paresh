"""S141: has this push to main already passed V1 Full Validation, file for file, on its pull request?

The week of 20-26 Nov 2026 merged 94 pull requests; each merge reran the ~11-minute suite on main
(1,381 of Full Validation's 4,067 minutes), most of them on files the PR had just passed. A push
is "already validated" only when all of these hold, read from GitHub's API:

1. the push is a squash merge of a pull request (GitHub lists the PR for the commit, merged, with
   this commit as its merge commit);
2. main's tree after the push equals the tree of the PR's last head commit (the branch held all of
   main when merged, so the PR's run tested these exact files);
3. V1 Full Validation succeeded on a pull_request run for that head commit.

Anything else, an API error included, answers "no" and the full suite runs. The nightly scheduled
run still tests main in full (data commits carry [skip ci]), and Production QA still runs on every
push. Prints `already=true|false` for $GITHUB_OUTPUT and the reason on stderr.

    python scripts/ci_already_validated.py <sha> <tree-sha>
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request

API = "https://api.github.com"
WORKFLOW = "v1-full-validation.yml"


def decide(sha: str, tree: str, pulls: list[dict], head_tree: str | None, passed_runs: int) -> tuple[bool, str]:
    """The rule above, on what the API returned."""
    pr = next((p for p in pulls if p.get("merged_at") and p.get("merge_commit_sha") == sha), None)
    if pr is None:
        return False, "not a pull request's merge commit"
    if not head_tree or head_tree != tree:
        return False, f"#{pr.get('number')}: main's files differ from the PR's last commit (branch was behind main)"
    if passed_runs < 1:
        return False, f"#{pr.get('number')}: no passed pull_request run on its last commit"
    return True, f"#{pr.get('number')}: same files passed on the PR ({pr['head']['sha'][:12]})"


def _get(path: str, token: str) -> dict | list:
    req = urllib.request.Request(f"{API}{path}", headers={
        "Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def main(argv: list[str]) -> int:
    sha, tree = argv[0], argv[1]
    repo, token = os.environ["GITHUB_REPOSITORY"], os.environ["GITHUB_TOKEN"]
    try:
        pulls = _get(f"/repos/{repo}/commits/{sha}/pulls", token)
        pr = next((p for p in pulls if p.get("merged_at") and p.get("merge_commit_sha") == sha), None)
        head_tree, passed = None, 0
        if pr is not None:
            head = pr["head"]["sha"]
            head_tree = _get(f"/repos/{repo}/git/commits/{head}", token)["tree"]["sha"]
            runs = _get(f"/repos/{repo}/actions/workflows/{WORKFLOW}/runs"
                        f"?head_sha={head}&event=pull_request&status=success&per_page=1", token)
            passed = int(runs.get("total_count", 0))
        already, why = decide(sha, tree, pulls, head_tree, passed)
    except Exception as exc:  # any doubt runs the full suite
        already, why = False, f"API error, full run: {exc}"
    print(f"already={'true' if already else 'false'}")
    print(why, file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
