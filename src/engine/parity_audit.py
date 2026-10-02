"""Diagnostics for comparing a recomputed backtest with the frozen monthly ledger.

The ledger remains authoritative. This module never edits it: it reports coverage
gaps and strategy/benchmark drift so a caller can distinguish a mismatch from
a missing comparison period.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from src.engine.track_record import calendar_month_returns


DEFAULT_TOLERANCE = 5e-4  # 0.05 percentage points


def compare_monthly_ledger(
    ledger: dict[str, Any],
    strategy_curve: pd.Series,
    benchmark_curve: pd.Series,
    *,
    tolerance: float = DEFAULT_TOLERANCE,
) -> dict[str, Any]:
    """Compare recomputed calendar-month returns with frozen ledger rows.

    Returns a machine-readable report. Existing ledger rows are never changed.
    Missing months are reported separately from numerical drift. A month is
    within tolerance only when both stored series that exist can be compared.
    """
    if tolerance < 0 or not np.isfinite(tolerance):
        raise ValueError("tolerance must be a finite, non-negative number")

    strategy = calendar_month_returns(strategy_curve)
    benchmark = calendar_month_returns(benchmark_curve)
    months = ledger.get("months", {})
    rows: list[dict[str, Any]] = []

    for key, frozen in sorted(months.items()):
        period = pd.Period(key, freq="M")
        row: dict[str, Any] = {"month": key, "status": "match"}
        compared = 0
        missing: list[str] = []
        drifts: dict[str, float] = {}

        for field, curve in (("strategy", strategy), ("benchmark", benchmark)):
            stored = frozen.get(field)
            if stored is None:
                continue
            if period not in curve.index:
                missing.append(field)
                continue
            current = float(curve.loc[period])
            delta = current - float(stored)
            compared += 1
            row[f"{field}_stored"] = float(stored)
            row[f"{field}_recomputed"] = current
            row[f"{field}_drift"] = delta
            if abs(delta) > tolerance:
                drifts[field] = delta

        if missing:
            row["status"] = "missing_recomputed_period"
            row["missing_series"] = missing
        elif drifts:
            row["status"] = "drift"
            row["drifted_series"] = sorted(drifts)
        elif compared == 0:
            row["status"] = "not_comparable"

        rows.append(row)

    counts = {
        status: sum(1 for row in rows if row["status"] == status)
        for status in (
            "match", "drift", "missing_recomputed_period", "not_comparable"
        )
    }
    return {
        "tolerance": tolerance,
        "ledger_months": len(months),
        "recomputed_strategy_months": len(strategy),
        "recomputed_benchmark_months": len(benchmark),
        "counts": counts,
        "passed": counts["drift"] == 0 and counts["missing_recomputed_period"] == 0
                  and counts["not_comparable"] == 0,
        "rows": rows,
    }
