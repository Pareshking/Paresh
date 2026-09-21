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

    assert "archive/prices/yahoo/2026-09-19/prices.parquet" in archive.keys
    manifest_key = "archive/manifests/prices/yahoo/2026-09-19.json"
    assert manifest_key in archive.keys


def test_publisher_rejects_same_date_different_bytes(tmp_path, monkeypatch):
    from scripts import r2_publish
    from src.storage.r2 import R2ImmutableObjectExists

    path = tmp_path / "prices.parquet"
    pd.DataFrame(
        {"Symbol": ["AAA"], "Close": [100.0]},
        index=pd.to_datetime(["2026-09-19"]),
    ).to_parquet(path)

    class FakeArchive:
        def __init__(self, _config):
            self.object_key = None

        def put_file(self, key, _path, **_kwargs):
            self.object_key = key
            raise R2ImmutableObjectExists(key)

        def verify_file(self, _key, _path):
            raise RuntimeError("existing object differs")

        def get_bytes(self, _key):
            return b"{}"

    archive = FakeArchive(None)
    monkeypatch.setattr(r2_publish, "R2Archive", lambda _config: archive)
    monkeypatch.setattr(r2_publish.R2Config, "from_env", classmethod(lambda cls: None))

    with pytest.raises(RuntimeError, match="existing object differs"):
        r2_publish.publish(
            path,
            dataset="prices/yahoo",
            source="yahoo",
            key_root="archive/prices/yahoo",
            pipeline_version="test",
            release_tag="data-latest",
        )
