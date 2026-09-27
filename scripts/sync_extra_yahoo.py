"""Yahoo's two years for the extra universe, in a file of its own.

The 750's Yahoo pipeline (sync_data.py) keeps an incremental cache and judges
each session by how much of the universe has printed; mixing ~420 thinner
stocks into it would move those judgements for the 750. So the extra universe
(src/engine/extra_universe.py) gets its own file, downloaded whole each night:
five 100-ticker calls, about a minute.

It is Yahoo's copy, for the cross-source check and for the app's High, Low and
Open. Screener stays the price the ranking uses.

    python scripts/sync_extra_yahoo.py --out data_cache/prices_extra.parquet
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
LIST_PATH = ROOT / "data" / "indices" / "ind_nanocap_list.csv"
BATCH = 100


def tickers(path: Path = LIST_PATH) -> list[str]:
    if not path.exists():
        return []
    syms = pd.read_csv(path)["Symbol"].dropna().astype(str).str.strip().str.upper()
    return sorted(s for s in set(syms) if s and not s.startswith("DUMMY"))


def strip_suffix(frame: pd.DataFrame) -> pd.DataFrame:
    """(SYM.NS, field) columns -> (SYM, field), rows with no price at all dropped."""
    if frame.empty or not isinstance(frame.columns, pd.MultiIndex):
        return pd.DataFrame()
    frame = frame.copy()
    frame.columns = pd.MultiIndex.from_tuples(
        [(str(t).upper().removesuffix(".NS"), f) for t, f in frame.columns])
    frame.index = pd.DatetimeIndex(frame.index).tz_localize(None).normalize()
    return frame.dropna(how="all").sort_index()


def download(symbols: list[str], period: str = "2y", fetch=None) -> pd.DataFrame:
    if fetch is None:
        import yfinance as yf

        def fetch(batch):
            return yf.download(batch, period=period, progress=False,
                               group_by="ticker", threads=True, auto_adjust=True)
    parts = []
    for start in range(0, len(symbols), BATCH):
        batch = [s + ".NS" for s in symbols[start:start + BATCH]]
        got = strip_suffix(fetch(batch))
        if not got.empty:
            parts.append(got)
    return pd.concat(parts, axis=1).sort_index() if parts else pd.DataFrame()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="data_cache/prices_extra.parquet")
    args = ap.parse_args(argv)

    symbols = tickers()
    if not symbols:
        print("EXTRA_YAHOO no extra universe list; nothing to fetch")
        return 0
    frame = download(symbols)
    if frame.empty:
        print(f"::warning::EXTRA_YAHOO Yahoo returned nothing for {len(symbols)} symbols")
        return 1
    closes = frame.xs("Close", axis=1, level=1)
    served = [s for s in symbols if s in closes.columns and closes[s].notna().any()]
    last = closes.index[-1]
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(args.out, compression="zstd")
    missing = sorted(set(symbols) - set(served))
    print(f"EXTRA_YAHOO {len(served)}/{len(symbols)} served, {closes.shape[0]} sessions "
          f"to {last.date()} ({int(closes.loc[last].notna().sum())} priced on the last); "
          f"missing {len(missing)}: {missing[:20]} -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
