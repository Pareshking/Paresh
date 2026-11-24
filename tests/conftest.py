"""pytest session-wide fixtures."""

import os as _os
import tempfile as _tempfile

import pytest

# ── Cache isolation (S138 I7) ────────────────────────────────────────────────
# src/core/config.py's DATA_DIR is the download cache (the long NSE file, NSE's
# closes, market caps). Left at its default it is the working tree's data_cache/,
# so a test could pass only because a developer's machine had downloaded a file
# CI never has, and the suite wrote into the tree. Set before any src import; a
# value already in the environment is kept, so a run can still point it somewhere.
# One exception, named: NSE's published two-year closes, which tests on the real
# prices read (test_nse_prices.py's `committed`, test_nse_closes_published.py).
# They are not in git (S178); scripts/fetch_nse_closes.py puts them in the default
# cache (CI runs it before pytest), and only those files are copied in.
if "UMIYA_DATA_DIR" not in _os.environ:
    import shutil as _shutil
    from pathlib import Path as _Path

    _tmp_cache = _tempfile.mkdtemp(prefix="umiya_test_cache_")
    _default_cache = _Path(__file__).resolve().parents[1] / "data_cache"
    for _name in ("nse_prices_closes.parquet", "nse_prices_closes.parquet.revision"):
        if (_default_cache / _name).exists():
            _shutil.copy2(_default_cache / _name, _tmp_cache)
    _os.environ["UMIYA_DATA_DIR"] = _tmp_cache

# ── Network isolation ────────────────────────────────────────────────────────
# The suite used to reach the internet. A full run fetched the constituent CSVs
# from niftyindices.com, the market-cap archive from NSE, and -- because two
# tests execute app.py end to end, which runs the whole data pipeline at import
# -- the 10 MB published price snapshot from GitHub Releases. That made the
# tests slow, dependent on three third parties being up, and dependent on the
# release asset still existing.
#
# Blocking at the socket is deliberate. Stubbing requests.get would leave the
# next loader that reaches for urllib free to escape, and the point is that
# nothing can. Anything genuinely testing HTTP behaviour mocks at the library
# boundary and never reaches this.
import errno as _errno
import socket as _socket

_real_connect = _socket.socket.connect


class NetworkAccessDenied(OSError):
    """Raised when a test tries to open a socket to anything at all.

    Deliberately an OSError, not a bare RuntimeError. requests and urllib3
    translate an OSError from connect() into requests.exceptions.ConnectionError,
    which every loader here already treats as "the network is unavailable" and
    answers from its committed fallback. A RuntimeError would escape that
    handling and turn an offline run into a crash instead of a fallback.
    """


def _guarded_connect(self, address, *args, **kwargs):
    raise NetworkAccessDenied(
        _errno.ENETUNREACH,
        f"the test suite is offline by design; refused a connection to {address!r}. "
        "Mock the loader or the HTTP client instead of reaching the network.",
    )


# Every address is refused, localhost included. An earlier version allowed
# loopback and was useless: this environment (and most CI) routes outbound HTTP
# through a proxy on 127.0.0.1, so "block everything except localhost" blocked
# nothing and the suite still pulled 10 MB from GitHub Releases. Nothing in this
# suite needs a real socket -- Streamlit's AppTest runs the script in-process.
_socket.socket.connect = _guarded_connect

# Windows has no AF_UNIX socketpair: Python builds one by connecting a socket to
# a listener of its own on 127.0.0.1, and asyncio's event loop needs one to start
# (Streamlit's AppTest runs one). That connection never leaves the process, so it
# is let through; nothing else is. On Linux socketpair() never calls connect().
_real_socketpair = _socket.socketpair


def _socketpair(*args, **kwargs):
    _socket.socket.connect = _real_connect
    try:
        return _real_socketpair(*args, **kwargs)
    finally:
        _socket.socket.connect = _guarded_connect


_socket.socketpair = _socketpair


