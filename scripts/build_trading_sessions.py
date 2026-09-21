"""Build a normalized trading-session archive from observed production data.

The archive is deliberately source-derived: it records sessions that the
production price store actually contains rather than inventing an exchange
calendar. It is therefore safe for historical coverage audits and can later
be published to R2 as a canonical evidence dataset.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


def build(price_path: Path, output: Path) -> dict:
    frame = pd.read_parquet(price_path)
    if not isinstance(frame.index, pd.DatetimeIndex):
        raise RuntimeError("price archive must use a DatetimeIndex")

    sessions = sorted({ts.date().isoformat() for ts in pd.DatetimeIndex(frame.index)})
    if not sessions:
        raise RuntimeError("price archive contains no sessions")

    payload = {
        "schema_version": 1,
        "dataset": "trading_sessions/observed",
        "source": "production_price_archive",
        "first_session": sessions[0],
        "last_session": sessions[-1],
        "session_count": len(sessions),
        "sessions": sessions,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.suffix.lower() == ".parquet":
        pd.DataFrame(
            {
                "date": pd.to_datetime(sessions),
                "market": "NSE",
                "is_session": True,
                "source": "production_price_archive",
                "evidence_date": sessions[-1],
            }
        ).to_parquet(output, index=False)
    else:
        output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prices", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = build(args.prices, args.output)
    print(json.dumps({k: v for k, v in result.items() if k != "sessions"}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
