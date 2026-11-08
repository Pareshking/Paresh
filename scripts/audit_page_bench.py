#!/usr/bin/env python3
"""Time and memory per page of the local app (docs/AUDIT_PLAN.md, Block 0).

Starts `streamlit run app.py` with an empty cache directory (a cold start),
then opens each page of the menu in turn in headless Chromium and records:

  seconds   from navigation until the script has run and then stayed
            not-running for 1.5 s (stApp's data-test-script-state)
  rss_mb    the server's resident memory (process + children) afterwards
  peak_mb   the highest resident memory sampled (every 100 ms) during the load
  errors    Streamlit exception boxes rendered on the page

    python scripts/audit_page_bench.py [--out bench.json] [--rounds 2]

Round 1 is cold (empty cache); later rounds are warm. One reader at a time:
the concurrency case is in docs/MEMORY_AUDIT_2026-10-08.md.
Numbers are from this machine, not Streamlit Cloud; compare runs on the same
machine only.
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGES = ["", "portfolio", "actions", "sectors", "rrg", "watchlist",
         "breadth", "backtest", "configuration", "guide", "?stock=RELIANCE"]
SETTLE_S = 1.5
PAGE_TIMEOUT_S = 300


def _rss_mb(pid: int) -> float:
    """Resident memory of pid and its children, from /proc."""
    total = 0
    pids = [pid]
    try:
        kids = subprocess.run(["pgrep", "-P", str(pid)], capture_output=True, text=True).stdout.split()
        pids += [int(k) for k in kids]
    except Exception:
        pass
    for p in pids:
        try:
            for line in Path(f"/proc/{p}/status").read_text().splitlines():
                if line.startswith("VmRSS:"):
                    total += int(line.split()[1])
        except Exception:
            continue
    return total / 1024


class Sampler(threading.Thread):
    def __init__(self, pid: int):
        super().__init__(daemon=True)
        self.pid, self.peak, self._stop = pid, 0.0, threading.Event()

    def reset(self) -> None:
        self.peak = _rss_mb(self.pid)

    def run(self) -> None:
        while not self._stop.is_set():
            self.peak = max(self.peak, _rss_mb(self.pid))
            time.sleep(0.1)

    def stop(self) -> None:
        self._stop.set()


def _wait_idle(page, t0: float) -> float:
    """Seconds from t0 until Streamlit's running indicator has been absent for SETTLE_S."""
    page.wait_for_selector('[data-testid="stApp"]', timeout=PAGE_TIMEOUT_S * 1000)
    quiet_since, seen_run = None, False
    while time.perf_counter() - t0 < PAGE_TIMEOUT_S:
        # stApp carries data-test-script-state: initial -> running -> notRunning.
        state = page.get_attribute('[data-testid="stApp"]', "data-test-script-state")
        now = time.perf_counter()
        if state == "running":
            seen_run = True
        if state != "notRunning" or not seen_run:
            quiet_since = None
        elif quiet_since is None:
            quiet_since = now
        elif now - quiet_since >= SETTLE_S:
            return quiet_since - t0
        time.sleep(0.1)
    return float("nan")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="page_bench.json")
    ap.add_argument("--rounds", type=int, default=2)
    ap.add_argument("--port", type=int, default=8599)
    args = ap.parse_args()

    from playwright.sync_api import sync_playwright

    cache = tempfile.mkdtemp(prefix="bench_cache_")
    env = dict(os.environ, TMPDIR=cache)
    t_start = time.perf_counter()
    proc = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", "app.py", "--server.headless", "true",
         "--server.port", str(args.port), "--browser.gatherUsageStats", "false"],
        cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        start_new_session=True,
    )
    log: list[str] = []
    threading.Thread(target=lambda: [log.append(line) for line in proc.stdout], daemon=True).start()
    sampler = Sampler(proc.pid)
    sampler.start()
    results: list[dict] = []
    try:
        import urllib.request
        for _ in range(600):
            try:
                urllib.request.urlopen(f"http://localhost:{args.port}/_stcore/health", timeout=1)
                break
            except Exception:
                time.sleep(0.2)
        server_up_s = time.perf_counter() - t_start
        print(f"server up in {server_up_s:.1f} s, RSS {_rss_mb(proc.pid):.0f} MB")

        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            for rnd in range(1, args.rounds + 1):
                for path in PAGES:
                    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
                    page = ctx.new_page()
                    sampler.reset()
                    url = f"http://localhost:{args.port}/" + ("" if path.startswith("?") else path)
                    if path.startswith("?"):
                        url += path
                    t0 = time.perf_counter()
                    page.goto(url, timeout=PAGE_TIMEOUT_S * 1000)
                    secs = _wait_idle(page, t0)
                    errors = len(page.query_selector_all('[data-testid="stException"]'))
                    row = {"round": rnd, "page": path, "seconds": round(secs, 1),
                           "rss_mb": round(_rss_mb(proc.pid)), "peak_mb": round(sampler.peak),
                           "errors": errors}
                    results.append(row)
                    print(json.dumps(row))
                    ctx.close()
            browser.close()
    finally:
        sampler.stop()
        os.killpg(proc.pid, signal.SIGTERM)
        try:
            proc.wait(timeout=20)
        except Exception:
            os.killpg(proc.pid, signal.SIGKILL)

    report = {"server_up_s": round(server_up_s, 1), "pages": results,
              "log_tail": [line.rstrip() for line in log[-40:]]}
    Path(args.out).write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(f"-> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
