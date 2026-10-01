"""The Track Record's price basis: NSE's closes as published, not Yahoo's restated ones.

Yahoo folds every later dividend into earlier prices and corrects history after
the fact, so a month rebuilt on it ranks on data that did not exist at the time.
NSE's closes never change. These tests pin the pieces that turn them into the
engine's input, and the committed file the record is struck on.
"""
from __future__ import annotations

import datetime as dt
import json

import numpy as np
import pandas as pd
import pytest

import src.engine.pipeline  # noqa: F401  (pipeline first: it and momentum import each other)
from src.engine import systems
from src.engine.membership import load_history, members_on
from src.engine.track_record import TRACK_RECORD_CONFIG, config_fingerprint
from src.loaders import nse_history as nh
from src.loaders import nse_prices as npx

IDX = pd.bdate_range("2025-01-01", "2026-03-31")   # a year of formation window plus a quarter


def _closes(**cols):
    return pd.DataFrame({k: v for k, v in cols.items()}, index=IDX)


def _flat(level, n=len(IDX)):
    return np.full(n, float(level))


# ── renames and corrections ──────────────────────────────────────────────────

def test_a_renamed_stock_is_one_series_under_its_new_symbol():
    old = np.r_[_flat(100, 30), np.full(len(IDX) - 30, np.nan)]
    new = np.r_[np.full(30, np.nan), _flat(101, len(IDX) - 30)]
    out = npx.chain_symbols(_closes(OLD=old, NEW=new), {"OLD": {"new_symbol": "NEW"}})
    assert list(out.columns) == ["NEW"] and out["NEW"].notna().all()
    assert out["NEW"].iloc[0] == 100 and out["NEW"].iloc[-1] == 101


def test_a_symbol_with_no_new_series_is_renamed_whole():
    out = npx.chain_symbols(_closes(OLD=_flat(50)), {"OLD": {"new_symbol": "NEW"}})
    assert list(out.columns) == ["NEW"]


def test_a_correction_scales_only_the_closes_before_its_date():
    c = npx.correct(_closes(AAA=_flat(100)),
                    [{"symbol": "AAA", "before": "2026-02-02", "factor": 0.2}])
    assert c["AAA"][c.index < "2026-02-02"].eq(20).all()
    assert c["AAA"][c.index >= "2026-02-02"].eq(100).all()


# ── adjusting ────────────────────────────────────────────────────────────────

def _split_inputs():
    """SPLT halves on 2026-02-16 (price 100 -> 50) and the action is listed twice, as NSE does."""
    at = IDX.get_loc(pd.Timestamp("2026-02-16"))
    px = np.r_[_flat(100, at), _flat(50, len(IDX) - at)]
    closes = _closes(SPLT=px, FLAT=_flat(10))
    row = {"symbol": "SPLT", "series": "EQ", "kind": "split", "purpose": "FV SPLIT 10 TO 5",
           "ex_date": pd.Timestamp("2026-02-16"), "price_factor": 0.5}
    return closes, pd.DataFrame([row, {**row, "series": "BE"}])


def test_a_split_that_the_price_confirms_is_applied_once():
    closes, actions = _split_inputs()
    out, rep = npx.adjusted_close(closes, nh.dedupe_actions(actions.assign(
        record_date=pd.NaT, bc_start=pd.NaT, bc_end=pd.NaT)), ["SPLT", "FLAT"])
    assert out["SPLT"].nunique() == 1 and float(out["SPLT"].iloc[0]) == 50.0
    assert float(out["FLAT"].iloc[0]) == 10.0
    assert rep["corporate_action_steps"] == 1


def test_symbols_nse_does_not_carry_are_reported_not_invented():
    closes, actions = _split_inputs()
    out, rep = npx.adjusted_close(closes, actions, ["SPLT", "MISSING"])
    assert "MISSING" not in out.columns and rep["unpriced"] == ["MISSING"]


