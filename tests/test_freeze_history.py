"""Guards for nse_index_rebuild/freeze_history.py and the committed freeze record."""
import copy
import importlib.util
import json
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("freeze_history", ROOT / "nse_index_rebuild" / "freeze_history.py")
fh = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fh)

HIST = json.loads((ROOT / "data" / "membership_history.json").read_text(encoding="utf-8"))
FREEZE = json.loads((ROOT / "data" / "membership_history.freeze.json").read_text(encoding="utf-8"))


def test_the_committed_history_matches_its_freeze_record():
    assert fh.check(HIST, FREEZE) == []


def test_a_change_after_the_freeze_date_does_not_move_the_hash():
    later = copy.deepcopy(HIST)
    later["indices"]["nifty_50"]["changes"].append(
        {"date": "2026-12-31", "added": ["NEWCO"], "removed": ["OLDCO"]})
    assert fh.digest(fh.frozen_view(later)) == fh.digest(fh.frozen_view(HIST))


@pytest.mark.parametrize("edit", [
    lambda h: h["indices"]["nifty_50"]["baseline"]["symbols"].append("X"),
    lambda h: h["indices"]["nifty_500"]["changes"][0].update(date="2010-02-25"),
    lambda h: h["symbol_changes"]["changes"].pop(),
    lambda h: h["caveats"]["intervals"].pop(),
])
def test_an_edit_inside_the_frozen_range_is_detected(edit):
    changed = copy.deepcopy(HIST)
    edit(changed)
    assert fh.check(changed, FREEZE)


def test_the_change_log_is_continuous_and_ends_at_the_recorded_hash():
    log = FREEZE["changelog"]
    assert log and log[-1]["sha256_after"] == FREEZE["sha256"]
    assert all(b["sha256_before"] == a["sha256_after"] for a, b in zip(log, log[1:]))


def test_write_records_an_edit_with_its_reason_and_keeps_the_chain():
    changed = copy.deepcopy(HIST)
    changed["indices"]["nifty_50"]["baseline"]["symbols"].append("X")
    out = fh.write(changed, FREEZE, "test edit")
    assert out["changelog"][-1]["reason"] == "test edit"
    assert out["changelog"][-1]["sha256_before"] == FREEZE["sha256"]
    assert fh.check(changed, out) == []
    assert fh.write(HIST, FREEZE, "no change") == FREEZE   # an unchanged history adds no log entry
