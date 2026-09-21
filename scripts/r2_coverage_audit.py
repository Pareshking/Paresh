"""Coverage and no-shrinkage audit for accumulated analytical Parquet stores."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd


def _symbols(frame: pd.DataFrame) -> set[str]:
    if isinstance(frame.columns, pd.MultiIndex):
        return {str(v) for v in frame.columns.get_level_values(0)}
    return {str(v) for v in frame.columns}


def _cell_count(frame: pd.DataFrame) -> int:
    return int(frame.notna().sum().sum())


def audit_no_shrinkage(baseline: Path, candidate: Path) -> dict[str, Any]:
    before = pd.read_parquet(baseline)
    after = pd.read_parquet(candidate)
    if before.empty:
        raise RuntimeError("baseline is empty")
    if after.empty:
        raise RuntimeError("candidate is empty")

    before_idx = pd.DatetimeIndex(before.index)
    after_idx = pd.DatetimeIndex(after.index)
    if after_idx.min() > before_idx.min():
        raise RuntimeError(
            f"historical start shrank: {after_idx.min().date()} > {before_idx.min().date()}"
        )
    if after_idx.max() < before_idx.max():
        raise RuntimeError(
            f"latest session shrank: {after_idx.max().date()} < {before_idx.max().date()}"
        )

    before_symbols = _symbols(before)
    after_symbols = _symbols(after)
    missing_symbols = sorted(before_symbols - after_symbols)
    if missing_symbols:
        raise RuntimeError(f"symbols disappeared: {missing_symbols[:10]}")

    overlap = before.index.intersection(after.index)
    common_columns = before.columns.intersection(after.columns)
    if len(overlap) and len(common_columns):
        old = before.reindex(index=overlap, columns=common_columns)
        new = after.reindex(index=overlap, columns=common_columns)
        erased = int((old.notna() & new.isna()).to_numpy().sum())
        if erased:
            raise RuntimeError(f"historical cells erased: {erased}")

    result = {
        "baseline_rows": len(before),
        "candidate_rows": len(after),
        "baseline_symbols": len(before_symbols),
        "candidate_symbols": len(after_symbols),
        "baseline_cells": _cell_count(before),
        "candidate_cells": _cell_count(after),
        "baseline_min_date": str(before_idx.min().date()),
        "candidate_min_date": str(after_idx.min().date()),
        "baseline_max_date": str(before_idx.max().date()),
        "candidate_max_date": str(after_idx.max().date()),
        "status": "PASS",
    }
    print(json.dumps(result, sort_keys=True))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--candidate", required=True, type=Path)
    args = parser.parse_args()
    audit_no_shrinkage(args.baseline, args.candidate)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
