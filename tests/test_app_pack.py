"""The app pack (S172 (b), owner 26 Nov 2026: "Stop commit and save everything in R2")."""

import sys
from pathlib import Path

import pytest

from src.loaders import app_pack as ap
from src.loaders import app_source

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import app_pack as writer  # noqa: E402


class _Ref:
    def __init__(self, sha):
        self.revision_sha256 = sha


class FakeR2:
    """Just enough of R2DatasetReader: one dataset, a current revision or none."""

    def __init__(self, body=None):
        self.body = body

    def resolve_current(self, dataset):
        assert dataset == ap.DATASET
        if self.body is None:
            raise FileNotFoundError(dataset)
        return _Ref(ap.sha256(self.body))

    def read_bytes(self, ref):
        return self.body


@pytest.fixture(autouse=True)
def _fresh(monkeypatch, tmp_path):
    monkeypatch.setitem(ap.__dict__, "_STATE", {"dir": None, "revision": None, "checked": 0.0, "files": {}})
    monkeypatch.setenv("APP_PACK_DIR", str(tmp_path / "packdir"))
    app_source.UNREACHED.discard(ap.LABEL)


def test_every_listed_file_is_committed_and_none_is_a_reference_table_or_ledger():
    assert len(ap.FILES) == len(set(ap.FILES)) == 37
    for rel in ap.FILES:
        assert (ROOT / rel).is_file(), rel
        assert not rel.startswith("data/track_record"), rel
        assert rel == "data/reference/screener_earnings.csv" or not rel.startswith("data/reference/"), rel


def test_the_pack_is_deterministic_and_checked_file_by_file():
    body = ap.build(ROOT)
    assert body == ap.build(ROOT)
    files = ap.unpack(body)
    assert set(files) == set(ap.FILES)
    assert files["data/benchmarks.csv"] == (ROOT / "data/benchmarks.csv").read_bytes()


def test_a_pack_whose_bytes_differ_from_its_list_is_refused(tmp_path):
    (tmp_path / "data").mkdir()
    (tmp_path / "data/benchmarks.csv").write_text("date,x\n2026-11-25,1\n")
    import io
    import zipfile

    good = zipfile.ZipFile(io.BytesIO(ap.build(tmp_path, files=("data/benchmarks.csv",))))
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as z:            # the same list, other bytes for the file
        z.writestr(ap.MANIFEST, good.read(ap.MANIFEST))
        z.writestr("data/benchmarks.csv", b"date,x\n2026-11-25,9\n")
    tampered = out.getvalue()
    with pytest.raises(ap.PackError):
        ap.unpack(tampered)


def test_resolve_serves_the_packs_copy_and_leaves_other_paths_alone(tmp_path):
    (tmp_path / "data").mkdir()
    (tmp_path / "data/benchmarks.csv").write_text("from the pack\n")
    body = ap.build(tmp_path, files=("data/benchmarks.csv",))
    assert ap.refresh(FakeR2(body), force=True) == ap.sha256(body)
    got = ap.resolve(str(ROOT / "data/benchmarks.csv"))
    assert isinstance(got, str) and Path(got).read_text() == "from the pack\n"
    got = ap.resolve(ROOT / "data/benchmarks.csv")
    assert isinstance(got, Path)
    # Not in the pack: the path as given.
    assert ap.resolve(ROOT / "data/benchmark_indices.csv") == ROOT / "data/benchmark_indices.csv"
    # Not a pack file at all (a ledger stays in git).
    assert ap.resolve(ROOT / "data/track_record.json") == ROOT / "data/track_record.json"
    assert ap.LABEL not in app_source.UNREACHED


def test_no_pack_yet_serves_the_committed_files_without_the_backup_note():
    assert ap.refresh(FakeR2(None), force=True) is None
    assert ap.resolve(ROOT / "data/benchmarks.csv") == ROOT / "data/benchmarks.csv"
    assert ap.LABEL not in app_source.UNREACHED


def test_a_broken_pack_serves_the_committed_files_with_the_backup_note():
    assert ap.refresh(FakeR2(b"not a zip"), force=True) is None
    assert ap.resolve(ROOT / "data/benchmarks.csv") == ROOT / "data/benchmarks.csv"
    assert ap.LABEL in app_source.UNREACHED


def test_without_r2_keys_nothing_is_asked(monkeypatch):
    monkeypatch.setattr(app_source, "r2_config", lambda: None)
    assert ap.resolve(ROOT / "data/benchmarks.csv") == ROOT / "data/benchmarks.csv"


def test_the_writer_publishes_only_a_changed_pack_and_checks_it_against_the_checkout():
    store = FakeR2(None)
    published = []

    def publish(path, **kw):
        published.append(kw)
        store.body = Path(path).read_bytes()

    assert writer.run(store, publish, root=ROOT, today="2026-11-26") == []
    assert len(published) == 1 and published[0]["dataset"] == ap.DATASET and published[0]["as_of"] == "2026-11-26"
    assert writer.run(store, publish, root=ROOT) == []          # unchanged: nothing written
    assert len(published) == 1


def test_the_writer_fails_when_r2_holds_other_bytes(tmp_path):
    (tmp_path / "data").mkdir()
    (tmp_path / "data/benchmarks.csv").write_text("old\n")
    stale = FakeR2(ap.build(tmp_path, files=("data/benchmarks.csv",)))
    bad = writer.run(stale, lambda *a, **k: None, root=ROOT, check_only=True)
    assert "data/benchmarks.csv" in bad
