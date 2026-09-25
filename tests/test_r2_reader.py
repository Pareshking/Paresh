"""Tests for the manifest-pinned R2 dataset reader."""

import json

import pytest

from src.storage.manifest import sha256_bytes
from src.storage.reader import R2DatasetIntegrityError, R2DatasetReader


class FakeArchive:
    def __init__(self, objects):
        self.objects = dict(objects)

    def get_bytes(self, key):
        return self.objects[key]

    def head(self, key):
        return {"ContentLength": len(self.objects[key])}

    def list_keys(self, prefix=""):
        return iter(sorted(k for k in self.objects if k.startswith(prefix)))


def _archive_for_current(body=b"parquet-bytes"):
    sha = sha256_bytes(body)
    dataset = "trading_sessions/observed"
    as_of = "2026-09-21"
    object_key = (
        "archive/trading_days/observed/2026-09-21/revisions/"
        f"{sha}/trading_sessions_observed.parquet"
    )
    manifest_key = (
        "archive/manifests/trading_sessions/observed/2026-09-21/revisions/"
        f"{sha}.json"
    )
    pointer_key = "archive/manifests/trading_sessions/observed/2026-09-21/current.json"
    manifest = {
        "dataset": dataset,
        "as_of": as_of,
        "schema_version": 1,
        "sha256": sha,
        "revision_sha256": sha,
        "size_bytes": len(body),
        "object_key": object_key,
        "created_at": "2026-09-21T00:00:00Z",
    }
    pointer = {
        "dataset": dataset,
        "as_of": as_of,
        "revision_sha256": sha,
        "object_key": object_key,
        "manifest_key": manifest_key,
    }
    return FakeArchive(
        {
            pointer_key: json.dumps(pointer).encode(),
            manifest_key: json.dumps(manifest).encode(),
            object_key: body,
        }
    ), dataset, as_of, sha


def test_reader_resolves_current_pointer_and_validates_head_and_sha():
    archive, dataset, as_of, sha = _archive_for_current()
    reader = R2DatasetReader(archive)

    ref = reader.resolve_current(dataset, as_of=as_of)

    assert ref.revision_sha256 == sha
    assert ref.as_of == as_of
    assert ref.manifest["object_key"] == ref.object_key
    assert reader.read_bytes(ref) == b"parquet-bytes"


def test_reader_resolves_current_without_explicit_as_of():
    archive, dataset, as_of, _ = _archive_for_current()
    reader = R2DatasetReader(archive)

    ref = reader.resolve_current(dataset)

    assert ref.as_of == as_of


def test_reader_rejects_object_hash_mismatch():
    archive, dataset, as_of, _ = _archive_for_current(body=b"correct")
    pointer = next(k for k in archive.objects if k.endswith("/current.json"))
    payload = json.loads(archive.objects[pointer])
    archive.objects[payload["object_key"]] = b"wrong!!"

    reader = R2DatasetReader(archive)
    ref = reader.resolve_current(dataset, as_of=as_of)

    with pytest.raises(R2DatasetIntegrityError, match="SHA mismatch"):
        reader.read_bytes(ref)


def test_reader_rejects_manifest_revision_mismatch():
    archive, dataset, as_of, _ = _archive_for_current()
    manifest_key = next(k for k in archive.objects if "/revisions/" in k and k.endswith(".json"))
    manifest = json.loads(archive.objects[manifest_key])
    manifest["revision_sha256"] = "0" * 64
    archive.objects[manifest_key] = json.dumps(manifest).encode()

    reader = R2DatasetReader(archive)
    with pytest.raises(R2DatasetIntegrityError, match="manifest .*SHA"):
        reader.resolve_current(dataset, as_of=as_of)


def test_reader_rejects_invalid_manifest_as_of():
    archive, dataset, as_of, _ = _archive_for_current()
    manifest_key = next(k for k in archive.objects if "/revisions/" in k and k.endswith(".json"))
    manifest = json.loads(archive.objects[manifest_key])
    manifest["as_of"] = "2026-09-21T00:00:00"
    archive.objects[manifest_key] = json.dumps(manifest).encode()
    with pytest.raises(R2DatasetIntegrityError, match="invalid as_of"):
        R2DatasetReader(archive).resolve_current(dataset, as_of=as_of)


def test_reader_rejects_missing_manifest_created_at():
    archive, dataset, as_of, _ = _archive_for_current()
    manifest_key = next(k for k in archive.objects if "/revisions/" in k and k.endswith(".json"))
    manifest = json.loads(archive.objects[manifest_key])
    manifest.pop("created_at", None)
    archive.objects[manifest_key] = json.dumps(manifest).encode()
    with pytest.raises(R2DatasetIntegrityError, match="created_at"):
        R2DatasetReader(archive).resolve_current(dataset, as_of=as_of)


def _objects_for(dataset, as_of, body):
    sha = sha256_bytes(body)
    object_key = f"archive/{dataset}/{as_of}/revisions/{sha}/data.parquet"
    manifest_key = f"archive/manifests/{dataset}/{as_of}/revisions/{sha}.json"
    manifest = {
        "dataset": dataset, "as_of": as_of, "schema_version": 1,
        "sha256": sha, "revision_sha256": sha, "size_bytes": len(body),
        "object_key": object_key, "created_at": f"{as_of}T00:00:00Z",
    }
    pointer = {
        "dataset": dataset, "as_of": as_of, "revision_sha256": sha,
        "object_key": object_key, "manifest_key": manifest_key,
    }
    return {
        f"archive/manifests/{dataset}/{as_of}/current.json": json.dumps(pointer).encode(),
        manifest_key: json.dumps(manifest).encode(),
        object_key: body,
    }


def test_reader_ignores_a_nested_datasets_pointers():
    """prices/yahoo must not resolve to a pointer of prices/yahoo/raw.

    The manifest listing is a prefix match and "raw/..." sorts after every
    date, so the nested dataset's pointer used to win and fail the dataset
    check -- which is why the app was moved onto the frozen raw archive.
    """
    objects = {}
    objects.update(_objects_for("prices/yahoo", "2026-09-24", b"adjusted"))
    objects.update(_objects_for("prices/yahoo/raw", "2026-09-21", b"raw"))
    reader = R2DatasetReader(FakeArchive(objects))

    parent = reader.resolve_current("prices/yahoo")
    assert (parent.dataset, parent.as_of) == ("prices/yahoo", "2026-09-24")
    assert reader.read_bytes(parent) == b"adjusted"

    nested = reader.resolve_current("prices/yahoo/raw")
    assert (nested.dataset, nested.as_of) == ("prices/yahoo/raw", "2026-09-21")


def test_reader_rejects_a_pointer_that_disagrees_with_its_manifest():
    objects = _objects_for("prices/yahoo", "2026-09-24", b"adjusted")
    key = "archive/manifests/prices/yahoo/2026-09-24/current.json"
    pointer = json.loads(objects[key])
    pointer["object_key"] = "archive/somewhere/else.parquet"
    objects[key] = json.dumps(pointer).encode()
    objects["archive/somewhere/else.parquet"] = b"adjusted"
    with pytest.raises(R2DatasetIntegrityError, match="object_key mismatch"):
        R2DatasetReader(FakeArchive(objects)).resolve_current("prices/yahoo")
