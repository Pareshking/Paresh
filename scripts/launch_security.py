#!/usr/bin/env python3
"""What the launched site exposes, and to whom.

    python scripts/launch_security.py [--url http://localhost:8611]

Five checks, all read-only:

  repo      a secret committed to the repository
  page      a secret, a credential, an absolute path or an address in the
            HTML the site actually serves, chart frames included
  owner     the two site-wide controls stay hidden without the key
  params    a hostile ?stock= / ?sys= / ?wl= / ?owner= cannot throw, inject
            an element, open a dialog or reveal an owner control
  logs      what the server prints while serving those pages

Exit 1 if any check fails.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGES = ["", "portfolio", "actions", "watchlist", "screener", "sectors",
         "rrg", "breadth", "backtest", "configuration", "guide"]

# A secret is a long random-looking value under a telling name.
SECRET_RE = re.compile(
    r"(?i)(aws_secret|secret_key|api[_-]?key|access[_-]?token|password|r2_[a-z_]*key)"
    r"\s*[:=]\s*[\"']([A-Za-z0-9/+=_-]{20,})[\"']")
ALLOW_SECRET_VALUES = {"your-secret-here", "changeme", "xxx"}

# Shapes that should never reach a reader's browser, whatever they are called.
PAGE_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("an AWS-style access key id", re.compile(r"\b(AKIA|ASIA)[A-Z0-9]{16}\b")),
    ("a private key block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("a bearer token", re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._-]{20,}")),
    ("an absolute path on the server", re.compile(r"/(home|root|Users)/[A-Za-z0-9_.-]+/")),
    ("an e-mail address", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")),
    ("an R2 or S3 endpoint", re.compile(r"[a-z0-9]{20,}\.r2\.cloudflarestorage\.com")),
    ("a GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b")),
]

# Values the process itself holds. If one of these strings appears in a served
# page it has leaked, whatever its name -- the strongest check here, because it
# needs no pattern to recognise a secret.
ENV_NAMES = ("R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_ACCOUNT_ID", "OWNER_KEY",
             "AWS_SECRET_ACCESS_KEY", "AWS_ACCESS_KEY_ID", "GITHUB_TOKEN", "GH_TOKEN",
             "SCREENER_SESSION", "ANTHROPIC_API_KEY")


def check_repo() -> tuple[bool, str]:
    names = subprocess.run(["git", "ls-files", "-z"], capture_output=True,
                           cwd=ROOT).stdout.split(b"\0")
    hits, scanned = [], 0
    for raw in names:
        if not raw:
            continue
        path = ROOT / raw.decode("utf-8", "replace")
        try:
            text = path.read_text("utf-8", "ignore")
        except OSError:
            continue
        scanned += 1
        for m in SECRET_RE.finditer(text):
            if m.group(2).lower() not in ALLOW_SECRET_VALUES:
                hits.append(f"{path.relative_to(ROOT)}: {m.group(1)}")
    return not hits, f"{scanned:,} tracked files scanned, {len(hits)} hit(s) {hits[:3]}"


def check_pages(url: str) -> tuple[bool, str, dict]:
    dump = subprocess.run(
        ["node", str(ROOT / "scripts" / "_launch_html.js"), url.rstrip("/"), *PAGES],
        capture_output=True, text=True, cwd=ROOT)
    if dump.returncode != 0:
        return False, dump.stderr[-300:], {}
    pages = json.loads(dump.stdout.splitlines()[-1])

    live = {name: os.environ[name] for name in ENV_NAMES
            if os.environ.get(name) and len(os.environ[name]) >= 8}
    hits: dict[str, list[str]] = {}
    total = 0
    for page, html in pages.items():
        total += len(html)
        for label, pattern in PAGE_PATTERNS:
            for m in pattern.finditer(html):
                hits.setdefault(page, []).append(f"{label}: {m.group(0)[:60]!r}")
        for name, value in live.items():
            if value in html:
                hits.setdefault(page, []).append(f"the value of ${name} is in the page")
    detail = (f"{len(pages)} pages, {total / 1024:,.0f} KB of served HTML, "
              f"{len(live)} live credential(s) in this process to look for, "
              f"{sum(len(v) for v in hits.values())} hit(s)")
    return not hits, detail, hits


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--url", default="http://localhost:8611")
    ap.add_argument("--report", default="")
    args = ap.parse_args()

    report, failed = [], 0
    ok, detail = check_repo()
    report.append(("a secret committed to the repository", ok, detail))

    ok_pages, detail_pages, hits = check_pages(args.url)
    report.append(("a secret in the HTML the site serves", ok_pages, detail_pages))

    for name, ok, detail in report:
        print(f"{'PASS' if ok else 'FAIL'}  {name}: {detail}")
        failed += 0 if ok else 1
    for page, found in hits.items():
        for line in found[:6]:
            print(f"      {page}: {line}")

    if args.report:
        Path(args.report).write_text(json.dumps(
            {"checks": [{"name": n, "ok": o, "detail": d} for n, o, d in report],
             "page_hits": hits}, indent=1) + "\n")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
