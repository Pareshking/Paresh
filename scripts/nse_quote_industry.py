"""Print BSE's four-level classification for named stocks, matched by ISIN (S189's four: CMPDI, SUDEEPPHRM,
INA, BUILDPRO, whose Screener levels differ from the Nifty 1000 list's "Industry"). NSE's quote API refused
GitHub's runners (HTTP 403, run 45895841820), so this reads BSE's public list of scrips instead: the
exchanges publish one harmonised classification (macro-economic sector, sector, industry, basic industry),
so BSE's row is a second exchange's reading of the same scheme. One-off, owner 27 Nov 2026 ("find working
solutions"); a report only, nothing is written. A 403 is reported, not worked around.

    python scripts/nse_quote_industry.py CMPDI SUDEEPPHRM INA BUILDPRO
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
API = "https://api.bseindia.com/BseIndiaAPI/api"
HEADERS = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.bseindia.com/", "Accept": "application/json"}


def isins(symbols: list[str]) -> dict[str, str]:
    """Each symbol's ISIN from NSE's own Nifty 1000 list."""
    with open(ROOT / "data" / "indices" / "ind_nifty1000_list.csv", newline="", encoding="utf-8") as f:
        rows = {r["Symbol"].strip(): r["ISIN Code"].strip() for r in csv.DictReader(f)}
    return {s: rows.get(s, "") for s in symbols}


def match(scrips: list[dict], isin: str) -> dict | None:
    """BSE's row for an ISIN, whatever BSE names the column."""
    for row in scrips:
        if any(str(v).strip().upper() == isin.upper() for k, v in row.items() if "isin" in k.lower()):
            return row
    return None


def main(symbols: list[str]) -> int:
    want = isins([s.strip().upper() for s in symbols])
    r = requests.get(f"{API}/ListofScripData/w", headers=HEADERS, timeout=90,
                     params={"Group": "", "Scripcode": "", "industry": "", "segment": "Equity", "status": "Active"})
    print(f"BSE list of scrips: HTTP {r.status_code}")
    if r.status_code != 200:
        return 1
    scrips = r.json()
    scrips = scrips.get("Table", scrips) if isinstance(scrips, dict) else scrips
    print(f"{len(scrips)} rows; columns: {sorted(scrips[0]) if scrips else []}")
    found = 0
    for sym, isin in want.items():
        row = match(scrips, isin) if isin else None
        if row is None:
            print(f"{sym} ({isin or 'no ISIN'}): not in BSE's list")
            continue
        found += 1
        print(f"{sym} ({isin}) list row: {json.dumps(row, ensure_ascii=False)}")
        code = next((v for k, v in row.items() if k.lower() in ("scrip_cd", "scripcode", "security_code")), None)
        if code:
            h = requests.get(f"{API}/ComHeadernew/w", headers=HEADERS, timeout=60,
                             params={"quotetype": "EQ", "scripcode": code, "seriesid": ""})
            body = h.text[:1500] if h.status_code == 200 else ""
            print(f"{sym} header (HTTP {h.status_code}): {body}")
    return 0 if found else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:] or ["CMPDI", "SUDEEPPHRM", "INA", "BUILDPRO"]))
