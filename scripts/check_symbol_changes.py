#!/usr/bin/env python3
"""Did a ticker change without us noticing, or leave a twin behind?

    python scripts/check_symbol_changes.py [--fail-on-new]

NSE files the sessions before a ticker change under the old symbol and the
sessions after under the new one. Two mechanisms already join them, and both
work: `nse_identity.auto_renames()` reads NSE's own `symbolchange.csv` plus the
ISIN history, and `data/nse_prices/notes.json` carries a hand ledger for the
cases the automatic path cannot confirm. What was missing was anyone being
TOLD when a change happened — ICICIPRULI became ICICILIFE on 23 Oct 2026
(NSE/CML/76967, "name and symbol ... will be changed w.e.f. October 23, 2026")
and nothing in the repository said so for nineteen days.

So this is a detector, not a fix. It reports two things:

  UNJOINED   a symbol's series ends and another's begins on the very next
             session at a similar price, and neither the ledger nor the
             automatic resolver joins them. That is a rename, a demerger or a
             restructuring, and the price series is in two pieces until
             somebody says which.

  TWINS      two symbols carry the same closes on the same sessions. Screener
             back-fills a renamed company's whole history under the new ticker
             and leaves the old ticker in the store: ICICIPRULI and ICICILIFE
             agree on 716 sessions to the paisa. Harmless while the universe
             comes from NSE's index lists, which drop the old name -- but
             nothing checks that, and the day a stale name reaches an index
             list the same company would be ranked twice.

A rename that IS joined is not reported: the point is the gap between what NSE
did and what we know, not a list of every ticker that ever changed.

Exit 1 with --fail-on-new if anything is reported, so a workflow can gate on
it. Read-only: it changes no file and fetches nothing.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CLOSES = ROOT / "data" / "nse_prices" / "closes.parquet"
NOTES = ROOT / "data" / "nse_prices" / "notes.json"

# A rename's two sides meet at a similar price: NSE's own ratio across the 21
# joins already in the ledger runs 0.937 to 1.053, so 20% is generous without
# being meaningless. Wider than this is a different event, not a ticker change.
NEAR = 0.20
# Two columns are twins when they agree on this many sessions to the paisa.
TWIN_SESSIONS = 30
TWIN_TOL = 0.005


def _pairs(close: pd.DataFrame) -> list[tuple]:
    """(last day, old, new, old close, new close, ratio) for contiguous handovers."""
    sessions = list(close.index)
    pos = {d: i for i, d in enumerate(sessions)}
    first = {s: close[s].first_valid_index() for s in close.columns}
    last = {s: close[s].last_valid_index() for s in close.columns}

    ends: dict = {}
    for s, d in last.items():
        if d is not None and d != sessions[-1]:
            ends.setdefault(d, []).append(s)
    starts: dict = {}
    for s, d in first.items():
        if d is not None and d != sessions[0]:
            starts.setdefault(d, []).append(s)

    out = []
    for day, leaving in ends.items():
        i = pos[day]
        if i + 1 >= len(sessions):
            continue
        nxt = sessions[i + 1]
        for old in leaving:
            for new in starts.get(nxt, []):
                a, b = close[old].loc[day], close[new].loc[nxt]
                if pd.isna(a) or pd.isna(b) or a <= 0:
                    continue
                ratio = float(b) / float(a)
                if 1 - NEAR <= ratio <= 1 + NEAR:
                    out.append((day, old, new, float(a), float(b), ratio))
    return sorted(out, key=lambda r: r[0], reverse=True)


def _twins(close: pd.DataFrame) -> list[tuple]:
    """(a, b, overlapping sessions) for columns whose closes agree to the paisa."""
    tail = close.tail(800)
    cols = [c for c in tail.columns if tail[c].notna().sum() >= TWIN_SESSIONS]
    # Group so the comparison is not quadratic over 1,100 symbols -- but NOT by
    # the last close, which was the first version and could not find the case
    # this check exists for: in a rename the old ticker stops updating, so the
    # twins' last closes differ (ICICIPRULI 413.35 on 26 Oct against ICICILIFE
    # 438.40 on 9 Nov) and the two were never compared. Group on a session in
    # the middle instead, which both sides of a rename carry and agree on.
    mid = tail.index[len(tail) // 2]
    buckets: dict = {}
    for c in cols:
        v = tail[c].loc[:mid].dropna()
        if v.empty:
            continue
        buckets.setdefault(round(float(v.iloc[-1]), 2), []).append(c)
    out = []
    for _, group in buckets.items():
        for i, a in enumerate(group):
            for b in group[i + 1:]:
                both = tail[a].dropna().index.intersection(tail[b].dropna().index)
                if len(both) < TWIN_SESSIONS:
                    continue
                if (tail[a].loc[both] - tail[b].loc[both]).abs().max() < TWIN_TOL:
                    out.append((a, b, len(both)))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--fail-on-new", action="store_true",
                    help="exit 1 when anything is reported")
    ap.add_argument("--screener", default="",
                    help="a Screener store parquet ((symbol, field) columns) to check "
                         "for twins as well. The committed NSE file CANNOT show them: "
                         "NSE files the old ticker up to the change and the new one "
                         "after, so the two never overlap. Screener instead back-fills "
                         "the whole history under the new ticker and leaves the old one "
                         "in place, which is where ICICIPRULI and ICICILIFE agree on "
                         "716 sessions.")
    args = ap.parse_args()

    if not CLOSES.exists():
        print("SKIP  data/nse_prices/closes.parquet is not here; nothing to check")
        return 0
    close = pd.read_parquet(CLOSES)
    ledger = json.loads(NOTES.read_text(encoding="utf-8")).get("renames", {})

    sys.path.insert(0, str(ROOT))
    from src.loaders.nse_identity import auto_renames
    auto = auto_renames(set(close.columns))
    known = {**auto, **ledger}

    def joined(old: str, new: str) -> str | None:
        """How `old` is joined to `new`, or None."""
        target = known.get(old, {}).get("new_symbol")
        if target != new:
            return None
        return "auto" if known[old].get("auto") else "ledger"

    pairs = _pairs(close)
    unjoined = [p for p in pairs if joined(p[1], p[2]) is None]
    print(f"{len(pairs)} contiguous handovers within {NEAR:.0%} on price; "
          f"{len(pairs) - len(unjoined)} already joined, {len(unjoined)} not")
    for day, old, new, a, b, ratio in unjoined:
        print(f"  UNJOINED  {day:%Y-%m-%d}  {old} -> {new}  "
              f"{a:.2f} -> {b:.2f} (x{ratio:.3f}). Neither notes.json nor NSE's "
              f"symbolchange.csv joins these, so the series is in two pieces. "
              f"A demerger is not a rename: check which it is before adding one.")

    twins = _twins(close)
    print(f"\n{len(twins)} symbol pair(s) carrying identical closes in NSE's own file")
    if args.screener:
        wide = pd.read_parquet(args.screener)
        if isinstance(wide.columns, pd.MultiIndex):
            wide = wide.xs("Close", axis=1, level=1)
        extra = _twins(wide)
        print(f"{len(extra)} in the Screener store ({args.screener})")
        twins = twins + extra
    else:
        print("  (the Screener store was not given, so its twins are not checked; "
              "pass --screener to include them)")
    for a, b, n in twins:
        print(f"  TWINS     {a} and {b} agree on {n} sessions to the paisa. "
              f"Harmless while only one is in the ranked universe -- which is "
              f"what to check.")

    if (unjoined or twins) and args.fail_on_new:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
