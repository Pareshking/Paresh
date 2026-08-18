"""Seeding the price cache from the published snapshot.

Streamlit Cloud wipes /tmp on every restart, so production began each cold
start with no price history and re-downloaded two years of OHLCV for 750
symbols from Yahoo -- about 38 seconds, with a rate-limited third party in the
critical path. That is exactly how the screener went down twice on 2026-08-18.

The seed is an ACCELERATOR, NOT A DEPENDENCY: every failure path must leave the
cache untouched and let the old full-download behaviour happen, so an
unreachable snapshot costs a slow start rather than an outage.
"""
import os

import numpy as np
import pandas as pd
import pytest

from src.loaders import price_store


@pytest.fixture
def cache_path(tmp_path, monkeypatch):
    path = tmp_path / "prices.parquet"
    monkeypatch.setattr(price_store, "PRICES_FILE", str(path))
    return path


def _snapshot_bytes(rows=60, cols=8):
    idx = pd.bdate_range(end="2026-08-18", periods=rows)
    df = pd.DataFrame(
        np.random.default_rng(0).normal(100, 1, (rows, cols)).astype("float32"),
        index=idx, columns=[f"S{i}" for i in range(cols)],
    )
    import io
    buf = io.BytesIO()
    df.to_parquet(buf, compression="zstd")
    return buf.getvalue()


class _Resp:
    def __init__(self, status, payload=b""):
        self.status_code = status
        self._payload = payload

    def iter_content(self, chunk_size=1):
        yield self._payload


def _serve(monkeypatch, status, payload=b"", boom=None):
    def _get(url, **kwargs):
        if boom:
            raise boom
        return _Resp(status, payload)
    monkeypatch.setattr(price_store.requests, "get", _get)


def test_a_good_snapshot_seeds_the_cache(cache_path, monkeypatch):
    payload = _snapshot_bytes()
    monkeypatch.setattr(price_store, "MIN_PLAUSIBLE_BYTES", 100)
    _serve(monkeypatch, 200, payload)

    assert price_store.seed_price_cache_from_snapshot("http://x/prices.parquet") is True
    assert cache_path.exists()
    assert not pd.read_parquet(cache_path).empty


def test_an_existing_cache_is_never_overwritten(cache_path, monkeypatch):
    cache_path.write_bytes(b"do not touch")
    _serve(monkeypatch, 200, _snapshot_bytes())

    assert price_store.seed_price_cache_from_snapshot("http://x") is False
    assert cache_path.read_bytes() == b"do not touch"


@pytest.mark.parametrize("status", [403, 404, 500, 503])
def test_an_http_error_leaves_the_cache_absent(cache_path, monkeypatch, status):
    _serve(monkeypatch, status, b"nope")
    assert price_store.seed_price_cache_from_snapshot("http://x") is False
    assert not cache_path.exists()


def test_a_network_failure_is_swallowed(cache_path, monkeypatch):
    _serve(monkeypatch, 200, boom=OSError("connection reset"))
    assert price_store.seed_price_cache_from_snapshot("http://x") is False
    assert not cache_path.exists()


def test_a_tiny_body_is_rejected_rather_than_written(cache_path, monkeypatch):
    """A 404 HTML page or a truncated transfer must not become the cache."""
    _serve(monkeypatch, 200, b"<html>Not Found</html>")
    assert price_store.seed_price_cache_from_snapshot("http://x") is False
    assert not cache_path.exists()


def test_a_corrupt_parquet_is_rejected(cache_path, monkeypatch):
    monkeypatch.setattr(price_store, "MIN_PLAUSIBLE_BYTES", 10)
    _serve(monkeypatch, 200, b"x" * 5000)          # right size, not parquet
    assert price_store.seed_price_cache_from_snapshot("http://x") is False
    assert not cache_path.exists()


def test_no_partial_file_is_left_behind_on_failure(cache_path, monkeypatch):
    monkeypatch.setattr(price_store, "MIN_PLAUSIBLE_BYTES", 10)
    _serve(monkeypatch, 200, b"x" * 5000)
    price_store.seed_price_cache_from_snapshot("http://x")
    leftovers = list(cache_path.parent.glob("*.parquet"))
    assert leftovers == [], f"temporary files left behind: {leftovers}"


def test_the_seed_is_reported_in_telemetry(cache_path, monkeypatch):
    from src.core import startup_metrics as metrics

    monkeypatch.setattr(price_store, "MIN_PLAUSIBLE_BYTES", 100)
    _serve(monkeypatch, 200, _snapshot_bytes())
    price_store.seed_price_cache_from_snapshot("http://x")

    facts = metrics.snapshot()["facts"]
    assert facts["price_snapshot"] == "seeded"
    assert facts["price_snapshot_last_session"] == "2026-08-18"


def test_the_loader_tries_to_seed_before_deciding_anything(monkeypatch, tmp_path):
    """The hook must sit ahead of the cache-freshness branch, or an empty cache
    goes straight to a full Yahoo download."""
    import inspect

    from src.loaders import price_loader

    src = inspect.getsource(price_loader.fetch_price_history)
    seed_at = src.index("seed_price_cache_from_snapshot")
    cache_at = src.index("os.path.exists(PRICES_FILE)")
    assert seed_at > cache_at            # guarded by the same existence check
    assert "force_refresh" in src[:seed_at]
