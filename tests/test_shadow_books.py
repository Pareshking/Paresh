"""The two shadow records of 19 Nov 2026 (owner: "Both, separately"; TODO S144).

Near-high 90% and Breadth + long lookback, beside the Recommendation, never
traded. The live records and the Recommendation must not move because of them.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from src.engine.extra_universe import SYSTEM_750
from src.engine.track_record import (
    LEDGER_PATH,
    SHADOWS,
    TRACK_RECORD_CONFIG,
    breadth_on,
    config_fingerprint,
    overlay_month,
)
from src.ui.views.track_record_view import comparison_frame

ROOT = Path(__file__).resolve().parents[1]


def _updater():
    spec = importlib.util.spec_from_file_location("update_track_record",
                                                  ROOT / "scripts" / "update_track_record.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_each_book_changes_only_its_own_settings():
    live = TRACK_RECORD_CONFIG
    changed = {k: {x for x in live if SHADOWS[k].config[x] != live[x]} for k in ("high90", "breadth_long")}
    assert changed == {"high90": {"high_pct"}, "breadth_long": {"high_pct", "config_weights"}}
    assert SHADOWS["high90"].config["high_pct"] == 0.90
    assert SHADOWS["breadth_long"].config["config_weights"] == [0.0, 0.10, 0.20, 0.30, 0.40]
    assert SHADOWS["breadth_long"].breadth_rule == (0.60, 0.50)
    assert SHADOWS["high90"].breadth_rule is None


def test_every_book_has_its_own_ledger_fingerprint_and_start():
    paths = {b.ledger_path for b in SHADOWS.values()}
    assert len(paths) == len(SHADOWS) and LEDGER_PATH not in paths
    assert all(p.name.startswith("track_record") for p in paths)       # the workflow's git add
    prints = {config_fingerprint(**b.config) for b in SHADOWS.values()}
    assert len(prints) == len(SHADOWS)
    assert config_fingerprint(**TRACK_RECORD_CONFIG) not in prints
    for key in ("high90", "breadth_long"):
        assert SHADOWS[key].inception == pd.Period("2026-12", freq="M")


def test_the_updater_picks_each_book_and_keeps_shadow_alone_as_the_recommendation():
    mod = _updater()
    assert mod.record_setup(SYSTEM_750, shadow=True)[3] == SHADOWS["recommendation"].config
    for key in ("high90", "breadth_long"):
        system, ledger, start, cfg = mod.record_setup(SYSTEM_750, shadow=key)
        assert (Path(ledger), start, cfg) == (SHADOWS[key].ledger_path, SHADOWS[key].inception,
                                              SHADOWS[key].config)
    with pytest.raises(SystemExit):
        mod.record_setup(SYSTEM_750, shadow="nope")


def _closes(above: int, below: int, days: int = 260):
    idx = pd.bdate_range("2026-01-01", periods=days)
    up = np.linspace(100, 150, days)
    down = np.linspace(150, 100, days)
    cols = {f"U{i}": up for i in range(above)} | {f"D{i}": down for i in range(below)}
    return pd.DataFrame(cols, index=idx)


def test_breadth_is_the_share_of_members_above_their_200_day_average():
    px = _closes(above=70, below=40)
    members = {"schema_version": 2, "index": "nifty_500",
               "baseline": {"date": "2025-12-31", "symbols": list(px.columns)}, "changes": [], "aliases": {}}
    got = breadth_on(px, members, px.index[-1])
    assert got == pytest.approx(70 / 110)
    assert breadth_on(_closes(30, 20), {**members, "baseline": {"date": "2025-12-31",
                      "symbols": list(_closes(30, 20).columns)}}, px.index[-1]) is None   # < 100 names
    assert breadth_on(px, None, px.index[-1]) is None


def test_the_overlay_month_is_kept_daily_at_its_exposure_and_pays_the_switch():
    idx = pd.bdate_range("2026-11-25", "2026-12-31")
    curve = pd.Series(np.linspace(100, 110, len(idx)), index=idx)
    dec = pd.Period("2026-12", freq="M")
    full = overlay_month(curve, dec, 1.0, 1.0, cash_yield=0.0, switch_cost=0.0)
    nov_end = curve[curve.index.month == 11].iloc[-1]
    assert full == pytest.approx(curve.iloc[-1] / nov_end - 1)
    half = overlay_month(curve, dec, 0.5, 1.0, cash_yield=0.0, switch_cost=0.003)
    daily = pd.concat([curve[curve.index.month == 11].iloc[-1:], curve[curve.index.month == 12]]).pct_change().dropna()
    assert half == pytest.approx(float(np.prod(1 + 0.5 * daily)) * (1 - 0.5 * 0.003) - 1)
    assert 0 < half < full


def test_the_overlay_sits_beside_the_engines_month_and_the_table_shows_it():
    mod = _updater()
    idx = pd.bdate_range("2026-01-01", "2026-12-31")
    px = pd.DataFrame({f"S{i}": np.linspace(100, 90 + i, len(idx)) for i in range(150)}, index=idx)
    members = {"schema_version": 2, "index": "nifty_500",
               "baseline": {"date": "2025-12-31", "symbols": list(px.columns)}, "changes": [], "aliases": {}}
    curve = pd.Series(np.linspace(100, 120, len(idx)), index=idx)
    ledger = {"months": {"2026-12": {"strategy": 0.05, "benchmark": 0.01, "alpha": 0.04}}}
    lines = mod.add_overlay(ledger, ["2026-12"], SHADOWS["breadth_long"], curve, px, members)
    entry = ledger["months"]["2026-12"]
    assert entry["strategy"] == 0.05, "the engine's month (ledger parity) is never touched"
    ov = entry["overlay"]
    assert ov["signal"] == "2026-11-30" and ov["exposure"] in (0.5, 1.0) and ov["strategy"] is not None
    assert lines and "overlay 2026-12" in lines[0]
    assert mod.add_overlay(ledger, ["2026-12"], SHADOWS["high90"], curve, px, members) == []
    table = comparison_frame({}, {}, None, {"breadth_long": ledger, "high90": {"months": {"2026-12": {"strategy": 0.02}}}})
    by = {r["SYSTEM"]: r["DEC"] for _, r in table.iterrows()}
    assert by[SHADOWS["breadth_long"].name] == ov["strategy"]
    assert by[SHADOWS["high90"].name] == 0.02


def test_the_monthly_job_freezes_both_books_after_the_live_records():
    wf = yaml.safe_load((ROOT / ".github/workflows/monthly_track_record.yml").read_text(encoding="utf-8"))
    steps = next(iter(wf["jobs"].values()))["steps"]
    names = [s.get("name", "") for s in steps]
    i = names.index("Freeze the near-high and breadth shadow records")
    assert names.index("Freeze the shadow record") < i < names.index("Commit the ledger")
    run = steps[i]["run"]
    assert "--shadow \"$BOOK\"" in run and "high90 breadth_long" in run and "|| echo" in run


def test_at_full_exposure_the_overlay_is_the_engines_own_month_first_month_included():
    """Rehearsal of 19 Nov 2026: the first month came back n/a (no close before it)."""
    from src.engine.track_record import calendar_month_returns

    idx = pd.bdate_range("2026-10-01", "2026-11-30")
    curve = pd.Series(100 * np.cumprod(1 + np.sin(np.arange(len(idx))) / 100), index=idx)
    engine = calendar_month_returns(curve)
    for period in engine.index:
        got = overlay_month(curve, period, 1.0, 1.0, cash_yield=0.0, switch_cost=0.0)
        assert got == pytest.approx(float(engine.loc[period]))


def test_a_book_with_no_frozen_month_adds_no_row():
    live_like = {"750": {"months": {"2026-11": {"strategy": 0.01}}}}
    table = comparison_frame(live_like, {}, None, {"high90": {"months": {}}, "breadth_long": None})
    assert not ({SHADOWS["high90"].name, SHADOWS["breadth_long"].name} & set(table["SYSTEM"]))


# ── Skip 5 (owner, 20 Nov 2026: "Record skip 5 as a shadow book"; TODO S160) ──

def test_skip5_changes_only_the_score_date_and_starts_with_the_december_book():
    from src.engine.track_record import run_backtest_kwargs

    book = SHADOWS["skip5"]
    live = TRACK_RECORD_CONFIG
    assert {k: v for k, v in book.config.items() if live.get(k, object()) != v} == {"score_skip": 5}
    assert book.breadth_rule is None
    assert book.inception == pd.Period("2026-12", freq="M")
    assert book.ledger_path.name == "track_record_shadow_skip5.json"
    # The engine receives it; the live record runs with 0, and its configuration
    # (hence every frozen month's fingerprint) does not carry the key at all.
    assert run_backtest_kwargs(book.config)["score_skip"] == 5
    assert run_backtest_kwargs(live)["score_skip"] == 0
    assert "score_skip" not in live
    for other in ("recommendation", "high90", "breadth_long"):
        assert "score_skip" not in SHADOWS[other].config


def test_the_updater_picks_skip5():
    system, ledger, start, cfg = _updater().record_setup(SYSTEM_750, shadow="skip5")
    assert (Path(ledger), start, cfg) == (SHADOWS["skip5"].ledger_path, pd.Period("2026-12", freq="M"),
                                          SHADOWS["skip5"].config)


def test_the_monthly_job_freezes_skip5_after_the_other_shadows():
    wf = yaml.safe_load((ROOT / ".github/workflows/monthly_track_record.yml").read_text(encoding="utf-8"))
    steps = next(iter(wf["jobs"].values()))["steps"]
    names = [s.get("name", "") for s in steps]
    i = names.index("Freeze the skip-5 shadow record")
    assert names.index("Freeze the near-high and breadth shadow records") < i < names.index("Commit the ledger")
    run = steps[i]["run"]
    assert "--shadow skip5" in run and "|| echo" in run
