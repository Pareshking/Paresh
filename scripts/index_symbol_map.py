#!/usr/bin/env python3
"""Join an NSE bhavcopy to the point-in-time index membership, across ticker changes.

data/membership_history.json records members under today's ticker. A bhavcopy carries the ticker of its own day.
This module turns one into the other using the dated ticker-change ledger in the same file (`symbol_changes`).

    python scripts/index_symbol_map.py NIFTY_50 2015-06-30                 # members, as the bhavcopy of that day names them
    python scripts/index_symbol_map.py NIFTY_500 2012-01-02 --bhavcopy cm02JAN2012bhav.csv   # who has no row in the file

As a library:

    h = load()
    members(h, "nifty_50", "2015-06-30")            # history symbols (today's tickers)
    bhavcopy_symbols(h, "nifty_50", "2015-06-30")   # {ticker in that day's bhavcopy: history symbol}
    coverage(h, "nifty_50", "2015-06-30", symbols)  # matched / members with no bhavcopy row

Renames are never exits; mergers and demergers are (the old ticker simply stops being a member). load() joins
renames with the history's ledger, NSE's own symbolchange.csv and three renames NSE lists nowhere; checked on 35
dates 2010-2026 every member then has a bhavcopy row except on days it did not trade (FRETAIL, RELINFRA ...).
A member with no row is reported, not guessed.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

HISTORY = Path(__file__).resolve().parents[1] / "data" / "membership_history.json"
SYMBOLCHANGE = Path(__file__).resolve().parents[1] / "data" / "reference" / "nse" / "symbolchange.csv"

# Renames in no NSE list, each proven from NSE's own files (reports/membership_bhavcopy_check_2026-10-02.md).
EXTRA_RENAMES = [
    {"old_symbol": "KBL", "new_symbol": "KIRLOSBROS", "last_old_date": "2010-04-19", "first_new_date": "2010-04-20",
     "status": "NSE_FILES", "evidence": "Pd040110.csv: KBL = KIRLOSKAR BROTHERS LTD; equity_l.csv: KIRLOSBROS listed 20-APR-2010"},
    {"old_symbol": "ASIANHOTEL", "new_symbol": "ASIANHOTNR", "last_old_date": "2010-04-06", "first_new_date": "2010-04-07",
     "status": "NSE_FILES", "evidence": "Pd040110.csv: ASIANHOTEL = ASIAN HOTELS LTD; equity_l.csv: ASIANHOTNR listed "
                                        "07-APR-2010, ISIN INE363A01022"},
    {"old_symbol": "PROVOGUE", "new_symbol": "PROVOGE", "last_old_date": "2012-03-06", "first_new_date": "2012-03-26",
     "status": "NSE_FILES", "evidence": "isin_history.csv: PROVOGUE INE968G01025 to 2012-03-06, PROVOGE INE968G01033 "
                                        "from 2012-03-26 (issuer prefix INE968G01)"},
]


def nse_symbol_changes(path: Path = SYMBOLCHANGE) -> list[dict]:
    """NSE's own list of ticker changes (headerless: company, old, new, date), as ledger entries."""
    out = []
    try:
        with open(path, newline="", encoding="latin1") as fh:
            rows = list(csv.reader(fh))
    except OSError:
        return out
    for row in rows:
        if len(row) < 4:
            continue
        old, new, when = row[1].strip().upper(), row[2].strip().upper(), row[3].strip()
        try:
            first = datetime.strptime(when, "%d-%b-%Y").date()
        except ValueError:
            continue
        if old and new and old != new:
            out.append({"old_symbol": old, "new_symbol": new, "first_new_date": first.isoformat(),
                        "last_old_date": (first - timedelta(days=1)).isoformat(), "status": "NSE_SYMBOLCHANGE_LIST"})
    return out


def load(path: Path = HISTORY, renames: bool = True) -> dict:
    """The history; with `renames`, its ticker ledger extended in memory (never on disk).

    The history's `symbol_changes` covers renames named in index notices. A member renamed while no
    notice mentioned it (TATAMOTORS -> TMPV, INFOSYSTCH -> INFY, ...) is joined by NSE's own
    symbolchange.csv and the three renames NSE lists nowhere (EXTRA_RENAMES). The history's own
    entries come first, so they win where the two disagree.
    """
    history = json.loads(Path(path).read_text(encoding="utf-8"))
    if renames:
        ledger = history.setdefault("symbol_changes", {}).setdefault("changes", [])
        have = {(c["old_symbol"], c["new_symbol"]) for c in ledger}
        ledger.extend(c for c in nse_symbol_changes() + EXTRA_RENAMES
                      if (c["old_symbol"], c["new_symbol"]) not in have)
    return history


