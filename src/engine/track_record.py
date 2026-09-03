"""Append-only monthly track record: what the strategy ACTUALLY posted, month by month.

The backtest recomputes everything from live price data on every run. That is
correct for a backtest and useless as a track record: survivorship in the
universe file, a vendor's price revision, a changed weight slider -- any of them
silently rewrites what "January" returned, and a record that changes when you
change your mind is not a record. It is a rolling opinion.

So a closed month is written ONCE and then frozen. `finalize_months` refuses to
touch a month it has already stored; nothing short of a deliberate, explicit
recompute can alter history. Each entry carries the configuration fingerprint
that produced it, so a later parameter change is visible as a discontinuity in
the record rather than a silent rewrite of everything before it.

Month-to-date is deliberately NOT stored. It moves every session, so it is
computed live and shown beside the frozen months, never folded into them.

Conventions match the reference tracker:
  Q1 = Jan·Feb·Mar, Q2 = Apr·May·Jun, Q3 = Jul·Aug·Sep, Q4 = Oct·Nov·Dec
  CY = Jan..Dec compounded;  FY = Apr(Y)..Mar(Y+1) compounded (Indian FY)
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np
import pandas as pd

# Nothing before this month is ever recorded. The strategy's live history
# starts here; earlier "returns" would be pure hindsight simulation presented
# beside real ones.
INCEPTION = pd.Period("2026-01", freq="M")

LEDGER_PATH = Path("data/track_record.json")
SCHEMA_VERSION = 1

MONTH_LABELS = [
    "JAN", "FEB", "MAR", "APR", "MAY", "JUN",
    "JUL", "AUG", "SEP", "OCT", "NOV", "DEC",
]


# The configuration the record is kept under. It mirrors the Backtest tab's
# defaults, and it is pinned HERE rather than read from the UI on purpose: a
# track record has to be produced by one fixed setup, or its months are not
# comparable with each other. Changing anything in this dict changes the
# fingerprint, which marks every month written afterwards as a new regime and
# leaves the months before it untouched.
TRACK_RECORD_CONFIG: dict[str, Any] = {
    "top_n": 20,
    "rebal_freq": 21,
    "ema_period": 50,
    "high_pct": 0.80,
    "weight_method": "Equal Weight",
    "config_weights": [0.10, 0.30, 0.30, 0.20, 0.10],
    "cost_bps": 30.0,
    "buffer_n": 40,
    "benchmark": "^CRSLDX",
}


# ── Ledger I/O ───────────────────────────────────────────────────────────────

def empty_ledger() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "inception": str(INCEPTION),
        "benchmark": "^CRSLDX",
        "months": {},
    }


def load_ledger(path: Path | str = LEDGER_PATH) -> dict[str, Any]:
    """Read the ledger, or an empty one. A corrupt file is never silently reset.

    Returning a fresh ledger on a JSON error would let one bad write erase the
    entire history on the next successful run, which is the one failure mode
    this file exists to prevent.
    """
    p = Path(path)
    if not p.exists():
        return empty_ledger()
    with p.open("r", encoding="utf-8") as fh:
        ledger = json.load(fh)
    if not isinstance(ledger, dict) or "months" not in ledger:
        raise ValueError(f"{p} is not a track-record ledger")
    return ledger


def save_ledger(ledger: dict[str, Any], path: Path | str = LEDGER_PATH) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(ledger)
    payload["months"] = dict(sorted(payload.get("months", {}).items()))
    with p.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=False)
        fh.write("\n")


def config_fingerprint(**params: Any) -> str:
    """Short stable hash of the strategy configuration behind a month's return.

    Two months produced by different settings are not the same series. Storing
    the fingerprint makes that visible instead of leaving a step change in the
    numbers unexplained.
    """
    blob = json.dumps(params, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()[:12]


# ── Deriving calendar-month returns ──────────────────────────────────────────

def calendar_month_returns(curve: pd.Series) -> pd.Series:
    """Month-over-month returns of an equity curve, indexed by calendar month.

    The backtest's own period table runs fill-to-fill (03 Aug -> 31 Aug), which
    is right for attributing a rebalance and wrong for a column headed AUG. A
    track record wants the calendar month, so take month-end closes off the
    curve. The first month is measured from the curve's base point -- the value
    it is indexed at, before any P&L -- so no partial period is dropped.
    """
    s = pd.Series(curve).dropna()
    if s.empty:
        return pd.Series(dtype=float)
    s.index = pd.DatetimeIndex(s.index)
    month_last = s.resample("ME").last().dropna()
    if month_last.empty:
        return pd.Series(dtype=float)
    prev = month_last.shift(1)
    prev.iloc[0] = s.iloc[0]
    rets = (month_last / prev.replace(0, np.nan)) - 1.0
    rets.index = month_last.index.to_period("M")
    return rets.dropna()


def compound(returns: Iterable[float]) -> float | None:
    """Chain-link a run of monthly returns. None when there is nothing to chain."""
    vals = [float(r) for r in returns if r is not None and np.isfinite(r)]
    if not vals:
        return None
    return float(np.prod([1.0 + v for v in vals]) - 1.0)


# ── Append-only finalisation ─────────────────────────────────────────────────

def finalize_months(
    ledger: dict[str, Any],
    strategy_curve: pd.Series,
    benchmark_curve: pd.Series,
    fingerprint: str,
    as_of: pd.Timestamp,
    data_as_of: pd.Timestamp | None = None,
    force: bool = False,
) -> tuple[dict[str, Any], list[str], list[str]]:
    """Write newly CLOSED months into the ledger. Never rewrite a stored one.

    Returns (ledger, added, skipped). `skipped` names months that were eligible
    but already recorded -- the normal case on a re-run, and the whole point:
    running this twice must not change a single stored number.

    `force` exists for a deliberate rebuild and is never used by the scheduled
    updater. It rewrites history, which is exactly what everything else here is
    built to prevent, so it is opt-in and loud.
    """
    strat = calendar_month_returns(strategy_curve)
    bench = calendar_month_returns(benchmark_curve)

    current_month = pd.Period(pd.Timestamp(as_of), freq="M")
    months = dict(ledger.get("months", {}))
    added: list[str] = []
    skipped: list[str] = []

    for period in strat.index:
        if period < INCEPTION:
            continue  # pre-inception is not this strategy's record
        if period >= current_month:
            continue  # the month in progress is not closed; MTD covers it
        key = str(period)
        if key in months and not force:
            skipped.append(key)
            continue

        s_ret = float(strat.loc[period])
        b_ret = float(bench.loc[period]) if period in bench.index else None
        # How this month came to be recorded, which is not a detail. A month
        # frozen the moment it closed was struck from the data as it stood then.
        # A month RECONSTRUCTED later is computed from today's universe file and
        # today's prices, so it carries the backtest's own biases -- today's
        # index constituents applied to a month before some of them joined it.
        # Both are frozen once written; they are not equally strong evidence,
        # and the record should say which is which rather than leave it to be
        # inferred from a finalisation date.
        origin = "recorded" if period == current_month - 1 else "backfill"
        months[key] = {
            "strategy": round(s_ret, 6),
            "benchmark": round(b_ret, 6) if b_ret is not None else None,
            "alpha": round(s_ret - b_ret, 6) if b_ret is not None else None,
            "origin": origin,
            "finalized_on": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "config": fingerprint,
            "data_as_of": (
                pd.Timestamp(data_as_of).strftime("%Y-%m-%d")
                if data_as_of is not None
                else None
            ),
        }
        added.append(key)

    out = dict(ledger)
    out["months"] = months
    out.setdefault("schema_version", SCHEMA_VERSION)
    out.setdefault("inception", str(INCEPTION))
    return out, added, skipped


def drift_report(
    ledger: dict[str, Any], strategy_curve: pd.Series
) -> list[dict[str, Any]]:
    """Where a recompute now disagrees with what was frozen. Stored always wins.

    Not an error: prices get revised, universes change. It is a diagnostic --
    a large drift means the recomputed backtest and the record have parted
    company, which is worth knowing even though the record does not move.
    """
    recomputed = calendar_month_returns(strategy_curve)
    out: list[dict[str, Any]] = []
    for key, entry in sorted(ledger.get("months", {}).items()):
        period = pd.Period(key, freq="M")
        if period not in recomputed.index:
            continue
        now = float(recomputed.loc[period])
        was = entry.get("strategy")
        if was is None:
            continue
        if abs(now - float(was)) > 5e-4:
            out.append(
                {"month": key, "stored": float(was), "recomputed": now,
                 "drift": now - float(was)}
            )
    return out


# ── Presentation ─────────────────────────────────────────────────────────────

def _series_from(ledger: dict[str, Any], field: str) -> pd.Series:
    rows = {}
    for key, entry in ledger.get("months", {}).items():
        val = entry.get(field)
        if val is not None:
            rows[pd.Period(key, freq="M")] = float(val)
    if not rows:
        return pd.Series(dtype=float)
    return pd.Series(rows).sort_index()


def build_grid(
    ledger: dict[str, Any],
    field: str = "strategy",
    mtd: tuple[pd.Period, float] | None = None,
    years: Sequence[int] | None = None,
) -> pd.DataFrame:
    """Year-by-month grid with CY, FY and calendar-quarter aggregates.

    `mtd` adds the live, unfrozen month-to-date figure into its own cell so the
    current month is visible without being recorded. It is included in the
    quarter and CY compounding -- a year-to-date number that ignored the
    running month would be wrong in the other direction -- and the caller
    labels it as partial.
    """
    series = _series_from(ledger, field)
    if mtd is not None:
        period, value = mtd
        if value is not None and np.isfinite(value) and period >= INCEPTION:
            series.loc[period] = float(value)
            series = series.sort_index()

    if series.empty:
        return pd.DataFrame()

    if years is None:
        years = range(INCEPTION.year, int(series.index.max().year) + 1)

    def _get(y: int, m: int) -> float | None:
        p = pd.Period(year=y, month=m, freq="M")
        return float(series.loc[p]) if p in series.index else None

    rows = []
    for y in years:
        monthly = [_get(y, m) for m in range(1, 13)]
        row: dict[str, Any] = {"YEAR": y}
        for label, val in zip(MONTH_LABELS, monthly):
            row[label] = val
        row["CY RETURN"] = compound([v for v in monthly if v is not None])
        # Indian financial year: Apr of this row's year through Mar of the next.
        fy_months = [_get(y, m) for m in range(4, 13)] + [
            _get(y + 1, m) for m in range(1, 4)
        ]
        row["FY RETURN"] = compound([v for v in fy_months if v is not None])
        for qi in range(4):
            q_vals = [v for v in monthly[qi * 3 : qi * 3 + 3] if v is not None]
            row[f"Q{qi + 1}"] = compound(q_vals)
        rows.append(row)

    return pd.DataFrame(rows)


def summary_stats(ledger: dict[str, Any]) -> dict[str, Any]:
    """Headline figures over the FROZEN record only -- never the running month."""
    strat = _series_from(ledger, "strategy")
    bench = _series_from(ledger, "benchmark")
    if strat.empty:
        return {"months": 0}

    total_s = compound(strat.values)
    total_b = compound(bench.values) if not bench.empty else None
    n = len(strat)
    ann_s = (1 + total_s) ** (12.0 / n) - 1 if total_s is not None and n else None
    ann_b = (1 + total_b) ** (12.0 / n) - 1 if total_b is not None and n else None

    equity = (1 + strat).cumprod()
    max_dd = float((equity / equity.cummax() - 1).min()) if n else 0.0
    beat = (
        float((strat.reindex(bench.index) > bench).mean()) if not bench.empty else None
    )
    origins = [
        e.get("origin", "backfill") for e in ledger.get("months", {}).values()
    ]
    return {
        "months": n,
        "backfilled": sum(1 for o in origins if o == "backfill"),
        "recorded": sum(1 for o in origins if o == "recorded"),
        "first": str(strat.index.min()),
        "last": str(strat.index.max()),
        "total_return": total_s,
        "bench_return": total_b,
        "alpha": (total_s - total_b) if (total_s is not None and total_b is not None) else None,
        "ann_return": ann_s,
        "ann_bench": ann_b,
        "max_drawdown": max_dd,
        "best_month": float(strat.max()),
        "worst_month": float(strat.min()),
        "positive_months": int((strat > 0).sum()),
        "beat_rate": beat,
        "configs": sorted(
            {e.get("config") for e in ledger.get("months", {}).values() if e.get("config")}
        ),
    }


def months_to_cover(as_of: pd.Timestamp, inception: pd.Period = INCEPTION) -> int:
    """How many completed months a backtest must report to reach inception.

    The backtest window is counted back from the month in progress, so covering
    January from September means asking for the eight completed months Jan-Aug.
    """
    current = pd.Period(pd.Timestamp(as_of), freq="M")
    return max(int((current - inception).n), 0)
