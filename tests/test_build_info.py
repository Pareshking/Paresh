"""Deploy correspondence: which commit is actually serving the app.

Production QA fires on push and can connect before Streamlit has swapped
builds, testing the PREVIOUS commit and reporting the new one red -- which is
what happened to c151597, whose QA started two seconds after its push. The
probe compares the revision the app publishes against the commit that
triggered the run, so a deploy lag is named rather than blamed on the code.
"""
import os
import subprocess

import pytest

from src.core.build_info import deployed_revision, short_revision


def test_revision_matches_git():
    expected = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True
    ).stdout.strip()
    assert deployed_revision() == expected
    assert short_revision() == expected[:7]


def test_detached_head_sha_is_read_directly(tmp_path):
    git = tmp_path / ".git"
    git.mkdir()
    (git / "HEAD").write_text("a" * 40)
    assert deployed_revision(str(tmp_path)) == "a" * 40


def test_symbolic_ref_is_resolved(tmp_path):
    git = tmp_path / ".git"
    (git / "refs" / "heads").mkdir(parents=True)
    (git / "HEAD").write_text("ref: refs/heads/main\n")
    (git / "refs" / "heads" / "main").write_text("b" * 40 + "\n")
    assert deployed_revision(str(tmp_path)) == "b" * 40


def test_packed_refs_are_consulted_when_no_loose_ref(tmp_path):
    """A fresh clone -- which is what Streamlit Cloud makes -- often packs refs."""
    git = tmp_path / ".git"
    git.mkdir()
    (git / "HEAD").write_text("ref: refs/heads/main\n")
    (git / "packed-refs").write_text(
        "# pack-refs with: peeled fully-peeled sorted\n"
        f"{'c' * 40} refs/heads/main\n"
        f"{'d' * 40} refs/heads/other\n"
    )
    assert deployed_revision(str(tmp_path)) == "c" * 40


def test_gitdir_pointer_file_is_followed(tmp_path):
    real = tmp_path / "realgit"
    (real / "refs" / "heads").mkdir(parents=True)
    (real / "HEAD").write_text("ref: refs/heads/main\n")
    (real / "refs" / "heads" / "main").write_text("e" * 40)
    work = tmp_path / "work"
    work.mkdir()
    (work / ".git").write_text(f"gitdir: {real}\n")
    assert deployed_revision(str(work)) == "e" * 40


def test_absent_git_metadata_returns_none_rather_than_guessing(tmp_path):
    """None is safer than a wrong SHA: the probe would trust a false mismatch."""
    assert deployed_revision(str(tmp_path)) is None
    assert short_revision(str(tmp_path)) is None


def test_revision_is_published_in_startup_telemetry():
    from src.core import startup_metrics as metrics

    assert metrics.snapshot()["revision"] == deployed_revision()
