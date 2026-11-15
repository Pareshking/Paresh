"""The owner's one-tap clean-up deletes only what it was given, and only unchanged (15 Nov 2026)."""
import importlib.util
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("owner_cleanup", ROOT / "scripts" / "owner_cleanup.py")
oc = importlib.util.module_from_spec(_spec)
sys.modules["owner_cleanup"] = oc          # a dataclass looks its module up while it is built
_spec.loader.exec_module(oc)

A, B = "a" * 40, "b" * 40


def test_a_branch_is_deleted_only_when_unchanged_unprotected_and_without_an_open_pr():
    listed = [("fix/done", A), ("fix/moved", A), ("fix/open", A), ("fix/gone", A),
              ("main", A), ("agent/x", A), ("ci/stage4b-y", A)]
    tips = {"fix/done": A, "fix/moved": B, "fix/open": A, "main": A, "agent/x": A, "ci/stage4b-y": A}
    steps = {s.target: s for s in oc.plan_branches(listed, tips, open_heads={"fix/open"})}
    assert steps["fix/done"].action == "delete"
    assert steps["fix/moved"].action == "skip" and "moved" in steps["fix/moved"].why
    assert steps["fix/open"].action == "skip" and "pull request" in steps["fix/open"].why
    assert steps["fix/gone"].action == "gone"
    assert {steps[k].action for k in ("main", "agent/x", "ci/stage4b-y")} == {"skip"}


def _objs(n, size, prefix=oc.R2_PREFIX):
    return [{"Key": f"{prefix}f{i}", "Size": size} for i in range(n)]


def test_r2_is_deleted_only_when_it_is_exactly_what_was_recorded():
    per = oc.R2_BYTES // oc.R2_OBJECTS
    assert oc.plan_r2(_objs(23, per)).action == "delete"
    assert oc.plan_r2([]).action == "gone"
    assert oc.plan_r2(_objs(24, per)).action == "skip"                    # something was added
    assert oc.plan_r2(_objs(23, per * 2)).action == "skip"                # a different size
    stray = _objs(22, per) + [{"Key": "archive/prices/x", "Size": per}]
    assert oc.plan_r2(stray).action == "skip"                             # never outside the prefix


def test_an_asset_is_deleted_only_if_still_the_same_size_and_downloads():
    for want in oc.ASSETS:
        ok = {"name": want["name"], "size": want["size"], "download_count": want["downloads"]}
        assert oc.plan_asset([ok, {"name": "prices.parquet", "size": 1, "download_count": 9}], want).action == "delete"
        assert oc.plan_asset([{**ok, "download_count": want["downloads"] + 1}], want).action == "skip"
        assert oc.plan_asset([{**ok, "size": 5}], want).action == "skip"
        assert oc.plan_asset([], want).action == "gone"
    names = {a["name"] for a in oc.ASSETS}
    assert names == {"tmp_session_2026-10-03.zip", "history_backtests.zip", "prices_extra.parquet"}
    # the reference set and every live asset stay (docs/PENDING_DELETIONS.md)
    assert not {n for n in names if n.startswith("ref_") or n in {"prices.parquet", "prices_full.parquet"}}


def test_the_branch_list_holds_no_protected_or_open_pr_branch():
    listed = oc.read_list()
    assert len(listed) == 0           # all three 15 Nov batches are done
    names = [n for n, _ in listed]
    assert len(set(names)) == len(names)
    assert all(re.fullmatch(r"[0-9a-f]{40}", sha) for _, sha in listed)
    assert not [n for n in names if oc.kept(n)]
    assert "ccr-5b2956f6-7ybas4" not in names   # this session's branch is never listed


def test_a_delete_run_bundles_the_listed_branches_first():
    wf = yaml.safe_load((ROOT / ".github" / "workflows" / "owner_cleanup.yml").read_text(encoding="utf-8"))
    steps = wf["jobs"]["cleanup"]["steps"]
    names = [s.get("name", s.get("uses", "")) for s in steps]
    backup = names.index("Back up the listed branches")
    upload = next(i for i, s in enumerate(steps) if "upload-artifact" in s.get("uses", ""))
    clean = next(i for i, n in enumerate(names) if str(n).startswith("Clean up"))
    assert backup < upload < clean
    assert steps[upload]["with"]["retention-days"] == 90
    assert "git bundle create" in steps[backup]["run"] and "git bundle verify" in steps[backup]["run"]


def test_the_job_never_runs_by_itself_and_defaults_to_a_dry_run():
    wf = yaml.safe_load((ROOT / ".github" / "workflows" / "owner_cleanup.yml").read_text(encoding="utf-8"))
    on = wf.get("on", wf.get(True))
    assert set(on) == {"workflow_dispatch"}
    assert on["workflow_dispatch"]["inputs"]["mode"]["default"] == "dry-run"
    run = wf["jobs"]["cleanup"]["steps"][-1]["run"]
    assert "--delete" in run and 'inputs.mode }}" = "delete"' in run
