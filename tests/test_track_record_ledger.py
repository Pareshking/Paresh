"""A track record that changes when you change your mind is not a record.

The backtest recomputes from live prices every run, so a vendor price revision,
a universe change or a nudged slider silently rewrites what "January" returned.
The ledger exists to stop that: a closed month is written once and frozen. These
tests are the guarantee.
"""
import json

import numpy as np
import pandas as pd
import pytest

from src.engine.track_record import (
    INCEPTION,
    TRACK_RECORD_CONFIG,
    build_grid,
    calendar_month_returns,
    compound,
    config_fingerprint,
    drift_report,
    empty_ledger,
    finalize_months,
    load_ledger,
    months_to_cover,
    save_ledger,
    summary_stats,
)


def _curve(monthly: dict[str, float], start="2025-12-31") -> pd.Series:
    """Daily curve whose calendar-month returns are exactly `monthly`."""
    idx = pd.bdate_range(start=start, end="2026-12-31")
    s = pd.Series(1.0, index=idx, dtype=float)
    level = 1.0
    base_period = pd.Period(start, freq="M")
    for d in idx:
        p = str(d.to_period("M"))
        s.loc[d] = level
    # Walk month by month, setting the month-end level.
    for period_str, ret in monthly.items():
        p = pd.Period(period_str, freq="M")
        mask = idx.to_period("M") == p
        if not mask.any():
            continue
        level = level * (1 + ret)
        s.loc[idx[mask][-1]] = level
        later = idx > idx[mask][-1]
        s.loc[later] = level
    return s


def _flat(value=1.0):
    idx = pd.bdate_range(start="2025-12-31", end="2026-12-31")
    return pd.Series(value, index=idx, dtype=float)


# ── Immutability: the whole point ────────────────────────────────────────────

def test_a_frozen_month_is_never_rewritten_even_when_the_curve_changes():
    """Re-running with DIFFERENT numbers must not move a stored month."""
    first = _curve({"2026-01": 0.10, "2026-02": 0.05})
    led, added, _ = finalize_months(
        empty_ledger(), first, _flat(), "cfg1", as_of=pd.Timestamp("2026-03-15")
    )
    assert added == ["2026-01", "2026-02"]
    stored_jan = led["months"]["2026-01"]["strategy"]

    # The universe changed, prices were revised -- January now recomputes very
    # differently. The record must not care.
    second = _curve({"2026-01": -0.40, "2026-02": 0.99})
    led2, added2, skipped2 = finalize_months(
        led, second, _flat(), "cfg1", as_of=pd.Timestamp("2026-03-15")
    )
    assert added2 == []
    assert set(skipped2) == {"2026-01", "2026-02"}
    assert led2["months"]["2026-01"]["strategy"] == stored_jan
    assert led2["months"]["2026-01"]["strategy"] == pytest.approx(0.10, abs=1e-6)


def test_rerunning_is_idempotent():
    curve = _curve({"2026-01": 0.10, "2026-02": 0.05})
    led = empty_ledger()
    for _ in range(4):
        led, _, _ = finalize_months(
            led, curve, _flat(), "cfg1", as_of=pd.Timestamp("2026-03-15")
        )
    assert len(led["months"]) == 2


def test_a_new_month_appends_without_touching_the_old_ones():
    led, _, _ = finalize_months(
        empty_ledger(), _curve({"2026-01": 0.10}), _flat(), "cfg1",
        as_of=pd.Timestamp("2026-02-15"),
    )
    frozen_jan = dict(led["months"]["2026-01"])

    led, added, _ = finalize_months(
        led, _curve({"2026-01": 0.10, "2026-02": 0.07}), _flat(), "cfg1",
        as_of=pd.Timestamp("2026-03-15"),
    )
    assert added == ["2026-02"]
    assert led["months"]["2026-01"] == frozen_jan


def test_a_config_change_does_not_rewrite_history():
    """New settings mark new months. Old months keep their old fingerprint."""
    led, _, _ = finalize_months(
        empty_ledger(), _curve({"2026-01": 0.10}), _flat(), "cfg_old",
        as_of=pd.Timestamp("2026-02-15"),
    )
    led, added, _ = finalize_months(
        led, _curve({"2026-01": 0.10, "2026-02": 0.07}), _flat(), "cfg_new",
        as_of=pd.Timestamp("2026-03-15"),
    )
    assert led["months"]["2026-01"]["config"] == "cfg_old"
    assert led["months"]["2026-02"]["config"] == "cfg_new"
    assert summary_stats(led)["configs"] == ["cfg_new", "cfg_old"]


