"""The app reads its published files from R2 first, the release second."""
import hashlib
import io
import json

import pandas as pd
from src.loaders import app_source


class FakeArchive:
    def __init__(self):
        self.objects: dict[str, bytes] = {}

    def list_keys(self, prefix):
        return iter(sorted(k for k in self.objects if k.startswith(prefix)))

    def get_bytes(self, key):
        return self.objects[key]

    def head(self, key):
        return {"ContentLength": len(self.objects[key])}


def _publish(a, dataset, as_of, body: bytes, tamper=False):
    sha = hashlib.sha256(body).hexdigest()
    obj = f"root/{as_of}/revisions/{sha}/file.parquet"
    mkey = f"archive/manifests/{dataset}/{as_of}/revisions/{sha}.json"
    manifest = {"schema_version": 1, "dataset": dataset, "as_of": as_of,
                "object_key": obj, "sha256": sha, "size_bytes": len(body),
                "revision_sha256": sha, "created_at": "2026-09-27T00:00:00+00:00"}
    a.objects[obj] = body + (b"x" if tamper else b"")
    a.objects[mkey] = json.dumps(manifest).encode()
    a.objects[f"archive/manifests/{dataset}/{as_of}/current.json"] = json.dumps(
        {"dataset": dataset, "as_of": as_of, "revision_sha256": sha,
         "manifest_key": mkey, "object_key": obj}).encode()


def _parquet(v):
    buf = io.BytesIO()
    pd.DataFrame({"x": [v]}).to_parquet(buf)
    return buf.getvalue()


def test_the_newest_verified_revision_is_served(monkeypatch):
    a = FakeArchive()
    _publish(a, "snapshots/rankings", "2026-09-24", _parquet(1))
    _publish(a, "snapshots/rankings", "2026-09-25", _parquet(2))
    body = app_source.fetch_latest("snapshots/rankings", "rankings", archive=a)
    assert pd.read_parquet(io.BytesIO(body))["x"].iloc[0] == 2


def test_a_tampered_object_is_refused_and_the_caller_falls_back():
    a = FakeArchive()
    _publish(a, "snapshots/rankings", "2026-09-25", _parquet(2), tamper=True)
    assert app_source.fetch_latest("snapshots/rankings", "rankings", archive=a) is None


def test_no_keys_means_release_files(monkeypatch):
    for k in app_source._KEYS:
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(app_source, "_from_secrets", lambda: {})
    assert app_source.r2_config() is None
    assert app_source.fetch_latest("snapshots/rankings", "rankings") is None


def test_keys_are_read_from_an_r2_secrets_section(monkeypatch):
    for k in app_source._KEYS:
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(app_source, "_from_secrets", lambda: {
        "R2_ACCOUNT_ID": "acc", "R2_ACCESS_KEY_ID": "key", "R2_SECRET_ACCESS_KEY": "sec",
        "R2_ENDPOINT": "https://acc.r2.cloudflarestorage.com/", "R2_BUCKET": "b"})
    cfg = app_source.r2_config()
    assert cfg.bucket == "b" and cfg.endpoint == "https://acc.r2.cloudflarestorage.com"


def test_a_bad_endpoint_is_not_used(monkeypatch):
    for k in app_source._KEYS:
        monkeypatch.setenv(k, "x")
    assert app_source.r2_config() is None


def test_summary_names_the_source():
    app_source.SOURCES.clear()
    assert app_source.summary() == ""
    app_source.record("rankings", "r2")
    app_source.record("screener_store", "r2")
    assert app_source.summary() == "R2"
    app_source.record("price_snapshot", "release")
    assert "price_snapshot: release" in app_source.summary()
    app_source.SOURCES.clear()


def test_the_record_survives_a_code_reload():
    # The loaders that fill SOURCES are cached, so after src/core/code_reload
    # drops and re-imports this module they do not run again; the footer
    # must still say where the data came from.
    import importlib
    import sys

    app_source.SOURCES.clear()
    app_source.record("rankings", "r2")
    del sys.modules["src.loaders.app_source"]
    fresh = importlib.import_module("src.loaders.app_source")
    try:
        assert fresh.summary() == "R2"
    finally:
        fresh.SOURCES.clear()


def test_an_older_code_reload_without_persistent_still_imports():
    # code_reload is exempt from reloading, so production can hold a copy
    # that predates PERSISTENT while this module is re-imported.
    import importlib
    import sys

    from src.core import code_reload

    saved = code_reload.__dict__.pop("PERSISTENT")
    del sys.modules["src.loaders.app_source"]
    try:
        fresh = importlib.import_module("src.loaders.app_source")
        fresh.record("rankings", "r2")
        assert fresh.summary() == "R2"
    finally:
        code_reload.PERSISTENT = saved
        del sys.modules["src.loaders.app_source"]
        importlib.import_module("src.loaders.app_source")


def test_the_r2_reader_is_imported_with_the_module_not_inside_a_thread():
    # Log, 7 Oct 2026: two threads importing src.storage.reader at once raised
    # _DeadlockError and the R2 ranking fell back to the release file.
    from pathlib import Path

    src = (Path(__file__).resolve().parents[1] / "src/loaders/app_source.py").read_text(encoding="utf-8")
    head, _, body = src.partition("def fetch_latest(")
    assert "from src.storage.reader import R2DatasetReader" in head
    assert "import" not in body.split("\ndef ", 1)[0].replace("# ", "")
