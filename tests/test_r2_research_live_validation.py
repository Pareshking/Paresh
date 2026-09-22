import pytest
from scripts.r2_research_live_validation import main

def test_live_cli_requires_pin(monkeypatch):
    monkeypatch.setattr("sys.argv", ["r2_research_live_validation"])
    try:
        main()
    except SystemExit as exc:
        assert exc.code != 0


def test_research_pin_rejects_invalid_revision(monkeypatch):
    monkeypatch.setattr("sys.argv", ["r2_research_live_validation", "--dataset", "x", "--as-of", "2026-09-18", "--revision", "bad"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code != 0
