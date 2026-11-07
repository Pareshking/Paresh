"""record_run reuses its answer for the same frame objects within a render (A1)."""
import pandas as pd

from src.engine import model_record as mr


def _calls(monkeypatch):
    seen = []

    def fake(adj, bench, system="x"):
        seen.append((id(adj), system))
        return {"live_meta": {"n": len(seen)}}

    monkeypatch.setattr(mr, "record_run_uncached", fake)
    monkeypatch.setattr(mr, "_RUN_MEMO", [])
    return seen


def test_the_same_frames_are_computed_once(monkeypatch):
    seen = _calls(monkeypatch)
    adj, bench = pd.DataFrame({"A": [1.0]}), pd.Series([1.0])
    a = mr.record_run(adj, bench, "s750")
    b = mr.record_run(adj, bench, "s750")
    assert len(seen) == 1 and a == b and a is not b


def test_another_frame_or_system_recomputes(monkeypatch):
    seen = _calls(monkeypatch)
    adj, bench = pd.DataFrame({"A": [1.0]}), pd.Series([1.0])
    mr.record_run(adj, bench, "s750")
    mr.record_run(adj, bench, "nano")
    mr.record_run(adj.copy(), bench, "s750")
    mr.record_run(adj, pd.Series([1.0]), "s750")
    assert len(seen) == 4


def test_an_entry_expires(monkeypatch):
    seen = _calls(monkeypatch)
    monkeypatch.setattr(mr, "_RUN_MEMO_TTL_S", 0.0)
    adj = pd.DataFrame({"A": [1.0]})
    mr.record_run(adj, None, "s750")
    mr.record_run(adj, None, "s750")
    assert len(seen) == 2
