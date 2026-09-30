"""Per-system ledgers, inception and point-in-time membership."""
import json

import pandas as pd

from src.engine import systems as sy
from src.engine.membership import members_on, record_snapshot
from src.engine.track_record import empty_ledger, finalize_months, ledger_inception


def _nano(tmp_path):
    p = tmp_path / "nano.json"
    p.write_text(json.dumps({"months": {
        "2026-08-31": {"effective_from": "2026-09-01", "symbols": ["N1", "N2"]},
        "2026-09-30": {"effective_from": "2026-10-01", "symbols": ["N2", "N3"]}}}))
    return p


def test_nano_lists_are_in_force_from_the_session_that_built_them(tmp_path):
    h = sy.nano_history(_nano(tmp_path))
    assert members_on(h, "2026-08-30") is None                 # before the first list
    assert members_on(h, "2026-09-15") == {"N1", "N2"}
    # The 30 Sep close signals October's book, so it already uses the new list.
    assert members_on(h, "2026-09-30") == {"N2", "N3"}


def test_combined_is_the_union_from_the_first_date_both_answer(tmp_path):
    h750 = {"schema_version": 1, "baseline": None, "changes": []}
    h750, _ = record_snapshot(h750, "2026-01-02", ["AAA", "BBB"])
    h750, _ = record_snapshot(h750, "2026-09-20", ["AAA", "CCC"])
    h = sy.combined_history(h750, sy.nano_history(_nano(tmp_path)))
    assert h["baseline"]["date"] == "2026-08-31"
    assert members_on(h, "2026-09-10") == {"AAA", "BBB", "N1", "N2"}
    assert members_on(h, "2026-09-25") == {"AAA", "CCC", "N1", "N2"}
    assert members_on(h, "2026-09-30") == {"AAA", "CCC", "N2", "N3"}
    assert sy.combined_history(None, h) is None


def test_each_system_has_its_own_ledger_and_start():
    assert sy.inception("750") == pd.Period("2026-01", freq="M")
    assert sy.inception("nano") == sy.inception("combined") == pd.Period("2026-10", freq="M")
    assert len({sy.ledger_path(s) for s in ("750", "nano", "combined")}) == 3


def test_a_ledger_freezes_nothing_before_its_own_inception():
    ledger = empty_ledger(pd.Period("2026-10", freq="M"))
    assert ledger_inception(ledger) == pd.Period("2026-10", freq="M")
    idx = pd.bdate_range("2026-09-01", "2026-11-03")
    curve = pd.Series(range(100, 100 + len(idx)), index=idx, dtype=float)
    out, added, _ = finalize_months(ledger, curve, curve, "fp", as_of=idx[-1])
    assert added == ["2026-10"]                                # September is before inception
    assert out["inception"] == "2026-10"


def test_each_backtest_starts_at_canonical_inception_and_grows_monthly():
    from src.engine.systems import backtest_months
    assert backtest_months("750", "2026-01-31") == 1
    assert backtest_months("750", "2026-09-25") == 8
    assert backtest_months("nano", "2026-09-30") == 0        # September still running
    assert backtest_months("nano", "2026-10-01") == 1        # September complete
    assert backtest_months("combined", "2026-11-02") == 2
    assert backtest_months("nano", "2027-09-01") == 12
