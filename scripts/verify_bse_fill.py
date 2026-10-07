"""The days the long file took from BSE, checked against the independent histories.

    python scripts/verify_bse_fill.py --long nse_long_close.parquet --cells bse_fill_cells.csv \
        --report nse_long_report.json --ref tijori=ref_tijori_close_verified.parquet --ref eod2=... --out audit/

scripts/build_nse_long_prices.py fills NSE-only gaps from BSE (src/loaders/bse_fill.py)
and lists every filled cell in bse_fill_cells.csv. This compares each filled day's
close in the long file (adjusted) with each reference's close that day, two ways:

  level     |ours / reference - 1|, as audit_long_prices.py compares levels;
  anchored  the same after scaling the reference to our level on the NSE days at
            the gap's two ends (the median ratio over up to ANCHOR_DAYS each side),
            which takes out a constant difference of adjustment basis (a reference
            that also takes out small dividends sits a few percent lower before them).

A filled day agrees when it is within TOLERANCE of at least one reference on
either measure. The references are not derived from BSE's file or ours, but a
reference may itself have taken BSE's price on days NSE did not trade; say so
when quoting the result.

Writes bse_fill_verify.csv (one row per filled cell, each reference's value and
both differences), bse_fill_verify_outliers.csv and bse_fill_verify.json.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.audit_long_prices import closes  # noqa: E402

TOLERANCE = 0.02
ANCHOR_DAYS = 5


def _column(sym: str, long: pd.DataFrame, landed: dict[str, str]) -> str | None:
    seen = set()
    while sym not in long.columns and sym in landed and sym not in seen:
        seen.add(sym)
        sym = landed[sym]
    return sym if sym in long.columns else None


def verify(long: pd.DataFrame, cells: pd.DataFrame, refs: dict[str, pd.DataFrame],
           landed: dict[str, str] | None = None) -> tuple[pd.DataFrame, dict]:
    """(one row per filled cell with each reference's verdict, the summary)."""
    landed = landed or {}
    cells = cells.copy()
    for c in ("date", "gap_last_nse", "gap_next_nse"):
        cells[c] = pd.to_datetime(cells[c])
    filled_days = set(zip(cells["symbol"], cells["date"]))
    out = []
    for (sym, last, nxt), g in cells.groupby(["symbol", "gap_last_nse", "gap_next_nse"]):
        col = _column(sym, long, landed)
        ours = long[col].astype(float) if col else pd.Series(dtype=float)
        # NSE's own days around the gap: priced, and not themselves filled.
        nse_days = [d for d in ours.dropna().index if (sym, d) not in filled_days]
        before = [d for d in nse_days if d <= last][-ANCHOR_DAYS:]
        after = [d for d in nse_days if d >= nxt][:ANCHOR_DAYS]
        rows = g[["symbol", "date", "bse_code", "bse_close"]].assign(
            ours=[ours.get(d, np.nan) for d in g["date"]])
        for name, ref in refs.items():
            r = ref[sym] if sym in ref.columns else (ref[col] if col in ref.columns else None)
            if r is None:
                rows[f"{name}"] = np.nan
                rows[f"{name}_level"] = np.nan
                rows[f"{name}_anchored"] = np.nan
                continue
            vals = r.reindex(g["date"]).to_numpy()
            rows[name] = vals
            rows[f"{name}_level"] = np.abs(rows["ours"] / vals - 1)
            anchor = [ours[d] / r[d] for d in before + after if d in r.index and r[d] > 0]
            scale = float(np.median(anchor)) if anchor else np.nan
            rows[f"{name}_anchored"] = np.abs(rows["ours"] / (vals * scale) - 1)
        out.append(rows)
    frame = pd.concat(out, ignore_index=True) if out else pd.DataFrame(columns=["symbol", "date", "ours"])
    names = list(refs)
    level = frame[[f"{n}_level" for n in names]] if names else pd.DataFrame(index=frame.index)
    anch = frame[[f"{n}_anchored" for n in names]] if names else pd.DataFrame(index=frame.index)
    have = level.notna().any(axis=1)
    agree = ((level <= TOLERANCE) | (anch.set_axis(level.columns, axis=1) <= TOLERANCE)).any(axis=1)
    frame["any_reference"] = have
    frame["agrees_with_one"] = agree
    summary = {
        "cells_filled": int(len(frame)),
        "cells_with_a_reference": int(have.sum()),
        "within_2pct_of_at_least_one_reference": int(agree.sum()),
        "share_of_cells_with_a_reference": round(float(agree.sum() / have.sum()), 4) if have.any() else None,
        "share_of_all_filled_cells": round(float(agree.sum() / len(frame)), 4) if len(frame) else None,
        "by_reference": {},
    }
    for n in names:
        lv, an = frame[f"{n}_level"], frame[f"{n}_anchored"]
        k = lv.notna()
        summary["by_reference"][n] = {
            "cells": int(k.sum()),
            "level_within_2pct": round(float((lv[k] <= TOLERANCE).mean()), 4) if k.any() else None,
            "anchored_within_2pct": round(float((an[k] <= TOLERANCE).mean()), 4) if k.any() else None,
            "median_level_diff": round(float(lv[k].median()), 4) if k.any() else None,
        }
    return frame, summary


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--long", required=True, type=Path)
    ap.add_argument("--cells", required=True, type=Path)
    ap.add_argument("--report", type=Path, help="nse_long_report.json: renames_landed, for a renamed stock")
    ap.add_argument("--ref", action="append", default=[], help="name=path, repeatable")
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args(argv)
    long = pd.read_parquet(args.long)
    long.index = pd.DatetimeIndex(long.index).normalize()
    cells = pd.read_csv(args.cells)
    landed = json.loads(args.report.read_text())["renames_landed"] if args.report else {}
    refs = {n: closes(Path(p)) for n, p in (r.split("=", 1) for r in args.ref)}
    frame, summary = verify(long, cells, refs, landed)
    os.makedirs(args.out, exist_ok=True)
    frame.to_csv(args.out / "bse_fill_verify.csv", index=False)
    with_ref = frame[frame["any_reference"]]
    out = with_ref[~with_ref["agrees_with_one"]]
    out.to_csv(args.out / "bse_fill_verify_outliers.csv", index=False)
    summary["outlier_cells"] = int(len(out))
    summary["outlier_stocks"] = out.groupby("symbol").size().sort_values(ascending=False).to_dict()
    no_ref = frame[~frame["any_reference"]]
    summary["cells_no_reference_by_stock"] = no_ref.groupby("symbol").size().sort_values(ascending=False).to_dict()
    (args.out / "bse_fill_verify.json").write_text(json.dumps(summary, indent=1) + "\n")
    print(json.dumps({k: v for k, v in summary.items() if not k.startswith("cells_no_reference")}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