# ── the frame the engine runs on ─────────────────────────────────────────────

def _write(tmp_path, closes, notes=None):
    d = tmp_path / "nse"
    d.mkdir()
    closes.astype("float32").to_parquet(d / "closes.parquet")
    pd.DataFrame(columns=npx.ACTION_COLS).to_parquet(d / "actions.parquet")
    (d / "notes.json").write_text(json.dumps(notes or {}))
    return d


def _other(idx, **cols):
    return pd.DataFrame({k: np.asarray(v, dtype=float) for k, v in cols.items()}, index=idx)


def test_a_caller_can_pin_the_frame_to_the_other_sources_end(tmp_path):
    """Callers that fixed their month count against the other source ask for the same end."""
    d = _write(tmp_path, _closes(AAA=_flat(100)))
    other = _other(IDX[:-5], AAA=_flat(90, len(IDX) - 5))
    frame, rep = npx.basis_frame(other, None, months=1, directory=d, until=other.index[-1], screener=None)
    assert frame.index[-1] == IDX[-6] and rep["used"]
    assert float(frame["AAA"].iloc[-1]) == 100.0           # NSE's level, not the other source's


def test_sessions_after_the_file_are_carried_forward_on_the_other_sources_moves(tmp_path):
    d = _write(tmp_path, _closes(AAA=_flat(100)).iloc[:-5])
    other = _other(IDX, AAA=np.linspace(90, 99, len(IDX)))
    frame, _ = npx.basis_frame(other, None, months=1, directory=d, screener=None)
    assert frame.index[-1] == IDX[-1] and len(frame) == len(IDX)
    ratio = float(other["AAA"].iloc[-1] / other["AAA"].iloc[-6])
    assert float(frame["AAA"].iloc[-1]) == pytest.approx(100 * ratio, rel=1e-5)


def test_a_name_nse_lacks_comes_from_the_other_source_and_is_listed(tmp_path):
    d = _write(tmp_path, _closes(AAA=_flat(100)))
    other = _other(IDX, AAA=_flat(90, len(IDX)), REIT=_flat(300, len(IDX)))
    frame, rep = npx.basis_frame(other, None, months=1, directory=d, screener=None)
    assert float(frame["REIT"].iloc[0]) == 300.0 and rep["other_source_names"] == ["REIT"]


def test_a_file_too_short_for_the_study_is_refused_so_the_caller_keeps_its_own(tmp_path):
    d = _write(tmp_path, _closes(AAA=_flat(100)))
    frame, rep = npx.basis_frame(_other(IDX, AAA=_flat(90, len(IDX))), None, months=24, directory=d, screener=None)
    assert frame is None and rep["used"] is False and "needs" in rep["why"]


def test_no_committed_file_means_no_nse_basis(tmp_path):
    frame, rep = npx.basis_frame(_other(IDX, AAA=_flat(90, len(IDX))), None, months=1,
                                 directory=tmp_path / "absent")
    assert frame is None and rep["used"] is False


# ── the daily bundles ────────────────────────────────────────────────────────

def test_weekdays_skip_weekends():
    days = nh.weekdays(dt.date(2026, 2, 6), dt.date(2026, 2, 10))
    assert days == [dt.date(2026, 2, 6), dt.date(2026, 2, 9), dt.date(2026, 2, 10)]


def test_a_bonus_listed_every_day_and_under_two_series_is_one_action():
    """HDFCBANK's 1:1 bonus sat in 143 daily files under EQ and BE: 3.6e-12 when multiplied."""
    row = {"symbol": "HDFCBANK", "series": "EQ", "purpose": "BONUS 1:1", "kind": "bonus",
           "ex_date": pd.Timestamp("2025-08-26"), "record_date": pd.Timestamp("2025-08-26"),
           "bc_start": pd.Timestamp("2025-08-20"), "bc_end": pd.Timestamp("2025-08-26"),
           "price_factor": 0.5}
    a = pd.DataFrame([{**row, "date": pd.Timestamp("2025-08-01") + pd.Timedelta(days=i), "series": s}
                      for i in range(30) for s in ("EQ", "BE")])
    assert len(nh.dedupe_actions(a.drop(columns="date"))) == 1


