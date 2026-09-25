"""Keep the whole Screener history on Screener's current adjustment basis.

After a split, bonus or demerger Screener re-adjusts the stock's past prices,
but on its own schedule: a day later, three days, ten. There is no fixed lag
and nothing here assumes one.

- UNTIL Screener restates, the event is a one-day step in the series. The
  corporate-actions check scans the Screener store too
  (scripts/check_corporate_actions.py --source screener), logs the step, and
  adjust_ohlc neutralises it before ranking -- exactly as it does for Yahoo.
- WHEN Screener restates, every price it serves before the event is multiplied
  by one factor and the prices after it are unchanged. The nightly fetch only
  covers the last year, so merging it "fresh wins" puts the dates it covers on
  the new basis and leaves every older stored date on the old one: a fake step
  a year back. This module finds the factor from the dates both copies hold and
  applies it to the stored dates the fetch did not cover. The logged step is
  then gone from the data, and _step_is_still_present switches its adjustment
  off by itself.
- A restatement whose event is already older than the nightly window cannot be
  seen by the nightly fetch at all. The weekly deep check (sync_screener.py
  fetches the 10-year weekly series once every SCREENER_DEEP_CHECK_DAYS) runs
  the same comparison over the whole history.

Per symbol, on the dates both hold, factor f = reference / stored:
- f is piecewise constant: one value per stretch between restated events, 1.0
  after the latest. A stretch of fewer than MIN_RUN dates is a price correction
  (Screener fixing a close), not a restatement: it defines no factor, and the
  fresh value still wins on its own date when the frames are merged.
- A stored date the reference lacks takes the factor of the stretch it sits in;
  older than the reference, the earliest stretch's; between two stretches with
  different factors, whichever split keeps the series smoothest.
- Volume is scaled too, but only when the reference's volumes show Screener
  adjusted them (a bonus or split changes the share count). Otherwise left.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

MIN_RUN = 3            # common dates a stretch needs before its factor is believed
TOLERANCE = 0.01       # 1%: rounding noise is one factor, any real event is not
VOLUME_TOLERANCE = 0.05


@dataclass
class _Run:
    dates: pd.DatetimeIndex
    factor: float
    volume_factor: float = 1.0


def _stretches(f: pd.Series) -> list[_Run]:
    """Consecutive common dates sharing one factor, in date order."""
    runs: list[_Run] = []
    start = 0
    values = f.to_numpy()
    for i in range(1, len(values) + 1):
        if i == len(values) or abs(values[i] / values[start] - 1.0) > TOLERANCE:
            runs.append(_Run(f.index[start:i], float(np.median(values[start:i]))))
            start = i
    return runs


def _credible_runs(f: pd.Series) -> list[_Run]:
    """Stretches long enough to be a restatement, neighbours of one factor merged."""
    kept = [r for r in _stretches(f) if len(r.dates) >= MIN_RUN]
    merged: list[_Run] = []
    for run in kept:
        if merged and abs(run.factor / merged[-1].factor - 1.0) <= TOLERANCE:
            dates = merged[-1].dates.append(run.dates)
            merged[-1] = _Run(dates, float(np.median(f.loc[dates])))
        else:
            merged.append(run)
    for run in merged:
        if abs(run.factor - 1.0) <= TOLERANCE:
            run.factor = 1.0  # rounding noise; never rescale by it
    return merged


def _volume_factor(run: _Run, stored: pd.Series | None, reference: pd.Series | None) -> float:
    """1/factor when the reference's volumes were adjusted, else 1."""
    if run.factor == 1.0 or stored is None or reference is None:
        return 1.0
    s = stored.reindex(run.dates)
    r = reference.reindex(run.dates)
    ok = (s > 0) & (r > 0)
    if int(ok.sum()) < MIN_RUN:
        return 1.0
    observed = float(np.median((r[ok] / s[ok]).to_numpy()))
    return 1.0 / run.factor if abs(observed * run.factor - 1.0) <= VOLUME_TOLERANCE else 1.0


