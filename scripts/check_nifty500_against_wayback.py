"""Our Nifty 500 timeline against NSE's own published Nifty 500 list, as the Wayback Machine kept it.

    python scripts/check_nifty500_against_wayback.py --out audit/

NSE publishes the constituent list as a CSV (Company Name, Industry, Symbol,
Series, ISIN Code) and the Wayback Machine has crawled it 18 times, 2006 to
2026, from three addresses:

  nseindia.com/content/indices/ind_cnx500list.csv                2006 - 2015
  niftyindices.com/IndexConstituent/ind_nifty500list.csv         2018 - 2026
  archives.nseindia.com/content/indices/ind_nifty500list.csv     2022 - 2024

Each is a primary NSE file, independent of the press releases our timeline
(data/membership_history.json) was rebuilt from. (nse_index_rebuild/wayback_check.py
used Wayback for the Nifty 50, Next 50, Midcap 150, Smallcap 250 and Microcap 250
lists, not these.) The check: our members on the snapshot's date against the list,
both mapped to today's ticker through our rename ledger and NSE's symbol-change
file. Some snapshots are gzip-compressed; a DUMMY row is dropped.

First run (3 Oct 2026): 16 of 17 comparable snapshots agree on all ~500 names.
Differences (docs/DATA_CORRECTNESS.md, section 8):
  2010-01-02   ASIANHOTEL / ASIANHOTNR and KBL / KIRLOSBROS (renames the maps lack),
               PROVOGUE / PROVOGE (spelling), and ZANDUREALT (Zandu Pharmaceutical
               Works) in NSE's list where we have 3IINFOTECH: open, TODO S41.
  2022-05-04   AARTIIND in the list, GMRAIRPORT in ours: the change is effective that
               day and the crawl of that day still shows the earlier list.
A snapshot's date is the crawl's, not necessarily the day the list took effect: a
change effective on the crawl date can show either way.
"""

from __future__ import annotations

import argparse
import gzip
import io
import json
import os
import subprocess
import time

import pandas as pd

from src.engine import index_universe as iu

SOURCES = [
    "nseindia.com/content/indices/ind_cnx500list.csv",
    "archives.nseindia.com/content/indices/ind_nifty500list.csv",
    "niftyindices.com/IndexConstituent/ind_nifty500list.csv",
]
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _curl(url: str, dest: str | None = None, retries: int = 4) -> str | None:
    for attempt in range(retries):
        cmd = ["curl", "-sS", "-m", "120", "-L", "-w", "\n%{http_code}", url] if dest is None else \
              ["curl", "-sS", "-m", "120", "-L", "-o", dest, "-w", "%{http_code}", url]
        out = subprocess.run(cmd, capture_output=True, text=True).stdout
        code = out.strip().split("\n")[-1]
        if code == "200":
            return out.rsplit("\n", 1)[0] if dest is None else dest
        time.sleep(3 * (attempt + 1))
    return None


def snapshots() -> list[tuple[str, str]]:
    found = []
    for src in SOURCES:
        body = _curl(f"https://web.archive.org/cdx/search/cdx?url={src}&output=json"
                     "&fl=timestamp,statuscode,digest&filter=statuscode:200&collapse=digest")
        if body:
            found += [(row[0], src) for row in json.loads(body)[1:]]
    return sorted(found)


def fetch(ts: str, src: str, folder: str) -> pd.DataFrame | None:
    dest = os.path.join(folder, f"snap_{ts[:8]}.csv")
    if not (os.path.exists(dest) and os.path.getsize(dest) > 1000):
        _curl(f"https://web.archive.org/web/{ts}id_/https://{src}", dest)
    if not os.path.exists(dest):
        return None
    raw = open(dest, "rb").read()
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    text = raw.decode("utf-8", "ignore")
    if "Company Name" not in text:
        return None
    df = pd.read_csv(io.StringIO(text[text.index("Company Name"):]))
    df.columns = [c.strip() for c in df.columns]
    return df[~df["Symbol"].astype(str).str.upper().str.startswith("DUMMY")]


def rename_map(history: dict) -> dict[str, str]:
    ren = {c["old_symbol"]: c["new_symbol"] for c in history["symbol_changes"]["changes"]}
    path = os.path.join(ROOT, "data", "reference", "nse", "symbolchange.csv")
    sc = pd.read_csv(path, header=None, names=["name", "old", "new", "date"], on_bad_lines="skip")
    for old, new in zip(sc["old"].astype(str).str.strip(), sc["new"].astype(str).str.strip()):
        if old and new and old != new:
            ren.setdefault(old, new)
    return ren


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    full = iu.load_history_or_none()
    nifty500 = iu._stored(full, "nifty_500")
    ren = rename_map(full)

    def current(sym: str) -> str:
        seen: set[str] = set()
        while sym in ren and sym not in seen:
            seen.add(sym)
            sym = ren[sym]
        return sym

    summary, diffs = [], []
    for ts, src in snapshots():
        day = pd.Timestamp(ts[:8])
        df = fetch(ts, src, args.out)
        if df is None:
            summary.append((day.date(), None, None, None, None, None, "file unreadable"))
            continue
        listed = {current(s) for s in df["Symbol"].astype(str).str.strip()}
        ours = iu.members_on(nifty500, day)
        if not ours:
            summary.append((day.date(), len(listed), None, None, None, None, "before our history starts"))
            continue
        ours = {current(s) for s in ours}
        summary.append((day.date(), len(listed), len(ours), len(listed & ours),
                        len(listed - ours), len(ours - listed), ""))
        diffs += [(day.date(), "only in NSE's list", s) for s in sorted(listed - ours)]
        diffs += [(day.date(), "only in ours", s) for s in sorted(ours - listed)]
    table = pd.DataFrame(summary, columns=["snapshot", "NSE list", "ours", "in both",
                                           "only in NSE list", "only in ours", "note"])
    table.to_csv(os.path.join(args.out, "nifty500_wayback_check.csv"), index=False)
    pd.DataFrame(diffs, columns=["snapshot", "where", "symbol"]).to_csv(
        os.path.join(args.out, "nifty500_wayback_differences.csv"), index=False)
    print(table.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
