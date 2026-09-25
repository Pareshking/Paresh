"""Is a freshly built observed-session archive fit to publish?

Replaces a bare `len(frame) >= 1000`, which passed or failed on how the
Screener store happened to be built rather than on anything it guards. The
owner's direction (2026-09-25): collect Screener daily and let the history
fill in as time passes. So the checks are:

- SHAPE: dates strictly increasing and unique, every row an NSE session.
- DAILY RECENT YEAR: the last 365 calendar days hold at least
  MIN_RECENT_SESSIONS sessions (NSE trades ~248 a year); a store that fell
  back to weekly points fails.
- SPAN: the archive reaches back at least MIN_SPAN_YEARS.
- NEVER SHRINKS: every session in the archive currently published to R2 is
  still present. This is the check that would have caught 2026-09-21, when
  the nightly store replaced a 1161-date download with 249 dates.

    python scripts/check_observed_sessions.py --path trading_sessions_observed.parquet
"""

from __future__ import annotations

import argparse
from datetime import timedelta

import pandas as pd

MIN_RECENT_SESSIONS = 230
MIN_SPAN_YEARS = 9.5
DATASET = "trading_sessions/observed"


def check(frame: pd.DataFrame, previous: set[str] | None) -> list[str]:
    """Problems with `frame`; empty means publishable."""
    problems = []
    dates = pd.to_datetime(frame["date"])
    if not dates.is_monotonic_increasing or not dates.is_unique:
        problems.append("dates are not strictly increasing")
    if not frame["is_session"].all():
        problems.append("a row is not marked as a session")
    if not frame["market"].eq("NSE").all():
        problems.append("a row is not an NSE session")
    if dates.empty:
        return problems + ["the archive is empty"]

    last = dates.max()
    recent = int((dates > last - timedelta(days=365)).sum())
    if recent < MIN_RECENT_SESSIONS:
        problems.append(
            f"only {recent} sessions in the year to {last.date()} "
            f"(need {MIN_RECENT_SESSIONS}: the recent year must be daily)")

    span_years = (last - dates.min()).days / 365.25
    if span_years < MIN_SPAN_YEARS:
        problems.append(f"spans {span_years:.1f} years (need {MIN_SPAN_YEARS})")

    if previous:
        have = set(dates.dt.strftime("%Y-%m-%d"))
        lost = sorted(previous - have)
        if lost:
            problems.append(
                f"{len(lost)} session(s) in the published archive are missing, "
                f"e.g. {', '.join(lost[:5])}")
    return problems


def _published_sessions() -> set[str] | None:
    from src.storage.r2 import R2Archive, R2Config
    from src.storage.reader import R2DatasetReader

    reader = R2DatasetReader(R2Archive(R2Config.from_env()))
    try:
        ref = reader.resolve_current(DATASET)
    except FileNotFoundError:
        return None
    frame = reader.read_parquet(ref)
    print(f"PUBLISHED {DATASET} as_of={ref.as_of} revision={ref.revision_sha256[:12]} "
          f"sessions={len(frame)}")
    return set(pd.to_datetime(frame["date"]).dt.strftime("%Y-%m-%d"))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--path", required=True)
    args = ap.parse_args()

    frame = pd.read_parquet(args.path)
    problems = check(frame, _published_sessions())
    dates = pd.to_datetime(frame["date"])
    print(f"OBSERVED_SESSION_COUNT={len(frame)}")
    print(f"OBSERVED_FIRST={dates.min().date()} OBSERVED_LAST={dates.max().date()}")
    for p in problems:
        print(f"::error::{p}")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
