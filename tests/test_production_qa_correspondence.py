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


def _commit(repo, message, files=None):
    for name, text in (files or {}).items():
        path = Path(repo) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        _git(repo, "add", name)
    _git(repo, "-c", "user.email=a@b", "-c", "user.name=a",
         "commit", "-q", "--allow-empty", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


def test_src_changed_since_the_process_started_is_reported_stale(tmp_path, monkeypatch):
    """The 2026-09-25 case: #177 on disk, src/ still the build imported at #173."""
    _git(tmp_path, "init", "-q")
    loaded = _commit(tmp_path, "process starts here", {"src/ui/components.py": "old\n"})
    scripts_only = _commit(tmp_path, "scripts only", {"scripts/x.py": "1\n"})
    ui_fix = _commit(tmp_path, "menu fix", {"src/ui/components.py": "new\n"})
    monkeypatch.chdir(tmp_path)
    qa = _qa(monkeypatch, ui_fix)

    assert qa._stale_modules(loaded, ui_fix) == ["src/ui/components.py"]
    # A push that never touches src/ leaves nothing stale: app.py is re-read
    # every run and scripts/ never reach the process.
    assert qa._stale_modules(loaded, scripts_only) == []
    assert qa._stale_modules(ui_fix, ui_fix) == []
    # An old process without the telemetry field cannot be judged.
    assert qa._stale_modules(None, ui_fix) == []
