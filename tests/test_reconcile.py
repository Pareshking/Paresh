"""SS, Screener and NSE checking each other (src/engine/reconcile.py)."""
import numpy as np
import pandas as pd
import pytest

from src.engine import reconcile as rc

DAYS = pd.bdate_range("2025-11-03", periods=20)


# ── Rights terms and factor ──────────────────────────────────────────────────

@pytest.mark.parametrize("purpose,expected", [
    ("RIGHTS 3:25@PRM RS 1799", (3, 25, 1799, True)),
    ("RIGHTS 1:4 @PRM RS 8/-", (1, 4, 8, True)),
    ("RIGHTS 1:4@PRM RS 5.35/-", (1, 4, 5.35, True)),
    ("RIGHTS 3:19 @PRM RS 18/-", (3, 19, 18, True)),
    ("RIGHTS 1:5 @ RS 120/-", (1, 5, 120, False)),
])
def test_rights_terms_are_read_from_nse_purpose_text(purpose, expected):
    t = rc.parse_rights(purpose)
    assert (t["new"], t["held"], t["price"], t["premium"]) == expected


@pytest.mark.parametrize("purpose", ["DIVIDEND - RS 5 PER SHARE", "BONUS 1:1", "", None])
def test_anything_else_is_not_a_rights_issue(purpose):
    assert rc.parse_rights(purpose) is None


def test_adanient_factor_matches_screeners_own_adjustment():
    # 3 new for 25 at Rs 1 + 1799 premium, cum close Rs 2,516.80 (2025-11-14).
    assert rc.rights_factor(3, 25, 1800, 2516.8) == pytest.approx(0.96948, abs=1e-5)


def test_an_issue_at_or_above_the_market_price_changes_nothing():
    assert rc.rights_factor(1, 4, 120, 100) == 1.0


def _adanient():
    ex = pd.Timestamp("2025-11-17")
    raw = pd.Series(2516.8, index=DAYS)
    raw[DAYS >= ex] = 2440.0
    ss = pd.DataFrame({"ADANIENT": raw})
    screener = ss.copy()
    screener.loc[DAYS < ex, "ADANIENT"] *= 0.96948                 # Screener adjusts rights
    actions = pd.DataFrame({"symbol": ["ADANIENT"], "ex_date": [ex],
                            "purpose": ["RIGHTS 3:25@PRM RS 1799"]})
    return ss, screener, actions, ex


def test_rights_events_carry_the_factor_and_screeners_check():
    ss, screener, actions, ex = _adanient()
    ev = rc.rights_events(actions, ss, check=screener, raw=ss.copy())
    assert len(ev) == 1
    row = ev.iloc[0]
    assert row["ex_date"] == ex and row["cum_close"] == 2516.8 and row["issue_price"] == 1800
    assert row["face_value_assumed"]
    assert row["check_gap"] < 1e-4
    assert row["ss_basis"] == "raw" and row["apply"]


def test_ss_already_adjusted_is_left_alone():
    """Most rights issues: SS's ex-date move sits -log(factor) above NSE's raw one."""
    ss, screener, actions, ex = _adanient()
    raw = ss.copy()
    ev = rc.rights_events(actions, screener, raw=raw)            # Screener stands in for an adjusted SS
    assert ev.iloc[0]["ss_basis"] == "adjusted" and not ev.iloc[0]["apply"]
    res = rc.reconcile(screener, None, raw, actions)
    assert np.allclose(res.close["ADANIENT"], screener["ADANIENT"], rtol=1e-5)  # not adjusted twice
    assert res.votes.empty                                       # NSE brought to SS's basis


def test_ss_with_its_own_factor_is_kept_and_flagged():
    ss, _, actions, ex = _adanient()
    own = ss.copy()
    own.loc[DAYS < ex, "ADANIENT"] *= 0.90                       # SS used some other factor
    ev = rc.rights_events(actions, own, raw=ss)
    assert ev.iloc[0]["ss_basis"] == "own_factor" and not ev.iloc[0]["apply"]
    res = rc.reconcile(own, None, ss, actions)
    assert np.allclose(res.close["ADANIENT"], own["ADANIENT"], rtol=1e-5)
    assert res.votes.empty


def test_without_nse_the_basis_is_unknown_and_nothing_is_applied():
    ss, _, actions, _ = _adanient()
    ev = rc.rights_events(actions, ss)
    assert ev.iloc[0]["ss_basis"] == "unknown" and not ev.iloc[0]["apply"]


def test_the_cum_close_comes_from_nse_when_ss_is_already_scaled():
    ss, screener, actions, _ = _adanient()
    ev = rc.rights_events(actions, screener, raw=ss)
    assert ev.iloc[0]["cum_close"] == 2516.8


