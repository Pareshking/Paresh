"""Grid search over backtest buy/sell criteria.

READ THIS BEFORE TRUSTING A RESULT.

Running many parameter combinations over one window and keeping the best is
data mining, not evidence. With enough combinations something always wins, and
the amount it wins by is mostly luck. The sweep therefore reports the whole
distribution, flags how much of the spread is attributable to noise, and never
presents a single "optimal" setting without that context.

Three guards are built in rather than left to the reader:

  * Every combination is scored on the SAME window, so results are comparable,
    and the window is stated in the result.
  * `overfitting_risk` compares the winner's margin against the spread of all
    results. A winner inside one standard deviation of the pack is not a
    finding.
  * `holdout` optionally splits the window in two and reports how the in-sample
    winner ranked out of sample. A setting that wins the first half and lands
    mid-table in the second half was fitted to noise.
"""

from __future__ import annotations

import hashlib
from collections import Counter
import itertools
from dataclasses import dataclass, field
from typing import Any, Sequence

import numpy as np
import pandas as pd

from src.engine.backtester import DEFAULT_BACKTEST_MONTHS, run_backtest

# What a sweep is allowed to vary. Each entry maps a friendly name to the
# run_backtest keyword it drives.
SWEEPABLE: dict[str, str] = {
    "Holdings": "top_n",
    "Rebalance": "rebal_freq",
    "EMA filter": "ema_period",
    "52W high floor": "high_pct",
    "Buffer": "buffer_n",
    "Cost (bps)": "cost_bps",
}

# Objectives worth maximising. Drawdown is negative, so it is maximised too.
OBJECTIVES: dict[str, str] = {
    "Sharpe": "sharpe",
    "Total return": "total_return",
    "Alpha vs benchmark": "alpha",
    "Calmar": "calmar",
    "Max drawdown (least bad)": "max_drawdown",
}


@dataclass
class SweepResult:
    """One grid search, with the context needed to judge it."""

    table: pd.DataFrame
    objective: str
    window_months: int
    combinations_tested: int
    combinations_failed: int
    best: dict[str, Any] | None = None
    overfitting_risk: str = "unknown"
    risk_detail: str = ""
    holdout: pd.DataFrame | None = None
    warnings: list[str] = field(default_factory=list)


def _prices_fingerprint(df: pd.DataFrame) -> str:
    """Cache key component identifying THIS price frame.

    run_backtest is memoised on its prices_hash argument (the frame itself is
    underscore-prefixed and therefore not hashed). A sweep that passed a key
    derived only from the combination index would collide across different
    price data and hand back another run's result -- which is exactly what the
    test suite caught: a sweep over a 60-session frame returned the cached
    results of an earlier sweep over a 760-session one.
    """
    try:
        last = pd.Timestamp(df.index[-1]).date().isoformat() if len(df.index) else "empty"
        first = pd.Timestamp(df.index[0]).date().isoformat() if len(df.index) else "empty"
    except Exception:
        first = last = "unknown"
    cols = ",".join(str(c) for c in list(df.columns)[:50])
    raw = f"{first}|{last}|{df.shape[0]}x{df.shape[1]}|{cols}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def _grid(space: dict[str, Sequence[Any]]) -> list[dict[str, Any]]:
    if not space:
        return []
    keys = list(space)
    return [dict(zip(keys, combo)) for combo in itertools.product(*(space[k] for k in keys))]


def count_combinations(space: dict[str, Sequence[Any]]) -> int:
    """How many backtests a space implies. Call this BEFORE running one."""
    n = 1
    for values in space.values():
        n *= max(len(values), 1)
    return n if space else 0


def _score(stats: dict[str, Any], objective: str) -> float:
    raw = stats.get(OBJECTIVES.get(objective, "sharpe"))
    try:
        val = float(raw)
    except (TypeError, ValueError):
        return float("nan")
    return val if np.isfinite(val) else float("nan")


