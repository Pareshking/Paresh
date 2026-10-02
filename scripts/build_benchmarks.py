"""Build and extend data/benchmarks.csv (Nifty 500, Nifty 50) without Yahoo.

    python scripts/build_benchmarks.py --seed      # Screener history, then NSE days
    python scripts/build_benchmarks.py --update    # NSE days since the last row
    python scripts/build_benchmarks.py --seed --ss --nse-days 0
                                                   # SS' whole daily history
    python scripts/build_benchmarks.py --backfill-from 2021-10-01 --nse-days 400
                                                   # weekdays the file lacks (weekly era)
    python scripts/build_benchmarks.py --kaggle nse_kaggle_raw/Datasets/INDEX --nse-days 0
                                                   # daily history back to 1999

NSE's daily bundle (the index rows of Pd<ddmmyy>.csv) is the record. SS'
index chart (daily, back to the index's start) and Screener's fill what NSE
does not give: the seed's older history, which
Screener serves weekly beyond its last year, and any recent session NSE
refuses. An NSE row always replaces a Screener row for the same date.

--nse-days bounds how many NSE bundles one run asks for (one request each,
DELAY_S apart). Days NSE has no bundle for are holidays and are skipped.
See src/loaders/benchmark_store.py.
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import date, timedelta

import pandas as pd
import requests

from src.core.market_time import ist_now
from src.loaders import benchmark_store as bs
from src.loaders import nse_bundle

DELAY_S = 1.5
SEED_DAYS = 1825  # Screener's chart window for the seed (weekly beyond a year)


def screener_rows(days: int, session: requests.Session | None = None) -> pd.DataFrame:
    """Both indices from Screener's charts, as benchmark rows."""
    from src.loaders.screener_loader import fetch_series, resolve_id

    session = session or requests.Session()
    cols = {}
    for column, slug in bs.SCREENER_IDS.items():
        cid = resolve_id(slug, session)
        got = fetch_series(cid, session, days=days) if cid else None
        if got is not None:
            close = got[0].dropna()
            close.index = pd.DatetimeIndex(close.index).normalize()
            cols[column] = close[~close.index.duplicated(keep="last")]
    if not cols:
        return pd.DataFrame(columns=bs.FIELDS[1:])
    frame = pd.DataFrame(cols).dropna(how="all")
    frame.index.name = "date"
    frame["source"] = "screener"
    return frame


def ss_rows(pages: int | None = None) -> pd.DataFrame:
    """Both indices from SS, daily (pages=None: back to the index's start)."""
    from src.loaders import ss_prices

    cols = {}
    for i, (column, symbol) in enumerate(bs.SS_IDS.items()):
        if i:
            time.sleep(ss_prices.DELAY_S)
        rows, _ = ss_prices.fetch_history(symbol, pages)
        if ss_prices.quality_problems(rows):
            continue
        cols[column] = pd.Series(rows["close"].astype(float).values,
                                 index=pd.DatetimeIndex(pd.to_datetime(rows["date"])))
    if not cols:
        return pd.DataFrame(columns=bs.FIELDS[1:])
    frame = pd.DataFrame(cols).dropna(how="all")
    frame.index.name = "date"
    frame["source"] = "ss"
    return frame


def kaggle_rows(directory) -> pd.DataFrame:
    """Both indices from the Kaggle dataset's INDEX folder (NIFTY 500.csv, NIFTY 50.csv)."""
    from pathlib import Path

    cols = {}
    for column, name in (("nifty500", "NIFTY 500"), ("nifty50", "NIFTY 50")):
        path = Path(directory) / f"{name}.csv"
        if not path.exists():
            continue
        raw = pd.read_csv(path)
        raw.columns = [c.strip().lower() for c in raw.columns]
        s = pd.Series(pd.to_numeric(raw["close"], errors="coerce").values,
                      index=pd.DatetimeIndex(pd.to_datetime(raw["date"])).normalize())
        cols[column] = s[~s.index.duplicated(keep="last")].dropna()
    if not cols:
        return pd.DataFrame(columns=bs.FIELDS[1:])
    frame = pd.DataFrame(cols).dropna(subset=["nifty500"]) if "nifty500" in cols else pd.DataFrame(cols)
    frame.index.name = "date"
    frame["source"] = "kaggle"
    return frame