def test_force_is_the_only_way_to_rewrite():
    led, _, _ = finalize_months(
        empty_ledger(), _curve({"2026-01": 0.10}), _flat(), "cfg1",
        as_of=pd.Timestamp("2026-02-15"),
    )
    led, added, _ = finalize_months(
        led, _curve({"2026-01": -0.20}), _flat(), "cfg1",
        as_of=pd.Timestamp("2026-02-15"), force=True,
    )
    assert added == ["2026-01"]
    assert led["months"]["2026-01"]["strategy"] == pytest.approx(-0.20, abs=1e-6)


# ── What may enter the record ────────────────────────────────────────────────

def test_the_month_in_progress_is_never_frozen():
    """MTD moves every session; freezing it would record a half month."""
    led, added, _ = finalize_months(
        empty_ledger(),
        _curve({"2026-01": 0.10, "2026-02": 0.05, "2026-03": 0.02}),
        _flat(), "cfg1", as_of=pd.Timestamp("2026-03-15"),
    )
    assert "2026-03" not in led["months"]
    assert added == ["2026-01", "2026-02"]


def test_pre_inception_months_are_refused():
    """2025 is not this strategy's record, however much curve exists."""
    curve = _curve({"2025-11": 0.30, "2025-12": 0.20, "2026-01": 0.10},
                   start="2025-10-31")
    led, added, _ = finalize_months(
        empty_ledger(), curve, _flat(), "cfg1", as_of=pd.Timestamp("2026-02-15")
    )
    assert added == ["2026-01"]
    assert all(pd.Period(k, freq="M") >= INCEPTION for k in led["months"])


def test_benchmark_is_recorded_beside_every_month():
    strat = _curve({"2026-01": 0.10})
    bench = _curve({"2026-01": 0.04})
    led, _, _ = finalize_months(
        empty_ledger(), strat, bench, "cfg1", as_of=pd.Timestamp("2026-02-15")
    )
    e = led["months"]["2026-01"]
    assert e["benchmark"] == pytest.approx(0.04, abs=1e-6)
    assert e["alpha"] == pytest.approx(0.06, abs=1e-6)


# ── Derivation ───────────────────────────────────────────────────────────────

def test_calendar_month_returns_measure_whole_months():
    curve = _curve({"2026-01": 0.10, "2026-02": -0.05})
    rets = calendar_month_returns(curve)
    assert rets.loc[pd.Period("2026-01", freq="M")] == pytest.approx(0.10, abs=1e-9)
    assert rets.loc[pd.Period("2026-02", freq="M")] == pytest.approx(-0.05, abs=1e-9)


def test_months_to_cover_reaches_back_to_inception():
    assert months_to_cover(pd.Timestamp("2026-09-03")) == 8   # Jan..Aug
    assert months_to_cover(pd.Timestamp("2026-02-01")) == 1   # Jan
    assert months_to_cover(pd.Timestamp("2026-01-15")) == 0   # nothing closed


def test_drift_is_reported_but_never_applied():
    led, _, _ = finalize_months(
        empty_ledger(), _curve({"2026-01": 0.10}), _flat(), "cfg1",
        as_of=pd.Timestamp("2026-02-15"),
    )
    report = drift_report(led, _curve({"2026-01": 0.25}))
    assert len(report) == 1
    assert report[0]["month"] == "2026-01"
    assert report[0]["stored"] == pytest.approx(0.10, abs=1e-6)
    assert report[0]["recomputed"] == pytest.approx(0.25, abs=1e-6)
    assert led["months"]["2026-01"]["strategy"] == pytest.approx(0.10, abs=1e-6)


# ── Aggregation, against the reference tracker's conventions ─────────────────

def _grid_ledger(vals: dict[int, float]) -> dict:
    led = empty_ledger()
    led["months"] = {
        f"2026-{m:02d}": {"strategy": v, "benchmark": 0.0, "alpha": v}
        for m, v in vals.items()
    }
    return led


