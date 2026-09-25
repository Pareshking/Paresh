from pathlib import Path

import pytest

from src.storage.manifest import build_manifest, sha256_bytes, sha256_file, verify_manifest
from src.storage.r2 import R2Config, R2ImmutableObjectExists, R2VerificationError


def test_manifest_contains_required_archive_identity(tmp_path: Path):
    artifact = tmp_path / "sample.bin"
    artifact.write_bytes(b"archive-data")

    manifest = build_manifest(
        artifact,
        dataset="prices/screener",
        as_of="2026-09-18",
        source="screener",
        pipeline_version="test",
        row_count=3,
        symbol_count=2,
        min_date="2026-09-16",
        max_date="2026-09-18",
    )

    assert manifest["dataset"] == "prices/screener"
    assert manifest["as_of"] == "2026-09-18"
    assert manifest["source"] == "screener"
    assert manifest["row_count"] == 3
    assert manifest["symbol_count"] == 2
    assert manifest["min_date"] == "2026-09-16"
    assert manifest["max_date"] == "2026-09-18"
    assert manifest["size_bytes"] == len(b"archive-data")
    assert manifest["sha256"] == sha256_file(artifact)

    ok, reason = verify_manifest(artifact, manifest)
    assert (ok, reason) == (True, "ok")


def test_manifest_rejects_tampering(tmp_path: Path):
    artifact = tmp_path / "sample.bin"
    artifact.write_bytes(b"archive-data")
    manifest = build_manifest(
        artifact,
        dataset="prices/screener",
        as_of="2026-09-18",
        source="screener",
        pipeline_version="test",
    )

    artifact.write_bytes(b"changed")
    ok, reason = verify_manifest(artifact, manifest)
    assert ok is False
    assert reason == "sha256 differs"


def test_sha256_bytes():
    assert sha256_bytes(b"abc") == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


def test_r2_config_rejects_missing(monkeypatch):
    for name in (
        "R2_ACCOUNT_ID",
        "R2_ACCESS_KEY_ID",
        "R2_SECRET_ACCESS_KEY",
        "R2_ENDPOINT",
        "R2_BUCKET",
    ):
        monkeypatch.delenv(name, raising=False)

    with pytest.raises(Exception, match="Missing R2 configuration"):
        R2Config.from_env()


def test_r2_config_redacts_secret(monkeypatch):
    monkeypatch.setenv("R2_ACCOUNT_ID", "account")
    monkeypatch.setenv("R2_ACCESS_KEY_ID", "abcd1234")
    monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "super-secret")
    monkeypatch.setenv("R2_ENDPOINT", "https://account.r2.cloudflarestorage.com")
    monkeypatch.setenv("R2_BUCKET", "paresh")

    redacted = R2Config.from_env().redacted()
    assert "super-secret" not in str(redacted)
    assert redacted["access_key_id"] == "abcd..."


def test_immutable_object_error_type_is_explicit():
    assert issubclass(R2ImmutableObjectExists, RuntimeError)
    assert issubclass(R2VerificationError, RuntimeError)


class _StreamingBody:
    def __init__(self, data: bytes):
        self.data = data

    def iter_chunks(self, chunk_size=1024):
        for i in range(0, len(self.data), chunk_size):
            yield self.data[i:i + chunk_size]

    def read(self):  # pragma: no cover - verify_file must not buffer the object
        raise AssertionError("verify_file read the whole object into memory")


class _Client:
    def __init__(self, remote: bytes):
        self.remote = remote

    def head_object(self, **_):
        return {"ContentLength": len(self.remote)}

    def get_object(self, **_):
        return {"Body": _StreamingBody(self.remote)}


def _archive(remote: bytes):
    from src.storage.r2 import R2Archive

    cfg = R2Config("a", "k", "s", "https://a.r2.cloudflarestorage.com", "b")
    return R2Archive(cfg, client=_Client(remote))


def test_verify_file_streams_the_remote_hash(tmp_path: Path):
    local = tmp_path / "x.parquet"
    local.write_bytes(b"x" * (3 << 20))
    _archive(b"x" * (3 << 20)).verify_file("k", local)

    with pytest.raises(R2VerificationError, match="SHA-256 mismatch"):
        _archive(b"y" * (3 << 20)).verify_file("k", local)
    with pytest.raises(R2VerificationError, match="size mismatch"):
        _archive(b"x").verify_file("k", local)
