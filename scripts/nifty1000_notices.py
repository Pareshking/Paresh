#!/usr/bin/env python3
"""Every NSE Indices notice since the Nifty 1000's launch, read for what it says about the Nifty 1000 (S196).

    python scripts/nifty1000_notices.py            # fetch new notices, update the ledger, check the history
    python scripts/nifty1000_notices.py --check    # check the committed ledger against the history only

The other indices' history rests on NSE's notices (docs/MEMBERSHIP_FROM_NOTICES.md); the Nifty 1000 is tracked the
same way from its launch (ind_prs12112026.pdf, 12 Nov 2026). Each notice issued since then is downloaded once and
recorded in data/reference/nse/nifty1000_notices.json with its SHA-256 and what it says about the Nifty 1000:

- a replacement notice's own "Nifty 1000" table of inclusions and exclusions (parse_index_notices.sections), or
- a single-company notice ("Exclusion of X from Nifty Indices") whose table of indices names the Nifty 1000,
- or nothing ("mentions": false), so a notice read and found silent is told apart from one never read.

The check compares the ledger with data/membership_history.json: a change the history records after the first list
(nifty1000_backfill.FIRST_RECORDED) with no notice behind it, or a notice whose change is due and not recorded, is
printed as a warning (a notice effective today may not be in the history yet). A failed fetch fails the run.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from datetime import date, datetime
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import parse_index_notices as pin  # noqa: E402

LEDGER = ROOT / "data" / "reference" / "nse" / "nifty1000_notices.json"
HISTORY = ROOT / "data" / "membership_history.json"
LISTING = "https://www.niftyindices.com/press-release"
PDF = "https://www.niftyindices.com/Press_Release/{}"
LAUNCH = date(2026, 11, 12)
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
      "Referer": "https://www.niftyindices.com/"}
NAME = "Nifty 1000"
_ITEM = re.compile(r'data-date="([A-Z][a-z]{2} \d{2}, \d{4})"[^>]*>\s*<p>[^<]*</p>\s*'
                   r"<a href='/Press_Release/(ind_prs[\w]+\.pdf)'[^>]*>([^<]+)</a>")
# A row of a single-company notice's index table: "   1      Nifty 1000" (and not "Nifty1000 Equal Weight").
_INDEX_ROW = re.compile(r"^\s*\d{1,3}\s+Nifty 1000\s*$", re.M)
_HEADING = re.compile(r"(Exclusion|Inclusion)s? of (.+?) (?:from|in) Nifty", re.I)


def listing(html: str, since: date = LAUNCH) -> list[dict]:
    """[{issued, notice, title}] for every notice on the press-release page issued on or after `since`."""
    out = []
    for when, notice, title in _ITEM.findall(html):
        d = datetime.strptime(when, "%b %d, %Y").date()
        if d >= since:
            out.append({"issued": d.isoformat(), "notice": notice, "title": title.replace("&amp;", "&").strip()})
    return sorted(out, key=lambda n: (n["issued"], n["notice"]))


def read(text: str) -> dict:
    """What a notice's text says about the Nifty 1000."""
    eff = pin.effective_dates(text)
    out = {"effective": eff[0].isoformat() if eff else None, "mentions": False, "included": [], "excluded": []}
    sec = pin.sections(text, NAME)
    if sec:
        out.update(mentions=True, kind="table", included=sorted(sec.get("included", [])),
                   excluded=sorted(sec.get("excluded", [])))
    elif _INDEX_ROW.search(text):
        # The company is the heading's ("Exclusion of Ennature Bio Pharma Ltd. from Nifty Indices"); its symbol
        # is the one in brackets after its name. The first bracket in the text can be another company's.
        h = _HEADING.search(text)
        sym = None
        if h:
            m = re.search(re.escape(h.group(2).strip()) + r"\s*\(([A-Z0-9&\-]{2,20})\)", text)
            sym = m.group(1) if m else None
        word = "excluded" if h and h.group(1).lower().startswith("exclu") else "included"
        out.update(mentions=True, kind="index list", **{word: [sym] if sym else []})
        if not sym:
            out["unread"] = "company symbol not found after its name"
    return out


def _text(pdf: bytes) -> str:
    with tempfile.NamedTemporaryFile(suffix=".pdf") as fh:
        fh.write(pdf)
        fh.flush()
        return subprocess.run(["pdftotext", "-layout", fh.name, "-"], capture_output=True, text=True,
                              check=True).stdout


def _get(url: str, session=requests) -> bytes:
    r = session.get(url, headers=UA, timeout=60)
    if r.status_code != 200 or not r.content:
        raise RuntimeError(f"{url}: HTTP {r.status_code}, {len(r.content)} bytes")
    return r.content


def update(ledger: dict, session=requests) -> int:
    """Add every notice issued since the launch that the ledger lacks; the count added."""
    have = {n["notice"] for n in ledger["notices"]}
    added = 0
    for item in listing(_get(LISTING, session).decode("utf-8", errors="replace")):
        if item["notice"] in have:
            continue
        pdf = _get(PDF.format(item["notice"]), session)
        ledger["notices"].append({**item, "url": PDF.format(item["notice"]),
                                  "sha256": hashlib.sha256(pdf).hexdigest(), **read(_text(pdf))})
        added += 1
    ledger["notices"].sort(key=lambda n: (n["issued"], n["notice"]))
    return added


def check(ledger: dict, history: dict, today: str | None = None) -> list[str]:
    """Warnings: recorded changes with no notice, and due notices not recorded."""
    from src.engine.nifty1000_backfill import FIRST_RECORDED, members_at

    entry = (history.get("indices") or {}).get("nifty_1000")
    if not entry:
        return []
    today = today or date.today().isoformat()
    said = [n for n in ledger["notices"] if n.get("mentions")]
    told = {(s, "added") for n in said for s in n["included"]} | {(s, "removed") for n in said for s in n["excluded"]}
    out = []
    for c in entry.get("changes", []):
        if c["date"] <= FIRST_RECORDED:
            continue
        for how in ("added", "removed"):
            for s in c.get(how, []):
                if (s, how) not in told:
                    out.append(f"{c['date']}: {s} {how} in the history, no NSE notice names it for the Nifty 1000")
    for n in said:
        if not n["effective"] or n["effective"] > today:
            continue
        now = members_at(entry, today)
        out += [f"{n['notice']} includes {s} from {n['effective']}; the history does not hold it"
                for s in n["included"] if s not in now]
        out += [f"{n['notice']} excludes {s} from {n['effective']}; the history still holds it"
                for s in n["excluded"] if s in now]
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="check the committed ledger only; fetch nothing")
    args = ap.parse_args(argv)
    ledger = (json.loads(LEDGER.read_text(encoding="utf-8")) if LEDGER.exists() else
              {"index": NAME, "source": LISTING, "since": LAUNCH.isoformat(), "notices": []})
    if not args.check:
        try:
            n = update(ledger)
        except (requests.RequestException, RuntimeError, subprocess.CalledProcessError) as exc:
            print(f"::error::Nifty 1000 notices could not be read: {exc}")
            return 1
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        LEDGER.write_text(json.dumps(ledger, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"Nifty 1000 notices: {n} new, {len(ledger['notices'])} read since {LAUNCH}, "
              f"{sum(1 for x in ledger['notices'] if x.get('mentions'))} name the index")
    warnings = check(ledger, json.loads(HISTORY.read_text(encoding="utf-8")))
    for w in warnings:
        print(f"::warning::{w}")
    if not warnings:
        print("Nifty 1000 history agrees with every notice read")
    return 0


if __name__ == "__main__":
    sys.exit(main())
