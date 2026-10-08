#!/usr/bin/env python3
"""Phase-0 data footprint audit.

Measures Parquet on-disk size, schema, shape, date/symbol coverage, pandas memory,
numeric-buffer memory, index memory, and optional RSS before/after materialisation.

This script is intentionally observational: it never writes to or mutates the
input datasets.

Examples:
    python scripts/audit_data_footprint.py data_cache/nse_long/nse_long_close.parquet
    python scripts/audit_data_footprint.py --dir data_cache/nse_long
"""

from __future__ import annotations

import argparse
import json
import os
import resource
from pathlib import Path
from typing import Any

import pandas as pd


def rss_mb() -> float:
    """Maximum resident set size reported by the current process, in MB."""
    # Linux reports KB; macOS reports bytes. Streamlit Cloud is Linux.
    value = float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    if os.uname().sysname == "Darwin":
        return value / (1024 * 1024)
    return value / 1024


def frame_report(df: pd.DataFrame) -> dict[str, Any]:
    """Return memory/shape metadata without modifying df."""
    deep = df.memory_usage(index=True, deep=True)
    numeric = int(df.select_dtypes(include="number").memory_usage(index=False, deep=True).sum())
    index = int(deep.iloc[0])
    data = int(deep.iloc[1:].sum())
    dates = None
    if isinstance(df.index, pd.DatetimeIndex) and len(df.index):
        dates = {"min": str(df.index.min()), "max": str(df.index.max())}

    symbol_candidates = [
        c for c in ("symbol", "Symbol", "NSE_SYMBOL", "ticker", "Ticker")
        if c in df.columns
    ]
    symbols = None
    if symbol_candidates:
        c = symbol_candidates[0]
        symbols = int(df[c].nunique(dropna=True))
    elif len(df.columns):
        # Wide price matrices normally use symbols as columns.
        symbols = int(len(df.columns))

    missing = int(df.isna().sum().sum())
    return {
        "rows": int(len(df)),
        "columns": int(len(df.columns)),
        "shape": [int(len(df)), int(len(df.columns))],
        "dtypes": {str(k): int(v) for k, v in df.dtypes.astype(str).value_counts().items()},
        "date_range": dates,
        "unique_symbols_or_columns": symbols,
        "missing_cells": missing,
        "missing_fraction": round(missing / max(df.size, 1), 8),
        "memory_bytes_deep": int(deep.sum()),
        "memory_mb_deep": round(float(deep.sum()) / 1e6, 3),
        "index_memory_bytes": index,
        "data_memory_bytes": data,
        "numeric_buffer_bytes": numeric,
        "numeric_buffer_mb": round(numeric / 1e6, 3),
        "rss_max_mb_at_measurement": round(rss_mb(), 3),
    }


def audit_file(path: Path) -> dict[str, Any]:
    """Audit one Parquet file."""
    stat = path.stat()
    before = rss_mb()
    df = pd.read_parquet(path)
    after = rss_mb()
    report = frame_report(df)
    report.update(
        {
            "path": str(path),
            "disk_bytes": int(stat.st_size),
            "disk_mb": round(stat.st_size / 1e6, 3),
            "rss_max_mb_before_read": round(before, 3),
            "rss_max_mb_after_read": round(after, 3),
            "rss_delta_mb": round(after - before, 3),
        }
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="*", type=Path)
    parser.add_argument("--dir", type=Path, help="Directory; all *.parquet files are audited.")
    parser.add_argument("--json", type=Path, help="Optional output JSON path.")
    args = parser.parse_args()

    paths = list(args.paths)
    if args.dir:
        paths.extend(sorted(args.dir.glob("*.parquet")))
    paths = list(dict.fromkeys(p for p in paths if p.exists()))
    if not paths:
        parser.error("No existing Parquet files supplied.")

    start = rss_mb()
    reports = [audit_file(p) for p in paths]
    result = {
        "audit": "phase-0-data-footprint",
        "python_process_rss_start_mb": round(start, 3),
        "files": reports,
    }

    print(json.dumps(result, indent=2))
    if args.json:
        args.json.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
