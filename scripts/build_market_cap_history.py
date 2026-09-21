"""Build a normalized dated market-cap series from repository-maintained snapshots.

The repository currently records market-cap snapshots in data/nse_market_caps.csv.
This builder reconstructs dated snapshots from Git history, preserving the commit
that supplied each retained snapshot. It does not invent missing historical values.
"""

from __future__ import annotations

import argparse
import io
import subprocess
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PATH = ROOT / "data/nse_market_caps.csv"
REQUIRED = {"Symbol", "MarketCap", "AsOf", "Source"}


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout


def _snapshot(commit: str, path: str) -> pd.DataFrame | None:
    raw = _git("show", f"{commit}:{path}")
    frame = pd.read_csv(io.StringIO(raw))
    missing = REQUIRED - set(frame.columns)
    value_missing = {"Symbol", "MarketCap"} - set(frame.columns)
    if value_missing:
        raise RuntimeError(
            f"{path}@{commit[:8]} missing required value columns {sorted(value_missing)}"
        )
    # Older repository snapshots predate the explicit AsOf/Source columns.
    # They are retained in Git but are not converted into dated evidence,
    # because doing so would invent a market-cap date/source.
    if {"AsOf", "Source"} & missing:
        return None

    frame = frame.rename(
        columns={
            "Symbol": "symbol",
            "MarketCap": "market_cap",
            "AsOf": "date",
            "Source": "source",
        }
    )
    frame["symbol"] = frame["symbol"].astype(str).str.strip().str.upper()
    frame["date"] = pd.to_datetime(frame["date"], errors="raise")
    if frame["symbol"].duplicated().any():
        raise RuntimeError(f"{path}@{commit[:8]} contains duplicate symbols")
    if frame["market_cap"].isna().any():
        raise RuntimeError(f"{path}@{commit[:8]} contains null market caps")
    return frame[["symbol", "market_cap", "date", "source"]]


def build(output: Path, path: Path = DEFAULT_PATH) -> dict:
    rel = str(path.relative_to(ROOT))
    commits = _git("log", "--follow", "--reverse", "--format=%H", "--", rel).strip()
    if not commits:
        raise RuntimeError(f"no git history for {rel}")

    snapshots: dict[str, tuple[str, pd.DataFrame]] = {}
    skipped_legacy = 0
    for commit in commits.splitlines():
        frame = _snapshot(commit, rel)
        if frame is None:
            skipped_legacy += 1
            continue
        if frame.empty:
            continue
        as_of = str(frame["date"].max().date())
        # If the same evidence date appears in multiple revisions, retain the
        # latest repository revision encountered in chronological Git history.
        snapshots[as_of] = (commit, frame)

    if not snapshots:
        raise RuntimeError("no usable market-cap snapshots")

    parts = []
    for as_of, (commit, frame) in sorted(snapshots.items()):
        part = frame.copy()
        part["evidence_date"] = pd.Timestamp(as_of)
        part["evidence_commit"] = commit
        parts.append(part)

    result = (
        pd.concat(parts, ignore_index=True)
        .sort_values(["date", "symbol"])
        .reset_index(drop=True)
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    result.to_parquet(output, index=False)

    summary = {
        "snapshot_count": len(snapshots),
        "row_count": len(result),
        "first_date": str(result["date"].min().date()),
        "last_date": str(result["date"].max().date()),
        "unique_symbols": int(result["symbol"].nunique()),
        "skipped_legacy_commits": skipped_legacy,
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
