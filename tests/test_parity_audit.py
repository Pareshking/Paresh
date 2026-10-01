import pandas as pd

from src.engine.parity_audit import compare_monthly_ledger


def _curve(values):
    return pd.Series(
        values,
        index=pd.to_datetime(["2026-01-01", "2026-01-31", "2026-02-28"]),
        dtype=float,
    )


def test_monthly_parity_reports_matches_without_mutating_ledger():
    ledger = {
        "months": {
            "2026-01": {"strategy": 0.10, "benchmark": 0.05},
            "2026-02": {"strategy": 0.10, "benchmark": 0.02},
        }
    }
    before = repr(ledger)
    strategy = _curve([1.0, 1.10, 1.21])
    benchmark = _curve([1.0, 1.05, 1.071])

    report = compare_monthly_ledger(ledger, strategy, benchmark)

    assert report["passed"] is True
    assert report["counts"]["match"] == 2
    assert repr(ledger) == before


def test_monthly_parity_separates_drift_and_missing_periods():
    ledger = {
        "months": {
            "2026-01": {"strategy": 0.10, "benchmark": 0.05},
            "2026-02": {"strategy": 0.20, "benchmark": 0.02},
            "2026-03": {"strategy": 0.01, "benchmark": 0.01},
        }
    }
    strategy = _curve([1.0, 1.10, 1.21])
    benchmark = _curve([1.0, 1.05, 1.071])

    report = compare_monthly_ledger(ledger, strategy, benchmark)
    by_month = {row["month"]: row for row in report["rows"]}

    assert by_month["2026-01"]["status"] == "match"
    assert by_month["2026-02"]["status"] == "drift"
    assert by_month["2026-03"]["status"] == "missing_recomputed_period"
    assert report["passed"] is False


def test_monthly_parity_rejects_invalid_tolerance():
    import pytest

    ledger = {"months": {}}
    curve = _curve([1.0, 1.1, 1.2])
    with pytest.raises(ValueError):
        compare_monthly_ledger(ledger, curve, curve, tolerance=-0.1)
