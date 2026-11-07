"""Diagnostics for comparing a recomputed backtest with the frozen monthly ledger.

The ledger remains authoritative. This module never edits it: it reports coverage
gaps and strategy/benchmark drift so a caller can distinguish a mismatch from
a missing comparison period.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.engine.track_record import calendar_month_returns


DEFAULT_TOLERANCE = 5e-4  # 0.05 percentage points
# Drifts the owner has looked at and accepted (frozen month kept as it is).
ACCEPTED_DRIFT_PATH = Path(__file__).with_name("parity_accepted_drift.json")


def load_accepted_drift(path: Path = ACCEPTED_DRIFT_PATH, system: str = "750") -> dict[str, Any]:
    """The accepted drifts by month for one record; empty when the file is absent.

    The Nifty 750's are under "months" (the original layout); every other
    record's under "systems" -> <system> -> "months", so an entry accepted for
    one record can never pass another's month (owner, 7 Nov 2026: Nano Cap's
    October accepted like the 750's).
    """
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    if system == "750":
        return data.get("months", {})
    return data.get("systems", {}).get(system, {}).get("months", {})


def _is_accepted(entry: Any, stored: float, current: float, tolerance: float) -> bool:
    """Accepted only for the exact stored value and a replay still at the
    accepted one: a different stored value or a further move fails again."""
    if not isinstance(entry, dict) or "stored" not in entry or "replay" not in entry:
        return False
    return (abs(float(entry["stored"]) - stored) <= 1e-9
            and abs(float(entry["replay"]) - current) <= tolerance)


def compare_monthly_ledger(
    ledger: dict[str, Any],
    strategy_curve: pd.Series,
    benchmark_curve: pd.Series,
    *,
    tolerance: float = DEFAULT_TOLERANCE,
    accepted: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compare recomputed calendar-month returns with frozen ledger rows.

    Returns a machine-readable report. Existing ledger rows are never changed.
    Missing months are reported separately from numerical drift. A month is
    within tolerance only when both stored series that exist can be compared.

    `accepted` (month -> {series: {"stored", "replay"}}) marks drifts the owner
    accepted; such a month reads "accepted" and does not fail the comparison.
    """
    if tolerance < 0 or not np.isfinite(tolerance):
        raise ValueError("tolerance must be a finite, non-negative number")

    strategy = calendar_month_returns(strategy_curve)
    benchmark = calendar_month_returns(benchmark_curve)
    months = ledger.get("months", {})
    accepted = accepted or {}
    rows: list[dict[str, Any]] = []

    for key, frozen in sorted(months.items()):
        period = pd.Period(key, freq="M")
        row: dict[str, Any] = {"month": key, "status": "match"}
        compared = 0
        missing: list[str] = []
        drifts: dict[str, float] = {}
        allowed: list[str] = []

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
                if _is_accepted(accepted.get(key, {}).get(field), float(stored), current, tolerance):
                    allowed.append(field)
                else:
                    drifts[field] = delta

        if missing:
            row["status"] = "missing_recomputed_period"
            row["missing_series"] = missing
        elif drifts:
            row["status"] = "drift"
            row["drifted_series"] = sorted(drifts)
        elif compared == 0:
            row["status"] = "not_comparable"
        elif allowed:
            row["status"] = "accepted"
            row["accepted_series"] = sorted(allowed)

        rows.append(row)

    counts = {
        status: sum(1 for row in rows if row["status"] == status)
        for status in (
            "match", "accepted", "drift", "missing_recomputed_period", "not_comparable"
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


# Statuses that make the comparison red (the parity gate's `ledger_parity`).
_RED = ("drift", "missing_recomputed_period", "not_comparable")


def freeze_refusal(report: dict[str, Any]) -> str | None:
    """Why the month freeze must not strike a month, or None when it may.

    `report` is compare_monthly_ledger's, with the accepted drifts passed in.
    Any month the comparison marks red (a drift not accepted, a month the
    replay cannot cover, a row with nothing to compare) refuses the freeze:
    a replay that disagrees with the frozen months is a replay on different
    data, and the month about to be struck would be struck on it (S89/S92:
    October 2026 was frozen on 3 Nov on a store carrying BSE closes, with
    September already drifting). Accepted drifts (status "accepted") pass.
    """
    red = [row for row in report.get("rows", []) if row.get("status") in _RED]
    if not red:
        return None
    parts = []
    for row in red:
        if row["status"] == "drift":
            parts.append(row["month"] + " (" + ", ".join(
                f"{name} {row[f'{name}_drift'] * 100:+.3f} pp"
                for name in row.get("drifted_series", [])) + ")")
        else:
            parts.append(f"{row['month']} ({row['status'].replace('_', ' ')})")
    return ("ledger parity is red for " + "; ".join(parts)
            + ": no month frozen (accept the drift in parity_accepted_drift.json, "
            "or fix the prices, then re-run)")
