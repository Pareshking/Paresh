"""Build an analytical trading-session dataset from an observed price archive."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def build(price_path: Path, output: Path) -> dict:
    frame = pd.read_parquet(price_path)
    if not isinstance(frame.index, pd.DatetimeIndex):
        raise RuntimeError("price archive must use a DatetimeIndex")
    dates = sorted(pd.DatetimeIndex(frame.index).normalize().unique())
    if not len(dates):
        raise RuntimeError("price archive contains no sessions")

    result = pd.DataFrame(
        {
            "date": dates,
            "market": "NSE",
            "is_session": True,
            "source": "observed_production_price_archive",
            "evidence_date": dates[-1],
        }
    )
    result.to_parquet(output, index=False)
    summary = {
        "session_count": len(result),
        "first_session": str(result["date"].min().date()),
        "last_session": str(result["date"].max().date()),
    }
    print(summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prices", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    build(args.prices, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
