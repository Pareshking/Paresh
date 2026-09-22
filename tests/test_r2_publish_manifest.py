import json

from scripts.r2_publish import _publish_manifest
from src.storage.r2 import R2ImmutableObjectExists


class FakeArchive:
    def __init__(self, existing):
        self.existing = existing

    def put_bytes(self, key, body, **kwargs):
        if self.existing is not None:
            raise R2ImmutableObjectExists(key)
        self.existing = json.loads(body.decode())

    def get_bytes(self, key):
        return json.dumps(self.existing).encode()


def test_same_revision_pipeline_metadata_drift_is_idempotent():
    existing = {"dataset": "x", "as_of": "2026-09-22", "sha256": "abc", "row_count": 1, "pipeline_version": "old"}
    candidate = dict(existing, pipeline_version="new")
    result = _publish_manifest(FakeArchive(existing), candidate, "manifest.json")
    assert result["pipeline_version"] == "old"


def test_same_revision_material_manifest_drift_is_rejected():
    existing = {"dataset": "x", "as_of": "2026-09-22", "sha256": "abc", "row_count": 1, "pipeline_version": "old"}
    candidate = dict(existing, row_count=2)
    try:
        _publish_manifest(FakeArchive(existing), candidate, "manifest.json")
    except RuntimeError as exc:
        assert "row_count" in str(exc)
    else:
        raise AssertionError("material manifest drift was not rejected")
