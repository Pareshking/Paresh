"""S227: a ticker NSE changed after the list was built opens the stock's page (owner, 25 Nov 2026:
"Redirect now, rename in Jan"). Display only: the ranking keeps the old ticker."""
from __future__ import annotations

import pandas as pd

from src.ui import stock_lines as sl


def _fake(monkeypatch, renames, changes):
    import src.loaders.nse_identity as ni
    monkeypatch.setattr(ni, "auto_renames", lambda present=None, **k: {
        o: {"new_symbol": n} for o, n in renames.items() if present is None or o in present})
    monkeypatch.setattr(ni, "symbol_changes", lambda *a, **k: changes)
    sl.renamed_on_nse.cache_clear()


def test_a_renamed_ranked_stock_is_found_under_its_new_ticker(monkeypatch):
    _fake(monkeypatch, {"SHUKRAPHAR": "SHUKRAMED"},
          pd.DataFrame({"old": ["SHUKRAPHAR"], "new": ["SHUKRAMED"], "date": [pd.Timestamp("2026-11-20")]}))
    assert sl.renamed_on_nse(frozenset({"SHUKRAPHAR", "TCS"})) == {"SHUKRAMED": ("SHUKRAPHAR", "20 Nov 2026")}


def test_no_redirect_when_the_new_ticker_is_already_ranked(monkeypatch):
    # The 750's renames are already followed (aliases): HEGAM is ranked, so HEG needs nothing.
    _fake(monkeypatch, {"HEG": "HEGAM"}, pd.DataFrame(columns=["old", "new", "date"]))
    assert sl.renamed_on_nse(frozenset({"HEG", "HEGAM"})) == {}


def test_a_missing_reference_file_gives_no_redirect(monkeypatch):
    import src.loaders.nse_identity as ni

    def broken(*a, **k):
        raise OSError("no symbolchange.csv")
    monkeypatch.setattr(ni, "auto_renames", broken)
    sl.renamed_on_nse.cache_clear()
    assert sl.renamed_on_nse(frozenset({"SHUKRAPHAR"})) == {}


def test_the_committed_files_redirect_shukramed():
    sl.renamed_on_nse.cache_clear()
    import json
    from pathlib import Path
    months = json.loads((Path(__file__).resolve().parents[1] / "data" / "nanocap_membership.json").read_text())["months"]
    got = sl.renamed_on_nse(frozenset(months[sorted(months)[-1]]["symbols"]))
    assert got.get("SHUKRAMED", ("",))[0] == "SHUKRAPHAR"
