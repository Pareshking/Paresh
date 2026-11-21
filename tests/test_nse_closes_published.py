"""The two-year NSE closes outside git: local file first, then R2, then the release.

Owner, 21 Nov 2026: "move closes.parquet to R2 now". src/loaders/nse_prices.closes_path().
"""

from __future__ import annotations

import importlib
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
    def __init__(self, status: int, content: bytes = b""):
        self.status_code, self.content = status, content


@pytest.fixture
def repo(_live_modules, tmp_path, monkeypatch):
    """npx.DIR as an empty repository folder (actions and notes only), and a private cache."""
    d = tmp_path / "data" / "nse_prices"
    d.mkdir(parents=True)
    pd.DataFrame(columns=npx.ACTION_COLS).to_parquet(d / "actions.parquet")
    (d / "notes.json").write_text("{}")
    cache = tmp_path / "cache"
    monkeypatch.setattr(npx, "DIR", d)
    monkeypatch.setattr(importlib.import_module("src.core.config"), "DATA_DIR", str(cache))
    calls = {"r2": 0, "release": 0}

    def no_r2(*a, **k):
        calls["r2"] += 1
        return None

    def no_release(*a, **k):
        calls["release"] += 1
        return _Resp(404)

    monkeypatch.setattr(app_source, "fetch_latest", no_r2)
    monkeypatch.setattr("requests.get", no_release)
    return d, cache, calls


def test_a_local_file_is_read_and_nothing_is_fetched(repo):
    d, _, calls = repo
    _frame().to_parquet(d / npx.CLOSES_FILE)
    assert npx.closes_path(d) == d / npx.CLOSES_FILE
    assert calls == {"r2": 0, "release": 0}


def test_another_folder_never_fetches(repo, tmp_path):
    _, _, calls = repo
    assert npx.closes_path(tmp_path / "elsewhere") is None
    assert calls == {"r2": 0, "release": 0}


def test_r2_first(repo, monkeypatch):
    d, cache, calls = repo
    monkeypatch.setattr(app_source, "fetch_latest", lambda ds, label: _bytes(_frame()) if ds == npx.CLOSES_DATASET else None)
    got = npx.load(d)
    assert got is not None and list(got["closes"].columns) == ["AAA", "BBB"]
    assert (cache / npx.CLOSES_CACHE_NAME).exists()
    assert calls["release"] == 0
    assert app_source.SOURCES.get("nse_closes") == "r2"


def test_the_release_when_r2_cannot_serve(repo, monkeypatch):
    d, cache, calls = repo
    monkeypatch.setattr("requests.get", lambda url, timeout: _Resp(200, _bytes(_frame()))
                        if url.endswith("/" + npx.CLOSES_ASSET) else _Resp(404))
    assert npx.closes_path(d) == cache / npx.CLOSES_CACHE_NAME
    assert calls["r2"] == 1
    assert app_source.SOURCES.get("nse_closes") == "release"


def test_a_fresh_copy_is_not_fetched_again(repo, monkeypatch):
    d, cache, calls = repo
    cache.mkdir()
    _frame().to_parquet(cache / npx.CLOSES_CACHE_NAME)
    assert npx.closes_path(d) == cache / npx.CLOSES_CACHE_NAME
    assert calls == {"r2": 0, "release": 0}


def test_a_stale_copy_beats_none_and_is_retried(repo):
    d, cache, calls = repo
    cache.mkdir()
    path = cache / npx.CLOSES_CACHE_NAME
    _frame().to_parquet(path)
    old = time.time() - npx.CLOSES_CACHE_TTL_S - 60
    os.utime(path, (old, old))
    assert npx.closes_path(d) == path
    assert calls == {"r2": 1, "release": 1}


def test_unreadable_bytes_are_not_cached(repo, monkeypatch):
    d, cache, _ = repo
    monkeypatch.setattr(app_source, "fetch_latest", lambda *a, **k: b"<html>not a parquet</html>")
    assert npx.closes_path(d) is None
    assert not (cache / npx.CLOSES_CACHE_NAME).exists()
    assert list(cache.glob("*.part")) == []


def test_nothing_anywhere_is_none(repo):
    d, _, _ = repo
    assert npx.load(d) is None


def test_the_memo_stamp_follows_the_fetched_copy(repo, monkeypatch):
    """basis_frame's memo must miss when the fetched copy changes, as it does for a local one."""
    d, cache, _ = repo
    monkeypatch.setattr(app_source, "fetch_latest", lambda *a, **k: _bytes(_frame()))
    first = dict((n, (m, s)) for n, m, s in npx._file_stamp(d))[npx.CLOSES_FILE]
    assert first[1] is not None
    path = cache / npx.CLOSES_CACHE_NAME
    _frame("2026-12-04").to_parquet(path)
    second = dict((n, (m, s)) for n, m, s in npx._file_stamp(d))[npx.CLOSES_FILE]
    assert second != first