def test_a_special_weekend_session_is_read_when_it_is_named(tmp_path):
    sat = dt.date(2025, 2, 1)
    p = nh.KEEP
    pd.DataFrame([[pd.Timestamp(sat), "CM", "EQ", "AAA", 10.0, 9.0, 11.0, 9.0, 1, 1.0]],
                 columns=p).to_parquet(tmp_path / f"prices_{sat.isoformat()}.parquet")
    without, _, _ = nh.read_cache(tmp_path, dt.date(2025, 1, 31), dt.date(2025, 2, 3))
    with_it, _, _ = nh.read_cache(tmp_path, dt.date(2025, 1, 31), dt.date(2025, 2, 3), [sat])
    assert without.empty and len(with_it) == 1


# ── what is committed ────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def committed():
    data = npx.load()
    assert data is not None, "data/nse_prices is missing"
    return data


def test_the_four_names_the_index_absorbed_have_nse_prices(committed):
    out, rep = npx.adjusted_close(committed["closes"], committed["actions"],
                                  ["CIGNITITEC", "GSPL", "GUJGASLTD", "JBCHEPHARM"],
                                  notes=committed["notes"])
    assert rep["unpriced"] == []
    for s in out.columns:
        assert out[s].dropna().iloc[-1] > 0 and out[s].notna().sum() > 300


def test_every_name_the_membership_record_lists_is_priced_but_the_reits(committed):
    h = load_history()
    names = set()
    for d in ["2025-12-31", "2026-01-30", "2026-03-30", "2026-06-30", "2026-09-30"]:
        names |= set(members_on(h, d, canonical=True))
    out, rep = npx.adjusted_close(committed["closes"], committed["actions"], sorted(names),
                                  notes=committed["notes"])
    assert set(rep["unpriced"]) <= {"BAGMANE", "BIRET", "EMBASSY"}, rep["unpriced"]


def test_no_unexplained_price_jump_is_left_in_a_name_the_record_can_hold(committed):
    """A close that halves or doubles overnight is a missed split, not a market move."""
    h = load_history()
    names = set()
    for d in ["2025-12-31", "2026-03-30", "2026-09-30"]:
        names |= set(members_on(h, d, canonical=True))
    out, _ = npx.adjusted_close(committed["closes"], committed["actions"], sorted(names),
                                notes=committed["notes"])
    moves = out.astype(float).pct_change(fill_method=None).stack()
    big = moves[(moves < -0.45) | (moves > 0.80)]
    assert big.empty, big


def test_shriramfin_split_is_corrected_where_nses_file_missed_it(committed):
    out, _ = npx.adjusted_close(committed["closes"], committed["actions"], ["SHRIRAMFIN"],
                                notes=committed["notes"])
    s = out["SHRIRAMFIN"]
    jump = float(s["2025-01-10"] / s[:"2025-01-09"].iloc[-1])
    assert 0.85 < jump < 1.15


def test_every_rename_names_its_evidence_and_leaves_one_series(committed):
    notes = committed["notes"]
    assert len(notes["renames"]) >= 20
    for old, r in notes["renames"].items():
        assert r["new_symbol"] and len(r["evidence"]) > 20, old
    out, _ = npx.adjusted_close(committed["closes"], committed["actions"],
                                [r["new_symbol"] for r in notes["renames"].values()],
                                notes=committed["notes"])
    assert not (set(notes["renames"]) & set(out.columns))
    ts = out["TSFINV"].dropna()
    assert ts.index[0] < pd.Timestamp("2025-01-01")              # SUNDARMHLD's past, under its new name
    assert float(ts["2025-10-16"] / ts[:"2025-10-15"].iloc[-1]) == pytest.approx(0.94, abs=0.05)


