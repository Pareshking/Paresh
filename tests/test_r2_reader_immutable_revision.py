import pytest

from src.storage.reader import R2DatasetReader


class FakeArchive:
    def __init__(self):
        self.manifests = {}
        self.objects = {}

    def list_keys(self, prefix):
        return [k for k in self.manifests if k.startswith(prefix)]

    def get_bytes(self, key):
        return self.manifests[key]

    def head(self, key):
        return {"ContentLength": len(self.objects[key])}


def _manifest(dataset, as_of, revision, created_at, object_key, body_size):
    import json
    body = b"not-parquet"
    return json.dumps({
        "schema_version": 1,
        "dataset": dataset,
        "as_of": as_of,
        "sha256": revision,
        "revision_sha256": revision,
        "size_bytes": body_size,
        "object_key": object_key,
        "created_at": created_at,
    }).encode()


def test_resolve_latest_revision_uses_immutable_manifests():
    import hashlib
    dataset = "indices/membership/nifty_total_market"
    as_of = "2026-09-18"
    body1 = b"one"
    body2 = b"two"
    r1 = hashlib.sha256(body1).hexdigest()
    r2 = hashlib.sha256(body2).hexdigest()
    archive = FakeArchive()
    archive.objects["obj1"] = body1
    archive.objects["obj2"] = body2
    k1 = f"archive/manifests/{dataset}/{as_of}/revisions/{r1}.json"
    k2 = f"archive/manifests/{dataset}/{as_of}/revisions/{r2}.json"
    archive.manifests[k1] = _manifest(dataset, as_of, r1, "2026-09-18T10:00:00Z", "obj1", len(body1))
    archive.manifests[k2] = _manifest(dataset, as_of, r2, "2026-09-18T11:00:00Z", "obj2", len(body2))
    ref = R2DatasetReader(archive).resolve_latest_revision(dataset, as_of)
    assert ref.revision_sha256 == r2
    assert ref.object_key == "obj2"


def test_resolve_latest_revision_fails_closed_when_none_exist():
    with pytest.raises(FileNotFoundError, match="no immutable R2 revisions"):
        R2DatasetReader(FakeArchive()).resolve_latest_revision(
            "indices/membership/nifty_total_market", "2026-09-18"
        )
