#!/usr/bin/env python3
"""Build or extend the store of every NSE index (S168, src/loaders/nse_indices.py).

    python scripts/collect_nse_indices.py --store nse_indices.parquet --raw-dir DIR
        # build from NSE's files already downloaded, named ind_close_all_DDMMYYYY
        # or YYYYMMDD so each is checked against its session
    python scripts/collect_nse_indices.py --store nse_indices.parquet --fetch --from-r2
        # start from the published store in R2, download every session after its
        # last date, then add them (the nightly run)
    python scripts/collect_nse_indices.py --store nse_indices.parquet --fetch --backfill
        # no store yet: every session from 21 Feb 2012 (about 3,800 requests, once)

The nightly run never backfills by itself: a store it cannot read from R2 is a
failure, not an invitation to download fourteen years again.

Writes the store only when every new row passes the guard: no index printed twice
in one session, and no stored close changed by more than a paisa. Exits 1 and
writes nothing otherwise. A session NSE has no file for (a holiday, 404) is
skipped; an answer that is not that session's CSV (an HTML page, or a file
dated another day) is reported and skipped.

Prints one summary line, `NSE_INDICES rows=... keys=... first=... last=... added=...`,
and the rename seams with whether each is continuous (points change equals the
close difference).
"""
from __future__ import annotations

import argparse
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.loaders import nse_indices as ni  # noqa: E402

# Measured 21 Nov 2026 from a cloud machine: 160 requests, four at a time, in 20 s
# with no refusal (0.12 s a day); one at a time 0.52 s. The first backfill ran one
# at a time with a 1.2 s pause and needed about three hours for 2012-2026.
WORKERS = 4
DELAY_S = 0.1


def _fetch(day: pd.Timestamp) -> bytes | None:
    url = ni.URL.format(d=day)
    for attempt in range(5):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            raw = urllib.request.urlopen(req, timeout=30).read()
            time.sleep(DELAY_S)
            return raw
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return None
            # 403/429/5xx: NSE asking us to slow down, or a bad moment; back off.
            time.sleep(5 * 2 ** attempt)
        except Exception:  # noqa: BLE001 -- a dropped connection: try again
            time.sleep(5 * 2 ** attempt)
    raise RuntimeError(f"NSE did not answer for {day:%d %b %Y}")


def from_dir(directory: Path, aliases: dict) -> tuple[pd.DataFrame, list[str]]:
    frames, skipped = [], []
    for path in sorted(directory.glob("*.csv")):
        try:
            frames.append(ni.parse_file(path.read_bytes(), aliases, ni.session_from_name(path.stem)))
        except ni.NotAnIndexFile as exc:
            skipped.append(f"{path.name}: {exc}")
    return (pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=ni.STORE_COLUMNS)), skipped


def fetch_since(last: pd.Timestamp | None, aliases: dict, until: pd.Timestamp,
                workers: int = WORKERS) -> tuple[pd.DataFrame, list[str]]:
    start = ni.FIRST_SESSION if last is None else last + pd.Timedelta(days=1)
    frames, skipped = [], []
    # Weekend sessions happen (Muhurat, budget days), so every day is asked;
    # a day without a session is a 404 and costs one request. Fetched `workers` at
    # a time; read in date order, so the result does not depend on who answered first.
    days = list(pd.date_range(start, until, freq="D"))
    with ThreadPoolExecutor(max(1, workers)) as pool:
        answers = list(pool.map(_fetch, days))
    for day, raw in zip(days, answers):
        if raw is None:
            continue
        try:
            frames.append(ni.parse_file(raw, aliases, day))
        except ni.NotAnIndexFile as exc:
            skipped.append(f"{day:%Y-%m-%d}: {exc}")
    return (pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=ni.STORE_COLUMNS)), skipped


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--store", type=Path, required=True)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--raw-dir", type=Path)
    src.add_argument("--fetch", action="store_true")
    ap.add_argument("--until", default=None, help="last day to ask for (default: today); a backfill in batches "
                    "passes a year end, publishes, and the next run continues from the published store")
    ap.add_argument("--workers", type=int, default=WORKERS, help="requests at a time")
    ap.add_argument("--from-r2", action="store_true", help="read the published store from R2 first")
    ap.add_argument("--backfill", action="store_true", help="allow starting with no store (from 21 Feb 2012)")
    args = ap.parse_args()

    aliases = ni.load_aliases()
    if args.from_r2 and not args.store.exists():
        try:
            from src.storage.r2 import R2Archive, R2Config
            from src.storage.reader import R2DatasetReader
            reader = R2DatasetReader(R2Archive(R2Config.from_env()))
            reader.read_parquet(reader.resolve_current(ni.DATASET)).to_parquet(args.store, index=False)
        except Exception as exc:  # noqa: BLE001
            if not args.backfill:
                print(f"::error::the published NSE indices store could not be read ({type(exc).__name__}); "
                      "run with --backfill to build it from 21 Feb 2012")
                return 1
            print(f"::warning::no published store ({type(exc).__name__}); backfilling from 21 Feb 2012")
    stored = pd.read_parquet(args.store) if args.store.exists() else None
    if args.fetch and stored is None and not args.backfill:
        print("::error::no store to extend; pass --backfill to build it from 21 Feb 2012")
        return 1
    if args.raw_dir:
        new, skipped = from_dir(args.raw_dir, aliases)
    else:
        last = None if stored is None or stored.empty else pd.Timestamp(stored["date"].max())
        until = pd.Timestamp(args.until) if args.until else pd.Timestamp.now().normalize()
        new, skipped = fetch_since(last, aliases, until, args.workers)
    for line in skipped:
        print(f"::warning::not an index file, skipped: {line}")
    try:
        out = ni.merge(stored, new)
    except ValueError as exc:
        print(f"::error::NSE indices NOT written: {exc}")
        return 1
    # Decision B (owner, 21 Nov 2026): days NSE has no file for, derived and marked.
    out = ni.derive_missing(out)
    added = len(out) - (0 if stored is None else len(stored))
    out.to_parquet(args.store, index=False)
    print(f"NSE_INDICES rows={len(out)} keys={out['key'].nunique()} first={out['date'].min():%Y-%m-%d} "
          f"last={out['date'].max():%Y-%m-%d} added={added} derived={int(out['derived'].sum())}")
    sm = ni.seams(out)
    for r in sm.itertuples():
        print(f"SEAM {r.key} {r.date:%Y-%m-%d} {r.old!r} -> {r.new!r} continuous={r.continuous}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
