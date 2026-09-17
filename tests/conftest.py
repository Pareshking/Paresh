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
