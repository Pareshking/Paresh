#!/usr/bin/env python3
"""NSDL's FPI daily trends: the official record of foreign portfolio flows (S106).

    python scripts/nsdl_fpi.py --backfill 2016-01      # every month from Jan 2016
    python scripts/nsdl_fpi.py --latest                # the newest reporting dates
    python scripts/nsdl_fpi.py --probe [--date 31-Oct-2026]

NSDL (https://www.fpi.nsdl.co.in/web/Reports/) publishes FPI gross purchases,
sales and net investment per reporting date, from custodians' reports of the
previous trading day (T+1): confirmed figures, where NSE and MSEI give only the
latest day's provisional exchange figures. The Archive page returns a whole
month up to the date posted (dd-Mon-yyyy). NSDL refused the Claude session but
answers GitHub's runners (probe on PR #479, 7 Nov 2026).

Rows go to data/nsdl_fpi_daily.csv, equity only: reporting date, the stock
exchange route's gross purchases, sales and net, the primary market's net, the
equity sub-total net (Rs crore) and its US$ million. Refuses to write (exit 1)
when a row's purchases minus sales differ from its net by more than Rs 1 crore,
a date repeats with different figures, or nothing parsed.
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
import time
from datetime import date, datetime
from html import unescape
from pathlib import Path

import requests

BASE = "https://www.fpi.nsdl.co.in/web/Reports/"
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64)"}
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "nsdl_fpi_daily.csv"
FIELDS = ["date", "exchange_buy", "exchange_sell", "exchange_net", "primary_net", "equity_net",
          "equity_net_usd_mn", "source"]
DATE_RE = re.compile(r"^\d{2}-[A-Z][a-z]{2}-\d{4}$")


def hidden_fields(page: str) -> dict[str, str]:
    out = {}
    for m in re.finditer(r'<input[^>]*type="hidden"[^>]*>', page, re.I):
        tag = m.group(0)
        name = re.search(r'name="([^"]*)"', tag)
        value = re.search(r'value="([^"]*)"', tag)
        if name:
            out[name.group(1)] = unescape(value.group(1)) if value else ""
    return out


def table_rows(page: str, limit: int | None = None) -> list[list[str]]:
    rows = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", page, re.S | re.I):
        cells = [re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", c))).strip()
                 for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S | re.I)]
        if any(cells):
            rows.append(cells)
        if limit and len(rows) >= limit:
            break
    return rows


def _num(s: str) -> float:
    s = s.replace(",", "").strip()
    neg = s.startswith("(") and s.endswith(")")
    v = float(s.strip("()"))
    return -v if neg else v


def parse_daily(page: str, source: str) -> list[dict]:
    """Equity rows per reporting date from a Latest or Archive page.

    A date block starts with [date, "Equity", "Stock Exchange", buy, sell, net,
    usd, fx], then ["Primary market & others", buy, sell, net, usd], then the
    equity ["Sub-total", buy, sell, net, usd]."""
    rows = table_rows(page)
    out = []
    for i, r in enumerate(rows):
        if len(r) >= 6 and DATE_RE.match(r[0]) and r[1].lower().startswith("equity") and "exchange" in r[2].lower():
            d = datetime.strptime(r[0], "%d-%b-%Y").date()
            buy, sell, net = _num(r[3]), _num(r[4]), _num(r[5])
            prim = next((x for x in rows[i + 1:i + 3] if x and x[0].lower().startswith("primary")), None)
            sub = next((x for x in rows[i + 1:i + 4] if x and x[0].lower().startswith("sub-total")), None)
            if sub is None:
                continue
            out.append({"date": d.isoformat(), "exchange_buy": buy, "exchange_sell": sell, "exchange_net": net,
                        "primary_net": _num(prim[3]) if prim and len(prim) > 3 else 0.0,
                        "equity_net": _num(sub[3]), "equity_net_usd_mn": _num(sub[4]) if len(sub) > 4 else None,
                        "source": source})
    return out


def problems(rows: list[dict]) -> list[str]:
    bad = []
    if not rows:
        bad.append("nothing parsed")
    seen: dict[str, dict] = {}
    for r in rows:
        if abs((r["exchange_buy"] - r["exchange_sell"]) - r["exchange_net"]) > 1.0:
            bad.append(f"{r['date']}: purchases - sales != net ({r['exchange_buy']} - {r['exchange_sell']} vs {r['exchange_net']})")
        prev = seen.get(r["date"])
        if prev and abs(prev["equity_net"] - r["equity_net"]) > 0.01:
            bad.append(f"{r['date']}: two different equity nets ({prev['equity_net']}, {r['equity_net']})")
        seen[r["date"]] = r
    return bad


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update(UA)
    return s


def month_page(s: requests.Session, day: date) -> str:
    arch = s.get(BASE + "Archive.aspx", timeout=60).text
    form = hidden_fields(arch)
    when = day.strftime("%d-%b-%Y")
    form.update({"__EVENTTARGET": "btnSubmit1", "__EVENTARGUMENT": "", "hdnDate": when, "txtDate": when})
    r = s.post(BASE + "Archive.aspx", data=form, timeout=120)
    r.raise_for_status()
    return r.text


def month_ends(since: str, until: date) -> list[date]:
    y, m = (int(x) for x in since.split("-"))
    out = []
    while (y, m) <= (until.year, until.month):
        nxt = date(y + (m == 12), m % 12 + 1, 1)
        out.append(min(date.fromordinal(nxt.toordinal() - 1), until))
        y, m = nxt.year, nxt.month
    return out


def write(rows: list[dict]) -> int:
    old = {}
    if OUT.exists():
        with open(OUT, newline="", encoding="utf-8") as fh:
            old = {r["date"]: r for r in csv.DictReader(fh)}
    for r in rows:
        old[r["date"]] = r                     # NSDL's later page wins for a date
    with open(OUT, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        for d in sorted(old):
            w.writerow({k: old[d].get(k) for k in FIELDS})
    return len(old)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--backfill", metavar="YYYY-MM")
    ap.add_argument("--latest", action="store_true")
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--date", default="31-Oct-2026")
    a = ap.parse_args()
    s = _session()
    rows: list[dict] = []
    if a.probe:
        page = s.get(BASE + "Latest.aspx", timeout=60).text
        for r in table_rows(page, 40):
            print(" | ".join(r))
        print(parse_daily(page, "latest"))
        return 0
    if a.backfill:
        for d in month_ends(a.backfill, date.today()):
            try:
                got = parse_daily(month_page(s, d), f"archive {d:%Y-%m}")
            except requests.RequestException as exc:
                print(f"::warning::{d:%Y-%m}: {type(exc).__name__}")
                continue
            print(f"{d:%Y-%m}: {len(got)} reporting dates")
            rows += got
            time.sleep(1.5)                    # one request at a time, gently
    if a.latest:
        rows += parse_daily(s.get(BASE + "Latest.aspx", timeout=60).text, "latest")
    bad = problems(rows)
    for b in bad:
        print(f"::error::{b}")
    if bad:
        return 1
    n = write(rows)
    print(f"{len(rows)} rows read; {n} reporting dates in {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
