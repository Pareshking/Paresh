"""S87: the monthly freeze refuses to strike a new month from a replay that no
longer reproduces an earlier frozen month, and the workflow still freezes the
other records and fails loudly."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _updater():
    spec = importlib.util.spec_from_file_location("update_track_record",
                                                  ROOT / "scripts" / "update_track_record.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _parity(*statuses):
    return {"rows": [{"month": f"2026-{i + 1:02d}", "status": s} for i, s in enumerate(statuses)]}


def test_a_drifted_frozen_month_stops_a_new_month():
    mod = _updater()
    # The 3 Nov case: September drifted, October about to be struck.
    parity = _parity("match", "accepted", "match", "drift")
    assert mod.refuse_to_freeze(parity, ["2026-10"], force=False) == ["2026-04"]


def test_accepted_and_matching_months_do_not_stop_it():
    mod = _updater()
    parity = _parity("match", "accepted", "accepted", "match", "missing_recomputed_period")
    assert mod.refuse_to_freeze(parity, ["2026-10"], force=False) == []


def test_nothing_to_add_is_never_refused():
    mod = _updater()
    assert mod.refuse_to_freeze(_parity("drift"), [], force=False) == []


def test_a_deliberate_rebuild_is_not_stopped():
    mod = _updater()
    assert mod.refuse_to_freeze(_parity("drift"), ["2026-10"], force=True) == []


def test_the_workflow_freezes_the_other_records_and_fails_loudly():
    yaml = pytest.importorskip("yaml")
    spec = yaml.safe_load((ROOT / ".github/workflows/monthly_track_record.yml").read_text())
    steps = {s.get("name"): s for s in spec["jobs"]["freeze"]["steps"]}
    for name in ("Freeze Nano Cap and Combined", "Freeze the shadow record", "Commit the ledger"):
        assert steps[name].get("if") == "${{ !cancelled() }}", name
    nano = steps["Freeze Nano Cap and Combined"]["run"]
    assert "exit 1" in nano and "failed=" in nano
    assert "|| echo" not in steps["Freeze newly closed months"]["run"]
