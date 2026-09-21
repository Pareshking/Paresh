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
