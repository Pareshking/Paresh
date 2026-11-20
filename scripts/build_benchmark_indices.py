#!/usr/bin/env python3
"""Build and extend data/benchmark_indices.csv from Screener's index charts (S148, S149).

    python scripts/build_benchmark_indices.py --seed     # all history Screener has
    python scripts/build_benchmark_indices.py --update   # the last 400 days, daily

Every run then compares each index with an ETF that tracks it over the last
month and prints the result; a pair that disagrees by more than
ETF_TOLERANCE_PTS is a warning in the job log and exit code 2 with
--strict. The ETFs are fetched for the check only and are not written.

See src/loaders/benchmark_indices.py for why these come from Screener and not
NSE's bundle.
"""

from __future__ import annotations

import argparse
import sys
import time

import pandas as pd
import requests

from src.core.market_time import session_is_complete
from src.loaders import benchmark_indices as bi
from src.loaders.screener_loader import fetch_series, resolve_id

DELAY_S = 1.0
DAILY_DAYS = 400
SEED_DAYS = 10000


def complete_only(close: pd.Series) -> pd.Series:
    """Drop rows for sessions that have not closed. Screener's chart serves the
    live or pre-open quote as a row dated today: on 20 Nov 2026 at 08:20 IST it
    returned Nifty 50 at 25,434.40 for a session that had not opened."""
    keep = [session_is_complete(d.date()) for d in close.index]
    return close[keep]


def _closes(slug: str, session: requests.Session, days: int) -> pd.Series | None:
    cid = resolve_id(slug, session)
    got = fetch_series(cid, session, days=days) if cid else None
    if got is None:
        return None
    close = got[0].dropna()
    close.index = pd.DatetimeIndex(close.index).normalize()
    return complete_only(close[~close.index.duplicated(keep="last")].sort_index())


def rows_for(key: str, slug: str, session: requests.Session, seed: bool) -> pd.DataFrame:
    """The index's rows: the long (weekly) history when seeding, then the daily last 400 days."""
    parts = []
    if seed:
        long = _closes(slug, session, SEED_DAYS)
        if long is not None:
            parts.append(pd.DataFrame({"date": long.index, "index": key, "close": long.values,
                                       "source": "screener_weekly"}))
        time.sleep(DELAY_S)
    daily = _closes(slug, session, DAILY_DAYS)
    if daily is not None:
        parts.append(pd.DataFrame({"date": daily.index, "index": key, "close": daily.values,
                                   "source": "screener_daily"}))
    return bi.merge(*parts) if len(parts) == 2 else (parts[0] if parts else pd.DataFrame(columns=bi.FIELDS))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--seed", action="store_true")
    mode.add_argument("--update", action="store_true")
    ap.add_argument("--strict", action="store_true", help="exit 2 when an ETF check disagrees")
    args = ap.parse_args(argv)

    session = requests.Session()
    frame = bi.read()
    if not frame.empty:   # a row written before its session closed, by an earlier run
        frame = frame[[session_is_complete(pd.Timestamp(d).date()) for d in frame["date"]]]
    for i, (key, (name, slug, _etf)) in enumerate(bi.SERIES.items()):
        if i:
            time.sleep(DELAY_S)
        try:
            new = rows_for(key, slug, session, args.seed)
        except Exception as exc:  # noqa: BLE001  one index must not end the run
            print(f"{name}: {type(exc).__name__}: {exc}")
            continue
        if new.empty:
            print(f"{name}: no closes from Screener")
            continue
        frame = bi.merge(frame, new)
        last = new["date"].max()
        print(f"{name}: {len(new)} rows, last {pd.Timestamp(last):%d %b %Y}")
    bi.write(frame)

    bad = 0
    for key, (name, _slug, etf) in bi.SERIES.items():
        if not etf:
            continue
        close = bi.series(key, frame=frame)
        if close.empty:
            continue
        time.sleep(DELAY_S)
        try:
            etf_close = _closes(etf, session, DAILY_DAYS)
        except Exception as exc:  # noqa: BLE001
            print(f"ETF check {name} vs {etf}: {type(exc).__name__}")
            continue
        if etf_close is None:
            print(f"ETF check {name} vs {etf}: no ETF closes")
            continue
        ri, re_, ok = bi.etf_check(close, etf_close, close.index[-1])
        line = (f"ETF check {name} vs {etf}, 1M: index "
                f"{'—' if ri is None else f'{ri:+.2f}%'}, ETF {'—' if re_ is None else f'{re_:+.2f}%'}")
        if ok:
            print(line + " · agree")
        else:
            bad += 1
            print(f"::warning::{line} · DISAGREE (tolerance {bi.ETF_TOLERANCE_PTS} pts)")
    return 2 if (bad and args.strict) else 0


if __name__ == "__main__":
    sys.exit(main())
