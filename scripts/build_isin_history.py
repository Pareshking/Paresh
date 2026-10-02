"""Build data/reference/nse/isin_history.csv from the bhavcopy mirror's cm files.

    git clone --depth 1 --filter=blob:none --sparse https://github.com/tilak999/NSE-Data-bank mirror
    git -C mirror sparse-checkout set historic_data
    python scripts/build_isin_history.py --mirror mirror/historic_data

NSE's old-format bhavcopy (cm<DDMONYYYY>bhav.csv) carries each security's
ISIN; the mirror holds it from 10 Jun 2010 to 4 Jun 2021, with the ISIN
column from 22 Jun 2011. One row per (symbol, ISIN) pair of the stock series,
with the first and last day it traded. The file is history: it does not
change, so it is built once and committed. See src/loaders/nse_identity.py.
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.loaders.nse_identity import ISIN_HISTORY  # noqa: E402

STOCK_SERIES = {"EQ", "BE", "BZ", "SM", "ST"}
_NAME = re.compile(r"cm(\d{2}[A-Z]{3}\d{4})bhav\.csv$")


def pairs(directory: Path) -> tuple[pd.DataFrame, dict]:
    rows, skipped = [], {"empty": 0, "no_isin": 0}
    for path in sorted(Path(directory).glob("cm*bhav.csv")):
        m = _NAME.search(path.name)
        if not m:
            continue
        day = datetime.strptime(m.group(1), "%d%b%Y")
        try:
            raw = pd.read_csv(path, dtype=str)
        except pd.errors.EmptyDataError:
            skipped["empty"] += 1
            continue
        raw.columns = [c.strip().upper() for c in raw.columns]
        if "ISIN" not in raw.columns:
            skipped["no_isin"] += 1
            continue
        raw = raw[raw["SERIES"].str.strip().isin(STOCK_SERIES)]
        rows.append(pd.DataFrame({"symbol": raw["SYMBOL"].str.strip().str.upper(),
                                  "isin": raw["ISIN"].str.strip(), "date": day}))
    if not rows:
        return pd.DataFrame(columns=["symbol", "isin", "first", "last"]), skipped
    long = pd.concat(rows, ignore_index=True)
    long = long[long["isin"].str.match(r"^IN[A-Z0-9]{10}$", na=False)]
    out = (long.groupby(["symbol", "isin"])["date"].agg(first="min", last="max")
           .reset_index().sort_values(["symbol", "first"]))
    return out, skipped


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mirror", type=Path, required=True, help="the mirror's historic_data/")
    ap.add_argument("--out", type=Path, default=ISIN_HISTORY)
    args = ap.parse_args(argv)
    table, skipped = pairs(args.mirror)
    if table.empty:
        print("no ISIN rows found")
        return 1
    args.out.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(args.out, index=False, date_format="%Y-%m-%d")
    print(f"ISIN_HISTORY pairs={len(table)} symbols={table['symbol'].nunique()} "
          f"isins={table['isin'].nunique()} first={table['first'].min().date()} "
          f"last={table['last'].max().date()} skipped={skipped}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
