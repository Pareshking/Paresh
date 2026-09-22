"""One-time Screener deep-history bootstrap.

Screener returns daily observations for roughly the recent year and weekly
observations farther back. This job deliberately requests the long window once
(10 years) and merges it into the existing source-separated Screener store.

After this bootstrap, the normal daily job continues to accumulate the recent
daily window. The older weekly observations remain in the same store and are
never discarded.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pandas as pd

from src.core import startup_metrics as metrics
from src.core.config import SCREENER_DEEP_HISTORY_DAYS, SCREENER_DELAY_S
from src.core.market_time import session_is_complete
from src.loaders import screener_loader as sl
from src.loaders.indices_loader import fetch_indices_data

def _drop_unsettled(frame: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    if frame is None or frame.empty:
        return frame, []
    idx = pd.DatetimeIndex(frame.index)
    keep = [session_is_complete(d.date()) for d in idx]
    dropped = [str(d.date()) for d, k in zip(idx, keep) if not k]
    return frame.loc[keep], dropped


def run() -> int:
    started = datetime.now()
    print(f"[{started:%Y-%m-%d %H:%M:%S}] Screener 10Y bootstrap starting…")

    universe_df = fetch_indices_data(["NIFTY TOTAL MARKET"])
    if universe_df.empty or "Symbol" not in universe_df:
        print("[ERROR] Universe load returned empty; refusing bootstrap.")
        return 1
    symbols = sorted(universe_df["Symbol"].dropna().unique().tolist())
    print(f"Universe: {len(symbols)} symbols")

    ids = sl.load_ids()
    print(f"Known company ids: {len(ids)}")

    frame, ids, unresolved = sl.fetch_universe(
        symbols,
        days=SCREENER_DEEP_HISTORY_DAYS,
        ids=ids,
        delay_s=SCREENER_DELAY_S,
    )
    sl.save_ids(ids)
    fetched = frame.shape[1] // 2 if not frame.empty else 0
    print(f"Fetched {fetched} symbols; {len(unresolved)} unresolved")
    if unresolved[:8]:
        print(f"  unresolved sample: {unresolved[:8]}")

    if frame.empty:
        print("Nothing came back; leaving the store untouched.")
        return 1

    frame, dropped = _drop_unsettled(frame)
    if dropped:
        print(f"Dropped {len(dropped)} unsettled session(s): {dropped}")

    merged, new_rows, preserved = sl.merge_into_store(frame)
    closes = sl.closes(merged)
    print(
        f"Store: {merged.shape[0]} sessions x {closes.shape[1]} symbols "
        f"({str(closes.index[0])[:10]} -> {str(closes.index[-1])[:10]})"
    )
    print(f"  +{new_rows} new session(s), {preserved} cell(s) preserved")

    if closes.empty:
        print("[ERROR] Bootstrap produced an empty close matrix.")
        return 1

    older = closes.index < (closes.index.max() - pd.Timedelta(days=370))
    old_count = int(older.sum())
    print(f"  historical sessions older than 370 days: {old_count}")
    if old_count < 400:
        print("[ERROR] Deep history did not produce the expected weekly-depth evidence.")
        return 1

    coverage = closes.notna().sum(axis=1)
    print("  earliest 5 sessions by coverage:")
    for d in closes.index[:5]:
        print(
            f"    {str(d)[:10]} {int(coverage.loc[d]):4d}/{closes.shape[1]} "
            f"{coverage.loc[d] / closes.shape[1] * 100:5.1f}%"
        )

    facts = metrics.snapshot().get("facts", {})
    if str(facts.get("screener_run_complete")) == "no":
        print("[ERROR] Screener stopped partway; refusing to publish bootstrap.")
        return 1

    print(
        f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Screener 10Y bootstrap done "
        f"({(datetime.now() - started).total_seconds() / 60:.1f} min)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
