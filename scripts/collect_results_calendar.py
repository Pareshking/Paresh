#!/usr/bin/env python3
"""Nightly copy of NSE's board-meeting calendar: when each company reports (TODO S110, item 4).

    python scripts/collect_results_calendar.py            # fetch, check, write
    python scripts/collect_results_calendar.py --dry-run  # fetch and report, write nothing

Two NSE feeds, the same session pattern as scripts/collect_fii_dii.py:

- api/event-calendar?index=equities: meetings announced from today on (about four weeks).
- api/corporate-board-meetings?index=equities&from_date&to_date: meetings already held,
  over the last PAST_DAYS, so the Dashboard can say a holding has reported.

Writes data/results_calendar.csv, one row per company and meeting date:
symbol, date (YYYY-MM-DD), purpose, results (1 if the purpose includes financial
results), detail (NSE's description, trimmed), source (calendar / held).

Checked on 8 Nov 2026 before use: 626 forward events (9 Nov to 5 Dec); every one of
the model book's 20 holdings had a date (3 to come, 17 held 9 Oct to 7 Nov); CUPID
11 Nov and DIVISLAB 7 Nov agree with tipsheet's calendar (stocks.events). Companies
can move a meeting, so the page says "as announced".

It refuses to replace the file with an empty or shrunken forward calendar and exits
non-zero, so a refused download is loud instead of wiping the dates.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "results_calendar.csv"
META = ROOT / "data" / "results_calendar_meta.json"
HOME = "https://www.nseindia.com/companies-listing/corporate-filings-event-calendar"
CALENDAR = "https://www.nseindia.com/api/event-calendar"
HELD = "https://www.nseindia.com/api/corporate-board-meetings"
PAST_DAYS = 60
MIN_FORWARD = 50          # NSE's calendar carries hundreds in a results season, dozens at worst
SHRINK_LIMIT = 0.5        # the forward calendar falling by half overnight is a broken download
DETAIL_CHARS = 140
COLUMNS = ["symbol", "date", "purpose", "results", "detail", "source"]


class CalendarError(RuntimeError):
    pass


def session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
                      "Accept": "application/json", "Referer": HOME})
    s.get(HOME, timeout=30)       # sets the cookies NSE's api/ needs
    return s


def _get_json(s: requests.Session, url: str, params: dict, tries: int = 4):
    last = None
    for attempt in range(1, tries + 1):
        try:
            r = s.get(url, params=params, timeout=60)
            if r.status_code == 200 and r.content:
                return r.json()
            last = f"HTTP {r.status_code}, {len(r.content)} bytes"
        except (requests.RequestException, ValueError) as exc:
            last = repr(exc)
        time.sleep(attempt * 3)
        s.get(HOME, timeout=30)
    raise CalendarError(f"{url}: {last}")


def _clean(text) -> str:
    return " ".join(str(text or "").split())


def normalise(forward: list[dict], held: list[dict]) -> pd.DataFrame:
    rows = []
    for r in forward or []:
        rows.append({"symbol": r.get("symbol"), "date": r.get("date"), "purpose": r.get("purpose"),
                     "detail": r.get("bm_desc"), "source": "calendar"})
    # NSE usually lists a meeting twice, the notice ("Board Meeting Intimation")
    # and the meeting with its purpose; for some meetings the notice is the only
    # row (audit, 8 Nov 2026: 17 of Oct-Nov, SCHAND, BAGMANE ...). The notice is
    # kept when it is alone, its purpose read from its description.
    held = list(held or [])
    named = {(_clean(r.get("bm_symbol")).upper(), _clean(r.get("bm_date"))) for r in held
             if _clean(r.get("bm_purpose")).lower() != "board meeting intimation"}
    for r in held:
        purpose = _clean(r.get("bm_purpose"))
        key = (_clean(r.get("bm_symbol")).upper(), _clean(r.get("bm_date")))
        if purpose.lower() == "board meeting intimation":
            if key in named:
                continue
            purpose = ("Financial Results" if "result" in _clean(r.get("bm_desc")).lower()
                       else "Board meeting")
        rows.append({"symbol": r.get("bm_symbol"), "date": r.get("bm_date"), "purpose": purpose,
                     "detail": r.get("bm_desc"), "source": "held"})
    d = pd.DataFrame(rows, columns=["symbol", "date", "purpose", "detail", "source"])
    if d.empty:
        return pd.DataFrame(columns=COLUMNS)
    d["symbol"] = d["symbol"].map(_clean).str.upper()
    d["date"] = pd.to_datetime(d["date"], format="%d-%b-%Y", errors="coerce")
    d = d.dropna(subset=["date"])
    d = d[d["symbol"] != ""]
    d["purpose"] = d["purpose"].map(_clean)
    d["detail"] = d["detail"].map(_clean).str.slice(0, DETAIL_CHARS)
    d["results"] = d["purpose"].str.contains("financial result", case=False).astype(int)
    # One row per company and day; a meeting both announced and held keeps "held".
    d = d.sort_values(["symbol", "date", "source"], ascending=[True, True, False])
    d = d.drop_duplicates(["symbol", "date"], keep="first")
    d["date"] = d["date"].dt.strftime("%Y-%m-%d")
    return d[COLUMNS].sort_values(["date", "symbol"]).reset_index(drop=True)


def check(new: pd.DataFrame, old: pd.DataFrame | None, today: date) -> list[str]:
    """Reasons to refuse the new file (empty list: fine)."""
    fwd = new[(new["source"] == "calendar") & (pd.to_datetime(new["date"]).dt.date >= today)]
    out = []
    if len(fwd) < MIN_FORWARD:
        out.append(f"only {len(fwd)} forward meetings (at least {MIN_FORWARD} expected)")
    if old is not None and len(old):
        old_fwd = old[(old["source"] == "calendar") & (pd.to_datetime(old["date"]).dt.date >= today)]
        if len(old_fwd) and len(fwd) < len(old_fwd) * (1 - SHRINK_LIMIT):
            out.append(f"{len(fwd)} forward meetings against {len(old_fwd)} still ahead in the last file")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    today = date.today()
    s = session()
    forward = _get_json(s, CALENDAR, {"index": "equities"})
    held = _get_json(s, HELD, {"index": "equities", "from_date": (today - timedelta(days=PAST_DAYS)).strftime("%d-%m-%Y"),
                               "to_date": today.strftime("%d-%m-%Y")})
    new = normalise(forward, held)
    old = pd.read_csv(OUT) if OUT.exists() else None
    bad = check(new, old, today)
    print(f"{len(new)} meetings: {int((new['source'] == 'calendar').sum())} announced, "
          f"{int((new['source'] == 'held').sum())} held; {new['date'].min()}..{new['date'].max()}")
    for b in bad:
        print(f"::error::{b}")
    if bad:
        return 1
    if not args.dry_run:
        new.to_csv(OUT, index=False)
        META.write_text(json.dumps({"fetched_on": today.isoformat(), "rows": len(new),
                                    "announced": int((new["source"] == "calendar").sum()),
                                    "held": int((new["source"] == "held").sum()),
                                    "sources": [CALENDAR, HELD]}, indent=1) + "\n")
        print(f"-> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