def _split_gap(gap: pd.DatetimeIndex, close: pd.Series, left: _Run, right: _Run,
               left_value: float, right_value: float) -> int:
    """How many gap dates take the LEFT factor: the split with the smallest jump."""
    best, best_cost = 0, np.inf
    raw = close.reindex(gap).to_numpy()
    for j in range(len(gap) + 1):
        path = np.concatenate((
            [left_value], raw[:j] * left.factor, raw[j:] * right.factor, [right_value]))
        cost = float(np.max(np.abs(np.diff(np.log(path)))))
        if cost < best_cost - 1e-12:
            best, best_cost = j, cost
    return best


def rebase_symbol(stored: pd.DataFrame, reference: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any] | None]:
    """`stored` moved onto `reference`'s basis on the dates `reference` lacks.

    Both are one symbol's frame with a Close column (Volume optional). Dates the
    reference holds are left as they are: the merge that follows lets the
    reference win there. Returns the frame and a report, or None if unchanged.
    """
    close = stored["Close"].dropna()
    close = close[close > 0]
    ref = reference["Close"].dropna()
    ref = ref[ref > 0]
    common = close.index.intersection(ref.index)
    if len(common) < MIN_RUN:
        return stored, None
    runs = _credible_runs(ref.loc[common] / close.loc[common])
    if not runs or all(r.factor == 1.0 for r in runs):
        return stored, None

    stored_vol = stored["Volume"] if "Volume" in stored else None
    ref_vol = reference["Volume"] if "Volume" in reference else None
    for run in runs:
        run.volume_factor = _volume_factor(run, stored_vol, ref_vol)

    # Which run each stored-only date belongs to.
    targets = close.index.difference(ref.index)
    owner = pd.Series(-1, index=targets, dtype="int64")
    firsts = [r.dates[0] for r in runs]
    lasts = [r.dates[-1] for r in runs]
    owner[targets < firsts[0]] = 0
    owner[targets > lasts[-1]] = len(runs) - 1
    for i, run in enumerate(runs):
        owner[(targets >= firsts[i]) & (targets <= lasts[i])] = i
        if i + 1 < len(runs):
            gap = targets[(targets > lasts[i]) & (targets < firsts[i + 1])]
            if len(gap):
                j = _split_gap(gap, close, run, runs[i + 1],
                               float(ref.loc[lasts[i]]), float(ref.loc[firsts[i + 1]]))
                owner[gap[:j]] = i
                owner[gap[j:]] = i + 1

    out = stored.copy()
    rescaled = 0
    for i, run in enumerate(runs):
        dates = owner.index[owner.to_numpy() == i]
        if not len(dates):
            continue
        if run.factor != 1.0:
            out.loc[dates, "Close"] = out.loc[dates, "Close"] * run.factor
            rescaled += len(dates)
        if run.volume_factor != 1.0 and "Volume" in out:
            out.loc[dates, "Volume"] = out.loc[dates, "Volume"] * run.volume_factor
    if not rescaled:
        return stored, None
    return out, {
        "factors": [round(r.factor, 6) for r in runs],
        "boundaries": [str(r.dates[0].date()) for r in runs],
        "dates_rescaled": rescaled,
        "oldest_date": str(owner.index.min().date()),
        "volume_rescaled": any(r.volume_factor != 1.0 for r in runs),
    }


def rebase_store(store: pd.DataFrame, reference: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, dict[str, Any]]]:
    """Every symbol both frames carry, rebased onto `reference`. Nothing else changes."""
    if store is None or store.empty or reference is None or reference.empty:
        return store, {}
    have = set(reference.columns.get_level_values(0))
    out = store
    report: dict[str, dict[str, Any]] = {}
    for sym in sorted(set(store.columns.get_level_values(0)) & have):
        new, info = rebase_symbol(store[sym], reference[sym])
        if info is None:
            continue
        if out is store:
            out = store.copy()
        for col in new.columns:
            out[(sym, col)] = new[col]
        report[sym] = info
    return out, report
