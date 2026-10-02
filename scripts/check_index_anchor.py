#!/usr/bin/env python3
"""Anchor check: today's index lists from two NSE publishing hosts against data/membership_history.json.

    python scripts/check_index_anchor.py            # fetch, compare, append to data/reference/nse/anchor_checks.jsonl
    python scripts/check_index_anchor.py --dry-run  # compare, write nothing

The history is rebuilt backward from today's NSE lists, so a wrong anchor would carry into every earlier date. This
compares the history's current members with the constituent files on www.niftyindices.com and on nsearchives.nseindia.com
and records the result with the date, one JSON line per index per run. Run daily (nse_reference_sync.yml) so the file
shows agreement on many separate days. A difference is recorded and printed as a warning (a notice effective today may
not be in the history yet); a failed fetch fails the run.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
HISTORY = ROOT / "data" / "membership_history.json"
OUT = ROOT / "data" / "reference" / "nse" / "anchor_checks.jsonl"
HOSTS = {"niftyindices": "https://www.niftyindices.com/IndexConstituent/",
         "nsearchives": "https://nsearchives.nseindia.com/content/indices/"}
FILES = {"nifty_50": "ind_nifty50list.csv", "nifty_next_50": "ind_niftynext50list.csv",
         "nifty_midcap_150": "ind_niftymidcap150list.csv", "nifty_smallcap_250": "ind_niftysmallcap250list.csv",
         "nifty_microcap_250": "ind_niftymicrocap250_list.csv", "nifty_total_market": "ind_niftytotalmarket_list.csv",
         "nifty_500": "ind_nifty500list.csv"}
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}


class AnchorError(RuntimeError):
    pass


def current_members(history: dict, index: str) -> set[str]:
    entry = history["indices"][index]
    state = set(entry["baseline"]["symbols"])
    for change in entry["changes"]:
        state = (state - set(change["removed"])) | set(change["added"])
    return {s for s in state if not s.startswith("DUMMY")}


def parse_symbols(raw: bytes) -> set[str]:
    rows = csv.DictReader(io.StringIO(raw.decode("utf-8-sig", errors="replace")))
    out = {(r.get("Symbol") or "").strip() for r in rows}
    return {s for s in out if s and not s.startswith("DUMMY")}


def fetch(url: str, tries: int = 4, session=requests) -> bytes:
    last = None
    for attempt in range(1, tries + 1):
        try:
            r = session.get(url, headers=UA, timeout=60)
            if r.status_code == 200 and r.content:
                return r.content
            last = f"HTTP {r.status_code}, {len(r.content)} bytes"
        except requests.RequestException as exc:
            last = repr(exc)
        time.sleep(attempt * 3)
    raise AnchorError(f"{url}: {last}")


def compare(history: dict, index: str, lists: dict[str, set[str]]) -> dict:
    mine = current_members(history, index)
    rec = {"index": index, "history": len(mine)}
    for host, syms in lists.items():
        rec[host] = len(syms)
        rec[f"only_{host}"] = sorted(syms - mine)
        rec[f"only_history_vs_{host}"] = sorted(mine - syms)
    rec["agrees"] = all(not rec[f"only_{h}"] and not rec[f"only_history_vs_{h}"] for h in lists)
    return rec


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    history = json.loads(HISTORY.read_text(encoding="utf-8"))
    today = datetime.now(timezone.utc).date().isoformat()
    records = []
    try:
        for index, fname in FILES.items():
            lists = {host: parse_symbols(fetch(base + fname)) for host, base in HOSTS.items()}
            records.append({"date_utc": today, **compare(history, index, lists)})
    except AnchorError as exc:
        print(f"::error::Anchor check could not fetch a list: {exc}")
        return 1
    for rec in records:
        flag = "agrees" if rec["agrees"] else "DIFFERS"
        print(f"{rec['index']}: history {rec['history']}, niftyindices {rec['niftyindices']}, "
              f"nsearchives {rec['nsearchives']} -> {flag}")
        if not rec["agrees"]:
            print(f"::warning::{rec['index']} differs from NSE's published list on {today}: "
                  f"{json.dumps({k: v for k, v in rec.items() if k.startswith('only_')})[:300]}")
    if not args.dry_run:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        with OUT.open("a", encoding="utf-8") as fh:
            for rec in records:
                fh.write(json.dumps(rec, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