def test_a_known_face_value_is_used():
    ss, _, actions, _ = _adanient()
    ev = rc.rights_events(actions, ss, face_values={"ADANIENT": 10.0})
    assert ev.iloc[0]["issue_price"] == 1809 and not ev.iloc[0]["face_value_assumed"]


def test_apply_factors_scales_only_the_closes_before_the_ex_date():
    ss, screener, actions, ex = _adanient()
    adj = rc.apply_factors(ss, rc.rights_events(actions, ss, raw=ss))
    assert np.allclose(adj["ADANIENT"], screener["ADANIENT"], rtol=1e-5)
    assert (adj.loc[DAYS >= ex, "ADANIENT"] == ss.loc[DAYS >= ex, "ADANIENT"]).all()


# ── The vote ─────────────────────────────────────────────────────────────────

def _path(moves, start=100.0):
    return start * np.cumprod([1.0, *[1 + m for m in moves]])


def _three(ss_moves, scr_moves, nse_moves):
    idx = DAYS[:len(ss_moves) + 1]
    f = lambda m: pd.DataFrame({"X": _path(m)}, index=idx)  # noqa: E731
    return {"ss": f(ss_moves), "screener": f(scr_moves), "nse": f(nse_moves)}


def test_agreement_is_not_listed():
    assert rc.vote(_three([0.01, -0.02], [0.01, -0.02], [0.0101, -0.0199])).empty


def test_two_against_one_uses_the_majority_and_names_the_odd_source():
    v = rc.vote(_three([0.01, 0.10], [0.01, 0.02], [0.01, 0.0201]))
    assert len(v) == 1
    r = v.iloc[0]
    assert r["verdict"] == "majority" and r["odd"] == "ss"
    assert r["used"] == pytest.approx(0.02005)


def test_all_three_differ_nse_is_used_and_flagged():
    r = rc.vote(_three([0.05], [0.02], [-0.01])).iloc[0]
    assert r["verdict"] == "unresolved" and r["used"] == pytest.approx(-0.01)


def test_two_sources_disagreeing_nse_judges():
    s = _three([0.05], [0.02], [-0.01])
    del s["screener"]
    r = rc.vote(s).iloc[0]
    assert r["verdict"] == "judge" and r["used"] == pytest.approx(-0.01)


def test_a_move_never_spans_a_day_a_source_lacks():
    """SS skipping a day must not count the two-day move as one day's."""
    s = _three([0.02, 0.03], [0.02, 0.03], [0.02, 0.03])
    s["ss"] = s["ss"].drop(DAYS[1])
    assert rc.vote(s).empty


# ── The reconciled series ────────────────────────────────────────────────────

def test_reconcile_replaces_a_bad_ss_tick_and_keeps_ss_level():
    s = _three([0.01, 0.10, -0.0818, 0.01], [0.01, 0.0, 0.0, 0.01], [0.01, 0.0, 0.0, 0.01])
    res = rc.reconcile(s["ss"], s["screener"], s["nse"])
    assert np.allclose(res.close["X"].values, s["screener"]["X"].values, rtol=1e-3)
    assert res.summary()["ss_outvoted"] == 2


def test_a_session_ss_lacks_is_filled_once_not_twice():
    s = _three([0.02, 0.03, 0.01], [0.02, 0.03, 0.01], [0.02, 0.03, 0.01])
    ss = s["ss"].drop(DAYS[2])
    res = rc.reconcile(ss, s["screener"], s["nse"])
    assert np.allclose(res.close["X"].values, s["screener"]["X"].values)
    assert len(res.filled) == 2 and set(res.filled["source"]) == {"screener"}


def test_reconcile_adjusts_rights_and_raises_no_drift():
    ss, screener, actions, _ = _adanient()
    res = rc.reconcile(ss, screener, ss.copy(), actions)
    assert res.summary()["rights_applied"] == 1
    assert res.drifts.empty and res.votes.empty
    assert np.allclose(res.close["ADANIENT"], screener["ADANIENT"], rtol=1e-5)


def test_without_the_action_the_rights_gap_is_reported_as_a_drift():
    ss, screener, _, ex = _adanient()
    res = rc.reconcile(ss, screener, None)
    assert len(res.drifts) == 1
    assert res.drifts.iloc[0]["date"] == ex
    assert res.drifts.iloc[0]["shift"] == pytest.approx(0.96948 - 1, abs=1e-4)   # SS/Screener steps down


def test_the_report_writes_its_files(tmp_path):
    from scripts.reconcile_report import write_report

    ss, screener, actions, _ = _adanient()
    res = rc.reconcile(ss, screener, ss.copy(), actions)
    text = write_report(res, tmp_path, DAYS[0].date(), DAYS[-1].date(), [])
    assert "ADANIENT" in text and "Rights issues (SS already adjusted / we adjusted / check) | 1 (0 / 1 / 0)" in text
    for name in ("report.md", "summary.json", "rights.csv", "votes.csv", "drifts.csv", "filled.csv"):
        assert (tmp_path / name).exists()