def nse_rows(days: list[date], *, fetch=nse_bundle.fetch_bundle, sleep=time.sleep,
             log=print) -> pd.DataFrame:
    """One row per day NSE published, from the bundle's index rows."""
    rows = {}
    session = requests.Session()
    for i, day in enumerate(days):
        if i:
            sleep(DELAY_S)
        try:
            files = fetch(day, session)
        except nse_bundle.NSEBlocked as exc:
            log(f"NSE refused ({exc}); stopping after {len(rows)} days")
            break
        except Exception as exc:  # noqa: BLE001  one bad day must not end the run
            log(f"{day}: {type(exc).__name__}")
            continue
        if (i + 1) % 50 == 0:
            log(f"  {i + 1}/{len(days)} days asked, {len(rows)} sessions so far")
        if not files:
            continue  # a holiday, or not published yet
        body = nse_bundle.member(files, "pd")
        if body is None:
            continue
        closes = bs.index_closes(nse_bundle.parse_prices(body, day))
        if closes:
            rows[pd.Timestamp(day)] = closes
    frame = pd.DataFrame.from_dict(rows, orient="index", columns=bs.FIELDS[1:3])
    frame.index.name = "date"
    frame["source"] = "nse"
    return frame.dropna(how="all", subset=bs.FIELDS[1:3])


def weekdays_between(start: date, end: date) -> list[date]:
    """Every weekday from `start` to `end` inclusive."""
    out, d = [], start
    while d <= end:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def weekdays_after(last: date | None, today: date, limit: int) -> list[date]:
    """Weekdays after `last` up to `today`, oldest first, at most `limit` (the newest)."""
    start = (last + timedelta(days=1)) if last else today - timedelta(days=limit * 7 // 5 + 7)
    out, d = [], start
    while d <= today:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out[-limit:] if limit else []


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seed", action="store_true", help="start from Screener's history")
    ap.add_argument("--ss", action="store_true",
                    help="add SS' daily index history (whole history with --seed)")
    ap.add_argument("--update", action="store_true", help="add the NSE days since the last row")
    ap.add_argument("--kaggle", default=None,
                    help="the Kaggle dataset's INDEX folder: daily closes back to 1999 for dates the file lacks")
    ap.add_argument("--backfill-from", type=date.fromisoformat, default=None,
                    help="also ask NSE for weekdays from this date that have no row "
                         "(Screener's older history is weekly), newest first")
    ap.add_argument("--nse-days", type=int, default=30,
                    help="most NSE bundles to request this run (default 30)")
    args = ap.parse_args(argv)
    if not (args.seed or args.update or args.backfill_from or args.ss or args.kaggle):
        ap.error("pass --seed, --update, --backfill-from, --ss and/or --kaggle")

    frame = bs.read()
    before = len(frame)
    if args.seed:
        frame = bs.merge(frame, screener_rows(SEED_DAYS))
        frame = bs.merge(frame, screener_rows(365))  # daily for the last year
    if args.kaggle:
        frame = bs.merge(frame, kaggle_rows(args.kaggle))
    if args.ss:
        try:
            frame = bs.merge(frame, ss_rows(None if args.seed else 1))
        except Exception as exc:  # noqa: BLE001  NSE and Screener still serve
            print(f"SS skipped: {type(exc).__name__}: {exc}")
    today = ist_now().date()
    last_nse = frame.index[frame["source"] == "nse"].max() if len(frame) else None
    last = None if last_nse is None or pd.isna(last_nse) else last_nse.date()
    days = weekdays_after(last, today, args.nse_days)
    if days:
        frame = bs.merge(frame, nse_rows(days))
    if args.backfill_from:
        # Weekdays with no row at all: a Screener row (daily for its last year,
        # Fridays before) already carries the right close for its date.
        have = set(frame.index.date)
        gaps = [d for d in weekdays_between(args.backfill_from, today) if d not in have]
        gaps = sorted(gaps, reverse=True)[: args.nse_days]
        print(f"Backfill: {len(gaps)} weekdays with no row, newest first")
        if gaps:
            frame = bs.merge(frame, nse_rows(sorted(gaps)))
            bs.write(frame)  # keep what was fetched even if a later step fails
    if args.update and not args.seed:
        # Anything NSE did not give (a refusal, a late bundle) from Screener's
        # last year; an NSE row for the same date still wins.
        try:
            recent = screener_rows(365)
            newest = frame.index.max() if len(frame) else None
            if newest is not None:
                recent = recent[recent.index > newest]
            frame = bs.merge(frame, recent)
        except Exception as exc:  # noqa: BLE001
            print(f"Screener top-up skipped: {type(exc).__name__}")
    if frame.empty:
        print("::error::no benchmark rows from NSE or Screener")
        return 1
    bs.write(frame)
    counts = frame["source"].value_counts()
    print(f"BENCHMARKS rows={len(frame)} (+{len(frame) - before}) "
          + " ".join(f"{k}={int(counts.get(k, 0))}" for k in bs.SOURCE_RANK)
          + f" first={frame.index.min().date()} last={frame.index.max().date()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
