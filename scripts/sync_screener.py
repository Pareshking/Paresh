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


def current_universe_delta(current_symbols: list[str], stored_symbols: list[str]) -> tuple[list[str], list[str]]:
    """Return (new_current, exited) using symbol identity only.

    Index reclassification is deliberately invisible here: if a symbol already
    exists in the Screener store, moving from SMALL250 to MID150 is not a new
    security and must not trigger a historical download. Conversely, a symbol
    newly present in the authoritative NSE universe is an acquisition event,
    even when another old symbol for the same index has disappeared.
    """
    current = {str(s).strip().upper() for s in current_symbols if str(s).strip()}
    stored = {str(s).strip().upper() for s in stored_symbols if str(s).strip()}
    return sorted(current - stored), sorted(stored - current)


def _concat_fresh(*frames: pd.DataFrame) -> pd.DataFrame:
    """Combine independent Screener fetches without manufacturing columns."""
    usable = [frame for frame in frames if frame is not None and not frame.empty]
    if not usable:
        return pd.DataFrame()
    result = pd.concat(usable, axis=1)
    if result.columns.duplicated().any():
        result = result.loc[:, ~result.columns.duplicated(keep="last")]
    return result.sort_index()


def run() -> int:
    started = datetime.now()
    print(f"[{started:%Y-%m-%d %H:%M:%S}] Screener sync starting…")

    universe_df = fetch_indices_data(["NIFTY TOTAL MARKET"])
    if universe_df.empty or "Symbol" not in universe_df:
        print("[ERROR] Universe load returned empty; nothing to fetch.")
        return 1
    symbols = sorted(universe_df["Symbol"].dropna().unique().tolist())
    print(f"Universe: {len(symbols)} symbols")

    stored = sl.load_store()
    stored_closes = sl.closes(stored)
    stored_symbols = stored_closes.columns.astype(str).str.strip().str.upper().tolist() if not stored_closes.empty else []
    new_current, exited = current_universe_delta(symbols, stored_symbols)
    print(f"Stored Screener symbols: {len(set(stored_symbols))}")
    print(f"New current symbols requiring history: {len(new_current)}")
    if new_current:
        print(f"  FORCED Screener historical acquisition: {new_current}")
    print(f"Exited current symbols (history retained, no further acquisition): {len(exited)}")

    ids = sl.load_ids()
    print(f"Known company ids: {len(ids)} (the rest resolve on first sight)")

    # A newly arrived current symbol gets its own acquisition pass first. This
    # is intentionally separate from the ordinary nightly sweep: it makes
    # universe churn a hard data-integrity gate rather than something that can
    # be missed because a later broad fetch was partial or rate-limited.
    forced = pd.DataFrame()
    forced_unresolved: list[str] = []
    if new_current:
        forced, ids, forced_unresolved = sl.fetch_universe(
            new_current, ids=ids, delay_s=SCREENER_DELAY_S
        )
        forced_fetched = sl.closes(forced).columns.astype(str).str.upper().tolist() if not forced.empty else []
        still_missing = sorted(set(new_current) - set(forced_fetched))
        if still_missing:
            print(
                "[ERROR] New current symbols were not acquired from Screener: "
                f"{still_missing}"
            )
            if forced_unresolved:
                print(f"  unresolved: {forced_unresolved}")
            return 2
        print(f"  Forced acquisition complete: {len(forced_fetched)}/{len(new_current)} symbols")

    # Existing current symbols continue through the normal paced sweep. New
    # symbols are excluded because they were already fetched above; this avoids
    # doubling requests while preserving the explicit forced-acquisition gate.
    regular_symbols = [symbol for symbol in symbols if symbol not in set(new_current)]
    frame_regular = pd.DataFrame()
    unresolved: list[str] = []
    if regular_symbols:
        frame_regular, ids, unresolved = sl.fetch_universe(
            regular_symbols, ids=ids, delay_s=SCREENER_DELAY_S
        )
    frame = _concat_fresh(forced, frame_regular)
    unresolved = forced_unresolved + unresolved
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
