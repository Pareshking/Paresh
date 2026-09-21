"""Build a normalized historical market-cap series from repository history."""

from __future__ import annotations

import argparse
import csv
import io
import subprocess
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PATH = ROOT / "data/nse_market_caps.csv"


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout


def _snapshot(commit: str, path: str) -> pd.DataFrame:
    raw = _git("show", f"{commit}:{path}")
    frame = pd.read_csv(io.StringIO(raw))
    required = {"Symbol", "MarketCap", "AsOf", "Source"}
    if not required.issubset(frame.columns):
        raise RuntimeError(f"{path}@{commit[:8]} missing {sorted(required - set(frame.columns))}")
    frame = frame.rename(columns={"Symbol":"symbol","MarketCap":"market_cap","AsOf":"date","Source":"source"})
    frame["symbol"] = frame["symbol"].astype(str).str.strip().str.upper()
    frame["date"] = pd.to_datetime(frame["date"])
    return frame[["symbol","market_cap","date","source"]]


def build(output: Path, path: Path = DEFAULT_PATH) -> dict:
    rel = str(path.relative_to(ROOT))
    log = _git("log","--follow","--reverse","--format=%H","--",rel).strip()
    if not log:
        raise RuntimeError(f"no git history for {rel}")

    snapshots: dict[str, tuple[str, pd.DataFrame]] = {}
    for commit in log.splitlines():
        frame = _snapshot(commit, rel)
        if frame.empty:
            continue
        as_of = str(frame["date"].max().date())
        snapshots[as_of] = (commit, frame)

    if not snapshots:
        raise RuntimeError("no usable market-cap snapshots")

    parts = []
    for as_of, (commit, frame) in sorted(snapshots.items()):
        frame = frame.copy()
        frame["evidence_date"] = pd.Timestamp(as_of)
        frame["evidence_commit"] = commit
        parts.append(frame)

    result = pd.concat(parts, ignore_index=True).sort_values(["date","symbol"])
    result.to_parquet(output, index=False)

    summary = {
        "snapshot_count": len(snapshots),
        "row_count": len(result),
        "first_date": str(result["date"].min().date()),
        "last_date": str(result["date"].max().date()),
    }
    print(summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--path", type=Path, default=DEFAULT_PATH)
    args = parser.parse_args()
    build(args.output, args.path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
