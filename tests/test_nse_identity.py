"""Renames from NSE's symbol-change list and ISINs (src/loaders/nse_identity.py)."""
import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.loaders import nse_identity as ni
from src.loaders import nse_prices as npx

ROOT = Path(__file__).resolve().parents[1]

CURRENT = {"INE144J01027": "20MICRONS", "INE07T201019": "RBA", "INE00R701025": "DALBHARAT",
           "INE155A01022": "TATAMOTORS2", "INE999Z01011": "NEWCO"}
CHANGES = pd.DataFrame({"old": ["AMIORG", "OLDA", "MIDB"], "new": ["NEWCO", "MIDB", "GONE"],
                        "date": pd.to_datetime(["2023-01-02", "2015-01-01", "2018-01-01"])})
HISTORY = pd.DataFrame({
    "symbol": ["BURGERKING", "OCLINDIA", "20MICRONS", "DELISTED", "AMIORG"],
    "isin": ["INE07T201019", "INE00R701017", "INE144J01019", "INE111X01010", "INE999Z01011"],
    "first": pd.to_datetime(["2020-12-14", "2011-06-22", "2011-06-22", "2011-06-22", "2019-01-01"]),
    "last": pd.to_datetime(["2021-06-04", "2019-01-04", "2013-01-25", "2014-01-01", "2021-06-04"]),
})


def _resolve():
    return ni.resolve(changes=CHANGES, history=HISTORY, current=CURRENT).set_index("old")


def test_the_same_isin_under_a_new_symbol_is_a_rename():
    assert _resolve().loc["BURGERKING", ["new", "source"]].tolist() == ["RBA", "isin"]


def test_an_isin_changed_with_the_face_value_still_matches_on_the_issuer_prefix():
    assert _resolve().loc["OCLINDIA", ["new", "source"]].tolist() == ["DALBHARAT", "isin_prefix"]


def test_both_records_agreeing_is_recorded():
    assert _resolve().loc["AMIORG", "source"] == "nse_list+isin"


def test_a_listed_symbol_is_never_re_pointed_and_a_dead_end_is_no_rename():
    t = _resolve()
    assert "20MICRONS" not in t.index                  # still listed, though its ISIN changed
    assert "DELISTED" not in t.index and "OLDA" not in t.index   # OLDA -> MIDB -> GONE: not listed


def test_records_that_disagree_are_a_conflict_and_not_applied():
    changes = pd.DataFrame({"old": ["BURGERKING"], "new": ["NEWCO"], "date": [pd.Timestamp("2022-01-01")]})
    t = ni.resolve(changes=changes, history=HISTORY, current=CURRENT).set_index("old")
    assert t.loc["BURGERKING", "conflict"] and pd.isna(t.loc["BURGERKING", "new"])
    assert "BURGERKING" not in ni.auto_renames(changes=changes, history=HISTORY, current=CURRENT)


def test_every_rename_in_the_ledger_is_found_by_the_committed_records():
    ledger = json.loads((ROOT / "data/nse_prices/notes.json").read_text())["renames"]
    auto = ni.auto_renames()
    for old, a in ledger.items():
        assert auto.get(old, {}).get("new_symbol") == a["new_symbol"], old


# ── Joining two series only where they meet ──────────────────────────────────

DAYS = pd.bdate_range("2021-01-04", periods=40)


def _close(old_last, new_first, jump=0.0):
    old = pd.Series(np.nan, index=DAYS)
    old.iloc[: old_last + 1] = 100.0
    new = pd.Series(np.nan, index=DAYS)
    new.iloc[new_first:] = 100.0 * (1 + jump)
    return pd.DataFrame({"OLD": old, "NEW": new})


def test_an_auto_rename_joins_where_the_series_meet():
    skipped = []
    out = npx.chain_symbols(_close(19, 20), {"OLD": {"new_symbol": "NEW", "auto": True}}, skipped)
    assert list(out.columns) == ["NEW"] and out["NEW"].notna().all() and not skipped


def test_an_auto_rename_across_a_long_gap_is_not_joined():
    skipped = []
    out = npx.chain_symbols(_close(5, 30), {"OLD": {"new_symbol": "NEW", "auto": True}}, skipped)
    assert set(out.columns) == {"OLD", "NEW"} and "days between" in skipped[0]


def test_an_auto_rename_with_a_price_cliff_is_not_joined():
    """DHFL -> PIRAMALFIN: same issuer code, the old equity extinguished."""
    skipped = []
    npx.chain_symbols(_close(19, 20, jump=-0.9), {"OLD": {"new_symbol": "NEW", "auto": True}}, skipped)
    assert "price moves" in skipped[0]


def test_the_ledger_joins_without_the_check():
    out = npx.chain_symbols(_close(5, 30), {"OLD": {"new_symbol": "NEW"}})
    assert list(out.columns) == ["NEW"]


def test_an_old_name_asked_for_gets_its_successors_series():
    closes = _close(19, 20)
    actions = pd.DataFrame(columns=npx.ACTION_COLS)
    out, rep = npx.adjusted_close(closes, actions, ["OLD"], notes={"renames": {"OLD": {"new_symbol": "NEW"}}})
    assert rep["unpriced"] == [] and out["OLD"].notna().all()
