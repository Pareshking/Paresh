"""Phase-3 R2 dual-publication contracts."""

from pathlib import Path

import pandas as pd
import pytest

yaml = pytest.importorskip("yaml")

ROOT = Path(__file__).resolve().parents[1]


def _workflow(name: str) -> dict:
    spec = yaml.safe_load(
        (ROOT / ".github/workflows" / name).read_text(encoding="utf-8")
    )
    return spec.get("on") or spec.get(True) or spec


def _steps(name: str) -> list[dict]:
    spec = yaml.safe_load(
        (ROOT / ".github/workflows" / name).read_text(encoding="utf-8")
    )
    return spec["jobs"][next(iter(spec["jobs"]))]["steps"]


def test_daily_sync_has_r2_dual_publication_after_release():
    steps = _steps("daily_sync.yml")
    names = [str(step.get("name", "")) for step in steps]
    release = names.index("Publish price snapshot")
    r2 = names.index("Publish validated datasets to R2")
    assert release < r2


def test_daily_sync_publishes_all_three_production_release_artifacts():
    steps = _steps("daily_sync.yml")
    step = next(s for s in steps if s.get("name") == "Publish validated datasets to R2")
    run = str(step["run"])
    for asset in ("prices.parquet", "prices_full.parquet", "rankings.parquet"):
        assert f"--path {asset}" in run
    assert "archive/prices/yahoo" in run
    assert "snapshots/application" in run
    assert "snapshots/rankings" in run


def test_screener_sync_has_r2_dual_publication_after_release():
    steps = _steps("screener_sync.yml")
    names = [str(step.get("name", "")) for step in steps]
    release = names.index("Publish screener history")
    r2 = names.index("Publish validated Screener dataset to R2")
    assert release < r2


def test_screener_sync_keeps_source_identity_and_r2_credentials():
    steps = _steps("screener_sync.yml")
    step = next(
        s for s in steps if s.get("name") == "Publish validated Screener dataset to R2"
    )
    run = str(step["run"])
    assert "--dataset prices/screener" in run
    assert "--source screener" in run
    assert "--key-root archive/prices/screener" in run
    env = step["env"]
    for name in (
        "R2_ACCOUNT_ID",
        "R2_ACCESS_KEY_ID",
        "R2_SECRET_ACCESS_KEY",
        "R2_ENDPOINT",
        "R2_BUCKET",
    ):
        assert name in env


def test_publisher_uses_content_identity_for_same_date_conflict(tmp_path, monkeypatch):
    from scripts import r2_publish

    frame = pd.DataFrame(
        {"Symbol": ["AAA", "BBB"], "Close": [100.0, 200.0]},
        index=pd.to_datetime(["2026-09-18", "2026-09-19"]),
    )
    path = tmp_path / "prices.parquet"
    frame.to_parquet(path)

    class FakeArchive:
        def __init__(self, _config):
            self.keys = {}

        def put_file(self, key, path, **_kwargs):
            self.keys[key] = Path(path).read_bytes()

        def put_bytes(self, key, body, **_kwargs):
            self.keys[key] = body

        def verify_file(self, key, path):
            if self.keys.get(key) != Path(path).read_bytes():
                raise AssertionError("existing object differs")

        def get_bytes(self, key):
            return self.keys[key]

    archive = FakeArchive(None)
    monkeypatch.setattr(r2_publish, "R2Archive", lambda _config: archive)
    monkeypatch.setattr(r2_publish.R2Config, "from_env", classmethod(lambda cls: None))

    r2_publish.publish(
        path,
        dataset="prices/yahoo",
        source="yahoo",
        key_root="archive/prices/yahoo",
        pipeline_version="test",
        release_tag="data-latest",
    )

    revision_keys = [
        key for key in archive.keys
        if "/revisions/" in key and key.endswith("prices.parquet")
    ]
    assert len(revision_keys) == 1
    manifest_keys = [
        key for key in archive.keys
        if "/revisions/" in key and key.endswith(".json")
    ]
    assert len(manifest_keys) == 1
    current_key = "archive/manifests/prices/yahoo/2026-09-19/current.json"
    assert current_key in archive.keys


def test_publisher_preserves_same_date_different_bytes_as_new_revision(tmp_path, monkeypatch):
    import json

    from scripts import r2_publish

    path = tmp_path / "prices.parquet"

    def write_frame(close: float) -> None:
        pd.DataFrame(
            {"Symbol": ["AAA"], "Close": [close]},
            index=pd.to_datetime(["2026-09-19"]),
        ).to_parquet(path)

    write_frame(100.0)

    class FakeArchive:
        def __init__(self, _config):
            self.keys = {}

        def put_file(self, key, path, **_kwargs):
            if key in self.keys:
                raise RuntimeError("unexpected duplicate key")
            self.keys[key] = Path(path).read_bytes()

        def put_bytes(self, key, body, **_kwargs):
            self.keys[key] = body

        def get_bytes(self, key):
            return self.keys[key]

        def verify_file(self, key, path):
            assert self.keys[key] == Path(path).read_bytes()

    archive = FakeArchive(None)
    monkeypatch.setattr(r2_publish, "R2Archive", lambda _config: archive)
    monkeypatch.setattr(r2_publish.R2Config, "from_env", classmethod(lambda cls: None))

    r2_publish.publish(
        path,
        dataset="prices/yahoo",
        source="yahoo",
        key_root="archive/prices/yahoo",
        pipeline_version="test",
        release_tag="data-latest",
    )

    first_revisions = [
        key for key in archive.keys
        if "/revisions/" in key and key.endswith("prices.parquet")
    ]
    assert len(first_revisions) == 1

    write_frame(101.0)
    r2_publish.publish(
        path,
        dataset="prices/yahoo",
        source="yahoo",
        key_root="archive/prices/yahoo",
        pipeline_version="test-2",
        release_tag="data-latest",
    )

    revision_keys = [
        key for key in archive.keys
        if "/revisions/" in key and key.endswith("prices.parquet")
    ]
    assert len(revision_keys) == 2
    current = json.loads(
        archive.get_bytes(
            "archive/manifests/prices/yahoo/2026-09-19/current.json"
        )
    )
    assert any(current["revision_sha256"] in key for key in revision_keys)


