"""Stocks the index once held and has since dropped must have prices.

The deep price history is the CURRENT constituents' only. Scored on the index as
it stood, a backtest could then pick from the survivors alone: in 2026, 54 to 98
of the 750 members at each month end had no prices at all, and the ones missing
are the stocks that fell out of the index, which flatters the result.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

import src.engine.pipeline  # noqa: F401  (pipeline first: it and momentum import each other)
from src.engine.membership import load_history, members_on
from src.engine.track_record import finalize_months
from src.loaders import former_members as fm

ROOT = Path(__file__).resolve().parents[1]
IDX = pd.bdate_range("2025-12-01", "2026-03-31")


def _history(aliases=None):
    h = {"baseline": {"date": "2025-12-31", "symbols": ["AAA", "OLDX", "GONE"]},
         "changes": [{"date": "2026-03-30", "added": ["NEWY"], "removed": ["GONE"]}]}
    if aliases:
        h["aliases"] = aliases
    return h


def _frame(*cols):
    return pd.DataFrame({c: np.linspace(100, 110, len(IDX)) for c in cols}, index=IDX).astype("float32")


# ── ticker changes ───────────────────────────────────────────────────────────

def test_a_ticker_change_is_one_continuous_member_when_asked_canonically():
    h = _history({"OLDX": {"new_symbol": "NEWX", "effective": "2026-03-01"}})
    assert members_on(h, "2026-01-30") == {"AAA", "OLDX", "GONE"}                # the raw record
    assert members_on(h, "2026-01-30", canonical=True) == {"AAA", "NEWX", "GONE"}  # prices' name
    assert members_on(_history(), "2026-01-30", canonical=True) == {"AAA", "OLDX", "GONE"}


def test_the_committed_history_treats_heg_as_hegam_throughout():
    h = load_history()
    for day in ("2026-01-30", "2026-08-31", "2026-09-22"):
        raw, canon = members_on(h, day), members_on(h, day, canonical=True)
        assert "HEG" in raw and "HEG" not in canon and "HEGAM" in canon
    assert len(members_on(h, "2026-09-22", canonical=True)) == 750


# ── what needs prices ────────────────────────────────────────────────────────

def test_symbols_needed_is_every_member_ever_the_frame_lacks():
    assert fm.symbols_needed(_history(), ["AAA"]) == ["GONE", "NEWY", "OLDX"]
    assert fm.symbols_needed(_history(), ["AAA", "GONE", "NEWY", "OLDX"]) == []
    assert fm.symbols_needed(None, ["AAA"]) == []


def test_with_former_members_adds_only_names_the_record_lists():
    current = _frame("AAA", "NEWY")
    stored = _frame("GONE", "OLDX", "STRAY")           # STRAY was never a member
    out = fm.with_former_members(current, _history(), stored=stored)
    assert list(out.columns) == ["AAA", "NEWY", "GONE", "OLDX"]
    assert out.index.equals(current.index) and str(out["GONE"].dtype) == "float32"


def test_with_no_membership_record_nothing_is_added():
    current = _frame("AAA")
    assert fm.with_former_members(current, None, stored=_frame("GONE")).equals(current)
    assert fm.with_former_members(current, {}, stored=_frame("GONE")).equals(current)


def test_a_name_the_frame_already_has_is_never_overwritten():
    current = _frame("AAA", "GONE")
    out = fm.with_former_members(current, _history(), stored=_frame("GONE", "OLDX").mul(2))
    assert out["GONE"].equals(current["GONE"]) and "OLDX" in out.columns


def test_stored_history_is_aligned_to_the_frames_dates_and_gaps_stay_gaps():
    short = _frame("GONE").iloc[10:30]
    out = fm.with_former_members(_frame("AAA"), _history(), stored=short)
    assert out.index.equals(IDX) and out["GONE"].iloc[:10].isna().all() and out["GONE"].iloc[10:30].notna().all()


# ── industries for the sector cap ────────────────────────────────────────────

def test_industry_follows_the_majority_of_current_members_with_the_same_tv_industry(tmp_path):
    (tmp_path / "idx.csv").write_text(
        "Company Name,Industry,Symbol,Series,ISIN Code\n"
        "a,Healthcare,A1,EQ,x\nb,Healthcare,A2,EQ,x\nc,Chemicals,A3,EQ,x\nd,Metals,B1,EQ,x\n")
    (tmp_path / "tv.csv").write_text(
        "Symbol,TV_Sector,TV_Industry\nA1,Health,Pharma\nA2,Health,Pharma\nA3,Health,Pharma\n"
        "B1,Mat,Steel\nF1,Health,Pharma\nF2,Mat,Steel\nF3,Mat,Other\nF4,Z,Q\n")
    out = fm.industry_for(["F1", "F2", "F3", "F4", "NOPE"], tv_file=tmp_path / "tv.csv",
                          index_file=tmp_path / "idx.csv")
    assert out == {"F1": "Healthcare", "F2": "Metals", "F3": "Metals", "F4": "Other", "NOPE": "Other"}


# ── the committed supplement ─────────────────────────────────────────────────

def test_the_committed_file_prices_every_former_member_it_can_and_names_the_rest():
    meta = json.loads((ROOT / "data" / "former_member_prices.json").read_text(encoding="utf-8"))
    stored = fm.load()
    assert meta["symbols"] == stored.shape[1] and stored.shape[1] > 90
    assert set(meta["unavailable"]).isdisjoint(stored.columns)
    # nothing the record needs is silently absent: it is priced or it is listed
    idx = pd.read_csv(ROOT / "data" / "indices" / "ind_niftytotalmarket_list.csv")
    needed = set(fm.symbols_needed(load_history(), idx["Symbol"]))
    assert needed - set(stored.columns) == set(meta["unavailable"])
    assert stored.index.min() <= pd.Timestamp("2025-01-02")   # a 12-month window before 2026


def test_a_month_end_pool_is_now_almost_entirely_priced():
    h = load_history()
    idx = pd.read_csv(ROOT / "data" / "indices" / "ind_niftytotalmarket_list.csv")
    priced = set(idx["Symbol"]) | set(fm.load().columns)
    for day in ("2025-12-31", "2026-02-27", "2026-05-29", "2026-08-31"):
        pool = members_on(h, day, canonical=True)
        assert len(pool - priced) <= 4, (day, sorted(pool - priced))   # only the merged-away names


# ── a rebuild says it is one ─────────────────────────────────────────────────

def _curve():
    idx = pd.bdate_range("2026-01-01", "2026-03-31")
    return pd.Series(np.linspace(1.0, 1.1, len(idx)), index=idx)


def test_a_forced_rewrite_labels_every_month_a_reconstruction():
    led = {"months": {}, "inception": "2026-01"}
    kw = dict(fingerprint="fp", as_of=pd.Timestamp("2026-04-02"))
    normal, _, _ = finalize_months(led, _curve(), _curve(), **kw)
    forced, added, _ = finalize_months(led, _curve(), _curve(), force=True, **kw)
    assert normal["months"]["2026-03"]["origin"] == "recorded"       # the month that just closed
    assert {forced["months"][k]["origin"] for k in added} == {"backfill"}


def test_the_rebuilt_ledger_is_one_regime_on_the_index_as_it_stood():
    led = json.loads((ROOT / "data" / "track_record.json").read_text(encoding="utf-8"))
    months = led["months"]
    assert len({m["config"] for m in months.values()}) == 1
    assert {m["universe"] for m in months.values()} == {"point_in_time"}
    # The rebuilt months are reconstructions; a month frozen as it closed afterwards is recorded.
    assert {m["origin"] for k, m in months.items() if k <= "2026-08"} == {"backfill"}
    assert {m["origin"] for k, m in months.items() if k > "2026-08"} <= {"recorded"}
    first, last = led["rebuilds"][0], led["rebuilds"][-1]
    assert first["membership"].startswith("point in time") and "5b356a6ba93b" in first["replaced_configs"]
    assert set(first["months"]) <= set(months) and first["former_members_unpriceable"]   # Yahoo had none
    assert last["config"] == next(iter(months.values()))["config"]                      # the NSE rebuild
