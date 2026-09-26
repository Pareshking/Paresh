from scripts import r2_recovery_audit

def test_recovery_revalidates_every_current_pointer():
    class FakeArchive:
        def list_keys(self, prefix):
            return iter(["archive/manifests/prices/screener/2026-09-21/current.json"])

    class FakeReader:
        def __init__(self, archive):
            pass
        def resolve_current(self, dataset, as_of):
            class Ref:
                revision_sha256 = "a" * 64
            return Ref()
        def read_bytes(self, ref):
            return b"payload"

    old = r2_recovery_audit.R2DatasetReader
    r2_recovery_audit.R2DatasetReader = FakeReader
    try:
        result = r2_recovery_audit.audit_recovery(FakeArchive())
    finally:
        r2_recovery_audit.R2DatasetReader = old

    assert result["status"] == "PASS"
    assert result["current_pointers"] == 1
    assert result["verified"][0]["dataset"] == "prices/screener"
    assert result["verified"][0]["size_bytes"] == 7


def test_recovery_revalidates_every_immutable_revision():
    class FakeArchive:
        def list_keys(self, prefix):
            return iter([
                "archive/manifests/prices/screener/2026-09-21/revisions/" + "b" * 64 + ".json",
                "archive/manifests/prices/screener/2026-09-21/current.json",
            ])

    class FakeReader:
        def __init__(self, archive):
            pass
        def resolve_revision(self, dataset, as_of, revision_sha256):
            class Ref:
                pass
            ref = Ref()
            ref.revision_sha256 = revision_sha256
            return ref
        def resolve_current(self, dataset, as_of):
            class Ref:
                revision_sha256 = "b" * 64
            return Ref()
        def read_bytes(self, ref):
            return b"payload"

    old = r2_recovery_audit.R2DatasetReader
    r2_recovery_audit.R2DatasetReader = FakeReader
    try:
        result = r2_recovery_audit.audit_recovery(FakeArchive())
    finally:
        r2_recovery_audit.R2DatasetReader = old

    assert result["immutable_revisions"] == 1
    assert len(result["immutable_verified"]) == 1
    assert result["immutable_verified"][0]["revision_sha256"] == "b" * 64



def test_manifest_contract_excludes_only_creation_timestamp():
    from scripts.r2_publish import _immutable_manifest_contract
    manifest = {
        "dataset": "d",
        "pipeline_version": "v1",
        "ranking_contract": {"universe": ["A"]},
        "created_at": "2026-09-22T00:00:00+00:00",
    }
    contract = _immutable_manifest_contract(manifest)
    assert "created_at" not in contract
    assert contract["pipeline_version"] == "v1"
    assert contract["ranking_contract"] == {"universe": ["A"]}


def _run_with(reader_cls, keys):
    class FakeArchive:
        def list_keys(self, prefix):
            return iter(keys)

    old = r2_recovery_audit.R2DatasetReader
    r2_recovery_audit.R2DatasetReader = reader_cls
    try:
        return r2_recovery_audit.audit_recovery(FakeArchive())
    finally:
        r2_recovery_audit.R2DatasetReader = old


class _Ref:
    def __init__(self, sha):
        self.revision_sha256 = sha


def test_an_unreadable_revision_fails_the_audit_instead_of_passing():
    """The audit gates every retention delete; a payload that no longer reads
    (deleted, truncated, SHA mismatch) must stop it, never be reported PASS."""
    import pytest

    class Reader:
        def __init__(self, archive):
            pass

        def resolve_revision(self, dataset, as_of, sha):
            return _Ref(sha)

        def read_bytes(self, ref):
            raise FileNotFoundError("payload missing")

    key = "archive/manifests/prices/yahoo/2026-09-21/revisions/" + "c" * 64 + ".json"
    with pytest.raises(FileNotFoundError):
        _run_with(Reader, [key])


def test_a_malformed_revision_key_fails_the_audit():
    import pytest

    key = "archive/manifests/prices/yahoo/2026-09-21/revisions/short.json"
    with pytest.raises(RuntimeError, match="Invalid immutable manifest"):
        _run_with(lambda archive: None, [key])


def test_nested_dataset_names_are_resolved_whole():
    """prices/yahoo/raw must not be read as prices/yahoo (or prices)."""
    seen = []

    class Reader:
        def __init__(self, archive):
            pass

        def resolve_revision(self, dataset, as_of, sha):
            seen.append((dataset, as_of))
            return _Ref(sha)

        def read_bytes(self, ref):
            return b"x"

    key = "archive/manifests/prices/yahoo/raw/2026-09-21/revisions/" + "d" * 64 + ".json"
    result = _run_with(Reader, [key])
    assert seen == [("prices/yahoo/raw", "2026-09-21")]
    assert result["status"] == "PASS"
