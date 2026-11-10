#!/usr/bin/env python3
"""Does every figure that appears on more than one page agree?

    python scripts/launch_consistency.py [--url http://localhost:8611]

This is the generalisation of the bug found on 8 Nov 2026, where the header
said the Nifty 500 was 2.9% above its 200-day EMA and the market-questions
table said +3.0 -- two code paths, two answers, one truth. A reader who spots
one of those stops believing the rest, so the launch check is not "does each
page render" but "do the pages agree with each other".

Each rule below names a figure, where it appears, and how close is close
enough. A rule that cannot find its figure on a page says so rather than
passing quietly: a check that silently matches nothing is worse than no check.

Read-only. Exit 1 if any figure disagrees or goes missing.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGES = ["", "screener", "portfolio", "actions", "sectors", "breadth", "backtest"]


def _num(text: str, pattern: str) -> float | None:
    """The first number a pattern captures, with the site's minus sign."""
    m = re.search(pattern, text, re.I)
    if not m:
        return None
    raw = m.group(1).replace("−", "-").replace(",", "").strip()
    try:
        return float(raw)
    except ValueError:
        return None


# (name, tolerance, {page: regex capturing the figure})
RULES: list[tuple[str, float, dict[str, str]]] = [
    ("Nifty 500 above its 200D EMA, %", 0.051, {
        "dashboard": r"Nifty 500\s+([\d.,−-]+)%\s+above its 200D EMA",
        # The by-size table is tab separated, two columns per measure (a
        # month ago, then now), so the figure is the FOURTH field of the
        # Nifty 500 row. Reading the first number after the heading gave
        # the month-ago column and made this rule cry wolf.
        "breadth": r"Nifty 500\t[^\t\n]+\t[^\t\n]+\t[^\t\n]+\t([+\u2212\d.,-]+)",
    }),
    ("Nifty 500 index level", 1.0, {
        "dashboard": r"Nifty 500\s+([\d,]+)\s",
        "screener": r"Nifty 500\s+([\d,]+)\s",
        "portfolio": r"Nifty 500\s+([\d,]+)\s",
    }),
    ("the universe's size", 0.0, {
        "dashboard": r"Universe\s+([\d,]+)",
        "screener": r"Universe\s+([\d,]+)",
        "actions": r"Universe\s+([\d,]+)",
    }),
    ("stocks above their 50D EMA", 0.0, {
        "dashboard": r"Above 50D EMA\s+([\d,]+)",
        "screener": r"Above 50D EMA\s+([\d,]+)",
    }),
    ("stocks near their 52W high", 0.0, {
        "dashboard": r"Near 52W high\s+([\d,]+)",
        "screener": r"Near 52W high\s+([\d,]+)",
    }),
    ("stocks above their 200D EMA, %", 0.51, {
        "dashboard": r"([\d.]+)% of the ranked stocks are above their 200D EMA",
        "breadth": r"Above 200D EMA([\d.]+)%",
    }),
]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--url", default="http://localhost:8611")
    ap.add_argument("--report", default="")
    args = ap.parse_args()

    dump = subprocess.run(
        ["node", str(ROOT / "scripts" / "_launch_text.js"), "1400",
         args.url.rstrip("/"), *PAGES],
        capture_output=True, text=True, cwd=ROOT)
    if dump.returncode != 0:
        print(dump.stderr[-400:], file=sys.stderr)
        return 1
    pages = json.loads(dump.stdout.splitlines()[-1])

    report, failed = [], 0
    for name, tol, where in RULES:
        found = {}
        missing = []
        for page, pattern in where.items():
            value = _num(pages.get(page, ""), pattern)
            if value is None:
                missing.append(page)
            else:
                found[page] = value
        spread = (max(found.values()) - min(found.values())) if len(found) > 1 else 0.0
        ok = not missing and len(found) > 1 and spread <= tol
        status = ("agree" if ok else
                  f"NOT FOUND on {missing}" if missing else
                  "only one page has it" if len(found) < 2 else
                  f"DISAGREE by {spread:.3f} (tolerance {tol})")
        print(f"{'PASS' if ok else 'FAIL'}  {name}: {found} -- {status}")
        report.append({"figure": name, "values": found, "missing": missing,
                       "spread": spread, "ok": ok})
        failed += 0 if ok else 1

    print(f"\n{len(RULES) - failed}/{len(RULES)} figures agree across pages")
    if args.report:
        Path(args.report).write_text(json.dumps(report, indent=1) + "\n")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
