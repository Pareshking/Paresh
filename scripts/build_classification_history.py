"""Build point-in-time sector/industry classification evidence from Git snapshots."""

from __future__ import annotations

import hashlib
import io
import subprocess
from pathlib import Path

import pandas as pd

from src.core.tickers import is_tradeable_symbol

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PATH = ROOT / "data/nse_tv_classification.csv"
REQUIRED = {"Symbol", "TV_Sector", "TV_Industry"}


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout


def _snapshot(commit: str, path: str) -> pd.DataFrame:
    raw = _git("show", f"{commit}:{path}")
    frame = pd.read_csv(io.StringIO(raw))
    missing = REQUIRED - set(frame.columns)
    if missing:
        raise RuntimeError(f"{path}@{commit[:8]} missing {sorted(missing)}")
    frame = frame.rename(
        columns={"Symbol": "symbol", "TV_Sector": "sector", "TV_Industry": "industry"}
    )
    frame["symbol"] = frame["symbol"].astype(str).str.strip().str.upper()
    frame["sector"] = frame["sector"].astype(str).str.strip()
    frame["industry"] = frame["industry"].astype(str).str.strip()
    frame = frame.loc[:, ["symbol", "sector", "industry"]]
    frame = frame[frame["symbol"].map(is_tradeable_symbol)]
    if frame["symbol"].duplicated().any():
        raise RuntimeError(f"{path}@{commit[:8]} contains duplicate symbols")
    if frame[["sector", "industry"]].isna().any().any():
        raise RuntimeError(f"{path}@{commit[:8]} contains null classifications")
    return frame.sort_values("symbol").reset_index(drop=True)


def build(output: Path, path: Path = DEFAULT_PATH) -> dict:
    rel = str(path.relative_to(ROOT))
    commits = _git(
        "log", "--follow", "--reverse", "--date=short", "--format=%H %ad", "--", rel
    ).strip()
    if not commits:
        raise RuntimeError(f"no Git history for {rel}")

    snapshots: list[pd.DataFrame] = []
    previous_digest = None
    skipped = 0
    for line in commits.splitlines():
        commit, evidence_date = line.split(None, 1)
        try:
            frame = _snapshot(commit, rel)
        except (subprocess.CalledProcessError, RuntimeError, pd.errors.ParserError):
            skipped += 1
            continue
        digest = hashlib.sha256(
            pd.util.hash_pandas_object(frame, index=False).values.tobytes()
        ).hexdigest()
        if digest == previous_digest:
            continue
        part = frame.copy()
        part["effective_from"] = pd.Timestamp(evidence_date)
        part["evidence_date"] = pd.Timestamp(evidence_date)
        part["evidence_commit"] = commit
        part["source"] = "repository TV classification snapshot"
        snapshots.append(part)
        previous_digest = digest

    if not snapshots:
        raise RuntimeError("no usable classification snapshots")

    result = (
        pd.concat(snapshots, ignore_index=True)
        .sort_values(["effective_from", "symbol"])
        .reset_index(drop=True)
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    result.to_parquet(output, index=False)
    summary = {
        "snapshot_count": len(snapshots),
        "row_count": len(result),
        "first_date": str(result["effective_from"].min().date()),
        "last_date": str(result["effective_from"].max().date()),
        "unique_symbols": int(result["symbol"].nunique()),
        "skipped": skipped,
    }
    print(summary)
    return summary


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    build(args.output)