def test_quarters_are_calendar_quarters():
    led = _grid_ledger({1: 0.10, 2: 0.10, 3: 0.10, 4: 0.05})
    row = build_grid(led).iloc[0]
    assert row["Q1"] == pytest.approx(1.1 ** 3 - 1, abs=1e-9)
    assert row["Q2"] == pytest.approx(0.05, abs=1e-9)


def test_cy_compounds_january_through_december():
    led = _grid_ledger({1: 0.10, 2: -0.05, 12: 0.20})
    row = build_grid(led).iloc[0]
    assert row["CY RETURN"] == pytest.approx(1.10 * 0.95 * 1.20 - 1, abs=1e-9)


def test_fy_runs_april_to_march_across_the_year_boundary():
    led = empty_ledger()
    led["months"] = {
        "2026-04": {"strategy": 0.10, "benchmark": 0.0, "alpha": 0.10},
        "2027-02": {"strategy": 0.20, "benchmark": 0.0, "alpha": 0.20},
        "2027-05": {"strategy": 0.50, "benchmark": 0.0, "alpha": 0.50},
    }
    grid = build_grid(led).set_index("YEAR")
    # FY2026 = Apr 2026 .. Mar 2027: picks up Apr-26 and Feb-27, not May-27.
    assert grid.loc[2026, "FY RETURN"] == pytest.approx(1.10 * 1.20 - 1, abs=1e-9)
    assert grid.loc[2027, "FY RETURN"] == pytest.approx(0.50, abs=1e-9)


def test_reference_tracker_conventions_reproduce():
    """The user's sheet: Q1 2%, Q2 39%, Q3 12%, FY 56% off its monthly row."""
    led = _grid_ledger(
        {1: -0.036, 2: 0.174, 3: -0.096, 4: 0.25, 5: 0.06,
         6: 0.05, 7: 0.04, 8: 0.08, 9: 0.0}
    )
    row = build_grid(led).iloc[0]
    assert round(row["Q1"] * 100) == 2
    assert round(row["Q2"] * 100) == 39
    assert round(row["Q3"] * 100) == 12
    assert round(row["FY RETURN"] * 100) == 56


def test_mtd_enters_the_grid_without_entering_the_ledger():
    led = _grid_ledger({1: 0.10})
    period = pd.Period("2026-02", freq="M")
    grid = build_grid(led, mtd=(period, 0.03))
    row = grid.iloc[0]
    assert row["FEB"] == pytest.approx(0.03, abs=1e-9)
    assert row["Q1"] == pytest.approx(1.10 * 1.03 - 1, abs=1e-9)
    assert "2026-02" not in led["months"], "the ledger itself stays frozen"


def test_compound_of_nothing_is_none():
    assert compound([]) is None
    assert compound([float("nan")]) is None


# ── Persistence ──────────────────────────────────────────────────────────────

def test_round_trip_through_disk(tmp_path):
    led, _, _ = finalize_months(
        empty_ledger(), _curve({"2026-01": 0.10, "2026-02": 0.05}), _flat(),
        "cfg1", as_of=pd.Timestamp("2026-03-15"),
    )
    path = tmp_path / "track_record.json"
    save_ledger(led, path)
    assert load_ledger(path)["months"] == led["months"]


def test_a_corrupt_ledger_raises_rather_than_resetting(tmp_path):
    """Silently returning an empty ledger would erase history on the next write."""
    path = tmp_path / "track_record.json"
    path.write_text('{"nonsense": true}')
    with pytest.raises(ValueError):
        load_ledger(path)


def test_missing_ledger_starts_empty(tmp_path):
    assert load_ledger(tmp_path / "absent.json")["months"] == {}


def test_the_shipped_ledger_is_readable_and_starts_at_inception():
    led = load_ledger()
    assert led["inception"] == str(INCEPTION)
    assert led["benchmark"] == TRACK_RECORD_CONFIG["benchmark"]
    for key in led["months"]:
        assert pd.Period(key, freq="M") >= INCEPTION


def test_fingerprint_changes_with_configuration():
    a = config_fingerprint(**TRACK_RECORD_CONFIG)
    b = config_fingerprint(**{**TRACK_RECORD_CONFIG, "top_n": 30})
    assert a != b
    assert a == config_fingerprint(**TRACK_RECORD_CONFIG)