def test_publisher_retries_identical_revision_idempotently(tmp_path, monkeypatch):
    from scripts import r2_publish

    path = tmp_path / "prices.parquet"
    pd.DataFrame(
        {"Symbol": ["AAA"], "Close": [100.0]},
        index=pd.to_datetime(["2026-09-19"]),
    ).to_parquet(path)

    class FakeArchive:
        def __init__(self, _config):
            self.keys = {}

        def put_file(self, key, path, **_kwargs):
            if key in self.keys:
                from src.storage.r2 import R2ImmutableObjectExists
                raise R2ImmutableObjectExists(key)
            self.keys[key] = Path(path).read_bytes()

        def put_bytes(self, key, body, **_kwargs):
            self.keys[key] = body

        def get_bytes(self, key):
            return self.keys[key]

        def verify_file(self, key, path):
            assert self.keys[key] == Path(path).read_bytes()

    archive = FakeArchive(None)
    monkeypatch.setattr(r2_publish, "R2Archive", lambda _config: archive)
    monkeypatch.setattr(r2_publish.R2Config, "from_env", classmethod(lambda cls: None))

    r2_publish.publish(
        path, dataset="prices/yahoo", source="yahoo",
        key_root="archive/prices/yahoo", pipeline_version="test",
        release_tag="data-latest",
    )
    before = len(archive.keys)
    r2_publish.publish(
        path, dataset="prices/yahoo", source="yahoo",
        key_root="archive/prices/yahoo", pipeline_version="test",
        release_tag="data-latest",
    )
    assert len(archive.keys) == before


def test_r2_publisher_performs_post_publication_readback(monkeypatch, tmp_path):
    from scripts import r2_publish

    path = tmp_path / "prices.parquet"
    pd.DataFrame(
        {"Symbol": ["AAA"], "Close": [100.0]},
        index=pd.to_datetime(["2026-09-19"]),
    ).to_parquet(path)

    class FakeArchive:
        def __init__(self, _config):
            self.keys = {}
            self.verify_calls = []

        def put_file(self, key, path, **_kwargs):
            self.keys[key] = Path(path).read_bytes()

        def put_bytes(self, key, body, **_kwargs):
            self.keys[key] = body

        def get_bytes(self, key):
            return self.keys[key]

        def verify_file(self, key, path):
            self.verify_calls.append((key, str(path)))
            assert self.keys[key] == Path(path).read_bytes()

    archive = FakeArchive(None)
    monkeypatch.setattr(r2_publish, "R2Archive", lambda _config: archive)
    monkeypatch.setattr(r2_publish.R2Config, "from_env", classmethod(lambda cls: None))

    r2_publish.publish(
        path, dataset="prices/screener", source="screener",
        key_root="archive/prices/screener", pipeline_version="test",
        release_tag="data-latest",
    )

    assert len(archive.verify_calls) == 1
    assert any("/revisions/" in key for key, _ in archive.verify_calls)


def test_r2_publisher_fails_on_pointer_mismatch(monkeypatch, tmp_path):
    from scripts import r2_publish

    path = tmp_path / "prices.parquet"
    pd.DataFrame(
        {"Symbol": ["AAA"], "Close": [100.0]},
        index=pd.to_datetime(["2026-09-19"]),
    ).to_parquet(path)

    class FakeArchive:
        def __init__(self, _config):
            self.keys = {}

        def put_file(self, key, path, **_kwargs):
            self.keys[key] = Path(path).read_bytes()

        def put_bytes(self, key, body, **_kwargs):
            if key.endswith("/current.json"):
                body = body.replace(b'"revision_sha256":', b'"revision_sha256":"tampered","_original_revision_sha256":')
            self.keys[key] = body

        def get_bytes(self, key):
            return self.keys[key]

        def verify_file(self, key, path):
            assert self.keys[key] == Path(path).read_bytes()

    archive = FakeArchive(None)
    monkeypatch.setattr(r2_publish, "R2Archive", lambda _config: archive)
    monkeypatch.setattr(r2_publish.R2Config, "from_env", classmethod(lambda cls: None))

    with pytest.raises(RuntimeError, match="current pointer verification failed"):
        r2_publish.publish(
            path, dataset="prices/screener", source="screener",
            key_root="archive/prices/screener", pipeline_version="test",
            release_tag="data-latest",
        )


def test_screener_10y_bootstrap_audits_r2_after_publication():
    steps = _steps("screener_10y_bootstrap.yml")
    names = [str(step.get("name", "")) for step in steps]
    publish = names.index("Publish deep Screener history to R2")
    audit = names.index("Audit published R2 Screener revision")
    release = names.index("Publish deep Screener history to release")
    assert publish < audit < release
    step = steps[audit]
    run = str(step["run"])
    assert "scripts/r2_audit.py" in run
    assert "--dataset prices/screener" in run


def test_r2_live_archive_audit_workflow_is_read_only_and_targets_screener():
    steps = _steps("r2_archive_audit.yml")
    step = next(s for s in steps if s.get("name") == "Audit latest Screener R2 publication")
    assert "scripts/r2_audit.py --dataset prices/screener" in str(step["run"])
    assert "R2_SECRET_ACCESS_KEY" in step["env"]
