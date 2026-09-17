"""pytest session-wide fixtures and import stubs.

Libraries that are genuinely absent are stubbed here so every test file can be
collected without ModuleNotFoundError. Stubs are intentionally minimal — just
enough for import-time resolution; tests that exercise live behaviour mock
specific callables themselves.

The stubbing is CONDITIONAL, and that matters. The meta-path finder below used
to intercept every "plotly" import unconditionally, so it won and installed a
MagicMock even where the real package was installed -- which is everywhere the
suite actually runs, since plotly and streamlit-lightweight-charts are both in
requirements.txt. src/ui/charts.py was therefore never once exercised against
the library it ships against: any misuse of the plotly API returned a MagicMock
and passed. Stubbing now happens only for what genuinely cannot be imported.
"""

import importlib.abc
import importlib.machinery
import importlib.util
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


def _installed(name: str) -> bool:
    """Whether a top-level package can actually be imported."""
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


# ── plotly + streamlit_lightweight_charts ────────────────────────────────────
# Only the ones that are missing. Streamlit reaches for several plotly
# submodules (plotly.io, plotly.tools, plotly.express …) and pre-registering a
# fixed list breaks whenever it reaches for another, so an absent package is
# covered by a prefix finder rather than by name.
_STUB_PREFIXES = tuple(
    name for name in ("plotly", "streamlit_lightweight_charts") if not _installed(name)
)


class _StubFinder(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    """Auto-stub any import whose name starts with one of _STUB_PREFIXES."""

    def find_spec(self, fullname, path, target=None):
        if any(
            fullname == p or fullname.startswith(p + ".")
            for p in _STUB_PREFIXES
        ):
            if fullname not in sys.modules:
                return importlib.machinery.ModuleSpec(fullname, self)
        return None

    def create_module(self, spec):
        mod = unittest.mock.MagicMock()
        mod.__name__ = spec.name
        mod.__package__ = spec.name.rpartition(".")[0] or spec.name
        mod.__path__ = []       # marks it as a package
        mod.__spec__ = spec
        return mod

    def exec_module(self, module):
        pass   # nothing to execute; MagicMock handles attribute access


if _STUB_PREFIXES:
    sys.meta_path.insert(0, _StubFinder())

# Streamlit's plotly_chart.py serialises the figure via plotly.io.to_json and
# then assigns the result to a protobuf string field. A MagicMock there is
# rejected by protobuf, so the stub needs a valid return value. The real
# plotly.io needs nothing -- it returns a str already.
if "plotly" in _STUB_PREFIXES:
    import plotly.io as _pio   # noqa: E402 — must come after finder install

    _pio.to_json.return_value = "{}"


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
    from src.loaders import indices_loader, mcap_loader, price_loader, ranking_store, tv_loader

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
    monkeypatch.setattr(price_loader, "fetch_price_history", lambda *a, **k: raw)
    monkeypatch.setattr(price_loader, "fetch_benchmark_history", lambda *a, **k: bench)
    monkeypatch.setattr(price_loader, "get_market_regime", lambda *a, **k: regime)
    monkeypatch.setattr(mcap_loader, "fetch_market_caps", lambda *a, **k: mcaps)
    monkeypatch.setattr(tv_loader, "load_tv_classification", lambda *a, **k: {})
    monkeypatch.setattr(ranking_store, "fetch_snapshot", lambda *a, **k: (None, None))
    return {"symbols": symbols, "idx_info": idx_info, "prices": raw}
