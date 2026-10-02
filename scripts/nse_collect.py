"""Collect NSE's daily bundle into R2, one file per trading day, and check it.

Record only: nothing here feeds the app yet. Screener stays the price the
ranking uses (owner, 2026-09-27) until NSE's record is complete and has been
compared against it.

Three datasets, each one small file per trading day, written once through the
same immutable publisher as every other archive dataset:

  nse/prices_daily       every security's OHLC, previous close, value, volume
  nse/corporate_actions  the book closures NSE listed that day, parsed
  nse/market_caps        every listed security's market cap
  nse/source_checks      where Screener disagrees with NSE that day
  nse/closed_days        a day NSE has no bundle for, a week or more after it
                         (a holiday): remembered so it is never asked again

Modes (combinable; each stops the whole run on the first refusal from NSE):

  --recent N     the last N weekdays NSE may have published and R2 lacks
  --backfill N   up to N older weekdays R2 lacks (neither a trading day nor a
                 known closed day), newest first, back to --since; NSE's
                 bundle archive reaches back to January 2010
  --max-minutes  stop starting new days after this long (inside the job limit)
  --check        compare the newest NSE day with Screener
  --probe DATE   print what a bundle holds and how it parses; writes nothing

    python scripts/nse_collect.py --recent 7 --backfill 120 --check
    python scripts/nse_collect.py --probe 2026-09-25 --probe 2017-03-15
"""

from __future__ import annotations

import argparse
import sys
import tempfile
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import requests

from src.core.market_time import ist_now
from src.engine import source_check
from src.loaders import nse_bundle

DATASETS = {
    "prices": ("nse/prices_daily", "archive/nse/prices_daily"),
    "corporate_actions": ("nse/corporate_actions", "archive/nse/corporate_actions"),
    "market_caps": ("nse/market_caps", "archive/nse/market_caps"),
    "source_checks": ("nse/source_checks", "archive/nse/source_checks"),
    "closed_days": ("nse/closed_days", "archive/nse/closed_days"),
}
SOURCE = "nse_pr_bundle"
PIPELINE = "nse-ledger-v1"
DELAY_S = 2.5
HISTORY_START = date(2023, 10, 1)
ARCHIVE_START = date(2010, 1, 1)   # NSE's PR bundles exist from here (probed 2026-10-02)
CLOSED_AFTER_DAYS = 7              # no bundle this long after the day: NSE was closed


# ── What R2 already holds ────────────────────────────────────────────────────

def present_dates(archive, dataset: str = DATASETS["prices"][0]) -> set[date]:
    prefix = f"archive/manifests/{dataset}/"
    out: set[date] = set()
    for key in archive.list_keys(prefix):
        rest = key[len(prefix):]
        if rest.endswith("/current.json"):
            try:
                out.add(date.fromisoformat(rest.split("/", 1)[0]))
            except ValueError:
                continue
    return out


def recent_weekdays(n: int, today: date) -> list[date]:
    """The last `n` weekdays up to `today`, newest first."""
    out, d = [], today
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d -= timedelta(days=1)
    return out


def load_calendar(path: str | None) -> list[date]:
    """Trading sessions from a price archive's index, when one is given."""
    if not path or not Path(path).exists():
        return []
    frame = pd.read_parquet(path, columns=[])
    idx = pd.DatetimeIndex(frame.index).normalize().unique()
    return sorted(d.date() for d in idx)


def weekdays(start: date, end: date) -> list[date]:
    """Every weekday from `start` to `end`: the calendar when none is given.

    A holiday costs one request, once: it is then recorded in nse/closed_days.
    """
    out, d = [], start
    while d <= end:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def backfill_dates(calendar: list[date], have: set[date], n: int,
                   start: date = HISTORY_START) -> list[date]:
    """Up to `n` calendar sessions R2 lacks, newest first."""
    missing = [d for d in calendar if d >= start and d not in have]
    return sorted(missing, reverse=True)[:n]


# ── Publishing ───────────────────────────────────────────────────────────────

