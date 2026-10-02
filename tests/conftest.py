"""pytest session-wide fixtures and import stubs.

Libraries that are genuinely absent are stubbed here so every test file can be
collected without ModuleNotFoundError. Stubs are intentionally minimal.
"""

import sys
import types
import unittest.mock

import pytest

# ── yfinance ─────────────────────────────────────────────────────────────────
# price_loader.py imports yfinance at module level.  Stub the three entry
# points used there; individual tests can patch yf.download etc. as needed.
if "yfinance" not in sys.modules:
    _yf = types.ModuleType("yfinance")
    _yf.download = unittest.mock.MagicMock(return_value=None)
    _yf.set_tz_cache_location = unittest.mock.MagicMock()
    _yf.Ticker = unittest.mock.MagicMock()
    sys.modules["yfinance"] = _yf



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

    from src.core.types import MarketRegime, RegimeData
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
