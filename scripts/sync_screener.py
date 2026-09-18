"""Nightly screener.in pull, accumulated into our own price history.

Separate from sync_data.py on purpose. That job is the Yahoo pipeline and the
thing production ranks off today; this one builds a second, independent history
that has to prove itself over weeks before anything depends on it. Coupling them
would mean a screener outage could fail the run that feeds the live screener.

WHAT THIS BUYS. Screener serves a session the morning after it closes. Yahoo
publishes an Indian session over a day and a half and sometimes stalls: on
2026-09-17 it reached 378 of 750 symbols and stayed there for over two days,
while screener had every missing name.

WHAT IT COSTS. One request per symbol per night, paced, which put a 30-symbol
sample at 1.74s each and projects the full universe at ~22 minutes.

THE LIMIT THAT SHAPES EVERYTHING. Daily resolution reaches back about a year
and is downsampled to weekly beyond it. There is no way to ask for more. So the
archive cannot be bought in one request -- it is accumulated, one night at a
time, which is why this job starts running before anything consumes it. Every
night not collected is a day of daily history that cannot be recovered later.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pandas as pd  # noqa: E402

from src.core import startup_metrics as metrics  # noqa: E402
from src.core.config import SCREENER_DELAY_S, SCREENER_PRICES_FILE  # noqa: E402
from src.core.market_time import session_is_complete  # noqa: E402
from src.loaders import screener_loader as sl  # noqa: E402
from src.loaders.indices_loader import fetch_indices_data  # noqa: E402


def _drop_unsettled(frame: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Drop any session still trading.

    Screener serves the running price during market hours, exactly as Yahoo
    does. Accumulating that would freeze an intraday quote into the history
    permanently as though it were a close -- and unlike a vendor's late
    backfill, nothing would ever correct it, because tomorrow's response no
    longer contains today's intraday value to overwrite it with.
    """
    if frame is None or frame.empty:
        return frame, []
    idx = pd.DatetimeIndex(frame.index)
    keep = [session_is_complete(d.date()) for d in idx]
    dropped = [str(d.date()) for d, k in zip(idx, keep) if not k]
    return frame.loc[keep], dropped


def run() -> int:
    started = datetime.now()
    print(f"[{started:%Y-%m-%d %H:%M:%S}] Screener sync starting…")

    universe_df = fetch_indices_data(["NIFTY TOTAL MARKET"])
    if universe_df.empty or "Symbol" not in universe_df:
        print("[ERROR] Universe load returned empty; nothing to fetch.")
        return 1
    symbols = sorted(universe_df["Symbol"].dropna().unique().tolist())
    print(f"Universe: {len(symbols)} symbols")

    ids = sl.load_ids()
    print(f"Known company ids: {len(ids)} (the rest resolve on first sight)")

    frame, ids, unresolved = sl.fetch_universe(symbols, ids=ids, delay_s=SCREENER_DELAY_S)
    sl.save_ids(ids)
    print(f"Fetched {frame.shape[1] // 2 if not frame.empty else 0} symbols; "
          f"{len(unresolved)} unresolved")
    if unresolved[:8]:
        print(f"  unresolved sample: {unresolved[:8]}")

    if frame.empty:
        print("Nothing came back; leaving the store untouched.")
        return 1

    frame, dropped = _drop_unsettled(frame)
    if dropped:
        print(f"Dropped {len(dropped)} unsettled session(s): {dropped}")

    merged, new_rows, preserved = sl.merge_into_store(frame)
    c = sl.closes(merged)
    print(f"\nStore: {merged.shape[0]} sessions x {c.shape[1]} symbols "
          f"({str(c.index[0])[:10]} -> {str(c.index[-1])[:10]})")
    print(f"  +{new_rows} new session(s), {preserved} cell(s) preserved from earlier runs")

    cov = c.notna().sum(axis=1)
    print("\n  last 5 sessions by coverage:")
    for d in c.index[-5:]:
        print(f"    {str(d)[:10]}  {int(cov.loc[d]):4d}/{c.shape[1]}  "
              f"{cov.loc[d] / c.shape[1] * 100:5.1f}%")

    facts = metrics.snapshot().get("facts", {})
    if str(facts.get("screener_run_complete")) == "no":
        print("\n  NOTE: the site asked us to stop partway. What arrived is kept; "
              "the rest is left for the next run.")
    print(f"\n[{datetime.now():%Y-%m-%d %H:%M:%S}] Screener sync done "
          f"({(datetime.now() - started).total_seconds() / 60:.1f} min).")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
