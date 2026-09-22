"""R2 operational continuity checks for an observed session dataset.

The check is intentionally source-agnostic: it verifies the published dataset's
own ordered session evidence without inventing exchange holidays or calendar
sessions.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


def audit_sessions(path: Path) -> dict[str, object]:
    frame = pd.read_parquet(path)
    required = {"date", "market", "is_session"}
    missing = required - set(frame.columns)
    if missing:
        raise RuntimeError(f"missing required columns: {sorted(missing)}")
    dates = pd.to_datetime(frame["date"], errors="raise").dt.normalize()
    if dates.isna().any():
        raise RuntimeError("session dates contain null values")
    if not dates.is_unique:
        raise RuntimeError("session dates are duplicated")
    if not dates.is_monotonic_increasing:
        raise RuntimeError("session dates are not monotonic increasing")
    if not frame["is_session"].eq(True).all():
        raise RuntimeError("observed session dataset contains non-session rows")
    if not frame["market"].eq("NSE").all():
        raise RuntimeError("observed session dataset contains non-NSE rows")
    return {
        "status": "PASS",
        "rows": len(frame),
        "first_date": str(dates.iloc[0].date()) if len(frame) else None,
        "last_date": str(dates.iloc[-1].date()) if len(frame) else None,
        "unique_dates": int(dates.nunique()),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = audit_sessions(args.dataset)
    print(json.dumps(result, sort_keys=True) if args.json else
          f"R2_SESSION_CONTINUITY=PASS rows={result['rows']} "
          f"range={result['first_date']}..{result['last_date']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
