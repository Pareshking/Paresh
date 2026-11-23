"""The two-year NSE closes outside git: local file first, then R2, then the release.

Owner, 21 Nov 2026: "move closes.parquet to R2 now". src/loaders/nse_prices.closes_path().
The copy on disk is kept while it is the published revision, and replaced as
soon as it is not, whatever its age (TODO S210, 23 Nov 2026).
"""

from __future__ import annotations

import importlib
import hashlib
import io
import os
import time

import pandas as pd
import pytest

# Other tests reload these modules (code_reload), so each test takes the live ones.
npx = app_source = None


@pytest.fixture(autouse=True)
def _live_modules():
    global npx, app_source
    npx = importlib.import_module("src.loaders.nse_prices")
    app_source = importlib.import_module("src.loaders.app_source")


def _frame(last: str = "2026-11-05") -> pd.DataFrame:
    idx = pd.date_range(end=last, periods=3, freq="B")
    return pd.DataFrame({"AAA": [1.0, 2.0, 3.0], "BBB": [4.0, 5.0, 6.0]}, index=idx).astype("float32")


def _bytes(frame: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    frame.to_parquet(buf)
    return buf.getvalue()


class _Resp:
    def __init__(self, status: int, content: bytes = b"", etag: str = ""):
        self.status_code, self.content = status, content
        self.headers = {"ETag": etag} if etag else {}

    def close(self):
        pass


def _probe(kwargs) -> bool:
    """The release check: a one-byte ranged GET."""
    return (kwargs.get("headers") or {}).get("Range") == "bytes=0-0"


class _Ref:
    def __init__(self, body: bytes, as_of: str = "2026-11-20"):
        self.revision_sha256 = hashlib.sha256(body).hexdigest()
        self.as_of = as_of
        self.body = body


class _FakeR2:
    """R2DatasetReader's two calls: the pointer (cheap) and the object (the download)."""

    def __init__(self, body: bytes):
        self.publish(body)
        self.pointer_reads = 0
        self.object_reads = 0

    def publish(self, body: bytes) -> None:
        self.ref = _Ref(body)

    def resolve_current(self, dataset):
        assert dataset == npx.CLOSES_DATASET
        self.pointer_reads += 1
        return self.ref

    def read_bytes(self, ref):
        self.object_reads += 1
        return ref.body


@pytest.fixture
def repo(_live_modules, tmp_path, monkeypatch):
    """npx.DIR as an empty repository folder (actions and notes only), a private cache, nothing published."""
    d = tmp_path / "data" / "nse_prices"
    d.mkdir(parents=True)
    pd.DataFrame(columns=npx.ACTION_COLS).to_parquet(d / "actions.parquet")
    (d / "notes.json").write_text("{}")
    cache = tmp_path / "cache"
    monkeypatch.setattr(npx, "DIR", d)
    monkeypatch.setattr(importlib.import_module("src.core.config"), "DATA_DIR", str(cache))
    monkeypatch.setattr(npx, "_CLOSES_CHECKED", {})
    calls = {"r2": 0, "probe": 0, "get": 0}

    def no_r2():
        calls["r2"] += 1
        return None

    def no_release(*a, **k):
        calls["probe" if _probe(k) else "get"] += 1
        return _Resp(404)

    monkeypatch.setattr(npx, "_r2_reader", no_r2)
    monkeypatch.setattr("requests.get", no_release)
    return d, cache, calls


def _with_r2(monkeypatch, body: bytes) -> _FakeR2:
    fake = _FakeR2(body)
    monkeypatch.setattr(npx, "_r2_reader", lambda: fake)
    return fake


def test_a_local_file_is_read_and_nothing_is_fetched(repo):
    d, _, calls = repo
    _frame().to_parquet(d / npx.CLOSES_FILE)
    assert npx.closes_path(d) == d / npx.CLOSES_FILE
    assert calls == {"r2": 0, "probe": 0, "get": 0}


def test_another_folder_never_fetches(repo, tmp_path):
    _, _, calls = repo
    assert npx.closes_path(tmp_path / "elsewhere") is None
    assert calls == {"r2": 0, "probe": 0, "get": 0}


def test_r2_first(repo, monkeypatch):
    d, cache, calls = repo
    fake = _with_r2(monkeypatch, _bytes(_frame()))
    got = npx.load(d)
    assert got is not None and list(got["closes"].columns) == ["AAA", "BBB"]
    assert (cache / npx.CLOSES_CACHE_NAME).exists()
    assert fake.object_reads == 1 and calls["get"] == 0
    assert app_source.SOURCES.get("nse_closes") == "r2"


def test_a_copy_at_the_published_revision_is_kept_whatever_its_age(repo, monkeypatch):
    d, cache, _ = repo
    fake = _with_r2(monkeypatch, _bytes(_frame()))
    path = npx.closes_path(d)
    old = time.time() - 3 * 24 * 3600
    os.utime(path, (old, old))
    npx._CLOSES_CHECKED.clear()                     # a new process: it asks again
    assert npx.closes_path(d) == path
    assert fake.pointer_reads == 2 and fake.object_reads == 1


def test_a_young_copy_of_an_older_revision_is_replaced(repo, monkeypatch):
    """S210: the nightly job ranked on a 14-hour-old copy after the closes were republished."""
    d, cache, _ = repo
    fake = _with_r2(monkeypatch, _bytes(_frame("2026-11-05")))
    path = npx.closes_path(d)
    assert pd.read_parquet(path).index.max() == pd.Timestamp("2026-11-05")
    fake.publish(_bytes(_frame("2026-11-20")))      # the backfill republishes
    npx._CLOSES_CHECKED.clear()                     # the next job, minutes later
    assert npx.closes_path(d) == path
    assert pd.read_parquet(path).index.max() == pd.Timestamp("2026-11-20")
    assert fake.object_reads == 2


def test_a_running_process_asks_at_most_every_recheck_interval(repo, monkeypatch):
    d, _, _ = repo
    fake = _with_r2(monkeypatch, _bytes(_frame()))
    t0 = time.time()
    npx._published_closes(now=t0)
    npx._published_closes(now=t0 + npx.CLOSES_RECHECK_S - 1)
    assert fake.pointer_reads == 1
    fake.publish(_bytes(_frame("2026-11-20")))
    path = npx._published_closes(now=t0 + npx.CLOSES_RECHECK_S + 1)
    assert fake.pointer_reads == 2
    assert pd.read_parquet(path).index.max() == pd.Timestamp("2026-11-20")


def test_a_copy_from_before_this_rule_is_checked_once(repo, monkeypatch):
    """A copy saved without its revision (the 24-hour rule's) is replaced by the published one."""
    d, cache, _ = repo
    cache.mkdir()
    _frame("2026-11-05").to_parquet(cache / npx.CLOSES_CACHE_NAME)
    fake = _with_r2(monkeypatch, _bytes(_frame("2026-11-20")))
    path = npx.closes_path(d)
    assert pd.read_parquet(path).index.max() == pd.Timestamp("2026-11-20")
    assert fake.object_reads == 1


def test_the_release_when_r2_cannot_serve(repo, monkeypatch):
    d, cache, calls = repo
    monkeypatch.setattr("requests.get", lambda url, **k: _Resp(200, _bytes(_frame()), etag='"e1"')
                        if url.endswith("/" + npx.CLOSES_ASSET) else _Resp(404))
    assert npx.closes_path(d) == cache / npx.CLOSES_CACHE_NAME
    assert calls["r2"] == 1
    assert app_source.SOURCES.get("nse_closes") == "release"


def test_the_release_copy_is_downloaded_again_only_when_its_etag_changes(repo, monkeypatch):
    d, _, _ = repo
    state = {"etag": '"e1"', "last": "2026-11-05", "gets": 0}

    def get(url, **k):
        if _probe(k):
            return _Resp(206, b"P", etag=state["etag"])
        state["gets"] += 1
        return _Resp(200, _bytes(_frame(state["last"])), etag=state["etag"])

    monkeypatch.setattr("requests.get", get)
    path = npx.closes_path(d)
    npx._CLOSES_CHECKED.clear()
    npx.closes_path(d)
    assert state["gets"] == 1                        # same ETag: kept
    state.update(etag='"e2"', last="2026-11-20")
    npx._CLOSES_CHECKED.clear()
    npx.closes_path(d)
    assert state["gets"] == 2
    assert pd.read_parquet(path).index.max() == pd.Timestamp("2026-11-20")


def test_a_held_copy_beats_none_when_nothing_answers(repo):
    d, cache, calls = repo
    cache.mkdir()
    path = cache / npx.CLOSES_CACHE_NAME
    _frame().to_parquet(path)
    old = time.time() - npx.CLOSES_CACHE_TTL_S - 60
    os.utime(path, (old, old))
    assert npx.closes_path(d) == path
    assert calls["r2"] == 1 and calls["get"] == 1
    npx.closes_path(d)                               # unchecked copies are not memoised: asked again
    assert calls["r2"] == 2


def test_unreadable_bytes_are_not_cached(repo, monkeypatch):
    d, cache, _ = repo
    _with_r2(monkeypatch, b"<html>not a parquet</html>")
    assert npx.closes_path(d) is None
    assert not (cache / npx.CLOSES_CACHE_NAME).exists()
    assert list(cache.glob("*.part")) == []


def test_nothing_anywhere_is_none(repo):
    d, _, _ = repo
    assert npx.load(d) is None


def test_the_memo_stamp_follows_the_fetched_copy(repo, monkeypatch):
    """basis_frame's memo must miss when the fetched copy changes, as it does for a local one."""
    d, cache, _ = repo
    fake = _with_r2(monkeypatch, _bytes(_frame()))
    first = dict((n, (m, s)) for n, m, s in npx._file_stamp(d))[npx.CLOSES_FILE]
    assert first[1] is not None
    fake.publish(_bytes(_frame("2026-12-04")))
    npx._CLOSES_CHECKED.clear()
    second = dict((n, (m, s)) for n, m, s in npx._file_stamp(d))[npx.CLOSES_FILE]
    assert second != first