def test_the_special_sessions_nse_held_are_in_the_file(committed):
    for d in committed["notes"]["special_sessions"]:
        assert pd.Timestamp(d) in committed["closes"].index, d


# ── the record's basis is part of its identity ───────────────────────────────

def test_the_price_basis_is_in_the_config_fingerprint():
    assert TRACK_RECORD_CONFIG["prices"] == "screener_primary"
    yahoo = {**TRACK_RECORD_CONFIG, "prices": "yahoo_adjusted"}
    assert config_fingerprint(**yahoo) != config_fingerprint(**TRACK_RECORD_CONFIG)


def test_the_committed_ledger_is_one_basis_one_config_and_says_so():
    led = json.loads((systems.ledger_path("750")).read_text())
    assert led["price_basis"] == "screener_primary"
    assert {m["config"] for m in led["months"].values()} == {config_fingerprint(**TRACK_RECORD_CONFIG)}
    assert led["rebuilds"][-1]["prices"] == "screener_primary"
    assert led["rebuilds"][-1]["former_members_unpriceable"] == []


# ── reading the sessions from R2 ─────────────────────────────────────────────

class _FakeR2:
    """Just enough of R2Archive/R2DatasetReader for read_r2."""

    def __init__(self, days, bad=()):
        self.days, self.bad = days, set(bad)
        self.archive = self

    def list_keys(self, prefix):
        if "prices_daily" in prefix:
            return [f"{prefix}{d}/current.json" for d in self.days]
        return [f"{prefix}{self.days[0]}/current.json"]

    def resolve_current(self, dataset, *, as_of):
        return (dataset, as_of)

    def read_parquet(self, ref):
        dataset, d = ref
        if d in self.bad:
            raise OSError("boom")
        if dataset == nh.R2_PRICES:
            return pd.DataFrame([[pd.Timestamp(d), "CM", s, "AAA", 10.0, 9.0, 11.0, 9.0, 1, 1.0]
                                 for s in ("EQ", "SM")], columns=nh.KEEP)
        return pd.DataFrame({"date": [pd.Timestamp(d)], "symbol": ["AAA"], "ex_date": [pd.Timestamp("2026-02-02")],
                             "purpose": ["BONUS 1:1"], "series": ["EQ"]})


def test_sessions_are_read_from_r2_with_eq_be_rows_only_and_actions_classified():
    fake = _FakeR2(["2026-02-02", "2026-02-03"])
    p, a, bad = nh.read_r2(dt.date(2026, 2, 1), dt.date(2026, 2, 28), reader=fake)
    assert bad == [] and set(p["series"]) == {"EQ"} and len(p) == 2
    assert a["kind"].iloc[0] == "bonus" and a["price_factor"].iloc[0] == pytest.approx(0.5)


def test_an_unreadable_r2_day_is_reported_not_skipped_silently():
    fake = _FakeR2(["2026-02-02", "2026-02-03"], bad=["2026-02-03"])
    p, _, bad = nh.read_r2(dt.date(2026, 2, 1), dt.date(2026, 2, 28), reader=fake)
    assert len(p) == 1 and bad and bad[0].startswith("2026-02-03")


# ── a month closes the day NSE's first session of the next one is on file ────

def test_the_frame_runs_to_nses_last_session_unless_a_caller_pins_it(tmp_path):
    d = _write(tmp_path, _closes(AAA=_flat(100)))
    other = _other(IDX[:-3], AAA=_flat(90, len(IDX) - 3))        # the other source is 3 sessions behind
    ahead, _ = npx.basis_frame(other, None, months=1, directory=d, screener=None)
    pinned, _ = npx.basis_frame(other, None, months=1, directory=d, until=other.index[-1], screener=None)
    assert ahead.index[-1] == IDX[-1] and pinned.index[-1] == IDX[-4]