def publish_tables(tables: dict[str, pd.DataFrame], day: date, workdir: Path,
                   publish) -> list[str]:
    """Write each non-empty table for `day` and publish it. Returns what went."""
    done = []
    for key, frame in tables.items():
        if frame is None or frame.empty:
            continue
        dataset, root = DATASETS[key]
        folder = workdir / day.isoformat()
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{key}.parquet"
        frame.to_parquet(path, index=False, compression="zstd")
        publish(path, dataset=dataset, source=SOURCE, key_root=root,
                pipeline_version=PIPELINE, release_tag="nse")
        done.append(key)
    return done


def collect(days: list[date], *, fetch, publish, workdir: Path,
            delay_s: float = DELAY_S, sleep=time.sleep, log=print,
            deadline: float | None = None, today: date | None = None,
            clock=time.monotonic) -> dict:
    """Fetch, parse and publish each day. Stops at the first refusal, or once
    `deadline` (a `clock` reading) has passed. A day with no bundle a week or
    more after it is published to nse/closed_days."""
    stats = {"published": [], "absent": [], "failed": [], "blocked": False,
             "closed": [], "out_of_time": False}
    for i, day in enumerate(days):
        if deadline is not None and clock() >= deadline:
            log(f"NSE_TIME budget spent; {len(days) - i} days left for the next run")
            stats["out_of_time"] = True
            break
        if i:
            sleep(delay_s)
        try:
            files = fetch(day)
        except nse_bundle.NSEBlocked as exc:
            log(f"NSE_BLOCKED at {day} ({exc}); stopping this run")
            stats["blocked"] = True
            break
        except requests.RequestException as exc:
            log(f"FETCH_ERROR {day}: {type(exc).__name__}")
            stats["failed"].append(day)
            continue
        if files is None:
            stats["absent"].append(day)
            if today is not None and (today - day).days >= CLOSED_AFTER_DAYS:
                closed = pd.DataFrame({"date": [day], "reason": ["no NSE bundle"]})
                publish_tables({"closed_days": closed}, day, workdir, publish)
                stats["closed"].append(day)
            continue
        try:
            tables = nse_bundle.parse_bundle(files, day)
        except Exception as exc:                 # one bad file never stops the run
            log(f"PARSE_ERROR {day}: {type(exc).__name__}: {exc}"[:300])
            stats["failed"].append(day)
            continue
        if "prices" not in tables or tables["prices"].empty:
            log(f"NO_PRICES {day}: bundle has {sorted(files)}")
            stats["failed"].append(day)
            continue
        sent = publish_tables(tables, day, workdir, publish)
        log(f"NSE_DAY {day} " + " ".join(f"{k}={len(tables[k])}" for k in sorted(tables))
            + f" published={','.join(sent)}")
        stats["published"].append(day)
    return stats


# ── Cross-source check ───────────────────────────────────────────────────────

def _closes(path: str | None, field: str = "Close") -> pd.DataFrame | None:
    if not path or not Path(path).exists():
        return None
    frame = pd.read_parquet(path)
    if not isinstance(frame.columns, pd.MultiIndex):
        return None
    out = frame.xs(field, axis=1, level=1)
    out.index = pd.DatetimeIndex(out.index).normalize()
    return out


def run_check(nse_prices: pd.DataFrame, screener_path: str | None,
              yahoo_path: str | None) -> pd.DataFrame:
    screener = _closes(screener_path)
    yahoo = _closes(yahoo_path)
    symbols = sorted(set(screener.columns) if screener is not None
                     else set(yahoo.columns) if yahoo is not None else [])
    return source_check.compare(nse_prices, screener, yahoo, symbols)


# ── Probe ────────────────────────────────────────────────────────────────────

def probe(day: date, fetch) -> None:
    files = fetch(day)
    if files is None:
        print(f"PROBE {day}: no bundle (404 or not a zip)")
        return
    print(f"PROBE {day}: {len(files)} files")
    for name in sorted(files):
        body = files[name]
        print(f"  {name}  {len(body):,} bytes")
        if name.lower().endswith(".csv"):
            for line in body.decode("utf-8", "replace").splitlines()[:3]:
                print(f"      | {line[:200]}")
    for key, frame in nse_bundle.parse_bundle(files, day).items():
        print(f"  PARSED {key}: {len(frame)} rows")
        print(frame.head(3).to_string(max_colwidth=40))
        if key == "corporate_actions" and len(frame):
            print(frame["kind"].value_counts().to_string())


