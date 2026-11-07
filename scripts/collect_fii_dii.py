#!/usr/bin/env python3
"""Append NSE's provisional FII/FPI and DII cash-market flows for the day (S91).

    python scripts/collect_fii_dii.py

NSE publishes one day at a time (https://www.nseindia.com/api/fiidiiTradeReact, the
"FII & DII trading activity" report) and keeps no history, so the history is what
this collects, from 7 Nov 2026. Rows go to data/fii_dii_flows.csv (date, category,
buy, sell, net in Rs crore, fetched_at). Refuses to write (exit 1) when a row's buy
minus sell differs from its net by more than Rs 1 crore, a category is missing, or
the date is in the future. A date already stored is left as it is (NSE's figures
are provisional; the first reading is kept and the file says so). NSDL, the
cross-check S91 names, refuses connections from GitHub's and Claude's runners.
"""
from __future__ import annotations

import csv
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "fii_dii_flows.csv"
URL = "https://www.nseindia.com/api/fiidiiTradeReact"
FIELDS = ["date", "category", "buy", "sell", "net", "fetched_at"]
CATEGORIES = {"FII/FPI", "DII"}


def fetch() -> list[dict]:
    s = requests.Session()
    s.headers.update({"User-Agent": "Mozilla/5.0 (X11; Linux x86_64)", "Accept": "application/json",
                      "Referer": "https://www.nseindia.com/reports/fii-dii"})
    s.get("https://www.nseindia.com/reports/fii-dii", timeout=30)
    r = s.get(URL, timeout=30)
    r.raise_for_status()
    return r.json()


def parse(payload: list[dict], now: datetime) -> tuple[list[dict], list[str]]:
    rows, bad = [], []
    for item in payload:
        cat = str(item.get("category", "")).strip()
        try:
            day = datetime.strptime(str(item["date"]).strip(), "%d-%b-%Y").date()
            buy, sell, net = (float(str(item[k]).replace(",", "")) for k in ("buyValue", "sellValue", "netValue"))
        except (KeyError, ValueError) as exc:
            bad.append(f"unreadable row {item!r} ({exc})")
            continue
        if abs((buy - sell) - net) > 1.0:
            bad.append(f"{cat} {day}: buy {buy} - sell {sell} is not net {net}")
        if day > now.date():
            bad.append(f"{cat} {day}: date in the future")
        rows.append({"date": day.isoformat(), "category": cat, "buy": buy, "sell": sell, "net": net,
                     "fetched_at": now.strftime("%Y-%m-%dT%H:%M:%SZ")})
    missing = CATEGORIES - {r["category"] for r in rows}
    if missing:
        bad.append(f"missing categories: {sorted(missing)}")
    return rows, bad


def main() -> int:
    now = datetime.now(timezone.utc)
    rows, bad = parse(fetch(), now)
    for b in bad:
        print(f"::error::{b}")
    if bad:
        return 1
    stored = set()
    if OUT.exists():
        with open(OUT, newline="", encoding="utf-8") as fh:
            stored = {(r["date"], r["category"]) for r in csv.DictReader(fh)}
    new = [r for r in rows if (r["date"], r["category"]) not in stored]
    if not new:
        print(f"{rows[0]['date']} already stored; nothing to add.")
        return 0
    first = not OUT.exists()
    with open(OUT, "a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        if first:
            w.writeheader()
        w.writerows(new)
    print(f"Added {len(new)} rows for {new[0]['date']} -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
