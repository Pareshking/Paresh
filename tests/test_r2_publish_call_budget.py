"""What one R2 publication costs, and what it still refuses to publish.

C4: the payload used to be read back twice - once by
``put_file(verify=True)`` and again by ``_verify_publication`` - so every
publish downloaded the whole object twice (350.7 MB on the monthly BSE
publish). Exactly one read-back remains, and these tests pin both halves of
that: the budget, and that the surviving check still fails a byte-wrong
upload *before* a manifest or a current pointer names it.

C1: ``--skip-if-published`` lets a job that fires several times a day on
unchanged data cost two cheap calls instead of nine, while a re-run after a
real data fix still publishes.

Every test here drives the real ``R2Archive`` over a stub S3 client, so the
counted calls are the calls boto3 would have made.
"""

from __future__ import annotations

import io
import json

import pandas as pd
import pytest
from botocore.exceptions import ClientError

from src.storage import r2 as r2_mod
from src.storage.r2 import R2Archive, R2Config, R2VerificationError


class _Body(io.BytesIO):
    def iter_chunks(self, chunk_size: int = 1 << 20):
        while chunk := self.read(chunk_size):
            yield chunk


class _Client:
    """A stub S3 client that records operations and can corrupt a payload."""

    def __init__(self, *, corrupt: bool = False) -> None:
        self.ops: list[tuple[str, str]] = []
        self.store: dict[str, bytes] = {}
        self.corrupt = corrupt

    @staticmethod
    def _missing(operation: str) -> ClientError:
        return ClientError(
            {"Error": {"Code": "404"}, "ResponseMetadata": {"HTTPStatusCode": 404}},
            operation,
        )

    def put_object(self, Bucket, Key, Body=None, **kw):  # noqa: N803
        self.ops.append(("put_object", Key))
        body = Body.read() if hasattr(Body, "read") else Body
        if self.corrupt and Key.endswith(".parquet"):
            body = body[:-1] + bytes([body[-1] ^ 0xFF])
        if kw.get("IfNoneMatch") == "*" and Key in self.store:
            raise ClientError(
                {"Error": {"Code": "412"},
                 "ResponseMetadata": {"HTTPStatusCode": 412}},
                "PutObject",
            )
        self.store[Key] = body
        return {}

    def head_object(self, Bucket, Key):  # noqa: N803
        self.ops.append(("head_object", Key))
        if Key not in self.store:
            raise self._missing("HeadObject")
        return {"ContentLength": len(self.store[Key])}

    def get_object(self, Bucket, Key):  # noqa: N803
        self.ops.append(("get_object", Key))
        if Key not in self.store:
            raise self._missing("GetObject")
        return {"Body": _Body(self.store[Key])}


@pytest.fixture(autouse=True)
def _clean_counter():
    r2_mod.reset_call_counts()
    yield
    r2_mod.reset_call_counts()


def _archive(client: _Client) -> R2Archive:
    config = R2Config.from_values({
        "account_id": "acct",
        "access_key_id": "key",
        "secret_access_key": "secret",
        "endpoint": "https://acct.r2.cloudflarestorage.com",
        "bucket": "bucket",
    })
    return R2Archive(config, client=client)


def _wire(monkeypatch, client: _Client) -> R2Archive:
    from scripts import r2_publish

    adapter = _archive(client)
    monkeypatch.setattr(r2_publish, "R2Archive", lambda _config: adapter)
    monkeypatch.setattr(r2_publish.R2Config, "from_env", classmethod(lambda cls: None))
    monkeypatch.setenv("R2_CALL_LOG", "1")
    return adapter


def _payload(tmp_path, close: float = 100.0):
    path = tmp_path / "prices.parquet"
    pd.DataFrame(
        {"Symbol": ["AAA"], "Close": [close]},
        index=pd.to_datetime(["2026-09-19"]),
    ).to_parquet(path)
    return path