# ── Entry point ──────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--recent", type=int, default=0)
    ap.add_argument("--backfill", type=int, default=0)
    ap.add_argument("--calendar", help="parquet whose index lists trading sessions "
                                       "(default: weekdays, less known closed days)")
    ap.add_argument("--since", default=HISTORY_START.isoformat(),
                    help="oldest trading day the backfill may reach (YYYY-MM-DD)")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--screener", help="Screener store parquet, for --check")
    ap.add_argument("--max-minutes", type=float, default=None,
                    help="stop starting new days after this many minutes")
    ap.add_argument("--probe", action="append", default=[],
                    help="YYYY-MM-DD, or 'latest'; repeatable")
    ap.add_argument("--delay", type=float, default=DELAY_S)
    ap.add_argument("--dates", default="",
                    help="YYYY-MM-DD days to collect if R2 lacks them, space- or "
                         "comma-separated; weekend special sessions included "
                         "(a Budget Sunday, a muhurat session)")
    args = ap.parse_args(argv)

    session = requests.Session()

    def fetch(day):
        return nse_bundle.fetch_bundle(day, session=session)

    today = ist_now().date()
    for p in args.probe:
        if p == "latest":
            for d in recent_weekdays(5, today):
                files = fetch(d)
                if files is not None:
                    p = d.isoformat()
                    break
        probe(datetime.strptime(p, "%Y-%m-%d").date(), fetch)
        time.sleep(args.delay)
    if not (args.recent or args.backfill or args.check or args.dates.strip()):
        return 0

    from scripts.r2_publish import publish
    from src.storage.r2 import R2Archive, R2Config

    archive = R2Archive(R2Config.from_env())
    have = present_dates(archive)
    print(f"NSE_ARCHIVE holds {len(have)} days"
          + (f", {min(have)} to {max(have)}" if have else ""))

    days = [d for d in recent_weekdays(args.recent, today) if d not in have] if args.recent else []
    extra = [date.fromisoformat(x) for x in args.dates.replace(",", " ").split()]
    days += [d for d in extra if d not in have and d not in days]
    if args.backfill:
        since = date.fromisoformat(args.since)
        closed = present_dates(archive, DATASETS["closed_days"][0])
        cal = load_calendar(args.calendar) or weekdays(since, today - timedelta(days=1))
        known = have | closed | set(days)
        days += [d for d in backfill_dates(cal, known, args.backfill, start=since)]
        print(f"NSE_BACKFILL since {since}: {sum(1 for d in cal if d >= since and d not in known)} "
              f"days to go ({len(closed)} known closed days), {len(days)} this run")

    blocked = False
    with tempfile.TemporaryDirectory() as tmp:
        deadline = time.monotonic() + args.max_minutes * 60 if args.max_minutes else None
        stats = collect(days, fetch=fetch, publish=publish, workdir=Path(tmp),
                        delay_s=args.delay, deadline=deadline, today=today)
        blocked = stats["blocked"]
        print(f"NSE_COLLECT published={len(stats['published'])} "
              f"absent={len(stats['absent'])} closed={len(stats['closed'])} "
              f"failed={len(stats['failed'])} "
              f"blocked={int(blocked)}")
        if stats["absent"]:
            print("  no bundle: " + ", ".join(d.isoformat() for d in stats["absent"][:20]))

        if args.check:
            have = present_dates(archive)
            if not have:
                print("NSE_CHECK skipped: no NSE day in the archive")
            else:
                from src.storage.reader import R2DatasetReader
                newest = max(have)
                reader = R2DatasetReader(archive)
                prices = reader.read_parquet(
                    reader.resolve_current(DATASETS["prices"][0], as_of=newest.isoformat()))
                flags = run_check(prices, args.screener, None)
                counts = flags["check"].value_counts().to_dict() if len(flags) else {}
                print(f"NSE_CHECK {newest} flags={len(flags)} {counts}")
                if len(flags):
                    print(flags.head(40).to_string(index=False))
                    publish_tables({"source_checks": flags}, newest, Path(tmp), publish)

    if blocked:
        print("::warning::NSE refused this runner; the rest resumes on the next run")
    return 0


if __name__ == "__main__":
    sys.exit(main())
