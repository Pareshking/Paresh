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

It refuses to replace the file when the download loses what the last file knew, and
exits non-zero, so a refused download is loud instead of wiping the dates. "Lost" is
a meeting in the last file that the new download no longer has in any form: not ahead,
not held, and the company has no meeting on another date either. A count is not the
test: the forward calendar empties itself every results season (the Q2 deadline is
14 Nov; on 15 Nov 2026 NSE listed 18 meetings ahead) and on the day of a meeting NSE
moves it from the calendar to the held list (S110: the count-based guard failed every
night from 12 Nov while nothing was wrong).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path

import pandas as pd
import requests
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # src/ (nse_web), however the script is started

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "results_calendar.csv"
META = ROOT / "data" / "results_calendar_meta.json"
# On www.nseindia.in, with .com as a fallback (src/core/nse_web.py, 18 Nov 2026):
# session() picks the host whose page answers, and every call below uses it.
HOME_PATH = "/companies-listing/corporate-filings-event-calendar"
CALENDAR_PATH = "/api/event-calendar"
HELD_PATH = "/api/corporate-board-meetings"
HOME = "https://www.nseindia.in" + HOME_PATH
CALENDAR = "https://www.nseindia.in" + CALENDAR_PATH
HELD = "https://www.nseindia.in" + HELD_PATH
PAST_DAYS = 60
MIN_HELD = 100            # meetings held in 60 days: thousands in a season, hundreds at the quietest
MAX_LOST = 25             # meetings the last file knew that may vanish (cancelled, or moved past
LOST_SHARE = 0.10         #   the window): more than 25 and 10% of those checked is a broken download
EDGE_DAYS = 3             # held meetings this close to the 60-day edge may fall out of the window
DETAIL_CHARS = 140
COLUMNS = ["symbol", "date", "purpose", "results", "detail", "source"]


class CalendarError(RuntimeError):
    pass


def session() -> requests.Session:
    """A session on the first NSE host whose calendar page answers; its base is `s.nse_base`."""
    from src.core import nse_web

    s, base = nse_web.session_for(HOME_PATH)
    s.nse_base = base
    return s


def _url(s, path: str) -> str:
    return getattr(s, "nse_base", "https://www.nseindia.in") + path


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
        s.get(_url(s, HOME_PATH), timeout=30)
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
    out = []
    held = int((new["source"] == "held").sum())
    if held < MIN_HELD:
        out.append(f"only {held} meetings held in {PAST_DAYS} days (at least {MIN_HELD} expected)")
    lost = lost_meetings(new, old, today)
    if old is not None and len(old):
        checked = _checked(old, today)
        if len(lost) > max(MAX_LOST, LOST_SHARE * len(checked)):
            sample = ", ".join(f"{r.symbol} {r.date}" for r in lost.head(5).itertuples())
            out.append(f"{len(lost)} of {len(checked)} meetings in the last file are gone from NSE's "
                       f"download (not ahead, not held, no new date): {sample} ...")
    return out


def _checked(old: pd.DataFrame, today: date) -> pd.DataFrame:
    """The last file's meetings the new download must still account for: every one
    announced, and every one held that is not about to leave the 60-day window."""
    d = pd.to_datetime(old["date"]).dt.date
    edge = today - timedelta(days=PAST_DAYS - EDGE_DAYS)
    return old[(old["source"] == "calendar") | (d >= edge)]


def lost_meetings(new: pd.DataFrame, old: pd.DataFrame | None, today: date) -> pd.DataFrame:
    """Meetings in the last file the new download has in no form (S110)."""
    if old is None or not len(old):
        return pd.DataFrame(columns=COLUMNS)
    checked = _checked(old, today)
    have = set(zip(new["symbol"], new["date"]))
    moved = set(new.loc[pd.to_datetime(new["date"]).dt.date >= today - timedelta(days=EDGE_DAYS), "symbol"])
    keep = [(s, d) not in have and s not in moved for s, d in zip(checked["symbol"], checked["date"])]
    return checked[keep]


def ist_today() -> date:
    """NSE's date. The job is due 21:53 IST but GitHub's queue often runs it after
    midnight IST, when the runner's UTC date is still the day before."""
    return datetime.now(ZoneInfo("Asia/Kolkata")).date()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    today = ist_today()
    s = session()
    forward = _get_json(s, _url(s, CALENDAR_PATH), {"index": "equities"})
    held = _get_json(s, _url(s, HELD_PATH), {"index": "equities", "from_date": (today - timedelta(days=PAST_DAYS)).strftime("%d-%m-%Y"),
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
                                    "sources": [_url(s, CALENDAR_PATH), _url(s, HELD_PATH)]}, indent=1) + "\n")
        print(f"-> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
