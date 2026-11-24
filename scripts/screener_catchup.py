#!/usr/bin/env python3
"""Decide whether the nightly price chain needs a catch-up run (owner, 24 Nov 2026).

GitHub's scheduler sometimes drops the nightly Screener sync outright: on 23 Nov
2026 the 17:07 UTC slot and both daily-sync slots (17:30, 02:00 UTC) never
started, and the site kept 20 Nov's closes into the next morning.
`.github/workflows/screener_catchup.yml` runs this twice a night and acts only
when the published data is behind:

  screener  the published Screener store does not reach the newest session NSE
            has settled -> dispatch the Screener sync (the daily sync chains
            after it, as on a normal night);
  daily     the store reaches it but no daily sync has succeeded since the
            store was last published -> dispatch the daily sync;
  none      both are current -> the run ends green with nothing to do.

The target is the newest weekday past its settle window (22:30 IST) that NSE's
published list does not mark as a holiday, so a holiday or a weekend asks for
nothing. When the list does not cover the year, the answer is "cannot tell" and
the chain runs, as before this job existed.

Usage:
  screener_catchup.py --store PATH --store-published ISO --daily-success ISO|""
Prints one word (screener, daily or none) and a reason on stderr.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def target_session(now: datetime | None = None) -> date | None:
    """The newest session the published closes should already hold, or None (cannot tell)."""
    from src.core.market_time import ist_now, recent_trading_days, session_is_downloadable
    from src.loaders.nse_calendar import covers, not_a_session

    reference = now or ist_now()
    for day in recent_trading_days(count=10, as_of=reference.date(), max_lookback_days=30):
        if not covers(day.year):
            return None
        if not_a_session(day):
            continue
        if session_is_downloadable(day, now=reference):
            return day
    return None


def store_last_session(path: str) -> date | None:
    """The last date in the Screener store, read from its index only."""
    import pandas as pd

    p = Path(path)
    if not p.exists():
        return None
    try:
        frame = pd.read_parquet(p, columns=[])
    except Exception:  # noqa: BLE001  (a store we cannot read is a store to rebuild)
        return None
    if not len(frame.index):
        return None
    return pd.Timestamp(frame.index.max()).date()


def _when(text: str | None) -> datetime | None:
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def decide(target: date | None, store_last: date | None, store_published: datetime | None,
           daily_success: datetime | None) -> tuple[str, str]:
    if target is None:
        return "screener", "cannot tell which session is due (NSE's holiday list does not cover the year); running as before"
    if store_last is None or store_last < target:
        return "screener", f"the Screener store ends {store_last or 'nowhere'}; {target} is due"
    if store_published is not None and (daily_success is None or daily_success < store_published):
        return "daily", (f"the store reaches {target} (published {store_published:%d %b %H:%M} UTC) but no daily sync has "
                         "succeeded since")
    return "none", f"the store reaches {target} and a daily sync has run since it was published: nothing to catch up"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--store", required=True)
    ap.add_argument("--store-published", default="")
    ap.add_argument("--daily-success", default="")
    a = ap.parse_args()
    action, why = decide(target_session(), store_last_session(a.store), _when(a.store_published), _when(a.daily_success))
    print(why, file=sys.stderr)
    print(action)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
