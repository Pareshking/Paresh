import pytest
from r2.consumers.r2_research import R2ResearchConsumerError, R2ResearchPin, read_pinned_dataset
from scripts.r2_research_live_validation import main

def test_live_cli_requires_pin(monkeypatch):
    # pytest.raises, not try/except: a main() that returned normally used to pass.
    monkeypatch.setattr("sys.argv", ["r2_research_live_validation"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code != 0


def test_research_pin_rejects_invalid_revision():
    pin = R2ResearchPin("x", "2026-09-18", "bad")
    with pytest.raises(R2ResearchConsumerError, match="lowercase 64-character SHA-256"):
        read_pinned_dataset(object(), pin=pin)
