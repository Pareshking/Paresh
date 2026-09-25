"""Production QA must accept a served build that contains the triggering commit."""
import importlib
import subprocess
import sys
from pathlib import Path

_SCRIPTS = str(Path(__file__).resolve().parents[1] / "scripts")


def _git(repo, *args) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()


def _qa(monkeypatch, expected):
    monkeypatch.setenv("UMIYA_EXPECTED_SHA", expected)
    if _SCRIPTS not in sys.path:
        sys.path.insert(0, _SCRIPTS)
    import production_qa

    return importlib.reload(production_qa)


def test_newer_descendant_build_counts_as_the_triggering_commit(tmp_path, monkeypatch):
    """Hermetic: its own two-commit repo, so a shallow CI checkout cannot matter."""
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "-c", "user.email=a@b", "-c", "user.name=a",
         "commit", "-q", "--allow-empty", "-m", "merge")
    older = _git(tmp_path, "rev-parse", "HEAD")
    _git(tmp_path, "-c", "user.email=a@b", "-c", "user.name=a",
         "commit", "-q", "--allow-empty", "-m", "data sync")
    newer = _git(tmp_path, "rev-parse", "HEAD")
    monkeypatch.chdir(tmp_path)

    qa = _qa(monkeypatch, older)
    assert qa._serves_expected(newer[:7])       # newer, contains the trigger
    assert qa._serves_expected(older[:7])       # exact
    qa = _qa(monkeypatch, newer)
    assert not qa._serves_expected(older[:7])   # an older build is not the trigger
