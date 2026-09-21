from __future__ import annotations

import hashlib
import json

import pytest

from scripts import r2_audit


def _objects():
    body = b"canonical"
    sha = hashlib.sha256(body).hexdigest()
    object_key = f"archive/prices/screener/2026-09-21/revisions/{sha}/prices.parquet"
    manifest_key = f"archive/manifests/prices/screener/2026-09-21/revisions/{sha}.json"
    current_key = "archive/manifests/prices/screener/2026-09-21/current.json"
    manifest = {
        "dataset": "prices/screener", "as_of": "2026-09-21",
        "source": "screener", "schema_version": 1, "size_bytes": len(body),
        "sha256": sha, "object_key": object_key, "revision_sha256": sha,
    }
    current = {
        "dataset": "prices/screener", "as_of": "2026-09-21",
        "source": "screener", "revision_sha256": sha,
        "object_key": object_key, "manifest_key": manifest_key,
    }
    return {
        current_key: json.dumps(current).encode(),
        manifest_key: json.dumps(manifest).encode(),
        object_key: body,
    }, object_key


def test_live_audit_checks_head_size(monkeypatch):
    objects, object_key = _objects()

    class FakeArchive:
        def __init__(self, _config): self.objects = objects
        def get_bytes(self, key): return self.objects[key]
        def head(self, key):
            return {"ContentLength": len(self.objects[key])}

    monkeypatch.setattr(r2_audit, "R2Archive", lambda _config: FakeArchive(None))
    monkeypatch.setattr(r2_audit.R2Config, "from_env", classmethod(lambda cls: None))
    assert r2_audit.audit(dataset="prices/screener", as_of="2026-09-21")["status"] == "PASS"


def test_live_audit_rejects_head_size_mismatch(monkeypatch):
    objects, object_key = _objects()

    class FakeArchive:
        def __init__(self, _config): self.objects = objects
        def get_bytes(self, key): return self.objects[key]
        def head(self, key):
            return {"ContentLength": len(self.objects[key]) + 1}

    monkeypatch.setattr(r2_audit, "R2Archive", lambda _config: FakeArchive(None))
    monkeypatch.setattr(r2_audit.R2Config, "from_env", classmethod(lambda cls: None))
    with pytest.raises(RuntimeError, match="object HEAD size mismatch"):
        r2_audit.audit(dataset="prices/screener", as_of="2026-09-21")
