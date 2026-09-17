"""Catch corporate actions masquerading as price moves.

NSE applies circuit limits of 5%, 10% or 20% to almost everything it lists. A
single session that moves 50% or 79% therefore did not happen as a price move.
It is a stock split, a bonus issue, or a demerger showing up in the price series
as though the money had evaporated.

That distinction matters here more than in most systems, because this is a
momentum strategy. A phantom -79% session is a catastrophic loss in a backtest
that never occurred, and a phantom +100% is a signal to buy something that never
rose. Neither is rare enough to ignore: the two-year frame carries sixteen such
sessions across 750 symbols.

Two different causes, both worth catching:

  SPLIT / BONUS -- yfinance's auto_adjust is supposed to restate the whole
  history so no jump ever appears. When a jump appears anyway, the adjustment
  did not reach the cached history. That is a data bug, and re-fetching fixes it.

  DEMERGER / SPIN-OFF -- auto_adjust does NOT handle these. The parent's price
  genuinely falls because value has left it, but the shareholder received shares
  in the new entity, so no economic loss occurred. Re-fetching does not fix this
  one; only tracking the entitlement does.

This module detects and classifies. It deliberately does NOT rewrite prices: a
wrong correction applied silently is worse than a flagged anomaly, and telling
the two causes apart needs information the price series does not carry.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

# Beyond this, a single session is not a price move. NSE's widest ordinary band
# is 20%; index-derivative names can move further on results days, so the
# threshold sits well clear of both to keep the signal clean.
IMPLAUSIBLE_MOVE: float = 0.35

# Ratio of today's price to yesterday's for the usual actions. A 1-for-5 split
# leaves the price at a fifth, so the ratio is 0.2.
COMMON_ACTIONS: dict[float, str] = {
    0.1000: "1:10 split",
    0.1250: "1:8 split",
    0.2000: "1:5 split",
    0.2500: "1:4 split",
    0.3333: "1:3 split",
    0.4000: "2:5 split",
    0.5000: "1:2 split or 1:1 bonus",
    0.6667: "3:2 (1:2 bonus)",
    0.7500: "4:3 (1:3 bonus)",
    2.0000: "2:1 reverse split",
    3.0000: "3:1 reverse split",
    5.0000: "5:1 reverse split",
    10.000: "10:1 reverse split",
}

# How close a ratio must sit to a clean action to be called one. Loose enough to
# survive a day's genuine drift on top of the action, tight enough that an
# arbitrary crash is not labelled a split.
RATIO_TOLERANCE: float = 0.04


def classify_ratio(ratio: float) -> tuple[str, float | None]:
    """Name the action a price ratio looks like, and how closely it matches.

    Returns (label, relative distance). An unmatched ratio is reported as a
    possible demerger rather than forced into the nearest split: a demerger
    leaves no clean ratio, and mislabelling one as a split would invite a
    "fix" that corrupts the data further.
    """
    if not np.isfinite(ratio) or ratio <= 0:
        return "unusable price", None
    best_label, best_gap = None, None
    for target, label in COMMON_ACTIONS.items():
        gap = abs(ratio - target) / target
        if best_gap is None or gap < best_gap:
            best_label, best_gap = label, gap
    if best_gap is not None and best_gap <= RATIO_TOLERANCE:
        return best_label, best_gap
    return "unmatched — possible demerger or spin-off", best_gap


def detect(
    prices: pd.DataFrame,
    threshold: float = IMPLAUSIBLE_MOVE,
    since: Any | None = None,
) -> pd.DataFrame:
    """Sessions whose move is too large to be a price move.

    `prices` is adjusted closes, dates by symbol. Returns one row per suspect
    session, worst first, with the action it resembles.
    """
    if prices is None or prices.empty:
        return pd.DataFrame()

    frame = prices.apply(pd.to_numeric, errors="coerce")
    if since is not None:
        frame = frame.loc[frame.index >= pd.Timestamp(since)]
    if len(frame) < 2:
        return pd.DataFrame()

    ratio = frame / frame.shift(1)
    move = ratio - 1.0
    flagged = move.abs() > threshold

    rows: list[dict[str, Any]] = []
    for date, symbol in zip(*np.where(flagged.to_numpy())):
        d = frame.index[date]
        s = frame.columns[symbol]
        r = float(ratio.iat[date, symbol])
        if not np.isfinite(r):
            continue
        label, gap = classify_ratio(r)
        rows.append(
            {
                "Date": pd.Timestamp(d),
                "Symbol": str(s),
                "Move %": float(r - 1.0),
                "Ratio": r,
                "Prev Close": float(frame.iat[date - 1, symbol]),
                "Close": float(frame.iat[date, symbol]),
                "Looks Like": label,
                "Match Gap": gap,
                "Kind": (
                    "split/bonus"
                    if gap is not None and gap <= RATIO_TOLERANCE
                    else "unclassified"
                ),
            }
        )

    if not rows:
        return pd.DataFrame()
    out = pd.DataFrame(rows)
    return out.reindex(out["Move %"].abs().sort_values(ascending=False).index)


def summarise(found: pd.DataFrame) -> dict[str, Any]:
    if found is None or found.empty:
        return {"total": 0, "split_like": 0, "unclassified": 0, "symbols": []}
    return {
        "total": int(len(found)),
        "split_like": int((found["Kind"] == "split/bonus").sum()),
        "unclassified": int((found["Kind"] == "unclassified").sum()),
        "symbols": sorted(found["Symbol"].unique().tolist()),
        "worst": {
            "symbol": found.iloc[0]["Symbol"],
            "date": found.iloc[0]["Date"].strftime("%Y-%m-%d"),
            "move": float(found.iloc[0]["Move %"]),
        },
    }


# ── Neutralising a flagged session ───────────────────────────────────────────

LOG_PATH = "data/corporate_actions_log.json"


def load_events(path: str | Path = LOG_PATH) -> list[dict[str, Any]]:
    """The flagged sessions on record, or an empty list."""
    import json

    p = Path(path)
    if not p.exists():
        return []
    try:
        with p.open(encoding="utf-8") as fh:
            log = json.load(fh)
    except (ValueError, OSError):
        return []
    return list((log.get("events") or {}).values())


def adjust_prices(
    prices: pd.DataFrame, events: list[dict[str, Any]] | None
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    """Remove flagged discontinuities by rescaling the history before each one.

    A 1:2 split halves the price overnight. Scaling every earlier price by the
    same ratio removes the step, leaving the stock's actual trajectory intact --
    which is exactly what the vendor's own adjustment would have done had it
    reached this data.

    Two properties matter more than the arithmetic:

    IT IS NEVER WRITTEN DOWN. The adjustment happens in memory, at read time,
    derived from the flagged event. A patch written into the stored prices
    would instead be applied on top of the vendor's, double-counting the split
    and producing a fresh error harder to spot than the original.

    AND IT IS RE-VERIFIED AGAINST THE PRICES IN HAND. The events come from a
    committed log, not from a live scan, so "the vendor restated it, the guard
    stops flagging it, nothing is applied" was not true of this function: it
    applied every logged event unconditionally. Yahoo restates a split-adjusted
    Indian series one to four weeks after the action -- exactly the window this
    log exists to cover -- and on the day that landed, the history would have
    been scaled by the ratio a SECOND time. A 1:3 split would have read as 1:9.
    So each event is checked against the actual ratio at its own date and
    skipped once the step is gone.

    IT ASSUMES A DEMERGER IS VALUE-NEUTRAL. For a split or bonus that is exact.
    For a demerger it is an approximation: the parent's price genuinely falls,
    but the holder receives shares in the new entity worth roughly the drop, so
    treating the session as no-change is much closer to the truth than booking a
    -65% loss that never happened.

    Returns the adjusted frame and the events actually applied.
    """
    if prices is None or prices.empty or not events:
        return prices, []

    out = prices.copy()
    applied: list[dict[str, Any]] = []
    index = pd.DatetimeIndex(out.index)

    for event in events:
        symbol = event.get("symbol")
        if symbol not in out.columns:
            continue
        try:
            when = pd.Timestamp(event["date"])
            ratio = float(event["ratio"])
        except (KeyError, TypeError, ValueError):
            continue
        if not np.isfinite(ratio) or ratio <= 0:
            continue
        before = index < when
        if not before.any():
            continue
        if not _step_is_still_present(out[symbol], when, ratio):
            # The vendor restated this series; the step the log describes is no
            # longer in the data. Applying the ratio now would re-create the
            # discontinuity it was written to remove.
            continue
        col = out.columns.get_loc(symbol)
        out.iloc[before, col] = out.iloc[before, col] * ratio
        applied.append({**event, "applied": True})

    return out, applied


def _step_is_still_present(
    series: pd.Series, when: pd.Timestamp, ratio: float
) -> bool:
    """Does ``series`` still show the logged discontinuity at ``when``?

    Compares the session's ACTUAL ratio against the logged one. A restated
    series moves normally across that date, so the observed ratio sits near 1.0
    and nowhere near the logged fraction; an unrestated one still carries the
    step. The test is "closer to the logged ratio than to no move at all",
    which needs no threshold of its own and degrades safely: an unreadable or
    absent price returns False, and not adjusting is the reversible mistake.
    """
    values = pd.to_numeric(series, errors="coerce")
    at = values.reindex([when]).iloc[0] if when in values.index else np.nan
    prior = values.loc[values.index < when].dropna()
    if not np.isfinite(at) or prior.empty:
        return False
    previous = float(prior.iloc[-1])
    if previous <= 0:
        return False
    observed = float(at) / previous
    return abs(observed - ratio) < abs(observed - 1.0)


def adjust_ohlc(
    frames: dict[str, pd.DataFrame], events: list[dict[str, Any]] | None
) -> tuple[dict[str, pd.DataFrame], list[dict[str, Any]]]:
    """Neutralise flagged actions across every PRICE frame at once.

    ``adjust_prices`` fixes one frame. The ranking pipeline reads four --
    adjusted close, close, high and low -- and adjusting a subset is worse than
    adjusting none: a 52-week high drawn from unadjusted highs sits three times
    above a split-adjusted close, so the stock reads as 67% below its own high
    and fails the Near-52W-High gate forever, on a split that never cost a
    holder a rupee.

    VOLUME IS DELIBERATELY NOT ADJUSTED. A split multiplies share count as it
    divides price, so historical volume really is on a different scale after
    one. Nothing here reads it on that horizon: the only consumer is a 20-day
    relative-volume label (momentum.py:350, :665), which compares the last
    session against the trailing twenty and is blind to a step older than that.
    Adjusting it would buy nothing and quietly change a displayed label.

    Returns the adjusted frames under their original keys, and the events that
    were actually applied (once, not once per frame).
    """
    if not events:
        return dict(frames), []
    out: dict[str, pd.DataFrame] = {}
    applied: list[dict[str, Any]] = []
    for name, frame in frames.items():
        adjusted, used = adjust_prices(frame, events)
        out[name] = adjusted
        if not applied:
            applied = used
    return out, applied


def trustworthy_ath(
    highs: pd.Series,
    peak_dates: pd.Series | None,
    events: list[dict[str, Any]] | None,
) -> pd.Series:
    """Blank all-time highs recorded on a price scale we can no longer identify.

    The 52-week high is computed from the price frame, so adjusting that frame
    fixes it. THE ALL-TIME HIGH IS NOT: it arrives as a separate per-symbol CSV
    that the nightly job rebuilds from its own ten-year download
    (src/loaders/ath_loader.py). Nothing done to the two-year frame in memory
    reaches a number read from that file.

    And momentum.py takes ``max(snapshot_ath, window_high)``. A high left on a
    pre-split scale is by construction the LARGER number, so it wins that max
    and silently defeats the adjustment applied to the frame beside it. On the
    shipped snapshot, ABFRL read -86.5% from a high of 364.4 against a close of
    49.0, across a 1:3 split and a demerger that cost a holder nothing. "At
    What that actually costs, measured on the shipped snapshot rather than
    asserted: the "% ATH" COLUMN was wrong for fourteen names by up to 65
    percentage points -- PGIL read -55.1% against a true -10.0%, INDIAGLYCO
    -77.0% against -11.4% -- and readers sort on that column. The "At ATH" dot
    did NOT change for a single one of them: 17 of 750 lit green before and
    after, because every corrected name still sits outside the -5% threshold
    (STAR is closest at -6.1%). Nor does anything SELECT on it; the Qualified
    list filters on Above 50 EMA and Near 52W High.

    So this is a displayed number, not a gate outcome -- today. STAR is 1.1
    points from lighting up, and the error it would light up from was 24 points
    wide, which is the reason to fix the number rather than wait for the day it
    changes a signal.

    WHY THIS BLANKS RATHER THAN RESCALES. The obvious fix -- multiply the high
    by the action's ratio whenever it predates the action -- is wrong, and the
    shipped data is what proves it. That CSV is MIXED. Measured across the
    fourteen flagged names, eleven highs sat on the pre-action scale and three
    (PGIL, PARAS, TDPOWERSYS) were already restated, because the nightly job
    re-downloads afresh and Yahoo restates some Indian symbols and not others.
    The recorded peak date cannot tell the two apart: PGIL's peak predates its
    split and was adjusted anyway. Rescaling on that rule would have divided
    three correct highs by two.

    So this makes no claim about the vendor's state. A corporate action dated
    AFTER the recorded peak means that peak was printed on a scale which may or
    may not survive in the file, and there is no way to tell from the file
    itself -- so the entry is dropped and momentum.py's max() falls through to
    the window high, which this codebase HAS adjusted and can vouch for. An
    action dated before the peak leaves the peak alone: it was printed on the
    current scale.

    The degradation is bounded and already documented -- ath_loader says the
    in-memory fallback "is NOT an all-time high" -- and it self-heals, because
    the next peak the nightly job records on the current scale restores trust.
    A high on a scale the stock no longer trades on is not the safer answer.
    """
    if highs is None or highs.empty or not events:
        return highs
    out = pd.to_numeric(highs, errors="coerce").copy()
    dates = (
        pd.to_datetime(peak_dates, errors="coerce")
        if peak_dates is not None and not peak_dates.empty
        else None
    )

    for event in events:
        symbol = event.get("symbol")
        if symbol not in out.index:
            continue
        try:
            when = pd.Timestamp(event["date"])
        except (KeyError, TypeError, ValueError):
            continue
        if dates is not None and symbol in dates.index:
            peak = dates.loc[symbol]
            if pd.notna(peak) and pd.Timestamp(peak) >= when:
                # Printed after the action, so already on the current scale.
                continue
        out.loc[symbol] = np.nan

    return out
