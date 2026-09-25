"""The Yahoo fallback stores an index's history only under its exact name."""

import pytest

from scripts import build_nse_index_prices as mod


class _Search:
    def __init__(self, quotes):
        self.quotes = quotes


def test_a_near_miss_index_is_refused_not_stored(monkeypatch):
    # "NIFTY MIDCAP" also finds Midcap 100; that must not become Midcap 150.
    monkeypatch.setattr(mod.yf, "Search", raising=False, value=lambda q, max_results=50: _Search(
        [{"quoteType": "INDEX", "shortname": "NIFTY MIDCAP 100", "symbol": "^CNXMIDCAP"}]
    ))
    monkeypatch.setattr(mod.yf, "download", raising=False, value=lambda *a, **k: pytest.fail("downloaded a wrong index"))
    with pytest.raises(RuntimeError, match="no exact match"):
        mod._fetch_yahoo("nifty_midcap150", "NIFTY MIDCAP 150", None, None)
