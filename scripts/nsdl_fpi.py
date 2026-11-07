#!/usr/bin/env python3
"""NSDL's FPI daily trends: read the Latest page, and the Archive page for a date (S106).

    python scripts/nsdl_fpi.py --probe [--date 31-Oct-2026]

NSDL (https://www.fpi.nsdl.co.in/web/Reports/) publishes daily FPI net investment
in equity and debt, reported by custodians (T+1), with an archive by date: the
official record of foreign portfolio flows, where NSE and MSEI give only the
latest day's provisional exchange figures. NSDL refused the Claude session but
answers GitHub's runners (probe, 7 Nov 2026). --probe prints what the pages hold.
"""
from __future__ import annotations

import argparse
import re
import sys
from html import unescape

import requests

BASE = "https://www.fpi.nsdl.co.in/web/Reports/"
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64)"}


def hidden_fields(page: str) -> dict[str, str]:
    out = {}
    for m in re.finditer(r'<input[^>]*type="hidden"[^>]*>', page, re.I):
        tag = m.group(0)
        name = re.search(r'name="([^"]*)"', tag)
        value = re.search(r'value="([^"]*)"', tag)
        if name:
            out[name.group(1)] = unescape(value.group(1)) if value else ""
    return out


def table_rows(page: str, limit: int = 60) -> list[list[str]]:
    rows = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", page, re.S | re.I):
        cells = [re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", c))).strip()
                 for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S | re.I)]
        if any(cells):
            rows.append(cells)
        if len(rows) >= limit:
            break
    return rows


def probe(date: str) -> None:
    s = requests.Session()
    s.headers.update(UA)
    latest = s.get(BASE + "Latest.aspx", timeout=40).text
    print("=== Latest: table rows")
    for r in table_rows(latest):
        print(" | ".join(r))
    arch = s.get(BASE + "Archive.aspx", timeout=40).text
    print("=== Archive: controls")
    for m in re.finditer(r"<(input|a|select)[^>]*>", arch, re.I):
        tag = m.group(0)
        if "VIEWSTATE" in tag or "EVENTVALIDATION" in tag:
            continue
        if any(k in tag for k in ("name=", "__doPostBack", "onclick")):
            print(re.sub(r"\s+", " ", tag)[:220])
    for name in ("fnVal", "datepicker", "dateFormat"):
        for m in re.finditer(name, arch):
            print(f"--- near {name}:", re.sub(r"\s+", " ", arch[max(0, m.start() - 80): m.start() + 300])[:380])
            break
    for fmt in (date, "2026-10-31", "31/10/2026"):
        form = hidden_fields(arch)
        form.update({"__EVENTTARGET": "btnSubmit1", "__EVENTARGUMENT": "", "hdnDate": fmt, "txtDate": fmt, "hdnFlag": "1"})
        r = s.post(BASE + "Archive.aspx", data=form, timeout=60)
        rows = table_rows(r.text, 80)
        print(f"=== Archive POST hdnDate={fmt}: HTTP {r.status_code}, {len(r.text)} bytes, {len(rows)} rows")
        for row in rows[:45]:
            print(" | ".join(row))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--date", default="31-Oct-2026")
    a = ap.parse_args()
    if a.probe:
        probe(a.date)
    return 0


if __name__ == "__main__":
    sys.exit(main())
