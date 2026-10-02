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
    ev = rc.rights_events(actions, ss, check=screener)
    assert len(ev) == 1
    row = ev.iloc[0]
    assert row["ex_date"] == ex and row["cum_close"] == 2516.8 and row["issue_price"] == 1800
    assert row["face_value_assumed"]
    assert row["check_gap"] < 1e-4


def test_a_known_face_value_is_used():
    ss, _, actions, _ = _adanient()
    ev = rc.rights_events(actions, ss, face_values={"ADANIENT": 10.0})
    assert ev.iloc[0]["issue_price"] == 1809 and not ev.iloc[0]["face_value_assumed"]


def test_apply_factors_scales_only_the_closes_before_the_ex_date():
    ss, screener, actions, ex = _adanient()
    adj = rc.apply_factors(ss, rc.rights_events(actions, ss))
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
    assert "ADANIENT" in text and "Rights issues adjusted | 1" in text
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
