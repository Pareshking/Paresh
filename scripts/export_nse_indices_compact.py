#!/usr/bin/env python3
"""Write the app's copy of the NSE indices store (S168/S170).

    python scripts/export_nse_indices_compact.py --store nse_indices.parquet
        # the nightly run: sessions after data/nse_indices_history.parquet's last
        # day go to data/nse_indices_recent.csv
    python scripts/export_nse_indices_compact.py --store nse_indices.parquet --freeze
        # roll everything into the history file (once a year, or after a backfill)

Stock indices only (data/reference/nse_index_groups.csv), from each index's launch,
with close, P/E, P/B, dividend yield and the derived flag. Prints
`NSE_INDICES_COMPACT history=... recent=... last=...`.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.loaders import nse_indices as ni  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--store", type=Path, required=True)
    ap.add_argument("--freeze", action="store_true")
    args = ap.parse_args()
    store = pd.read_parquet(args.store)
    h, r = ni.write_compact(store, freeze=args.freeze)
    print(f"NSE_INDICES_COMPACT history={h} recent={r} last={store['date'].max():%Y-%m-%d}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
