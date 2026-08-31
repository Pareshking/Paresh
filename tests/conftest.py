"""pytest session-wide fixtures and import stubs.

Libraries not installed in the isolated CI test environment are stubbed here
so every test file can be collected without ModuleNotFoundError.  Stubs are
intentionally minimal — just enough for import-time resolution; tests that
exercise live behaviour mock specific callables themselves.
"""

import importlib.abc
import importlib.machinery
import sys
import types
import unittest.mock

# ── yfinance ─────────────────────────────────────────────────────────────────
# price_loader.py imports yfinance at module level.  Stub the three entry
# points used there; individual tests can patch yf.download etc. as needed.
if "yfinance" not in sys.modules:
    _yf = types.ModuleType("yfinance")
    _yf.download = unittest.mock.MagicMock(return_value=None)
    _yf.set_tz_cache_location = unittest.mock.MagicMock()
    _yf.Ticker = unittest.mock.MagicMock()
    sys.modules["yfinance"] = _yf

# ── plotly + streamlit_lightweight_charts ─────────────────────────────────────
# Streamlit itself imports several plotly submodules (plotly.io, plotly.tools,
# plotly.express …).  Pre-registering a fixed list breaks whenever Streamlit
# accesses another submodule.  Instead, install a meta-path finder that
# intercepts *any* import whose name starts with "plotly" (or the other
# missing packages) and returns a MagicMock-based module so the import
# always succeeds.
_STUB_PREFIXES = ("plotly", "streamlit_lightweight_charts")


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


sys.meta_path.insert(0, _StubFinder())

# Streamlit's plotly_chart.py serialises the figure via plotly.io.to_json and
# then assigns the result to a protobuf string field.  With a stub, that
# method returns a MagicMock → protobuf rejects it.  Pre-import the stub and
# set a valid return value so the protobuf assignment succeeds.
import plotly.io as _pio   # noqa: E402 — must come after finder install
_pio.to_json.return_value = "{}"