def test_the_record_script_counts_months_from_the_nse_frame_not_the_other_source():
    import re
    from pathlib import Path
    src = (Path(__file__).resolve().parents[1] / "scripts" / "update_track_record.py").read_text()
    assert re.search(r"as_of = pd\.Timestamp\(nse\.index\[-1\]\)\s+months = months_to_cover\(as_of, start\)", src)


def test_the_monthly_job_tries_on_the_first_working_day():
    from pathlib import Path
    wf = (Path(__file__).resolve().parents[1] / ".github" / "workflows" / "monthly_track_record.yml").read_text()
    assert "- cron: '0 19 1-5 * *'" in wf and "--verify-r2" in wf


# ── Screener first, NSE only where Screener has none ─────────────────────────

def _store(**series):
    cols = pd.MultiIndex.from_tuples([(k, f) for k in series for f in ("Close", "Volume")])
    idx = sorted({d for v in series.values() for d in v.index})
    df = pd.DataFrame(index=pd.DatetimeIndex(idx), columns=cols, dtype=float)
    for k, v in series.items():
        df[(k, "Close")] = v
        df[(k, "Volume")] = 1.0
    return df


def test_screener_closes_win_wherever_screener_has_one():
    base = pd.DataFrame({"AAA": _flat(100)}, index=IDX)
    scr = _store(AAA=pd.Series(102.0, index=IDX))
    out, rep = npx.blend_screener(base, scr)
    assert rep["screener"] and (out["AAA"] == 102.0).all()
    assert rep["share_of_cells_from_screener"] == 1.0


def test_dates_screener_lacks_are_nse_scaled_to_screeners_level_with_no_step_at_the_seam():
    base = pd.DataFrame({"AAA": np.linspace(100, 130, len(IDX))}, index=IDX)
    sparse = pd.Series(base["AAA"].to_numpy() * 1.02, index=IDX).iloc[len(IDX) // 2:]   # Screener holds only the later half
    out, _ = npx.blend_screener(base, _store(AAA=sparse))
    assert out["AAA"].iloc[-1] == pytest.approx(sparse.iloc[-1], rel=1e-5)
    early = out["AAA"].iloc[: len(IDX) // 2]
    assert (early / base["AAA"].iloc[: len(IDX) // 2]).round(4).eq(1.02).all()          # NSE's shape on Screener's level
    assert abs(out["AAA"].iloc[len(IDX) // 2] / out["AAA"].iloc[len(IDX) // 2 - 1] - 1) < 0.01


def test_a_stock_screener_never_held_stays_on_nse_and_one_only_screener_holds_is_added():
    base = pd.DataFrame({"AAA": _flat(100), "BBB": _flat(50)}, index=IDX)
    scr = _store(AAA=pd.Series(101.0, index=IDX), REIT=pd.Series(300.0, index=IDX))
    out, rep = npx.blend_screener(base, scr, extra=["REIT", "AAA"])
    assert (out["BBB"] == 50.0).all() and rep["base_only_names"] == ["BBB"]
    assert (out["REIT"] == 300.0).all() and rep["screener_only_names"] == ["REIT"]


def test_no_screener_store_leaves_the_nse_frame_untouched():
    base = pd.DataFrame({"AAA": _flat(100)}, index=IDX)
    out, rep = npx.blend_screener(base, None)
    assert out is base and rep == {"screener": False}


def test_basis_frame_reports_the_screener_basis_only_when_screener_was_used(tmp_path):
    d = _write(tmp_path, _closes(AAA=_flat(100)))
    other = _other(IDX, AAA=_flat(90, len(IDX)))
    _, none = npx.basis_frame(other, None, months=1, directory=d, screener=None)
    _, some = npx.basis_frame(other, None, months=1, directory=d,
                              screener=_store(AAA=pd.Series(101.0, index=IDX)))
    assert none["basis"] == npx.BASIS and some["basis"] == npx.BASIS_SCREENER
