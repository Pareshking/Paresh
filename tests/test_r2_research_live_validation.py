import pytest
from r2.consumers.r2_research import R2ResearchConsumerError, R2ResearchPin, read_pinned_dataset
from scripts.r2_research_live_validation import main

def test_live_cli_requires_pin(monkeypatch):
    monkeypatch.setattr("sys.argv", ["r2_research_live_validation"])
    try:
        main()
    except SystemExit as exc:
        assert exc.code != 0


def test_research_pin_rejects_invalid_revision():
    pin = R2ResearchPin("x", "2026-09-18", "bad")
    with pytest.raises(R2ResearchConsumerError, match="lowercase 64-character SHA-256"):
        read_pinned_dataset(object(), pin=pin)
