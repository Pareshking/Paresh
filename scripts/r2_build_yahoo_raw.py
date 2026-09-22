"""Build a raw, unadjusted Yahoo OHLCV archive snapshot."""

from __future__ import annotations

import argparse
from pathlib import Path

from src.loaders.indices_loader import fetch_indices_data
from r2.raw.yahoo import download_raw_ohlcv


def build(output: Path, *, period: str = "10y") -> dict[str, int | str]:
    universe = fetch_indices_data(["NIFTY TOTAL MARKET"])
    if universe.empty or "Symbol" not in universe.columns:
        raise RuntimeError("NIFTY TOTAL MARKET universe is unavailable")

    symbols = universe["Symbol"].astype(str).str.strip().unique().tolist()
    requested = {
        s.upper() if s.upper().endswith(".NS") else f"{s.upper()}.NS"
        for s in symbols
    }

    raw = download_raw_ohlcv(symbols, period=period)
    if raw.empty:
        raise RuntimeError("Yahoo returned no raw OHLCV data")

    returned = {
        str(s).upper() if str(s).upper().endswith(".NS")
        else f"{str(s).upper()}.NS"
        for s in set(raw.columns.get_level_values(0))
    }
    missing = sorted(requested - returned)

    # A shorter history is valid: Yahoo's requested period is an upper bound,
    # not a requirement that every company must have existed for that long.
    # Missing symbols, however, are tracked explicitly so acquisition failures
    # cannot be confused with genuinely young listings.
    print(
        f"YAHOO_RAW_ACQUISITION requested={len(requested)} "
        f"returned={len(returned)} missing={len(missing)} period={period}"
    )
    if missing:
        print("YAHOO_RAW_MISSING " + ",".join(missing))

    output.parent.mkdir(parents=True, exist_ok=True)
    raw.to_parquet(output, compression="snappy")
    return {
        "symbols_requested": len(requested),
        "symbols_returned": len(returned),
        "symbols_missing": len(missing),
        "sessions": len(raw),
        "min_date": str(raw.index.min().date()),
        "max_date": str(raw.index.max().date()),
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
