"""The Recommendation's shadow record (owner, 12 Oct 2026, TODO 6 and 9).

Recorded forward beside the live system from November 2026 and never traded:
the live record's setup with 30 holdings, keep while in the top 90 and a 200-day
EMA, in its own ledger. The live records must not move because of it.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd
import pytest
import yaml

from src.engine.backtester import sector_slots
from src.engine.extra_universe import SYSTEM_750, SYSTEM_NANO
from src.engine.track_record import (
    LEDGER_PATH,
    SHADOW_CONFIG,
    SHADOW_INCEPTION,
    SHADOW_LEDGER_PATH,
    SHADOW_NAME,
    TRACK_RECORD_CONFIG,
    config_fingerprint,
    load_ledger,
)
from src.ui.views.track_record_view import comparison_frame

ROOT = Path(__file__).resolve().parents[1]


def _updater():
    spec = importlib.util.spec_from_file_location("update_track_record",
                                                  ROOT / "scripts" / "update_track_record.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_the_shadow_differs_from_the_live_record_in_three_settings_only():
    changed = {k for k in TRACK_RECORD_CONFIG if SHADOW_CONFIG[k] != TRACK_RECORD_CONFIG[k]}
    assert changed == {"top_n", "buffer_n", "ema_period"}
    assert (SHADOW_CONFIG["top_n"], SHADOW_CONFIG["buffer_n"], SHADOW_CONFIG["ema_period"]) == (30, 90, 200)
    assert set(SHADOW_CONFIG) == set(TRACK_RECORD_CONFIG)
    # The live record is the one pinned in TRACK_RECORD.md: 20 holdings, top 40, 50D EMA.
    assert (TRACK_RECORD_CONFIG["top_n"], TRACK_RECORD_CONFIG["buffer_n"],
            TRACK_RECORD_CONFIG["ema_period"]) == (20, 40, 50)


def test_the_shadow_has_its_own_fingerprint_ledger_and_start():
    assert config_fingerprint(**SHADOW_CONFIG) != config_fingerprint(**TRACK_RECORD_CONFIG)
    assert SHADOW_LEDGER_PATH != LEDGER_PATH
    assert SHADOW_LEDGER_PATH.parent == LEDGER_PATH.parent
    assert SHADOW_LEDGER_PATH.name.startswith("track_record")  # the workflow's git add covers it
    assert SHADOW_INCEPTION == pd.Period("2026-11", freq="M")


def test_thirty_names_keep_the_hard_caps():
    # 30 names at 3.33% each: the 40% industry cap holds at 12 names, 5% is never reached.
    assert sector_slots(SHADOW_CONFIG["top_n"], SHADOW_CONFIG["stock_cap"], SHADOW_CONFIG["sector_cap"]) == 12
    assert 1 / SHADOW_CONFIG["top_n"] < SHADOW_CONFIG["stock_cap"]


def test_the_updater_sets_up_the_shadow_and_leaves_the_live_records_alone():
    mod = _updater()
    system, ledger, start, cfg = mod.record_setup(SYSTEM_750, shadow=True)
    assert (system, Path(ledger), start, cfg) == (SYSTEM_750, SHADOW_LEDGER_PATH, SHADOW_INCEPTION,
                                                  SHADOW_CONFIG)
    system, ledger, start, cfg = mod.record_setup(SYSTEM_750)
    assert (Path(ledger), start, cfg) == (LEDGER_PATH, pd.Period("2026-01", freq="M"), TRACK_RECORD_CONFIG)
    assert mod.record_setup(SYSTEM_NANO)[3] == TRACK_RECORD_CONFIG
    with pytest.raises(SystemExit):
        mod.record_setup(SYSTEM_NANO, shadow=True)
    # A copy: the run sets cfg["prices"] from the basis it used.
    mod.record_setup(SYSTEM_750, shadow=True)[3]["prices"] = "changed"
    assert SHADOW_CONFIG["prices"] == TRACK_RECORD_CONFIG["prices"]


def test_the_monthly_workflow_freezes_the_shadow_after_the_live_records():
    wf = yaml.safe_load((ROOT / ".github" / "workflows" / "monthly_track_record.yml").read_text(encoding="utf-8"))
    steps = [s["name"] for s in wf["jobs"]["freeze"]["steps"]]
    i = steps.index("Freeze the shadow record")
    assert steps.index("Freeze newly closed months") < i < steps.index("Commit the ledger")
    run = wf["jobs"]["freeze"]["steps"][i]["run"]
    assert "update_track_record.py --shadow" in run and "|| echo" in run  # never fails the job


def test_a_missing_shadow_ledger_before_its_start_reads_empty(tmp_path):
    assert load_ledger(tmp_path / "track_record_shadow.json", SHADOW_INCEPTION)["months"] == {}


def _ledger(months: dict[str, float]) -> dict:
    return {"months": {k: {"strategy": v, "benchmark": 0.0, "alpha": v} for k, v in months.items()}}


def test_the_side_by_side_table_shows_the_shadow_frozen_months_only():
    ledgers = {SYSTEM_750: _ledger({"2026-10": 0.01, "2026-11": 0.02})}
    shadow = _ledger({"2026-10": 0.99, "2026-11": 0.03})  # October predates it: never shown
    live = {SYSTEM_750: {"mtd_period": "2026-12", "strategy_mtd": 0.005}}
    table = comparison_frame(ledgers, live, shadow)
    row = table[table["SYSTEM"] == SHADOW_NAME].iloc[0]
    assert pd.isna(row["OCT"]) and row["NOV"] == 0.03 and pd.isna(row["DEC"])
    assert list(table["SYSTEM"]).index(SHADOW_NAME) == len(table) - 1
    assert SHADOW_NAME not in set(comparison_frame(ledgers, live)["SYSTEM"])
