"""S141: a merge to main skips the full suite only when the same files passed it on the PR."""

from scripts import ci_already_validated as cav

PR = {"number": 7, "merged_at": "2026-11-27T05:00:00Z", "merge_commit_sha": "m1", "head": {"sha": "h" * 40}}


def test_same_files_that_passed_on_the_pr_are_already_validated():
    ok, why = cav.decide("m1", "t1", [PR], "t1", 1)
    assert ok and "#7" in why


def test_a_branch_behind_main_runs_everything():
    assert cav.decide("m1", "t1", [PR], "t0", 1)[0] is False


def test_no_passed_pr_run_runs_everything():
    assert cav.decide("m1", "t1", [PR], "t1", 0)[0] is False


def test_a_direct_push_or_an_unmerged_pr_runs_everything():
    assert cav.decide("m1", "t1", [], "t1", 1)[0] is False
    assert cav.decide("m1", "t1", [dict(PR, merged_at=None)], "t1", 1)[0] is False
    assert cav.decide("m1", "t1", [dict(PR, merge_commit_sha="other")], "t1", 1)[0] is False


def test_an_api_error_answers_no(monkeypatch, capsys):
    monkeypatch.setenv("GITHUB_REPOSITORY", "o/r")
    monkeypatch.setenv("GITHUB_TOKEN", "x")

    def boom(*_a, **_k):
        raise OSError("down")

    monkeypatch.setattr(cav, "_get", boom)
    assert cav.main(["m1", "t1"]) == 0
    assert capsys.readouterr().out.strip() == "already=false"