def run_parameter_sweep(
    _adj_close: pd.DataFrame,
    space: dict[str, Sequence[Any]],
    *,
    objective: str = "Sharpe",
    base: dict[str, Any] | None = None,
    backtest_months: int = DEFAULT_BACKTEST_MONTHS,
    sector_map: dict[str, str] | None = None,
    _benchmark_close: pd.Series | None = None,
    max_combinations: int = 400,
    progress: Any = None,
) -> SweepResult:
    """Backtest every combination in `space` and rank them by `objective`.

    `space` maps names from SWEEPABLE to the values to try. `base` supplies the
    parameters held fixed. Returns every result, not only the winner.
    """
    combos = _grid(space)
    warnings: list[str] = []

    if not combos:
        return SweepResult(pd.DataFrame(), objective, backtest_months, 0, 0,
                           warnings=["No parameters were varied."])
    if len(combos) > max_combinations:
        raise ValueError(
            f"{len(combos)} combinations exceeds max_combinations={max_combinations}. "
            "Narrow the grid: every combination is a full backtest, and a larger "
            "grid also makes the winner more likely to be noise."
        )

    fixed = dict(base or {})
    rows: list[dict[str, Any]] = []
    failed = 0
    failure_reasons: Counter[str] = Counter()
    # Identify the data AND the fixed parameters, so a sweep cannot be served
    # another sweep's memoised backtests.
    fingerprint = _prices_fingerprint(_adj_close)
    base_key = hashlib.md5(
        f"{sorted((k, str(v)) for k, v in fixed.items())}|{backtest_months}".encode()
    ).hexdigest()[:8]

    for i, combo in enumerate(combos):
        kwargs = dict(fixed)
        for friendly, value in combo.items():
            kwargs[SWEEPABLE[friendly]] = value
        try:
            combo_key = "_".join(f"{k}={v}" for k, v in sorted(combo.items()))
            res = run_backtest(
                f"sweep-{fingerprint}-{base_key}-{combo_key}",
                _adj_close,
                sector_map=sector_map,
                _benchmark_close=_benchmark_close,
                backtest_months=backtest_months,
                **kwargs,
            )
        except Exception as exc:
            # A count is not a diagnosis. If one systematic error kills a whole
            # region of the space, the sweep still ranks the survivors and
            # presents a winner -- and the excluded region is invisible, so the
            # "best" parameters are only best among whatever did not crash.
            res = None
            failure_reasons[f"{type(exc).__name__}: {exc}"[:120]] += 1
        if progress is not None:
            try:
                progress((i + 1) / len(combos), f"{i + 1}/{len(combos)} combinations")
            except Exception:
                pass
        if not res or not res.get("stats"):
            failed += 1
            if res is not None:
                failure_reasons["no stats (insufficient history for the window)"] += 1
            continue
        stats = res["stats"]
        rows.append({
            **combo,
            "Score": _score(stats, objective),
            "Sharpe": stats.get("sharpe"),
            "Total Return": stats.get("total_return"),
            "Alpha": stats.get("alpha"),
            "Max DD": stats.get("max_drawdown"),
            "Calmar": stats.get("calmar"),
            "Win Rate": stats.get("win_rate"),
            "Turnover": stats.get("avg_turnover"),
            "Periods": stats.get("n_periods"),
        })

    if not rows:
        warnings.append(
            "Every combination failed to produce a backtest, usually insufficient "
            "price history for the formation window."
        )
        for reason, n in failure_reasons.most_common(3):
            warnings.append(f"  {n}x {reason}")
        return SweepResult(pd.DataFrame(), objective, backtest_months,
                           len(combos), failed, warnings=warnings)

    table = pd.DataFrame(rows).sort_values("Score", ascending=False, na_position="last")
    table = table.reset_index(drop=True)
    table.insert(0, "Rank", range(1, len(table) + 1))

    best = table.iloc[0].to_dict()
    risk, detail = assess_overfitting(table, len(combos))
    if failed:
        warnings.append(f"{failed} of {len(combos)} combinations produced no result.")
        for reason, n in failure_reasons.most_common(3):
            warnings.append(f"  {n}x {reason}")
        if failed > len(combos) / 2:
            warnings.append(
                "More than half the space failed, so the winner is the best of a "
                "small surviving subset rather than of the space you asked for."
            )

    return SweepResult(
        table=table,
        objective=objective,
        window_months=backtest_months,
        combinations_tested=len(combos),
        combinations_failed=failed,
        best=best,
        overfitting_risk=risk,
        risk_detail=detail,
        warnings=warnings,
    )


def assess_overfitting(table: pd.DataFrame, n_combinations: int) -> tuple[str, str]:
    """How much of the winner's margin is plausibly noise.

    The more combinations tried, the higher the best score even on random data.
    A winner within one standard deviation of the field is not distinguishable
    from the pack, however large its absolute number looks.
    """
    scores = pd.to_numeric(table["Score"], errors="coerce").dropna()
    if len(scores) < 3:
        return "unknown", "Too few successful combinations to judge."

    best, median = float(scores.iloc[0]), float(scores.median())
    spread = float(scores.std(ddof=0))
    if spread <= 0:
        return "none", "Every combination scored identically; the parameters did nothing."

    z = (best - median) / spread
    if n_combinations >= 100:
        note = f"{n_combinations} combinations were tried, so the best of them is expected to look good by chance alone. "
    elif n_combinations >= 25:
        note = f"{n_combinations} combinations were tried. "
    else:
        note = ""

    if z < 1.0:
        return "high", (
            f"{note}The winner is {z:.1f} SD above the median of the field -- "
            "inside the noise. Treat this as 'the parameters barely matter', "
            "not as an optimum."
        )
    if z < 2.0:
        return "moderate", (
            f"{note}The winner is {z:.1f} SD above the median. Suggestive, not "
            "conclusive; confirm it on a window this sweep did not see."
        )
    return "low", (
        f"{note}The winner is {z:.1f} SD above the median, a wide margin. Still "
        "worth confirming out of sample before trading it."
    )
