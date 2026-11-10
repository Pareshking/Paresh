#!/usr/bin/env python3
"""Is the site readable by someone who cannot see it, or cannot see it well?

    python scripts/launch_a11y.py [--url http://localhost:8611] [--width 1400]

Target: WCAG 2.1 AA. Four things are measured, each on the rendered page
rather than on the stylesheet, because what a reader meets is the computed
colour on the background that is actually painted behind it:

  contrast   every visible text run, 4.5:1 normal / 3:1 large
  headings   one h1 per page, no skipped level
  names      every button, link and input announces something
  focus      the keyboard's path shows a ring at each stop

Read-only. Exit 1 if any check fails.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# The same eleven paths the launch gate draws. "config" and "sector_rotation"
# are not routes: Streamlit served the dashboard for them, and the check then
# measured the dashboard twice under another page's name.
PAGES = ["", "portfolio", "actions", "watchlist", "screener", "sectors",
         "rrg", "breadth", "backtest", "configuration", "guide"]


def _headings_fault(levels: list[int]) -> str:
    """A heading order a screen reader can navigate: one h1, no jump down."""
    if not levels:
        return "no headings at all"
    if levels[0] != 1:
        return f"first heading is h{levels[0]}, not h1"
    if levels.count(1) > 1:
        return f"{levels.count(1)} h1s"
    for a, b in zip(levels, levels[1:]):
        if b > a + 1:
            return f"h{a} jumps to h{b}"
    return ""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--url", default="http://localhost:8611")
    ap.add_argument("--width", default="1400")
    ap.add_argument("--report", default="")
    ap.add_argument("--self-test", action="store_true",
                    help="plant one failing text run on each page and require it to be caught")
    args = ap.parse_args()

    env = None
    if args.self_test:
        import os
        env = {**os.environ, "A11Y_SELFTEST": "1"}
    run = subprocess.run(
        ["node", str(ROOT / "scripts" / "_launch_a11y.js"), args.width,
         args.url.rstrip("/"), *PAGES],
        capture_output=True, text=True, cwd=ROOT, env=env)
    if run.returncode != 0:
        print(run.stderr[-600:], file=sys.stderr)
        return 1
    pages = json.loads(run.stdout.splitlines()[-1])

    failed = 0
    for page, res in pages.items():
        rows = list(res["contrast"])
        checked = res["checked"]
        for frame in res.get("frames", []):
            rows += frame["contrast"]
            checked += frame["checked"]
        names = res["noName"]
        alts = res["noAlt"]
        order = _headings_fault([h["level"] for h in res["headings"]])
        # WCAG 3.1.1: a screen reader needs to know which language to read in.
        lang = "" if res["lang"] else "no lang on <html>"
        stops = res["focus"]
        blind = [f for f in stops if not f["ring"]]
        frames_stopped = [f for f in stops if f.get("frameStop")]

        bad = (bool(rows) or bool(names) or bool(alts) or bool(order)
               or bool(blind) or bool(lang))
        failed += 1 if bad else 0
        print(f"{'FAIL' if bad else 'PASS'}  {page or 'dashboard'}: "
              f"{len(rows)} contrast of {checked} text runs, "
              f"{len(names)} unnamed of {res['named']} controls, {len(alts)} no-alt, "
              f"{len(stops)} focus stops ({len(blind)} with no ring, "
              f"{len(frames_stopped)} into a chart frame)"
              + (f", headings: {order}" if order else "")
              + (f", {lang}" if lang else ""))
        for r in sorted(rows, key=lambda r: r["ratio"])[:8]:
            print(f"      {r['ratio']}:1 (needs {r['need']}) {r['px']}px "
                  f"{r['color']} on {r['bg']} x{r['count']} — {r['sample']!r} [{r['where']}]")
        for n in names[:6]:
            print(f"      unnamed {n['tag']} {n['cls']} {n['test']}")
        for f in blind[:6]:
            print(f"      no focus ring: {f['tag']} {f['text']!r} {f['cls']}")

    if args.self_test:
        caught = sum(1 for res in pages.values()
                     if any("self test" in r["sample"] for r in res["contrast"]))
        print(f"\nself test: the planted 1.66:1 run was caught on "
              f"{caught}/{len(pages)} pages")
        return 0 if caught == len(pages) else 1

    print(f"\n{len(pages) - failed}/{len(pages)} pages clean")
    if args.report:
        Path(args.report).write_text(json.dumps(pages, indent=1) + "\n")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
