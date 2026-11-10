#!/usr/bin/env python3
"""The performance and weight baseline, for the owner's 10/20/20 targets.

    python scripts/launch_perf.py [--url http://localhost:8611] [--report out.json]

Owner, 9 Nov 2026: "I want my code to be 10% faster, 20% less resources usage
and 20% less space." A target needs a number to be measured against, and this
prints it: time to content and bytes for every page, the heaviest page's DOM
and heap, the repository's tracked size, and the test suite's runtime.

Everything here is read-only and nothing is a pass or a fail: a baseline that
fails is a baseline nobody records. Run it again after a change and compare.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGES = ["", "portfolio", "actions", "watchlist", "screener", "sectors",
         "rrg", "breadth", "backtest", "configuration", "guide"]


def _kb(n: float) -> str:
    return f"{n / 1024:,.0f} KB"


def _tracked_size() -> list[tuple[str, int]]:
    """The biggest directories git is actually carrying."""
    out = subprocess.run(["git", "ls-files", "-z"], capture_output=True,
                         cwd=ROOT, text=False).stdout
    sizes: dict[str, int] = {}
    for raw in out.split(b"\0"):
        if not raw:
            continue
        rel = raw.decode("utf-8", "replace")
        try:
            size = (ROOT / rel).stat().st_size
        except OSError:
            continue
        top = rel.split("/")[0] if "/" in rel else "(root files)"
        second = "/".join(rel.split("/")[:2]) if rel.count("/") >= 1 else top
        sizes[second if top in {"data", "docs", "scripts", "src"} else top] = (
            sizes.get(second if top in {"data", "docs", "scripts", "src"} else top, 0) + size)
    return sorted(sizes.items(), key=lambda kv: -kv[1])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--url", default="http://localhost:8611")
    ap.add_argument("--width", default="1400")
    ap.add_argument("--report", default="")
    ap.add_argument("--skip-tests", action="store_true",
                    help="leave the suite's runtime out (it is the slowest part)")
    args = ap.parse_args()

    run = subprocess.run(
        ["node", str(ROOT / "scripts" / "_launch_perf.js"), args.width,
         args.url.rstrip("/"), *PAGES],
        capture_output=True, text=True, cwd=ROOT)
    if run.returncode != 0:
        print(run.stderr[-600:], file=sys.stderr)
        return 1
    pages = json.loads(run.stdout.splitlines()[-1])

    print(f"{'page':<14} {'cold ms':>8} {'cold wire':>11} {'warm ms':>8} "
          f"{'warm wire':>11} {'nodes':>7} {'frames':>7} {'frame HTML':>11} {'heap':>9}")
    for page, m in pages.items():
        c, w = m["cold"], m["warm"]
        print(f"{page:<14} {c['ms']:>8,} {_kb(c['over']):>11} {w['ms']:>8,} "
              f"{_kb(w['over']):>11} {c['nodes']:>7,} {c['frames']:>7} "
              f"{_kb(c['frameBytes']):>11} {_kb(c['heap']):>9}")

    heaviest = max(pages.items(), key=lambda kv: kv[1]["cold"]["over"])
    slowest = max(pages.items(), key=lambda kv: kv[1]["cold"]["ms"])
    warmest = max(pages.items(), key=lambda kv: kv[1]["warm"]["over"])
    print(f"\nheaviest first visit: {heaviest[0]} at {_kb(heaviest[1]['cold']['over'])}; "
          f"slowest: {slowest[0]} at {slowest[1]['cold']['ms']:,} ms; "
          f"most still downloaded on a warm visit: {warmest[0]} at "
          f"{_kb(warmest[1]['warm']['over'])}")

    print("\nTracked size, biggest first:")
    total = 0
    rows = _tracked_size()
    for name, size in rows[:12]:
        print(f"  {_kb(size):>11}  {name}")
    total = sum(s for _, s in rows)
    print(f"  {_kb(total):>11}  everything git tracks")

    suite = None
    if not args.skip_tests:
        t0 = time.monotonic()
        res = subprocess.run([sys.executable, "-m", "pytest", "tests", "-q"],
                             capture_output=True, text=True, cwd=ROOT)
        suite = time.monotonic() - t0
        tail = [ln for ln in res.stdout.splitlines() if " passed" in ln or " failed" in ln]
        print(f"\nTest suite: {suite:,.0f} s — {tail[-1] if tail else 'no summary line'}")

    if args.report:
        Path(args.report).write_text(json.dumps(
            {"pages": pages, "tracked": rows, "suite_seconds": suite}, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
