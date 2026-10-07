#!/usr/bin/env python3
"""Refuse to publish a long NSE price file that is smaller than the one it replaces.

    python scripts/check_long_publish.py --new data_cache/nse_long --old published/

Owner, 2026-10-07: the data built over weeks must not be lost to a bad run.
`nse_long_prices.yml` uploads with --clobber, so a build that read fewer
sessions (an R2 read failing, a dispatch with a later `since`) would replace
the full file. Run before the upload; exit 1 refuses it. A file missing from
--old (the first build) passes.

Checks, new against old:
  the close file starts on the same first session or earlier, and ends no earlier;
  it holds at least as many sessions, and symbols to within SYMBOL_SLACK;
  the raw pack holds at least as many rows and sessions.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

CLOSE, PACK = "nse_long_close.parquet", "nse_raw_pack.parquet"
SYMBOL_SLACK = 0.01          # a few symbols may leave when a rename is joined


def close_shape(path: Path) -> dict:
    c = pd.read_parquet(path)
    return {"first": c.index.min(), "last": c.index.max(), "sessions": len(c), "symbols": c.shape[1]}


def pack_shape(path: Path) -> dict:
    rows = pq.ParquetFile(path).metadata.num_rows
    dates = pd.read_parquet(path, columns=["date"])["date"]
    return {"rows": rows, "sessions": int(pd.to_datetime(dates).nunique())}


def problems(new: Path, old: Path) -> list[str]:
    out = []
    if (old / CLOSE).exists():
        n, o = close_shape(new / CLOSE), close_shape(old / CLOSE)
        if n["first"] > o["first"]:
            out.append(f"close file starts {n['first'].date()}, the published one {o['first'].date()}")
        if n["last"] < o["last"]:
            out.append(f"close file ends {n['last'].date()}, the published one {o['last'].date()}")
        if n["sessions"] < o["sessions"]:
            out.append(f"close file has {n['sessions']} sessions, the published one {o['sessions']}")
        if n["symbols"] < o["symbols"] * (1 - SYMBOL_SLACK):
            out.append(f"close file has {n['symbols']} symbols, the published one {o['symbols']}")
    if (old / PACK).exists():
        n, o = pack_shape(new / PACK), pack_shape(old / PACK)
        if n["rows"] < o["rows"] or n["sessions"] < o["sessions"]:
            out.append(f"raw pack has {n['rows']:,} rows / {n['sessions']} sessions, "
                       f"the published one {o['rows']:,} / {o['sessions']}")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--new", type=Path, required=True)
    ap.add_argument("--old", type=Path, required=True)
    args = ap.parse_args(argv)
    found = problems(args.new, args.old)
    for p in found:
        print(f"::error::{p}; not published")
    if not found:
        print("The new long file is no smaller than the published one.")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
