"""The corporate-actions log union used on rebase conflicts (audit, 8 Nov 2026)."""
import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "merge_actions_log", Path(__file__).resolve().parents[1] / "scripts" / "merge_actions_log.py")
m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(m)


def test_both_sides_events_are_kept_and_first_seen_is_the_earliest():
    a = {"schema_version": 1, "events": {"2026-11-01:A": {"first_seen": "2026-11-02", "kind": "x"},
                                         "2026-11-03:B": {"first_seen": "2026-11-04"}}, "last_checked": "2026-11-05"}
    b = {"schema_version": 1, "events": {"2026-11-01:A": {"first_seen": "2026-11-03", "kind": "split"},
                                         "2026-11-06:C": {"first_seen": "2026-11-07"}}, "last_checked": "2026-11-07"}
    out = m.merge(a, b)
    assert set(out["events"]) == {"2026-11-01:A", "2026-11-03:B", "2026-11-06:C"}
    assert out["events"]["2026-11-01:A"] == {"first_seen": "2026-11-02", "kind": "split"}
    assert out["last_checked"] == "2026-11-07"
