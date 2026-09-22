import pytest
from scripts.r2_membership_live_validation import main

def test_cli_requires_a_date(monkeypatch):
    monkeypatch.setattr("sys.argv", ["r2_membership_live_validation"])
    with pytest.raises(SystemExit):
        main()

def test_cli_rejects_invalid_date(monkeypatch):
    monkeypatch.setattr("sys.argv", ["r2_membership_live_validation", "--as-of", "not-a-date"])
    with pytest.raises(ValueError):
        main()
