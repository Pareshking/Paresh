"""Build a raw, unadjusted Yahoo OHLCV archive snapshot.

This is an explicit Section-D acquisition tool. It does not alter the canonical
price cache and does not run the ranking engine.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from src.loaders.indices_loader import fetch_indices_data
from src.loaders.yahoo_raw import download_raw_ohlcv


def build(output: Path, *, period: str = "10y") -> dict[str, int | str]:
    universe = fetch_indices_data(["NIFTY TOTAL MARKET"])
    if universe.empty or "Symbol" not in universe.columns:
        raise RuntimeError("NIFTY TOTAL MARKET universe is unavailable")
    symbols = universe["Symbol"].astype(str).str.strip().unique().tolist()
    raw = download_raw_ohlcv(symbols, period=period)
    if raw.empty:
        raise RuntimeError("Yahoo returned no raw OHLCV data")
    output.parent.mkdir(parents=True, exist_ok=True)
    raw.to_parquet(output, compression="snappy")
    dates = raw.index
    return {
        "symbols_requested": len(symbols),
        "symbols_returned": len(set(raw.columns.get_level_values(0))),
        "sessions": len(raw),
        "min_date": str(dates.min().date()),
        "max_date": str(dates.max().date()),
        "output": str(output),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--period", default="10y")
    args = parser.parse_args(argv)
    print(build(args.output, period=args.period))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
