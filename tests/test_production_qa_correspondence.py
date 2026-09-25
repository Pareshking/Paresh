"""Production QA must accept a served build that contains the triggering commit."""
import importlib
import subprocess
import sys


def _qa(monkeypatch, expected):
    monkeypatch.setenv("UMIYA_EXPECTED_SHA", expected)
    sys.path.insert(0, "scripts")
    import production_qa

    return importlib.reload(production_qa)


def test_newer_descendant_build_counts_as_the_triggering_commit(monkeypatch):
    head = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    parent = subprocess.run(["git", "rev-parse", "HEAD~1"], capture_output=True, text=True).stdout.strip()
    if not parent:
        import pytest

        pytest.skip("needs git history")
    qa = _qa(monkeypatch, parent)
    assert qa._serves_expected(head[:7])        # newer, contains the trigger
    assert qa._serves_expected(parent[:7])      # exact
    qa = _qa(monkeypatch, head)
    assert not qa._serves_expected(parent[:7])  # older build is NOT the trigger
