"""Check the long NSE price file against Screener's history, point by point.

    python scripts/audit_against_screener.py --ours nse_long_close.parquet \
        --screener screener_max_history.parquet --out audit/

Screener (prices/screener/max_history on R2, screener_max_history.parquet on
the release) is adjusted for splits and bonuses like ours, but before its
latest year it keeps only some sessions -- about one a week, on varying
weekdays. So nothing is resampled to Fridays here: each of Screener's dates is
matched to our close on that same date, and the return between one Screener
point and the next is compared with ours over the same two dates.

Two outputs:

1. screener_point_mismatches.csv -- every interval where the two returns
   differ by more than 2% (log). Dividends are in neither series, so they do
   not open a gap; a single mismatch that reverses at the next point is a bad
   print on one side, and the `reverts` column says so.
2. screener_level_shifts.csv -- where the level of ours / Screener steps by more
   than 5% and stays (median of the next 5 common points against the previous
   5). A step that stays is an action one side adjusted and the other did not,
   or dated differently; which side moved that day says which is wrong.

Nothing here reaches the network.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.audit_long_prices import closes  # noqa: E402

GAP = np.log(1.02)     # interval returns differing by more than 2%
STEP = np.log(1.05)    # a lasting step in the level
WINDOW = 5             # common points either side of a step


def intervals(ours: pd.DataFrame, screener: pd.DataFrame) -> pd.DataFrame:
    """Every pair of consecutive Screener points that both series price.

    Long format: symbol, start, end, ours and Screener's log return over it,
    their difference, and whether the next interval undoes it.
    """
    common = sorted(set(ours.columns) & set(screener.columns))
    days = ours.index.intersection(screener.index)
    a = np.log(ours.loc[days, common])
    b = np.log(screener.loc[days, common])
    both = a.notna() & b.notna()
    rows = []
    for sym in common:
        m = both[sym].to_numpy()
        if m.sum() < 2:
            continue
        idx = days[m]
        ra = np.diff(a[sym].to_numpy()[m])
        rb = np.diff(b[sym].to_numpy()[m])
        rows.append(pd.DataFrame({"symbol": sym, "start": idx[:-1], "end": idx[1:],
                                  "ours": ra, "screener": rb}))
    if not rows:
        return pd.DataFrame(columns=["symbol", "start", "end", "ours", "screener", "diff"])
    out = pd.concat(rows, ignore_index=True)
    out["diff"] = out["ours"] - out["screener"]
    nxt = out.groupby("symbol")["diff"].shift(-1)
    out["reverts"] = (out["diff"].abs() > GAP) & ((out["diff"] + nxt).abs() < GAP)
    return out


def level_shifts(ours: pd.DataFrame, screener: pd.DataFrame) -> pd.DataFrame:
    """Lasting steps in log(ours / Screener), and which side moved."""
    common = sorted(set(ours.columns) & set(screener.columns))
    days = ours.index.intersection(screener.index)
    rows = []
    for sym in common:
        a, b = ours.loc[days, sym], screener.loc[days, sym]
        m = a.notna() & b.notna()
        if m.sum() < 2 * WINDOW + 1:
            continue
        a, b = np.log(a[m]), np.log(b[m])
        lr = a - b
        before = lr.rolling(WINDOW).median().shift(1)
        after = lr[::-1].rolling(WINDOW).median()[::-1]
        step = after - before
        hits = step[step.abs() > STEP]
        ra, rb = a.diff(), b.diff()
        last = None
        for day, s in hits.items():
            i = lr.index.get_loc(day)
            # the step is between the medians; the interval that opened it is
            # the one inside that span where the two returns differ most
            span = (ra - rb).iloc[max(i - WINDOW + 1, 1): i + WINDOW]
            j = lr.index.get_loc(span.abs().idxmax())
            if last is not None and j - last <= WINDOW:
                continue  # one event, not every point around it
            rows.append({"symbol": sym, "start": lr.index[j - 1].date(), "end": lr.index[j].date(),
                         "step": round(float(np.exp(s)), 4),
                         "ours_move": round(float(np.exp(ra.iloc[j])), 4),
                         "screener_move": round(float(np.exp(rb.iloc[j])), 4)})
            last = j
    out = pd.DataFrame(rows)
    if len(out):
        moved_ours = (np.log(out["ours_move"]).abs() > np.log(out["screener_move"]).abs())
        out["moved"] = np.where(moved_ours, "ours", "screener")
        out = out.drop_duplicates(["symbol", "start", "end"])
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ours", type=Path, required=True)
    ap.add_argument("--screener", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--since", default="2008-01-01")
    args = ap.parse_args(argv)

    ours = closes(args.ours)
    scr = closes(args.screener)
    ours = ours.loc[args.since:]
    scr = scr.loc[args.since:]
    args.out.mkdir(parents=True, exist_ok=True)

    iv = intervals(ours, scr)
    bad = iv[iv["diff"].abs() > GAP].copy()
    for c in ("ours", "screener", "diff"):
        bad[c] = np.round(np.exp(bad[c]) - 1, 4)
    bad.sort_values(["symbol", "start"]).to_csv(args.out / "screener_point_mismatches.csv", index=False)

    steps = level_shifts(ours, scr)
    steps.to_csv(args.out / "screener_level_shifts.csv", index=False)

    summary = {
        "symbols_compared": int(iv["symbol"].nunique()) if len(iv) else 0,
        "intervals": int(len(iv)),
        "intervals_within_2pct": round(float((iv["diff"].abs() <= GAP).mean()), 4) if len(iv) else None,
        "mismatches": int(len(bad)),
        "mismatches_that_revert": int(bad["reverts"].sum()) if len(bad) else 0,
        "symbols_with_mismatch": int(bad["symbol"].nunique()) if len(bad) else 0,
        "level_shifts": int(len(steps)),
        "level_shifts_ours_moved": int((steps["moved"] == "ours").sum()) if len(steps) else 0,
    }
    (args.out / "screener_summary.json").write_text(json.dumps(summary, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
