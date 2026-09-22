"""Audit raw-Yahoo-derived adjusted closes against the canonical V1 price snapshot.

This is an evidence gate, not a migration. It reports overlap, exact/near matches,
and material discrepancies by symbol. It never changes the canonical V1 files.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from r2.raw.yahoo import adjusted_from_raw


def _close_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if isinstance(frame.columns, pd.MultiIndex):
        # Accept either (ticker, field) or (field, ticker).
        levels = [
            {str(v).strip().lower() for v in frame.columns.get_level_values(i)}
            for i in range(frame.columns.nlevels)
        ]
        field_level = next(
            (i for i, vals in enumerate(levels) if "close" in vals), None
        )
        if field_level is not None:
            key = next(
                v for v in frame.columns.get_level_values(field_level)
                if str(v).strip().lower() == "close"
            )
            frame = frame.xs(key, level=field_level, axis=1)
    elif "Close" in frame.columns:
        frame = frame[["Close"]].rename(columns={"Close": "CLOSE"})
    return frame.apply(pd.to_numeric, errors="coerce")


def compare(raw_path: Path, v1_path: Path) -> dict[str, object]:
    raw = pd.read_parquet(raw_path)
    v1 = _close_frame(pd.read_parquet(v1_path))
    raw_adjusted, *_ = adjusted_from_raw(raw)
    raw_close = raw_adjusted.copy()

    raw_close.columns = [str(c).upper() for c in raw_close.columns]
    v1.columns = [str(c).upper() for c in v1.columns]

    common_symbols = sorted(set(raw_close.columns) & set(v1.columns))
    raw_close = raw_close[common_symbols]
    v1 = v1[common_symbols]

    overlap = raw_close.index.intersection(v1.index)
    raw_close = raw_close.reindex(overlap)
    v1 = v1.reindex(overlap)

    a = raw_close.to_numpy(dtype=float)
    b = v1.to_numpy(dtype=float)
    valid = np.isfinite(a) & np.isfinite(b) & (b != 0)
    abs_diff = np.abs(a - b)
    rel_diff = abs_diff / np.where(valid, np.abs(b), np.nan)

    rows = []
    for i, symbol in enumerate(common_symbols):
        mask = valid[:, i]
        if not mask.any():
            continue
        rd = rel_diff[:, i][mask]
        ad = abs_diff[:, i][mask]
        rows.append(
            {
                "symbol": symbol,
                "observations": int(mask.sum()),
                "exact": int((ad == 0).sum()),
                "within_1bp": int((rd <= 0.0001).sum()),
                "within_10bp": int((rd <= 0.001).sum()),
                "material_gt_1pct": int((rd > 0.01).sum()),
                "max_relative_diff": float(np.nanmax(rd)),
                "median_relative_diff": float(np.nanmedian(rd)),
            }
        )

    by_symbol = pd.DataFrame(rows)
    if by_symbol.empty:
        raise RuntimeError("No overlapping price observations were available")

    total_obs = int(valid.sum())
    material = int((rel_diff[valid] > 0.01).sum())
    within_10bp = int((rel_diff[valid] <= 0.001).sum())

    return {
        "raw_min": str(raw.index.min().date()),
        "raw_max": str(raw.index.max().date()),
        "v1_min": str(pd.DatetimeIndex(v1.index).min().date()),
        "v1_max": str(pd.DatetimeIndex(v1.index).max().date()),
        "overlap_sessions": len(overlap),
        "common_symbols": len(common_symbols),
        "overlap_observations": total_obs,
        "within_10bp": within_10bp,
        "within_10bp_share": within_10bp / total_obs,
        "material_gt_1pct": material,
        "material_gt_1pct_share": material / total_obs,
        "symbols_with_material_diffs": int((by_symbol["material_gt_1pct"] > 0).sum()),
        "by_symbol": by_symbol.sort_values("material_gt_1pct", ascending=False),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", type=Path, required=True)
    parser.add_argument("--v1", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    result = compare(args.raw, args.v1)
    args.report.parent.mkdir(parents=True, exist_ok=True)

    summary = {k: v for k, v in result.items() if k != "by_symbol"}
    print("RAW_V1_EQUIVALENCE", summary)
    result["by_symbol"].to_csv(args.report, index=False)

    # This is deliberately informational. Yahoo and Screener use different
    # corporate-action bases, so equality is evidence to inspect, not a blind
    # pass/fail threshold. Migration must remain a separate human-reviewed gate.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
