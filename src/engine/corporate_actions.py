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
