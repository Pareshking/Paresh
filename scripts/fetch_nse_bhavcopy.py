"""Download NSE's classic daily bhavcopy (cmDDMONYYYYbhav.csv) for days before 2010.

    python scripts/fetch_nse_bhavcopy.py --since 2008-01-01 --until 2009-12-31 --out bhav_pre2010

NSE's daily bundles (nse_collect) begin on 4 Jan 2010. A ranking on 1 Jan 2010
needs a year of history before it (owner, 2026-10-02), and NSE's archive
still serves the classic bhavcopy for those years: one zip per session, prices
for every security. One request per weekday, --delay seconds apart; a
weekday with no file (404) is a holiday. Three refusals in a row stop the run.
The files are then published like the mirror's: import_nse_history.py --prices
--mirror <out>.
"""

from __future__ import annotations

import argparse
import io
import sys
import time
import zipfile
from datetime import date, timedelta
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.loaders.nse_backfill import CM_URL  # noqa: E402

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140.0 Safari/537.36",
    "Referer": "https://www.nseindia.com/",
    "Accept": "*/*",
}


def url(day: date) -> str:
    return CM_URL.format(yyyy=day.year, MON=day.strftime("%b").upper(),
                         DDMONYYYY=day.strftime("%d%b%Y").upper())


def fetch(day: date, session: requests.Session) -> bytes | None:
    """The day's CSV, None when NSE has no file (a holiday). Raises on a refusal."""
    r = session.get(url(day), headers=HEADERS, timeout=60)
    if r.status_code == 404 or (r.status_code == 200 and r.content[:2] != b"PK"):
        return None
    if r.status_code in (401, 403, 429):
        raise PermissionError(f"HTTP {r.status_code}")
    r.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        return z.read(z.namelist()[0])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--since", type=date.fromisoformat, required=True)
    ap.add_argument("--until", type=date.fromisoformat, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--delay", type=float, default=2.0)
    args = ap.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    got, holidays, refused = 0, [], 0
    day = args.since
    while day <= args.until:
        if day.weekday() < 5:
            target = args.out / f"cm{day.strftime('%d%b%Y').upper()}bhav.csv"
            if not target.exists():
                try:
                    body = fetch(day, session)
                    refused = 0
                except PermissionError as exc:
                    refused += 1
                    print(f"  {day}: refused ({exc})")
                    if refused >= 3:
                        print("::warning::NSE refused three times in a row; stopping")
                        break
                    time.sleep(30)
                    continue
                if body is None:
                    holidays.append(day)
                else:
                    target.write_bytes(body)
                    got += 1
                time.sleep(args.delay)
        day += timedelta(days=1)
    print(f"BHAVCOPY fetched={got} holidays={len(holidays)} "
          f"files={len(list(args.out.glob('cm*bhav.csv')))} last={day - timedelta(days=1)}")
    return 0 if got or not refused else 1


if __name__ == "__main__":
    sys.exit(main())
