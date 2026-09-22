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
