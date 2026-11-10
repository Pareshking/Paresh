"""The R2 adapter's call counter: off by default, and it changes no call.

The counter exists so a later audit can count R2 operations without guessing
(docs/CALL_AND_STORAGE_AUDIT.md). Nothing in the repository sets R2_CALL_LOG,
so these tests also pin that the default is silence.
"""

from __future__ import annotations

import io

import pytest

from src.storage import r2 as r2_mod
from src.storage.r2 import R2Archive, R2Config


class _Body(io.BytesIO):
    def iter_chunks(self, chunk_size: int = 1 << 20):
        while chunk := self.read(chunk_size):
            yield chunk


class _Client:
    """Records every operation the adapter asks for."""

    def __init__(self) -> None:
        self.ops: list[tuple[str, str]] = []
        self.store: dict[str, bytes] = {}

    def put_object(self, Bucket, Key, Body=None, **kw):  # noqa: N803
        self.ops.append(("put_object", Key))
        self.store[Key] = Body.read() if hasattr(Body, "read") else Body
        return {}

    def head_object(self, Bucket, Key):  # noqa: N803
        self.ops.append(("head_object", Key))
        return {"ContentLength": len(self.store[Key])}

    def get_object(self, Bucket, Key):  # noqa: N803
        self.ops.append(("get_object", Key))
        return {"Body": _Body(self.store[Key])}

    def delete_object(self, Bucket, Key):  # noqa: N803
        self.ops.append(("delete_object", Key))
        self.store.pop(Key, None)

    def get_paginator(self, name):
        client = self

        class _Paginator:
            def paginate(self, **kw):
                client.ops.append(("list_objects_v2", kw.get("Prefix", "")))
                return [{"Contents": [{"Key": k, "Size": len(v)}
                                      for k, v in sorted(client.store.items())]}]

        return _Paginator()


@pytest.fixture
def archive() -> tuple[R2Archive, _Client]:
    config = R2Config.from_values({
        "account_id": "acct",
        "access_key_id": "key",
        "secret_access_key": "secret",
        "endpoint": "https://acct.r2.cloudflarestorage.com",
        "bucket": "bucket",
    })
    client = _Client()
    return R2Archive(config, client=client), client


@pytest.fixture(autouse=True)
def _clean_counter():
    r2_mod.reset_call_counts()
    yield
    r2_mod.reset_call_counts()


def _exercise(archive: R2Archive) -> None:
    archive.put_bytes("a/one.txt", b"one", immutable=False)
    archive.head("a/one.txt")
    archive.get_bytes("a/one.txt")
    list(archive.list_keys("a/"))
    list(archive.list_objects("a/"))
    archive.delete("a/one.txt")


def test_the_counter_is_silent_unless_the_env_var_is_set(archive, monkeypatch):
    adapter, _client = archive
    monkeypatch.delenv("R2_CALL_LOG", raising=False)
    _exercise(adapter)
    assert r2_mod.call_counts() == {}


def test_the_counter_names_each_operation_when_asked(archive, monkeypatch):
    adapter, _client = archive
    monkeypatch.setenv("R2_CALL_LOG", "1")
    _exercise(adapter)
    assert r2_mod.call_counts() == {
        "put_object": 1,
        "head_object": 1,
        "get_object": 1,
        "list_objects_v2": 2,
        "delete_object": 1,
    }


@pytest.mark.parametrize("counting", [False, True])
def test_counting_changes_no_call_the_adapter_makes(archive, monkeypatch, counting):
    """The same operations, in the same order, with the counter on and off."""
    adapter, client = archive
    if counting:
        monkeypatch.setenv("R2_CALL_LOG", "1")
    else:
        monkeypatch.delenv("R2_CALL_LOG", raising=False)
    _exercise(adapter)
    assert client.ops == [
        ("put_object", "a/one.txt"),
        ("head_object", "a/one.txt"),
        ("get_object", "a/one.txt"),
        ("list_objects_v2", "a/"),
        ("list_objects_v2", "a/"),
        ("delete_object", "a/one.txt"),
    ]


def test_verify_file_reads_the_whole_object_back(archive, monkeypatch, tmp_path):
    """One put_file(verify=True) costs a put, a head and a whole-object get."""
    adapter, _client = archive
    monkeypatch.setenv("R2_CALL_LOG", "1")
    source = tmp_path / "payload.bin"
    source.write_bytes(b"payload")
    adapter.put_file("a/payload.bin", source, immutable=False, verify=True)
    assert r2_mod.call_counts() == {
        "put_object": 1,
        "head_object": 1,
        "get_object": 1,
    }


def test_nothing_in_the_repository_switches_the_counter_on():
    """A job or the app must not start counting by accident."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    setters = []
    for path in list(root.glob(".github/workflows/*.yml")) + \
            list(root.glob("scripts/*.py")) + list(root.glob("src/**/*.py")):
        text = path.read_text(encoding="utf-8", errors="replace")
        if "R2_CALL_LOG" in text and path != root / "src/storage/r2.py":
            setters.append(str(path.relative_to(root)))
    assert setters == []
