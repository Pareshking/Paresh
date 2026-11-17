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


def test_live_cli_needs_both_pin_parts_or_neither(monkeypatch):
    monkeypatch.setattr("sys.argv", ["x", "--dataset", "d", "--as-of", "2026-09-18"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code != 0


def test_live_cli_without_a_pin_reads_the_newest_revision(monkeypatch, capsys):
    import json
    from types import SimpleNamespace

    import pandas as pd

    import scripts.r2_research_live_validation as live

    sha = "c" * 64
    seen = {}

    class Reader:
        def __init__(self, _archive):
            pass

        def resolve_current(self, dataset):
            return SimpleNamespace(dataset=dataset, as_of="2026-11-16", revision_sha256=sha)

    def _read(reader, *, pin):
        seen["pin"] = pin
        return SimpleNamespace(frame=pd.DataFrame({"a": [1, 2]}))

    monkeypatch.setattr(live, "R2DatasetReader", Reader)
    monkeypatch.setattr(live, "R2Archive", lambda cfg: None)
    monkeypatch.setattr(live.R2Config, "from_env", classmethod(lambda cls: None))
    monkeypatch.setattr(live, "read_pinned_dataset", _read)
    monkeypatch.setattr("sys.argv", ["x", "--dataset", "market_caps/nse_history"])
    assert main() == 0
    assert seen["pin"] == R2ResearchPin("market_caps/nse_history", "2026-11-16", sha)
    assert json.loads(capsys.readouterr().out)["acceptance"] == "PASS"
