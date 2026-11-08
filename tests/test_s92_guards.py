"""S92 (owner, 7 Nov 2026): two guards from S89.

(a) The month freeze refuses to strike a month while its replay disagrees with a
    frozen month the owner has not accepted (October 2026 was struck on 3 Nov
    with September drifting, on a Screener store carrying BSE closes).
(b) The Screener sync does not publish a store the three-source vote outvotes
    on more than SCREENER_OUTVOTE_LIMIT stocks (43 on each night 28 Oct-5 Nov).
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from src.engine import reconcile as rc
from src.engine.parity_audit import compare_monthly_ledger, freeze_refusal

ROOT = Path(__file__).resolve().parents[1]


# ── (a) the freeze decision ──────────────────────────────────────────────────

def _curve(jan: float, feb: float) -> pd.Series:
    """An equity curve with these January and February returns, into March."""
    days = pd.bdate_range("2026-01-01", "2026-03-03")
    level = pd.Series(1 + jan, index=days)
    level[days > "2026-01-31"] = (1 + jan) * (1 + feb)
    level.iloc[0] = 1.0                       # the base point January is measured from
    return level


LEDGER = {"inception": "2026-01", "months": {"2026-01": {"strategy": 0.02, "benchmark": 0.01}}}


def test_a_clean_replay_lets_the_freeze_strike():
    rep = compare_monthly_ledger(LEDGER, _curve(0.02, 0.03), _curve(0.01, 0.0))
    assert freeze_refusal(rep) is None


def test_an_unaccepted_drift_refuses_and_names_the_month():
    rep = compare_monthly_ledger(LEDGER, _curve(0.025, 0.03), _curve(0.01, 0.0))
    why = freeze_refusal(rep)
    assert why is not None and "\n" not in why
    assert "2026-01" in why and "strategy +0.500 pp" in why


def test_an_accepted_drift_does_not_block():
    accepted = {"2026-01": {"strategy": {"stored": 0.02, "replay": 0.025}}}
    rep = compare_monthly_ledger(LEDGER, _curve(0.025, 0.03), _curve(0.01, 0.0), accepted=accepted)
    assert rep["rows"][0]["status"] == "accepted"
    assert freeze_refusal(rep) is None


def test_a_drift_beyond_the_accepted_replay_blocks_again():
    accepted = {"2026-01": {"strategy": {"stored": 0.02, "replay": 0.025}}}
    rep = compare_monthly_ledger(LEDGER, _curve(0.03, 0.03), _curve(0.01, 0.0), accepted=accepted)
    assert "2026-01" in (freeze_refusal(rep) or "")


def test_a_month_the_replay_cannot_cover_blocks():
    ledger = {"months": {"2025-12": {"strategy": 0.01}, **LEDGER["months"]}}
    rep = compare_monthly_ledger(ledger, _curve(0.02, 0.03), _curve(0.01, 0.0))
    assert "2025-12 (missing recomputed period)" in (freeze_refusal(rep) or "")


# The script end to end, its data sources replaced: refusal writes nothing.

def _updater():
    spec = importlib.util.spec_from_file_location("update_track_record_s92",
                                                  ROOT / "scripts" / "update_track_record.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run_freeze(monkeypatch, tmp_path, jan_replay: float, accepted: dict, *extra: str):
    mod = _updater()
    days = pd.bdate_range("2025-01-01", "2026-03-03")
    closes = pd.DataFrame({"AAA": np.linspace(100, 120, len(days))}, index=days)
    store = pd.concat({"AAA": closes[["AAA"]].rename(columns={"AAA": "Close"})}, axis=1)
    info = {"basis": mod.nse_prices.BASIS_SCREENER, "screener": False, "symbols_priced": 1,
            "symbols_wanted": 1, "last_session_on_file": str(days[-1].date()),
            "frame_last_session": str(days[-1].date()), "other_source_names": [],
            "other_source_history": []}
    monkeypatch.setattr(mod, "fetch_indices_data", lambda _i: pd.DataFrame({"Symbol": ["AAA"]}))
    monkeypatch.setattr(mod.nse_prices, "screener_store", lambda: store)
    monkeypatch.setattr(mod, "fetch_benchmark_history", lambda period: closes["AAA"])
    monkeypatch.setattr(mod.systems, "membership_for", lambda _s: None)
    monkeypatch.setattr(mod.nse_prices, "basis_frame", lambda frame, *a, **k: (frame, info))
    monkeypatch.setattr(mod.former_members, "with_former_members", lambda frame, _m: frame)
    monkeypatch.setattr(mod.former_members, "unavailable", lambda: [])
    monkeypatch.setattr(mod, "record_sector_map", lambda _c: {})
    monkeypatch.setattr(mod, "load_accepted_drift", lambda **_kw: accepted)
    monkeypatch.setattr(mod, "run_backtest", lambda *a, **k: {
        "stats": {}, "equity_curve": _curve(jan_replay, 0.03), "benchmark": _curve(0.01, 0.0)})
    ledger = tmp_path / "track_record.json"
    ledger.write_text(json.dumps(LEDGER), encoding="utf-8")
    before = ledger.read_text(encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["update_track_record.py", "--ledger", str(ledger), *extra])
    code = mod.main()
    return code, before, json.loads(ledger.read_text(encoding="utf-8"))


def test_the_freeze_refuses_on_an_unaccepted_drift_and_writes_nothing(monkeypatch, tmp_path, capsys):
    code, before, after = _run_freeze(monkeypatch, tmp_path, 0.025, {})
    assert code == 1
    assert after == json.loads(before)                   # February not struck
    out = capsys.readouterr().out
    refusal = [line for line in out.splitlines() if line.startswith("✗ refusing to freeze")]
    assert len(refusal) == 1 and "2026-02" in refusal[0] and "2026-01" in refusal[0]


def test_the_freeze_strikes_when_the_drift_is_accepted(monkeypatch, tmp_path):
    accepted = {"2026-01": {"strategy": {"stored": 0.02, "replay": 0.025}}}
    code, _before, after = _run_freeze(monkeypatch, tmp_path, 0.025, accepted)
    assert code == 0
    assert after["months"]["2026-02"]["strategy"] == pytest.approx(0.03)
    assert after["months"]["2026-01"]["strategy"] == 0.02   # never rewritten


def test_the_freeze_strikes_on_a_clean_replay(monkeypatch, tmp_path):
    code, _before, after = _run_freeze(monkeypatch, tmp_path, 0.02, {})
    assert code == 0 and "2026-02" in after["months"]


def test_the_monthly_workflow_lets_the_refusal_fail_the_job():
    wf = yaml.safe_load((ROOT / ".github" / "workflows" / "monthly_track_record.yml").read_text())
    steps = wf["jobs"]["freeze"]["steps"]
    names = [s.get("name") for s in steps]
    freeze = steps[names.index("Freeze newly closed months")]
    assert freeze["run"].strip() == "python scripts/update_track_record.py"   # no `|| echo`
    later = steps[names.index("Freeze newly closed months") + 1:]
    assert all("if" not in s for s in later)   # a refusal skips the other freezes and the commit


# ── (b) the Screener publication decision ────────────────────────────────────

NAMES = [f"S{i:02d}" for i in range(30)]


@pytest.mark.parametrize("count,blocked", [
    (0, False),
    (rc.SCREENER_OUTVOTE_LIMIT - 1, False),
    (rc.SCREENER_OUTVOTE_LIMIT, False),           # "more than" the limit refuses
    (rc.SCREENER_OUTVOTE_LIMIT + 1, True),
    (43, True),                                    # the 28 Oct - 5 Nov nights
])
def test_publish_refusal_at_the_threshold(count, blocked):
    names = NAMES[:count] if count <= len(NAMES) else [f"X{i}" for i in range(count)]
    why = rc.publish_refusal(names)
    assert (why is not None) is blocked
    if blocked:
        assert all(n in why for n in names) and str(count) in why


def test_the_default_threshold_is_ten():
    assert rc.SCREENER_OUTVOTE_LIMIT == 10
    assert rc.outvote_limit({}) == 10
    assert rc.outvote_limit({"SCREENER_OUTVOTE_LIMIT": ""}) == 10   # an unset repo variable


def test_the_environment_overrides_the_threshold():
    assert rc.outvote_limit({"SCREENER_OUTVOTE_LIMIT": "3"}) == 3
    assert rc.publish_refusal(NAMES[:4], rc.outvote_limit({"SCREENER_OUTVOTE_LIMIT": "3"}))
    with pytest.raises(ValueError):
        rc.outvote_limit({"SCREENER_OUTVOTE_LIMIT": "ten"})
    with pytest.raises(ValueError):
        rc.outvote_limit({"SCREENER_OUTVOTE_LIMIT": "-1"})


def _sources(bad: int, symbols: int = 15):
    """SS and NSE agree; Screener's closes are off by 2% on day 5 for `bad` stocks."""
    days = pd.bdate_range("2026-10-01", periods=10)
    syms = NAMES[:symbols]
    base = pd.DataFrame({s: 100 * (1.01 ** np.arange(len(days))) for s in syms}, index=days)
    scr = base.copy()
    for s in syms[:bad]:
        scr.loc[days[5]:, s] *= 1.02          # a level step: one outvoted session each
    return base, scr, base.copy()


