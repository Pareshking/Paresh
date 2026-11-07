#!/usr/bin/env python3
"""Refuse to publish a Screener store the three-source vote outvotes widely (S92).

    python scripts/check_screener_outvotes.py --store data_cache/screener_prices.parquet \
        --ss data_cache/ss [--days 45]

Runs the nightly check's vote (src/engine/reconcile.py, as
scripts/reconcile_report.py does in ss_sync.yml) on the NEW store, before the
Screener sync publishes it: SS, this store and NSE's closes, over the last
--days calendar days. Exits 1, naming the stocks, when the vote outvoted
Screener (the other two agreeing against it) on more than
reconcile.SCREENER_OUTVOTE_LIMIT stocks (environment SCREENER_OUTVOTE_LIMIT
overrides it); the workflow then publishes nothing and the last published store
stays. From the 26 Oct to the 5 Nov 2026 nights the published store carried
BSE's closes for ~43 stocks, and this vote, run a day later, outvoted Screener
on 43 of them (S89).

The window is the nightly report's (45 days), not the last session alone: the
26 Oct store was a rebase, history rewritten, and a rewrite shows on whichever
sessions BSE's move differed from NSE's, not only on the newest one.

Without SS's store nothing can be outvoted (two voices only): it warns and
exits 0. Never changes a price.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.engine import reconcile as rc  # noqa: E402
import reconcile_report as rr  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--store", type=Path, required=True, help="the new Screener store")
    ap.add_argument("--ss", type=Path, required=True, help="SS's store directory")
    ap.add_argument("--days", type=int, default=45, help="calendar days the vote covers")
    args = ap.parse_args(argv)

    limit = rc.outvote_limit()
    screener = rr.load_screener(args.store, None, None)
    if screener is None or screener.empty:
        print("::warning::No Screener closes in the new store; nothing to vote on.")
        return 0
    end = pd.Timestamp(screener.index[-1])
    start = end - pd.Timedelta(days=args.days)
    screener = screener.loc[start:end]
    ss = rr.load_ss(args.ss, start, end) if args.ss.is_dir() else pd.DataFrame()
    if ss.empty:
        print("::warning::SS's store is unavailable: the vote needs three voices, so the "
              "Screener store was NOT checked against it tonight.")
        return 0
    nse = rr.load_nse(list(ss.columns), start, end)
    r2 = rr.read_r2(start, end)
    actions = rr.load_actions(None, r2[1] if r2 else None)
    nse = rr.complete_nse(nse, list(ss.columns), r2[0] if r2 else None, actions, start, end)
    if nse is None:
        print("::warning::NSE's closes are unavailable: the vote cannot judge Screener tonight.")
        return 0

    result = rc.reconcile(ss, screener, nse, actions)
    names = rc.outvoted_names(result.votes, "screener")
    print(f"Vote {start:%Y-%m-%d} → {end:%Y-%m-%d}: {ss.shape[1]} stocks from SS, "
          f"{screener.shape[1]} in the store, NSE for {nse.shape[1]}; Screener outvoted on "
          f"{len(names)} stock(s) (limit {limit})" + (f": {', '.join(names)}" if names else ""))
    refusal = rc.publish_refusal(names, limit)
    if refusal:
        print(f"::error::Not publishing the Screener store: {refusal}. "
              "The last published store stays.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