def _entry(history: dict, index: str) -> dict:
    key = index.strip().lower()
    entry = (history.get("indices") or {}).get(key)
    if entry is None:
        raise KeyError(f"unknown index {index!r}; have {sorted(history.get('indices') or {})}")
    return entry


def members(history: dict, index: str, on: str) -> set[str] | None:
    """Members on `on` (YYYY-MM-DD), in the history's symbols; None before the index's first recorded date."""
    entry = _entry(history, index)
    base = entry["baseline"]
    if on < base["date"]:
        return None
    state = set(base["symbols"])
    for change in entry["changes"]:
        if change["date"] > on:
            break
        state = (state - set(change["removed"])) | set(change["added"])
    return state


def symbol_on(history: dict, symbol: str, on: str) -> str:
    """The ticker `symbol` traded under on `on`: forward over renames already done, then back over those not yet done."""
    ledger = (history.get("symbol_changes") or {}).get("changes") or []
    seen = set()
    while symbol not in seen:
        seen.add(symbol)
        step = next((c for c in ledger if c["old_symbol"] == symbol and on >= c["first_new_date"]), None)
        if step is None:
            break
        symbol = step["new_symbol"]
    seen = set()
    while symbol not in seen:
        seen.add(symbol)
        step = next((c for c in ledger if c["new_symbol"] == symbol and on <= c["last_old_date"]), None)
        if step is None:
            break
        symbol = step["old_symbol"]
    return symbol


def bhavcopy_symbols(history: dict, index: str, on: str) -> dict[str, str] | None:
    """{ticker as that day's bhavcopy names it: history symbol} for the members on `on`."""
    current = members(history, index, on)
    if current is None:
        return None
    return {symbol_on(history, s, on): s for s in current}


def read_bhavcopy_symbols(path: Path) -> set[str]:
    """Tickers in a bhavcopy CSV, old (SYMBOL) or new (TckrSymb) layout."""
    with open(path, newline="", encoding="utf-8-sig") as fh:
        rows = csv.DictReader(fh)
        names = {(n or "").strip(): n for n in (rows.fieldnames or [])}
        col = names.get("SYMBOL") or names.get("TckrSymb")
        if col is None:
            raise ValueError(f"{path}: no SYMBOL or TckrSymb column; have {sorted(names)}")
        return {(r[col] or "").strip() for r in rows if (r[col] or "").strip()}


def coverage(history: dict, index: str, on: str, bhav_symbols: set[str]) -> dict:
    """Members found and not found among `bhav_symbols`."""
    mapping = bhavcopy_symbols(history, index, on)
    if mapping is None:
        return {"date": on, "index": index, "recorded": False}
    missing = sorted(t for t in mapping if t not in bhav_symbols)
    return {"date": on, "index": index, "recorded": True, "members": len(mapping),
            "matched": len(mapping) - len(missing), "missing": missing}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("index")
    ap.add_argument("date", help="YYYY-MM-DD")
    ap.add_argument("--bhavcopy", type=Path, help="a bhavcopy CSV for that date: report members with no row")
    ap.add_argument("--history", type=Path, default=HISTORY)
    ap.add_argument("--notice-ledger-only", action="store_true",
                    help="join with the history's own ledger only, not NSE's symbolchange.csv")
    args = ap.parse_args(argv)
    history = load(args.history, renames=not args.notice_ledger_only)
    if args.bhavcopy:
        rep = coverage(history, args.index, args.date, read_bhavcopy_symbols(args.bhavcopy))
        if not rep["recorded"]:
            print(f"{args.index} has no record on {args.date}")
            return 2
        print(f"{rep['matched']}/{rep['members']} members found in {args.bhavcopy.name}")
        for t in rep["missing"]:
            print("  no bhavcopy row:", t)
        return 0
    mapping = bhavcopy_symbols(history, args.index, args.date)
    if mapping is None:
        print(f"{args.index} has no record on {args.date}")
        return 2
    for ticker in sorted(mapping):
        print(ticker if ticker == mapping[ticker] else f"{ticker}\t(history: {mapping[ticker]})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