@pytest.mark.parametrize("bad,blocked", [(0, False), (9, False), (10, False), (11, True)])
def test_the_vote_counts_screener_outvotes_per_stock(bad, blocked):
    ss, scr, nse = _sources(bad)
    names = rc.outvoted_names(rc.reconcile(ss, scr, nse).votes, "screener")
    assert names == NAMES[:bad]
    assert (rc.publish_refusal(names) is not None) is blocked


def test_outvotes_of_another_source_or_before_the_window_do_not_count():
    votes = pd.DataFrame({
        "date": pd.to_datetime(["2026-10-01", "2026-11-05", "2026-11-05", "2026-11-05"]),
        "symbol": ["OLD", "SS1", "UNR", "NEW"],
        "verdict": ["majority", "majority", "unresolved", "majority"],
        "odd": ["screener", "ss", "", "screener"],
    })
    assert rc.outvoted_names(votes) == ["NEW", "OLD"]
    assert rc.outvoted_names(votes, since=pd.Timestamp("2026-11-01")) == ["NEW"]
    assert rc.outvoted_names(votes.iloc[0:0]) == []


def test_the_screener_sync_votes_before_both_publishes():
    wf = yaml.safe_load((ROOT / ".github" / "workflows" / "screener_sync.yml").read_text())
    steps = wf["jobs"]["screener"]["steps"]
    names = [s.get("name") for s in steps]
    vote = names.index("Three-source vote on the new store (SS, Screener, NSE)")
    release = names.index("Publish screener history")
    r2 = names.index("Publish validated Screener dataset to R2")
    assert vote < release < r2
    assert steps[vote]["id"] == "outvote_check"
    assert "scripts/check_screener_outvotes.py" in steps[vote]["run"]
    assert "steps.outvote_check.outcome != 'failure'" in steps[release]["if"]
    assert "if" not in steps[r2]      # runs only when every step before it succeeded


