"""Fill R2's NSE history back to 2010 from NSE's own record, without 3,400 bundle requests.

    python scripts/import_nse_history.py --actions --from-year 2010
    python scripts/import_nse_history.py --prices --mirror mirror/data --max-minutes 300

--actions  NSE's corporate-action list, one request per year per board (equities,
         SME), published one file per year to nse/corporate_actions_history.
--prices   every session in the GitHub mirror of NSE's full bhavcopy that R2's
         nse/prices_daily lacks, oldest first, published one file per day in
         the shape NSE's bundle gives (src/loaders/nse_backfill.py). No request
         goes to NSE. R2 is re-read every --refresh days, so a day the bundle
         collector publishes meanwhile is not published twice.

The bundle collector (scripts/nse_collect.py) still fills what the mirror
lacks -- the sessions before 10 Jun 2010 -- and every new day.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
import time
from concurrent.futures import ProcessPoolExecutor
from datetime import date
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.loaders import nse_backfill as bf  # noqa: E402
from src.loaders import nse_bundle as nb  # noqa: E402
from src.loaders.nse_history import R2_ACTIONS_HISTORY, R2_PRICES, r2_days  # noqa: E402

PIPELINE = "nse-ledger-v1"


def _publish(path: Path, dataset: str, source: str) -> None:
    from scripts.r2_publish import publish

    publish(path, dataset=dataset, source=source, key_root=f"archive/{dataset}",
            pipeline_version=PIPELINE, release_tag="nse")


def import_actions(from_year: int, to_year: int, workdir: Path, publish=_publish,
                   fetch=bf.fetch_actions_year, sleep=time.sleep, log=print) -> int:
    session = requests.Session()
    done = 0
    for i, year in enumerate(range(from_year, to_year + 1)):
        if i:
            sleep(bf.API_DELAY_S)
        try:
            acts = fetch(year, session)
        except nb.NSEBlocked as exc:
            log(f"NSE refused at {year} ({exc}); the rest on the next run")
            break
        if acts.empty:
            log(f"ACTIONS {year}: none")
            continue
        path = workdir / f"actions_{year}" / "corporate_actions_history.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        acts.to_parquet(path, index=False, compression="zstd")
        publish(path, R2_ACTIONS_HISTORY, "nse_corporate_action_list")
        counts = acts["kind"].value_counts()
        log(f"ACTIONS {year}: {len(acts)} rows " + " ".join(
            f"{k}={int(counts.get(k, 0))}" for k in ("split", "bonus", "rights", "demerger",
                                                     "consolidation", "dividend")))
        done += 1
    return done


def _publish_day(source: Path, day: date, workdir: Path, publish=_publish) -> str | None:
    """Convert and publish one session; the error text, or None when it went."""
    try:
        rows = bf.mirror_prices(source, day)
        if rows.empty:
            raise ValueError("no rows")
        path = workdir / day.isoformat() / "prices.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        rows.to_parquet(path, index=False, compression="zstd")
        publish(path, R2_PRICES, "nse_bhavdata_full_mirror")
        return None
    except bf.NotThatDay as exc:              # a holiday filed as a copy of the day before
        return f"copy: {exc}"
    except Exception as exc:  # noqa: BLE001  one bad file never stops the run
        return f"{type(exc).__name__}: {exc}"[:200]


def import_prices(mirror: Path, have, workdir: Path, *, since: date, until: date,
                  max_minutes: float | None = None, refresh: int = 50, workers: int = 1,
                  publish=_publish, clock=time.monotonic, log=print) -> dict:
    """Publish the mirror's sessions R2 lacks, oldest first. `have()` re-reads R2.

    Each session is several round trips to R2 (object, verification, manifest,
    pointer), about 6 s; `workers` processes publish that many sessions at once
    (processes, not threads: each has its own boto3 session). Work goes out in
    batches of `refresh` sessions, R2 re-read between them.
    """
    files = bf.mirror_days(mirror)
    known = have()
    todo = sorted(d for d in files if since <= d <= until and d not in known)
    log(f"MIRROR {len(files)} sessions, {min(files) if files else '-'} to "
        f"{max(files) if files else '-'}; R2 lacks {len(todo)} of them in [{since}, {until}]"
        f"; {workers} at a time")
    deadline = clock() + max_minutes * 60 if max_minutes else None
    stats = {"published": 0, "skipped": 0, "failed": [], "left": 0}
    pool = ProcessPoolExecutor(max_workers=workers) if workers > 1 else None
    try:
        for start in range(0, len(todo), refresh):
            if deadline is not None and clock() >= deadline:
                stats["left"] = len(todo) - start
                log(f"MIRROR time budget spent; {stats['left']} sessions left for the next run")
                break
            if start:
                known = have()
            batch = [d for d in todo[start:start + refresh] if d not in known]
            stats["skipped"] += min(refresh, len(todo) - start) - len(batch)
            if pool is None:
                results = [_publish_day(files[d], d, workdir, publish) for d in batch]
            else:
                results = list(pool.map(_publish_day, [files[d] for d in batch], batch,
                                        [workdir] * len(batch)))
            for day, err in zip(batch, results):
                if err and err.startswith("copy:"):
                    stats["copies"] = stats.get("copies", 0) + 1
                elif err:
                    stats["failed"].append(f"{day}: {err}")
                else:
                    stats["published"] += 1
            if batch:
                log(f"  {min(start + refresh, len(todo))}/{len(todo)} sessions, "
                    f"{stats['published']} published, through {batch[-1]}")
    finally:
        if pool is not None:
            pool.shutdown()
    return stats


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--actions", action="store_true", help="import NSE's corporate-action list")
    ap.add_argument("--from-year", type=int, default=2010)
    ap.add_argument("--to-year", type=int, default=date.today().year)
    ap.add_argument("--prices", action="store_true", help="import the mirror's sessions R2 lacks")
    ap.add_argument("--mirror", type=Path, help="the mirror's data/ directory (with --prices)")
    ap.add_argument("--since", type=date.fromisoformat, default=date(2010, 1, 1))
    ap.add_argument("--until", type=date.fromisoformat, default=date.today())
    ap.add_argument("--max-minutes", type=float, default=None)
    ap.add_argument("--refresh", type=int, default=50, help="re-read R2 every N sessions")
    ap.add_argument("--workers", type=int, default=8, help="sessions published at once")
    args = ap.parse_args(argv)
    if args.actions == args.prices:
        ap.error("pass exactly one of --actions or --prices")
    if args.prices and args.mirror is None:
        ap.error("--prices needs --mirror")

    with tempfile.TemporaryDirectory() as tmp:
        if args.actions:
            n = import_actions(args.from_year, args.to_year, Path(tmp))
            print(f"ACTIONS_IMPORT years={n}")
            return 0 if n else 1
        from src.storage.r2 import R2Archive, R2Config

        archive = R2Archive(R2Config.from_env())
        stats = import_prices(args.mirror, lambda: r2_days(archive, R2_PRICES), Path(tmp),
                              since=args.since, until=args.until, max_minutes=args.max_minutes,
                              refresh=args.refresh, workers=args.workers)
    print(f"MIRROR_IMPORT published={stats['published']} skipped={stats['skipped']} "
          f"failed={len(stats['failed'])} left={stats['left']}")
    for line in stats["failed"][:20]:
        print(f"  FAILED {line}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
