from __future__ import annotations

import json

import pytest

from scripts import r2_audit


class FakeArchive:
    def __init__(self, objects):
        self.objects = dict(objects)

    def get_bytes(self, key):
        return self.objects[key]


def _publication():
    body = b"example parquet bytes"
    import hashlib
    digest = hashlib.sha256(body).hexdigest()
    manifest_key = "archive/manifests/prices/screener/2026-09-21/revisions/x.json"
    object_key = "archive/prices/screener/2026-09-21/revisions/x/screener_prices.parquet"
    current_key = "archive/manifests/prices/screener/2026-09-21/current.json"
    manifest = {
        "dataset": "prices/screener",
        "as_of": "2026-09-21",
        "source": "screener",
        "schema_version": 1,
        "size_bytes": len(body),
        "sha256": digest,
        "object_key": object_key,
        "revision_sha256": digest,
    }
    current = {
        "dataset": "prices/screener",
        "as_of": "2026-09-21",
        "source": "screener",
        "revision_sha256": digest,
        "object_key": object_key,
        "manifest_key": manifest_key,
    }
    return {
        current_key: json.dumps(current).encode(),
        manifest_key: json.dumps(manifest).encode(),
        object_key: body,
    }, current_key, digest


def _run(monkeypatch, objects):
    fake = FakeArchive(objects)
    monkeypatch.setattr(r2_audit, "R2Archive", lambda _config: fake)
    monkeypatch.setattr(
        r2_audit.R2Config,
        "from_env",
        classmethod(lambda cls: object()),
    )
    return fake


def test_audit_passes_complete_publication(monkeypatch):
    objects, _, digest = _publication()
    _run(monkeypatch, objects)

    result = r2_audit.audit(dataset="prices/screener", as_of="2026-09-21")

    assert result["status"] == "PASS"
    assert result["sha256"] == digest


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (
            lambda c, m: c.update({"revision_sha256": "wrong"}),
            "pointer/manifest mismatch revision_sha256",
        ),
        (
            lambda c, m: m.update({"sha256": "wrong"}),
            "object SHA mismatch",
        ),
        (
            lambda c, m: m.update({"schema_version": 999}),
            "unsupported manifest schema version",
        ),
    ],
)
def test_audit_fails_closed_on_publication_corruption(monkeypatch, mutation, message):
    objects, current_key, _ = _publication()
    current = json.loads(objects[current_key])
    manifest_key = current["manifest_key"]
    manifest = json.loads(objects[manifest_key])
    mutation(current, manifest)
    objects[current_key] = json.dumps(current).encode()
    objects[manifest_key] = json.dumps(manifest).encode()

    _run(monkeypatch, objects)

    with pytest.raises(RuntimeError, match=message):
        r2_audit.audit(dataset="prices/screener", as_of="2026-09-21")


def test_audit_rejects_pointer_identity_mismatch(monkeypatch):
    objects, current_key, _ = _publication()
    current = json.loads(objects[current_key])
    current["as_of"] = "2026-09-20"
    objects[current_key] = json.dumps(current).encode()
    _run(monkeypatch, objects)

    with pytest.raises(RuntimeError, match="current pointer identity mismatch"):
        r2_audit.audit(dataset="prices/screener", as_of="2026-09-21")