@pytest.fixture
def offline_market_data(monkeypatch):
    """A complete, synthetic market for tests that execute app.py end to end.

    app.py runs its whole pipeline at module scope, so an AppTest of the real
    entrypoint pulls indices, market caps, prices, the benchmark and the
    published ranking. Patched at the loader boundary rather than at HTTP, so
    the test is deterministic and quick instead of merely offline: a 12-symbol
    universe renders the same navigation as 750 and builds the engine in
    milliseconds.
    """
    import numpy as np
    import pandas as pd
    import streamlit as st

    from src.core.types import MarketRegime, RegimeData

    # app.py's loaders are st.cache_data: a result another test left in this worker's cache (an empty load
    # under other patches) was read instead of this synthetic market, and the import failed at
    # `data["calc"]` on None, only under xdist's work stealing (24 Nov 2026). Start from empty caches.
    st.cache_data.clear()
    st.cache_resource.clear()
    from src.loaders import (
        indices_loader, mcap_loader, nse_prices, price_loader, price_source, ranking_store,
        tv_loader,
    )

    symbols = [f"SYM{i:02d}" for i in range(12)]
    idx = pd.bdate_range(end="2026-09-15", periods=320)
    rng = np.random.default_rng(11)
    close = pd.DataFrame(
        100 * np.exp(np.cumsum(rng.normal(0.0005, 0.011, (len(idx), len(symbols))), axis=0)),
        index=idx, columns=symbols,
    ).astype("float32")

    frames = {}
    for sym in symbols:
        frames[(sym, "Open")] = close[sym]
        frames[(sym, "High")] = close[sym] * 1.01
        frames[(sym, "Low")] = close[sym] * 0.99
        frames[(sym, "Close")] = close[sym]
        frames[(sym, "Adj Close")] = close[sym]
        frames[(sym, "Volume")] = pd.Series(1_000_000.0, index=idx)
    raw = pd.DataFrame(frames)
    raw.columns = pd.MultiIndex.from_tuples(raw.columns, names=["Ticker", "Price"])

    idx_info = pd.DataFrame({
        "Symbol": symbols,
        "Industry": [f"Industry {i % 4}" for i in range(len(symbols))],
        "Indices": ["N50"] * len(symbols),
    })
    mcaps = pd.Series(np.linspace(5_000, 500_000, len(symbols)), index=symbols)
    bench = pd.Series(
        100 * np.exp(np.cumsum(rng.normal(0.0004, 0.008, len(idx)))), index=idx
    )
    regime = RegimeData(
        status=MarketRegime.BULLISH, current_price=float(bench.iloc[-1]),
        dma_200=float(bench.mean()), distance_pct=1.0,
    )

    monkeypatch.setattr(indices_loader, "fetch_indices_data", lambda *a, **k: idx_info)
    # The app's prices: Screener's store (Close and Volume per symbol), NSE's
    # committed file under it. No Yahoo since 2026-10-02.
    store = pd.DataFrame({(sym, field): (close[sym] if field == "Close"
                                         else pd.Series(1_000_000.0, index=idx))
                          for sym in symbols for field in ("Close", "Volume")})
    store.columns = pd.MultiIndex.from_tuples(store.columns)
    monkeypatch.setattr(price_source, "fetch_screener_store", lambda *a, **k: store)
    monkeypatch.setattr(nse_prices, "middle_close", lambda *a, **k: None)
    monkeypatch.setattr(price_loader, "fetch_benchmark_history", lambda *a, **k: bench)
    monkeypatch.setattr(price_loader, "get_market_regime", lambda *a, **k: regime)
    monkeypatch.setattr(mcap_loader, "fetch_market_caps", lambda *a, **k: mcaps)
    monkeypatch.setattr(tv_loader, "load_tv_classification", lambda *a, **k: {})
    monkeypatch.setattr(ranking_store, "fetch_snapshot", lambda *a, **k: (None, None))
    return {"symbols": symbols, "idx_info": idx_info, "prices": raw, "store": store}


@pytest.fixture(autouse=True)
def _fresh_record_memo():
    """record_run's per-render memo (model_record._RUN_MEMO) starts empty in every test."""
    from src.engine import model_record

    model_record._RUN_MEMO.clear()
    yield
    model_record._RUN_MEMO.clear()


# ── Markers (S138 I2, I3) ────────────────────────────────────────────────────
# Set from what a test file does, not by hand, so a new file cannot fall outside
# them: `live_data` for a file that reads the repository's data/ (which the nightly
# sync rewrites: assert on past-dated facts or invariants, never the latest
# value), `r2` for the R2 storage tests. `pytest -m "not live_data"` runs the
# suite without them. The full suite still runs every test in CI.
import re as _re
from pathlib import Path as _MarkPath

_READS_REPO_DATA = _re.compile(
    r"REPO_DATA_DIR|INDICES_DIR|[\"']data/|/ [\"']data[\"']|parents\[1\] / [\"']data[\"']")
_file_marks: dict[str, tuple[bool, bool]] = {}


def pytest_configure(config):
    config.addinivalue_line("markers", "live_data: reads the repository's data/, which the nightly sync rewrites")
    config.addinivalue_line("markers", "r2: tests of the R2 storage layer (src/storage, r2/)")


def pytest_collection_modifyitems(config, items):
    for item in items:
        path = str(item.fspath)
        if path not in _file_marks:
            try:
                text = _MarkPath(path).read_text(encoding="utf-8")
            except OSError:
                text = ""
            name = _MarkPath(path).name
            _file_marks[path] = (bool(_READS_REPO_DATA.search(text)),
                                 name.startswith("test_r2_") or "src.storage" in text)
        live, r2 = _file_marks[path]
        if live:
            item.add_marker(pytest.mark.live_data)
        if r2:
            item.add_marker(pytest.mark.r2)
