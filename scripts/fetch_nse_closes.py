#!/usr/bin/env python3
"""Fetch the published two-year NSE closes into the local cache.

    python scripts/fetch_nse_closes.py

data/nse_prices/closes.parquet is not in git (TODO S178): the app and the jobs
read the published copy (src/loaders/nse_prices.closes_path(): R2, else the
release). The test suite is offline by design (tests/conftest.py), so the
tests that check the real closes read the copy this puts in DATA_DIR; CI runs
it before the suite (v1-full-validation.yml), and so should a developer whose
cached copy is missing. Exit 1 when neither R2 nor the release serves it.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402

from src.loaders import app_source  # noqa: E402
from src.loaders import nse_prices as npx  # noqa: E402


def main() -> int:
    path = npx._published_closes()
    if path is None:
        print("::error::the NSE closes are on neither R2 nor the release")
        return 1
    frame = pd.read_parquet(path)
    print(f"{path}: {frame.shape[0]} sessions x {frame.shape[1]} symbols, "
          f"{pd.Timestamp(frame.index.min()).date()} to {pd.Timestamp(frame.index.max()).date()} "
          f"(from {app_source.SOURCES.get('nse_closes', 'the cache')})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
