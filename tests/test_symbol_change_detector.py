"""The rename detector must fire on a case we know is real.

Its first version grouped twin candidates by their LAST close, which in a
rename differ (the old ticker stops updating), so it reported "0 twins"
against a pair already measured by hand as 716 identical sessions. These
tests exist so that cannot pass quietly again: each one builds a case whose
answer is known and requires the detector to find it.
"""
from __future__ import annotations

import pandas as pd
import pytest

from pathlib import Path

from scripts.check_symbol_changes import (
    _id_twins,
    _pairs,
    _rename_between,
    _twins,
    _unaliased_renames,
)


def _sessions(n: int) -> pd.DatetimeIndex:
    return pd.bdate_range("2024-01-01", periods=n)


def test_a_handover_is_found_when_one_series_ends_and_another_begins():
    idx = _sessions(10)
    df = pd.DataFrame(index=idx, columns=["OLDCO", "NEWCO"], dtype=float)
    df.loc[idx[:5], "OLDCO"] = 100.0
    df.loc[idx[5:], "NEWCO"] = 99.0
    found = _pairs(df)
    assert [(p[1], p[2]) for p in found] == [("OLDCO", "NEWCO")]
    assert found[0][0] == idx[4]           # the old symbol's last session
    assert found[0][5] == pytest.approx(0.99)


def test_a_handover_at_a_wildly_different_price_is_not_called_a_rename():
    idx = _sessions(10)
    df = pd.DataFrame(index=idx, columns=["OLDCO", "NEWCO"], dtype=float)
    df.loc[idx[:5], "OLDCO"] = 100.0
    df.loc[idx[5:], "NEWCO"] = 40.0       # not a ticker change
    assert _pairs(df) == []


def test_twins_are_found_even_though_their_last_closes_differ():
    """The bug: a renamed company's old ticker stops updating, so grouping
    candidates by last close never compares the very pair that matters."""
    idx = _sessions(120)
    shared = pd.Series(range(120), index=idx, dtype=float) + 400.0
    df = pd.DataFrame(index=idx, dtype=float)
    df["NEWTICK"] = shared                                  # the full history
    df["OLDTICK"] = shared.where(shared.index <= idx[100])  # stops early
    assert df["NEWTICK"].dropna().iloc[-1] != df["OLDTICK"].dropna().iloc[-1]

    twins = _twins(df)
    assert {frozenset((a, b)) for a, b, _ in twins} == {frozenset(("NEWTICK", "OLDTICK"))}
    assert twins[0][2] >= 100


def test_two_different_companies_are_not_twins():
    idx = _sessions(120)
    df = pd.DataFrame(index=idx, dtype=float)
    df["ACO"] = pd.Series(range(120), index=idx, dtype=float) + 400.0
    df["BCO"] = pd.Series(range(120), index=idx, dtype=float) + 400.5
    assert _twins(df) == []


def test_sundarmhld_to_rubicon_is_explained_not_a_handover():
    # S129 (b), 15 Nov 2026: NSE's equity_l.csv lists RUBICON as Rubicon Research,
    # a new listing on 16 Oct 2025 with its own ISIN; SUNDARMHLD became TSFINV.
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location(
        "check_symbol_changes", Path(__file__).resolve().parents[1] / "scripts" / "check_symbol_changes.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    why = mod.EXPLAINED[("SUNDARMHLD", "RUBICON")]
    assert "INE506V01022" in why and "TSFINV" in why
    eq = (Path(__file__).resolve().parents[1] / "data" / "reference" / "nse" / "equity_l.csv").read_text()
    assert "RUBICON,Rubicon Research Limited,EQ,16-OCT-2025" in eq


# ── S129 (c): Screener id twins and renames filed as an exit and an entry ────

_REPO = Path(__file__).resolve().parents[1]


def test_two_symbols_on_one_screener_company_id_are_id_twins():
    ids = {"HEG": "1301", "HEGAM": "1301", "ABB": "7", "ICICILIFE": "9", "ICICIPRULI": "9"}
    assert _id_twins(ids) == [("HEG", "HEGAM", "1301"), ("ICICILIFE", "ICICIPRULI", "9")]
    assert _id_twins({"ABB": "7", "ACC": "8"}) == []


def test_a_twin_is_explained_only_by_a_rename_that_joins_the_pair():
    known = {"HEG": {"new_symbol": "HEGAM"}}
    assert _rename_between("HEGAM", "HEG", known) == ("HEG", "HEGAM")
    assert _rename_between("HEG", "OTHER", known) is None


def _history(changes, aliases=None, baseline=("ABB",)):
    return {"baseline": {"date": "2021-10-29", "symbols": list(baseline)},
            "changes": changes, "aliases": aliases or {}}


def test_a_rename_filed_as_out_and_in_without_an_alias_is_reported():
    """ICICIPRULI -> ICICILIFE (NSE symbolchange.csv, 23-OCT-2026): the daily sync
    filed it as ICICIPRULI out, ICICILIFE in on 28 Oct, with no alias."""
    known = {"ICICIPRULI": {"new_symbol": "ICICILIFE"}}
    h = _history([{"date": "2026-10-28", "added": ["ICICILIFE"], "removed": ["ICICIPRULI"]}],
                 baseline=("ICICIPRULI",))
    assert _unaliased_renames(h, known) == [("2026-10-28", "ICICIPRULI", "ICICILIFE")]
    h["aliases"] = {"ICICIPRULI": {"new_symbol": "ICICILIFE", "effective": "2026-10-23"}}
    assert _unaliased_renames(h, known) == []


def test_an_old_ticker_whose_membership_ended_before_the_rename_is_not_reported():
    # TIDEWATER left the Smallcap 250 in 2017; it became VEEDOL in Oct 2024.
    known = {"TIDEWATER": {"new_symbol": "VEEDOL"}}
    h = _history([{"date": "2017-09-29", "added": [], "removed": ["TIDEWATER"]}],
                 baseline=("TIDEWATER",))
    assert _unaliased_renames(h, known) == []


# Renames already found and awaiting their data entry (a symbol_aliases row in
# data/membership_notices.json, then extend_membership_from_notices.py apply).
# Anything NOT listed fails: that is the new case nobody was told about. Remove
# the row once the alias is in the committed history.
PENDING_ALIASES = {("2026-10-28", "ICICIPRULI", "ICICILIFE")}


def _known_renames() -> dict:
    import json

    from src.loaders.nse_identity import auto_renames
    ledger = json.loads((_REPO / "data/nse_prices/notes.json").read_text()).get("renames", {})
    return {**auto_renames(), **ledger}


def test_every_committed_screener_id_twin_is_a_joined_rename():
    import json
    ids = json.loads((_REPO / "data/screener_company_ids.json").read_text())["ids"]
    known = _known_renames()
    bad = [t for t in _id_twins(ids) if _rename_between(t[0], t[1], known) is None]
    assert bad == [], f"symbols sharing a Screener company id with no rename joining them: {bad}"


def test_no_new_rename_is_filed_in_membership_as_an_exit_and_an_entry():
    import json
    history = json.loads((_REPO / "data/membership_history.json").read_text())
    found = set(_unaliased_renames(history, _known_renames()))
    assert found <= PENDING_ALIASES, f"new unaliased renames: {sorted(found - PENDING_ALIASES)}"
