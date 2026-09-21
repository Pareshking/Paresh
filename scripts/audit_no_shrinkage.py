"""Compare two wide historical price stores and fail on shrinkage.

The audit is deliberately source-agnostic: it checks that the newer store
preserves every prior session/symbol coordinate and does not lose populated
cells. It does not decide whether newly introduced history is economically
valid; that remains a separate source-quality check.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd


def audit_no_shrinkage(before: Path, after: Path) -> dict[str, Any]:
    old = pd.read_parquet(before)
    new = pd.read_parquet(after)

    old.index = pd.to_datetime(old.index, errors="raise").normalize()
    new.index = pd.to_datetime(new.index, errors="raise").normalize()

    old_symbols = {str(c) for c in old.columns}
    new_symbols = {str(c) for c in new.columns}
    missing_sessions = sorted(set(old.index) - set(new.index))
    missing_symbols = sorted(old_symbols - new_symbols)

    common_sessions = old.index.intersection(new.index)
    common_symbols = sorted(old_symbols & new_symbols)
    old_common = old.loc[common_sessions, common_symbols]
    new_common = new.loc[common_sessions, common_symbols]
    old_present = int(old_common.notna().sum().sum())
    new_present = int(new_common.notna().sum().sum())

    result = {
        "status": "PASS" if not missing_sessions and not missing_symbols and new_present >= old_present else "FAIL",
        "before_sessions": int(len(old.index)),
        "after_sessions": int(len(new.index)),
        "before_symbols": int(len(old_symbols)),
        "after_symbols": int(len(new_symbols)),
        "before_present_cells_on_overlap": old_present,
        "after_present_cells_on_overlap": new_present,
        "missing_sessions": [str(x.date()) for x in missing_sessions],
        "missing_symbols": missing_symbols,
    }
    if result["status"] == "FAIL":
        raise RuntimeError(json.dumps(result, sort_keys=True))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--before", type=Path, required=True)
    parser.add_argument("--after", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(audit_no_shrinkage(args.before, args.after), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
