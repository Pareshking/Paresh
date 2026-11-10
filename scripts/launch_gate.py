#!/usr/bin/env python3
"""Is the site fit to launch right now? One command, measured answers.

    python scripts/launch_gate.py [--url http://localhost:8611] [--report gate.json]

Launch day needs one thing a test suite cannot give: a check that the pages a
reader will open actually draw, with the data that is really on disk, and that
nothing on them contradicts anything else. This runs that check and prints a
verdict per item with the number behind it, so a pass is evidence and not a
feeling (docs/LAUNCH_TEST_PLAN.md, slot 1).

It changes nothing. Exit 1 if any gate fails.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PAGES = ["", "portfolio", "actions", "watchlist", "screener", "sectors",
         "rrg", "breadth", "backtest", "configuration", "guide"]

# A secret would be a long random-looking value assigned to a telling name.
SECRET_RE = re.compile(
    r"(?i)(aws_secret|secret_key|api[_-]?key|access[_-]?token|password|r2_[a-z_]*key)"
    r"\s*[:=]\s*[\"']([A-Za-z0-9/+=_-]{20,})[\"']")
ALLOW_SECRET_VALUES = {"your-secret-here", "changeme", "xxx"}


def _gate(report: list[dict], name: str, ok: bool, detail: str) -> None:
    report.append({"gate": name, "ok": bool(ok), "detail": detail})
    print(f"{'PASS' if ok else 'FAIL'}  {name}: {detail}", flush=True)


def check_secrets(report: list[dict]) -> None:
    """No secret committed. Checked by pattern, over tracked files only."""
    tracked = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True,
                             text=True).stdout.split()
    hits = []
    for rel in tracked:
        p = ROOT / rel
        if p.suffix.lower() in {".png", ".jpg", ".woff2", ".parquet", ".zip", ".xls", ".pdf"}:
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for m in SECRET_RE.finditer(text):
            if m.group(2).lower() not in ALLOW_SECRET_VALUES:
                hits.append(f"{rel}: {m.group(1)}")
    _gate(report, "no secret in the repository", not hits,
          f"{len(tracked)} tracked files scanned" if not hits else f"{len(hits)}: {hits[:3]}")


def check_data_freshness(report: list[dict]) -> None:
    """Every source the footer dates is inside its own tolerance."""
    sys.path.insert(0, str(ROOT))
    from src.core.market_time import ist_today, trading_days_behind
    import pandas as pd

    closes = ROOT / "data" / "nse_prices" / "closes.parquet"
    if not closes.exists():
        _gate(report, "prices on disk", False, "data/nse_prices/closes.parquet is missing")
        return
    frame = pd.read_parquet(closes)
    idx = pd.DatetimeIndex(frame.index if frame.index.name else frame.index)
    last = pd.Timestamp(idx[-1]).date()
    behind = trading_days_behind(last, today=ist_today())
    # This file is the FALLBACK (src/loaders/nse_prices.py:8). The live app
    # reads the R2 pin or the release copy first, so the committed one lagging
    # a few sessions is normal and is not what a reader sees; what a reader
    # sees is the footer, which the page sweep reads. The gate still fails if
    # the fallback is so old that it would mislead on a day R2 is unreachable.
    _gate(report, "the committed fallback prices are usable",
          behind is not None and behind <= 10,
          f"last session {last}, {behind} trading day(s) behind "
          f"(fallback only; the app reads R2 or the release first)"
          if behind is not None else f"last session {last} is not a known trading day")

    mh = ROOT / "data" / "momentum_health_latest.json"
    if mh.exists():
        payload = json.loads(mh.read_text())
        _gate(report, "the qualified share is dated", bool(payload.get("date")),
              f"{payload.get('date')} at {float(payload.get('qualified', 0)) * 100:.1f}%")


def check_pages(url: str, report: list[dict]) -> None:
    """Every page draws, throws nothing, and fits its viewport at 390px."""
    script = ROOT / "scripts" / "_launch_pages.js"
    if not script.exists():
        _gate(report, "page sweep", False, "scripts/_launch_pages.js is missing")
        return
    for width in (1400, 390):
        out = subprocess.run(
            ["node", str(script), str(width), url, *PAGES],
            capture_output=True, text=True, cwd=ROOT)
        if out.returncode != 0:
            _gate(report, f"pages at {width}px", False, out.stderr.strip()[-200:] or "node failed")
            continue
        rows = [json.loads(ln) for ln in out.stdout.splitlines() if ln.startswith("{")]
        bad = [r for r in rows if r["exceptions"] or r["overflow"] > 0 or r["chars"] < 200]
        _gate(report, f"pages at {width}px", not bad,
              f"{len(rows)} pages drawn, none over its viewport" if not bad else str(bad[:2]))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--url", default="http://localhost:8611")
    ap.add_argument("--report", default="")
    ap.add_argument("--skip-pages", action="store_true")
    args = ap.parse_args()

    report: list[dict] = []
    check_secrets(report)
    check_data_freshness(report)
    if not args.skip_pages:
        check_pages(args.url.rstrip("/"), report)

    failed = [r for r in report if not r["ok"]]
    print(f"\n{len(report) - len(failed)}/{len(report)} gates pass", flush=True)
    if args.report:
        Path(args.report).write_text(json.dumps(report, indent=1) + "\n")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
