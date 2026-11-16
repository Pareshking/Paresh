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


def test_mains_verdict_and_note_win_over_a_run_that_checked_out_before_they_changed():
    # 16 Nov 2026: S132 changed ALOKINDS to price_move and rewrote its note on main.
    main = {"events": {"2020-02-19:ALOKINDS": {"first_seen": "2026-09-18", "verdict": "price_move",
                                               "verdict_note": "Owner, 15 Nov 2026: BSE notice 20200217-50"}}}
    stale_run = {"events": {"2020-02-19:ALOKINDS": {"first_seen": "2026-09-18", "verdict": "corporate_action",
                                                    "verdict_note": "Owner check, 2026-09-27: ...", "move": 4.1}}}
    ev = m.merge(main, stale_run)["events"]["2020-02-19:ALOKINDS"]
    assert ev["verdict"] == "price_move" and ev["verdict_note"].startswith("Owner, 15 Nov")
    assert ev["move"] == 4.1                                     # the run's other fields still come through


def test_a_run_may_still_give_a_verdict_where_main_has_none():
    main = {"events": {"2026-04-30:VEDL": {"first_seen": "2026-05-01"}}}
    run = {"events": {"2026-04-30:VEDL": {"first_seen": "2026-05-01", "verdict": "corporate_action",
                                          "verdict_note": "Screener restated the history"}}}
    assert m.merge(main, run)["events"]["2026-04-30:VEDL"]["verdict"] == "corporate_action"
