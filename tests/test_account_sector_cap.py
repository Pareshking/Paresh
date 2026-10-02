"""The canonical account carries the 5% stock / 30% industry caps (owner, 2026-10-02).

Before this, record_run passed no sector map, so run_backtest's 30% default
never bound and the account held 40-60% in one industry while Actions and the
research backtest applied 30%.
"""
import inspect

import pandas as pd

from src.engine import model_record
from src.engine.model_record import record_sector_map
from src.engine.track_record import TRACK_RECORD_CONFIG
from src.loaders import former_members


def test_pinned_config_carries_the_caps():
    assert TRACK_RECORD_CONFIG["stock_cap"] == 0.05
    assert TRACK_RECORD_CONFIG["sector_cap"] == 0.40


def test_current_members_keep_their_nse_index_industry():
    # industry_for re-labels current members from TradingView; for these three
    # it disagreed with the index file the ranking and Actions read.
    idx = pd.read_csv(former_members.INDEX_FILE)
    nse = dict(zip(idx["Symbol"], idx["Industry"]))
    names = [s for s in ("CPPLUS", "SIGMAADV", "STLTECH") if s in nse]
    assert names, "fixture names left the index; pick current members"
    got = record_sector_map(names)
    assert all(got[s] == nse[s] for s in names)
    every = record_sector_map(list(nse))
    assert every == {s: str(nse[s]) for s in nse}


def test_former_members_still_get_a_label():
    idx = pd.read_csv(former_members.INDEX_FILE)
    gone = "CIGNITITEC"
    if gone in set(idx["Symbol"]):
        return
    assert record_sector_map([gone])[gone]


def test_record_run_passes_the_caps_and_a_sector_map():
    src = inspect.getsource(model_record.record_run)
    assert 'sector_cap=cfg["sector_cap"]' in src
    assert 'stock_cap=cfg["stock_cap"]' in src
    assert "sector_map=record_sector_map(" in src


def test_ledger_months_are_struck_under_the_capped_config():
    import json
    from src.engine.track_record import LEDGER_PATH
    ledger = json.loads(open(LEDGER_PATH, encoding="utf-8").read())
    # The latest STRATEGY rebuild; a benchmark-only correction re-strikes no month.
    last = [r for r in ledger["rebuilds"] if r.get("kind") != "benchmark_correction"][-1]
    assert {m["config"] for m in ledger["months"].values()} == {last["config"]}
    assert "40%" in last["note"]