def test_ss_days_already_on_the_adjusted_basis_are_outvoted():
    """Seen on ADANIENT: SS served some pre-ex days already rights-adjusted."""
    ss, screener, actions, ex = _adanient()
    nse = ss.copy()
    mixed = ss.copy()
    mixed.loc[DAYS[[3, 4]], "ADANIENT"] *= 0.96948
    res = rc.reconcile(mixed, screener, nse, actions)
    outvoted = res.votes[res.votes["odd"] == "ss"]
    assert set(outvoted["date"]) == {DAYS[3], DAYS[5]}            # into and out of the bad days
    assert np.allclose(res.close["ADANIENT"], screener["ADANIENT"], rtol=1e-5)
    assert res.drifts.empty


def test_the_drift_is_dated_on_the_step_not_beside_it():
    ss, screener, _, ex = _adanient()
    ss.loc[DAYS[2], "ADANIENT"] *= 0.96948                       # one stray day before the step
    assert rc.level_drifts(ss, screener).iloc[0]["date"] == ex


def test_a_shift_on_a_demerger_is_tagged_not_flagged():
    ss, screener, _, ex = _adanient()
    demerger = pd.DataFrame({"symbol": ["ADANIENT"], "ex_date": [ex], "purpose": ["DEMERGER"],
                             "kind": ["demerger"]})
    res = rc.reconcile(ss, screener, None, demerger)
    assert res.drifts.iloc[0]["action"] == "demerger"
    assert res.summary()["level_drifts"] == 0 and res.summary()["action_drifts"] == 1


def test_nse_raw_anchors_the_rights_check_for_a_stock_the_committed_set_lacks():
    ss, screener, actions, _ = _adanient()
    committed = pd.DataFrame({"OTHER": 1.0}, index=DAYS)
    res = rc.reconcile(screener, None, committed, actions, nse_raw=ss)   # SS already adjusted
    row = res.rights.iloc[0]
    assert row["ss_basis"] == "adjusted" and not row["apply"]
    assert np.allclose(res.close["ADANIENT"], screener["ADANIENT"], rtol=1e-5)


def test_the_face_value_is_inferred_from_the_factor_ss_applied():
    """TIL, 2026-03-23: 11:64 at a Rs 155 premium; SS's factor fits a Rs 10 face value."""
    ex = pd.Timestamp("2025-11-17")
    raw = pd.DataFrame({"TIL": np.where(DAYS < ex, 187.24, 170.0)}, index=DAYS)
    f10 = rc.rights_factor(11, 64, 165, 187.24)
    ss = raw.copy()
    ss.loc[DAYS < ex, "TIL"] *= f10
    actions = pd.DataFrame({"symbol": ["TIL"], "ex_date": [ex], "purpose": ["RIGHTS 11:64 @PRM RS 155"]})
    row = rc.rights_events(actions, ss, raw=raw).iloc[0]
    assert row["face_value"] == 10 and not row["face_value_assumed"]
    assert row["ss_basis"] == "adjusted" and row["factor"] == pytest.approx(0.9826, abs=1e-4)


def test_a_gross_two_source_disagreement_uses_the_smaller_move():
    """SS divided TVSHLTD by 47 for a preference-share bonus (Sep 2026); no NSE price."""
    s = _three([0.01, 46.0, 0.01], [0.01, 0.015, 0.01], [0.0, 0.0, 0.0])
    del s["nse"]
    res = rc.reconcile(s["ss"], s["screener"], None)
    r = res.votes.iloc[0]
    assert r["verdict"] == "unresolved" and r["used"] == pytest.approx(0.015)
    assert res.close["X"].iloc[-1] / res.close["X"].iloc[0] < 1.1


def test_nse_is_completed_from_its_raw_daily_files():
    from scripts.reconcile_report import complete_nse

    days = DAYS[:6]
    rows = [{"date": d, "mkt": "N", "series": "EQ", "symbol": "NEW", "close": c, "prev_close": c,
             "high": c, "low": c, "volume": 1.0, "value": c}
            for d, c in zip(days, [100, 101, 102, 51.5, 52, 53])]
    split = pd.DataFrame([{"symbol": "NEW", "series": "EQ", "kind": "split", "ex_date": days[3],
                           "purpose": "FACE VALUE SPLIT FROM RS 10 TO RS 5", "price_factor": 0.5}])
    committed = pd.DataFrame({"OLD": 1.0}, index=days)
    out = complete_nse(committed, ["OLD", "NEW"], pd.DataFrame(rows), split, days[0], days[-1])
    assert list(out.columns) == ["OLD", "NEW"]
    assert out["NEW"].iloc[0] == pytest.approx(50.0)               # split-adjusted, like the committed set
