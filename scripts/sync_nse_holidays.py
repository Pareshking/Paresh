#!/usr/bin/env python3
"""Keep data/reference/nse/holidays.csv in step with NSE's own holiday list.

    python scripts/sync_nse_holidays.py            # fetch, check, merge, write
    python scripts/sync_nse_holidays.py --dry-run  # fetch and report, write nothing

Owner, 15 Nov 2026: "We don't know NSE calendar for even 2027, is our code capable
to automatically get it?" It was not: the file was fetched by hand on 3 Oct 2026
and covered 2026 only. NSE publishes next year's list in December (on 15 Nov 2026
its holiday-master API still returned 2026 alone), so this runs every night in
`nse_reference_sync.yml` and picks the new year up the night NSE posts it.

Source: nseindia.com/api/holiday-master?type=trading, the "CM" (cash market) list.
NSE marks a holiday that has a Muhurat evening session with a trailing "*"
("Diwali Laxmi Pujan*"); that becomes special_session = "muhurat", the same
mapping the 3 Oct file used.

Safe by construction:
- A past date is never removed or changed: the file is the evidence of what NSE
  said, and the price audits read it.
- A future date NSE no longer lists (a holiday it cancelled) is removed only when
  NSE's list for that year still has at least MIN_PER_YEAR days, so a half-empty
  reply cannot strip a year.
- An empty or unreadable reply changes nothing and fails the step (the workflow
  makes that a warning, not a red sync).

It also warns, on every run, when the list does not cover the current year, or,
from 15 December, the next one: the site then says "cannot tell" instead of
guessing (src/core/market_time.last_due_session), and somebody should know.
"""
from __future__ import annotations

import argparse
import csv
import io
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # src/ (nse_web), however the script is started

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "reference" / "nse" / "holidays.csv"
# On www.nseindia.in, with .com as a fallback (src/core/nse_web.py, 18 Nov 2026).
HOME_PATH = "/resources/exchange-communication-holidays"
API_PATH = "/api/holiday-master"
HOME = "https://www.nseindia.in" + HOME_PATH
API = "https://www.nseindia.in" + API_PATH
COLUMNS = ["date", "description", "special_session", "source"]
MIN_PER_YEAR = 10            # NSE lists 14-20 trading holidays a year
NEXT_YEAR_FROM = (12, 15)    # from this day on, next year's list is expected


def parse(payload: dict, fetched_on: date) -> list[dict]:
    """NSE's CM holidays as rows of COLUMNS."""
    rows = []
    for item in (payload or {}).get("CM") or []:
        raw = str(item.get("tradingDate") or "").strip()
        desc = " ".join(str(item.get("description") or "").split())
        try:
            day = datetime.strptime(raw, "%d-%b-%Y").date()
        except ValueError:
            continue
        muhurat = desc.endswith("*") or bool(item.get("evening_session"))
        rows.append({"date": day.isoformat(), "description": desc.rstrip("*").strip(),
                     "special_session": "muhurat" if muhurat else "",
                     "source": f"nseindia.com/api/holiday-master?type=trading (CM), fetched {fetched_on.isoformat()}"})
    return sorted({r["date"]: r for r in rows}.values(), key=lambda r: r["date"])


def merge(old: list[dict], new: list[dict], today: date) -> tuple[list[dict], list[str]]:
    """The file after taking NSE's list in, and a line per change."""
    if not new:
        raise ValueError("NSE returned no holidays")
    by_old = {r["date"]: r for r in old}
    by_new = {r["date"]: r for r in new}
    per_year: dict[int, int] = {}
    for d in by_new:
        per_year[int(d[:4])] = per_year.get(int(d[:4]), 0) + 1
    out, changes = dict(by_old), []
    for d, r in by_new.items():
        if date.fromisoformat(d) < today and d in by_old:
            continue                                   # the past is evidence: never rewritten
        before = by_old.get(d)
        if before is None:
            changes.append(f"added {d} {r['description']}" + (" (Muhurat session)" if r["special_session"] else ""))
            out[d] = r
        elif (before["description"], before["special_session"]) != (r["description"], r["special_session"]):
            changes.append(f"changed {d}: {before['description']!r} -> {r['description']!r}")
            out[d] = r
    for d, r in by_old.items():
        year = int(d[:4])
        if d not in by_new and date.fromisoformat(d) >= today and per_year.get(year, 0) >= MIN_PER_YEAR:
            changes.append(f"removed {d} {r['description']} (no longer on NSE's {year} list)")
            del out[d]
    return sorted(out.values(), key=lambda r: r["date"]), changes


def coverage_warnings(rows: list[dict], today: date) -> list[str]:
    """Years the site needs that the list does not cover."""
    years = {int(r["date"][:4]) for r in rows}
    out = []
    if today.year not in years:
        out.append(f"NSE's holiday list does not cover {today.year}")
    if (today.month, today.day) >= NEXT_YEAR_FROM and today.year + 1 not in years:
        out.append(f"NSE's holiday list does not cover {today.year + 1} yet (NSE usually posts it in December)")
    return out


def read(path: Path = OUT) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as f:
        return [{k: (r.get(k) or "") for k in COLUMNS} for r in csv.DictReader(f)]


def write(rows: list[dict], path: Path = OUT) -> None:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=COLUMNS, lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    path.write_text(buf.getvalue(), encoding="utf-8")


def fetch() -> dict:
    from src.core import nse_web

    r, _ = nse_web.get(API_PATH, page=HOME_PATH, params={"type": "trading"})
    r.raise_for_status()
    return r.json()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    today = (datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)).date()   # IST
    new = parse(fetch(), today)
    rows, changes = merge(read(), new, today)
    years = sorted({r["date"][:4] for r in new})
    print(f"NSE holiday list: {len(new)} days for {', '.join(years)}; {len(changes)} change(s)")
    for c in changes:
        print(f"  {c}")
    if changes and not args.dry_run:
        write(rows)
        print(f"-> {OUT}")
    for w in coverage_warnings(rows, today):
        print(f"::warning::{w}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