def _checker():
    spec = importlib.util.spec_from_file_location("check_screener_outvotes_s92",
                                                  ROOT / "scripts" / "check_screener_outvotes.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("bad,code", [(0, 0), (9, 0), (11, 1)])
def test_the_sync_check_exits_non_zero_and_names_the_stocks(monkeypatch, tmp_path, capsys, bad, code):
    mod = _checker()
    ss, scr, nse = _sources(bad)
    monkeypatch.delenv("SCREENER_OUTVOTE_LIMIT", raising=False)
    monkeypatch.setattr(mod.rr, "load_screener", lambda *_a: scr)
    monkeypatch.setattr(mod.rr, "load_ss", lambda *_a: ss)
    monkeypatch.setattr(mod.rr, "load_nse", lambda *_a: nse)
    monkeypatch.setattr(mod.rr, "read_r2", lambda *_a: None)
    monkeypatch.setattr(mod.rr, "load_actions", lambda *_a: None)
    assert mod.main(["--store", str(tmp_path / "s.parquet"), "--ss", str(tmp_path)]) == code
    out = capsys.readouterr().out
    if code:
        assert "::error::Not publishing the Screener store" in out
        assert all(n in out for n in NAMES[:bad])


def test_the_sync_check_does_not_hold_the_store_without_ss(monkeypatch, tmp_path, capsys):
    mod = _checker()
    _ss, scr, _nse = _sources(11)
    monkeypatch.setattr(mod.rr, "load_screener", lambda *_a: scr)
    assert mod.main(["--store", str(tmp_path / "s.parquet"), "--ss", str(tmp_path / "none")]) == 0
    assert "::warning::" in capsys.readouterr().out


def test_the_freeze_uses_the_per_month_fingerprint_function_correctly():
    """Audit, 8 Nov 2026: `fingerprint` became a function (forward-dated rules); the
    rebuild log stored the function itself (unwritable JSON) and the price-basis test
    compared strings with it (always False, so price_basis was always dropped)."""
    from pathlib import Path
    src = (Path(__file__).resolve().parents[1] / "scripts" / "update_track_record.py").read_text()
    assert '"config": fingerprint,' not in src
    assert "configs <= {fingerprint}" not in src
    assert 'fingerprint(pd.Period(k, freq="M"))' in src
