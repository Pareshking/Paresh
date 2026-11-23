#!/usr/bin/env python3
"""Fail when the long NSE file steps where Screener does not: an action our parser missed (S213).

    python scripts/check_long_against_screener.py --long data_cache/nse_long/nse_long_close.parquet \
        --screener screener_prices.parquet [--sessions 60]

The long file adjusts NSE's raw closes for the actions NSE lists; Screener adjusts its own. On a
session both price, a one-day move that is 50% or more in one and not the other means one of
them missed a split, bonus or consolidation. On 19 Oct 2026 the long file read CCAVENUE +840%
(13.83 to 130.05) where Screener read -6%: NSE had listed the 10:1 as "CNSLDATNRE1 TO RS10",
which the parser did not read, with no ex-date. Over 1,140 stocks and 272 sessions to 20 Nov
2026 that was the only such day. The Saturday audits compare against Screener's frozen
3 Oct 2026 copy, so they could not see it; this runs every night against the live store.

Smaller gaps are expected and are not flagged: dividends of 10% or more come out of the long
file and stay in Screener (FMGOETZE, 4 Sep 2026: -3.0% against -18.3%, a Rs 94 payout), and
the two can price a demerger differently. Exit 1 lists each day found; 0 when none.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

BAND = np.log(1.5)          # a one-day move this large (either way) is a corporate action's size


def disagreements(long: pd.DataFrame, screener: pd.DataFrame, sessions: int = 60) -> pd.DataFrame:
    """One row per (symbol, session) where one source moved 50%+ and the other did not follow."""
    cols = sorted(set(long.columns) & set(screener.columns))
    idx = long.index.intersection(screener.index).sort_values()[-(sessions + 1):]
    if not cols or len(idx) < 2:
        return pd.DataFrame(columns=["symbol", "date", "long_move", "screener_move"])
    lo, sc = long.reindex(index=idx, columns=cols), screener.reindex(index=idx, columns=cols)
    both = lo.notna() & sc.notna()
    # Carried across a halt, so the first session after it is compared with the last before.
    ml = np.log(lo.ffill() / lo.ffill().shift(1))
    ms = np.log(sc.ffill() / sc.ffill().shift(1))
    hit = both & ((ml.abs() > BAND) | (ms.abs() > BAND)) & ((ml - ms).abs() > BAND)
    rows = [{"symbol": c, "date": d.date().isoformat(), "long_move": round(float(np.exp(ml.at[d, c])), 4),
             "screener_move": round(float(np.exp(ms.at[d, c])), 4)}
            for c in cols for d in idx[hit[c].to_numpy()]]
    return pd.DataFrame(rows, columns=["symbol", "date", "long_move", "screener_move"])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--long", type=Path, required=True)
    ap.add_argument("--screener", type=Path, required=True, help="the release's screener_prices.parquet")
    ap.add_argument("--sessions", type=int, default=60)
    args = ap.parse_args()
    from src.loaders import price_source as ps

    long = pd.read_parquet(args.long)
    if "date" in long.columns:
        long = long.set_index("date")
    long.index = pd.DatetimeIndex(long.index)
    frames = ps.from_screener(pd.read_parquet(args.screener))
    if frames is None:
        print("::error::the Screener store could not be read")
        return 1
    found = disagreements(long, frames.close, args.sessions)
    if found.empty:
        print(f"long file and Screener agree on every 50%+ move over the last {args.sessions} sessions")
        return 0
    for r in found.itertuples():
        print(f"::error::{r.symbol} {r.date}: long file x{r.long_move}, Screener x{r.screener_move}; "
              "an action one of them did not apply (docs/DATA_CORRECTNESS.md section 5)")
    return 1


if __name__ == "__main__":
    sys.exit(main())