def _publish(tmp_path_payload, **kwargs) -> None:
    from scripts import r2_publish

    r2_publish.publish(
        tmp_path_payload,
        dataset="prices/screener",
        source="screener",
        key_root="archive/prices/screener",
        pipeline_version="test",
        release_tag="data-latest",
        **kwargs,
    )


def test_one_publication_reads_the_payload_back_exactly_once(monkeypatch, tmp_path):
    client = _Client()
    _wire(monkeypatch, client)
    path = _payload(tmp_path)

    _publish(path)

    assert r2_mod.call_counts() == {
        "put_object": 3,      # payload, manifest, current pointer
        "head_object": 1,     # the size check of the read-back
        "get_object": 3,      # the payload once, then manifest and pointer
    }
    payload_gets = [
        key for op, key in client.ops
        if op == "get_object" and key.endswith(".parquet")
    ]
    assert len(payload_gets) == 1


def test_the_surviving_check_fails_a_corrupted_upload(monkeypatch, tmp_path):
    client = _Client(corrupt=True)
    _wire(monkeypatch, client)
    path = _payload(tmp_path)

    with pytest.raises(R2VerificationError, match="SHA-256 mismatch"):
        _publish(path)

    # And it failed before anything pointed at the bad bytes.
    assert not [key for key in client.store if key.endswith(".json")]


def test_a_publication_already_in_r2_is_skipped_for_two_calls(monkeypatch, tmp_path):
    client = _Client()
    _wire(monkeypatch, client)
    path = _payload(tmp_path)

    _publish(path, skip_if_published=True)
    keys_after_first = dict(client.store)
    r2_mod.reset_call_counts()
    client.ops.clear()

    _publish(path, skip_if_published=True)

    assert r2_mod.call_counts() == {"head_object": 1, "get_object": 1}
    assert client.store == keys_after_first


def test_a_data_fix_still_publishes_under_the_skip(monkeypatch, tmp_path):
    client = _Client()
    _wire(monkeypatch, client)

    _publish(_payload(tmp_path, 100.0), skip_if_published=True)
    _publish(_payload(tmp_path, 101.0), skip_if_published=True)

    revisions = [
        key for key in client.store
        if "/revisions/" in key and key.endswith(".parquet")
    ]
    assert len(revisions) == 2
    pointer = json.loads(
        client.store["archive/manifests/prices/screener/2026-09-19/current.json"]
    )
    assert any(pointer["revision_sha256"] in key for key in revisions)


def test_without_the_flag_a_repeat_publish_still_verifies_the_stored_bytes(
    monkeypatch, tmp_path
):
    """The default path is unchanged: it re-checks rather than skipping."""
    client = _Client()
    _wire(monkeypatch, client)
    path = _payload(tmp_path)

    _publish(path)
    r2_mod.reset_call_counts()
    client.ops.clear()
    _publish(path)

    # The payload once, the already-present manifest once, then the manifest
    # and the pointer for the contract check.
    counts = r2_mod.call_counts()
    assert counts["get_object"] == 4
    assert counts["head_object"] == 1
    payload_gets = [
        key for op, key in client.ops
        if op == "get_object" and key.endswith(".parquet")
    ]
    assert len(payload_gets) == 1


def test_the_evidence_bootstrap_passes_the_skip_on_every_publish():
    from pathlib import Path

    import yaml

    root = Path(__file__).resolve().parents[1]
    doc = yaml.safe_load(
        (root / ".github/workflows/r2-historical-evidence-bootstrap.yml")
        .read_text(encoding="utf-8")
    )
    runs = [
        str(step.get("run", ""))
        for step in doc["jobs"]["bootstrap"]["steps"]
        if "scripts/r2_publish.py" in str(step.get("run", ""))
    ]
    assert len(runs) == 7
    for run in runs:
        assert run.count("scripts/r2_publish.py") == run.count("--skip-if-published")
