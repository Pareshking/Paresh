"""S174 "1 a" D2: the ledger stays in git; R2 holds a nightly copy, checked to match."""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("trc", ROOT / "scripts/track_record_r2_copy.py")
trc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(trc)


class FakeR2:
    def __init__(self):
        self.store: dict[str, bytes] = {}
        self.writes = 0

    def resolve_current(self, dataset):
        if dataset not in self.store:
            raise FileNotFoundError(dataset)
        return dataset

    def read_bytes(self, ref):
        return self.store[ref]

    def publish(self, path, *, dataset, as_of, **kw):
        assert as_of == "2026-11-25" and kw["source"] == "git"
        self.store[dataset] = Path(path).read_bytes()
        self.writes += 1


def _ledger(tmp_path, body=b'{"months": {}}'):
    (tmp_path / "data").mkdir(exist_ok=True)
    (tmp_path / "data/track_record.json").write_bytes(body)
    return ("data/track_record.json",)


def test_a_missing_copy_is_published_then_checked(tmp_path):
    r2, files = FakeR2(), _ledger(tmp_path)
    assert trc.run(r2, r2.publish, files, tmp_path, today="2026-11-25") == []
    assert r2.writes == 1 and r2.store["record/ledger/track_record"] == b'{"months": {}}'


def test_a_matching_copy_writes_nothing(tmp_path):
    r2, files = FakeR2(), _ledger(tmp_path)
    r2.store["record/ledger/track_record"] = b'{"months": {}}'
    assert trc.run(r2, r2.publish, files, tmp_path, today="2026-11-25") == []
    assert r2.writes == 0


def test_a_changed_ledger_gets_a_new_copy(tmp_path):
    r2, files = FakeR2(), _ledger(tmp_path, b'{"months": {"2026-11": 1}}')
    r2.store["record/ledger/track_record"] = b'{"months": {}}'
    assert trc.run(r2, r2.publish, files, tmp_path, today="2026-11-25") == []
    assert r2.writes == 1


def test_check_only_reports_a_mismatch_and_writes_nothing(tmp_path):
    r2, files = FakeR2(), _ledger(tmp_path)
    r2.store["record/ledger/track_record"] = b"other"
    assert trc.run(r2, r2.publish, files, tmp_path, check_only=True) == ["data/track_record.json"]
    assert r2.writes == 0


def test_a_copy_that_does_not_read_back_fails(tmp_path):
    r2, files = FakeR2(), _ledger(tmp_path)
    assert trc.run(r2, lambda *a, **k: None, files, tmp_path, today="2026-11-25") == ["data/track_record.json"]


def test_every_ledger_file_is_in_git_and_kept_by_retention():
    for rel in trc.LEDGER_FILES:
        # The Nifty 1000's is first written at its first freeze (1-5 Dec 2026), the others already are.
        assert (ROOT / rel).exists() or rel == "data/track_record_1000.json", rel
    assert "record/ledger/" in (ROOT / "scripts/r2_retention.py").read_text()


def test_every_system_s_ledger_is_copied():
    # S236: the Nifty 1000's ledger was not in the copy.
    from src.engine.systems import LEDGERS
    assert {str(p.relative_to(ROOT)) for p in LEDGERS.values()} == set(trc.LEDGER_FILES)
