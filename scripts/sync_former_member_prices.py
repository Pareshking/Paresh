#!/usr/bin/env python3
"""Fetch prices for stocks the index once held and no longer does.

    python scripts/sync_former_member_prices.py            # fetch and write
    python scripts/sync_former_member_prices.py --dry-run  # say what it would fetch
    python scripts/sync_former_member_prices.py --only-if-out-of-date   # nightly

Reads the membership record, takes every name it ever lists as a member that the
current universe lacks, takes their closes from Screener's store (the app's own
basis), NSE's committed closes for any Screener lacks, and writes
data/former_member_prices.parquet. No Yahoo (owner, 2026-10-02).
Run it before the monthly Track Record update so a name that has just left the
index still has prices for the sale. Idempotent: it rewrites the whole file.

--only-if-out-of-date (the nightly run, S135) rebuilds only when the file
disagrees with today's membership record: a name that left the index is neither
priced nor listed unavailable, or a name listed unavailable has rejoined it.
On every other night it changes nothing.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.engine.membership import load_history  # noqa: E402
from src.loaders.former_members import (  # noqa: E402
    META_FILE, MIN_SESSIONS, PRICES_FILE, load, out_of_date, symbols_needed, unavailable,
)
from src.loaders.indices_loader import fetch_indices_data  # noqa: E402
from src.loaders import nse_prices  # noqa: E402

START = "2024-09-30"   # the deep frame's own start: a 12-month window before 2026


def nifty_1000_former(history: dict | None, current: list[str]) -> list[str]:
    """Names the Nifty 1000 ever listed that neither it nor `current` holds today (S194 L2).

    The Nifty 1000 is scored on its own point-in-time list, so a name that left it
    needs a price for its sale just as a former 750 member does (ENNATURE and
    IGLSPIRITS, in and out in November 2026, had none). Empty without the list.
    """
    from src.engine.index_universe import index_history
    from src.loaders.extra_universe_loader import NIFTY_1000_PATH

    h1000 = index_history("nifty_1000", history) if history else None
    if not h1000 or not Path(NIFTY_1000_PATH).exists():
        return []
    listed = pd.read_csv(NIFTY_1000_PATH)
    listed.columns = [str(c).strip() for c in listed.columns]
    now = set(current) | set(listed["Symbol"].astype(str).str.strip().str.upper())
    return symbols_needed(h1000, now)


def fetch(symbols: list[str], start: str = START) -> tuple[pd.DataFrame, dict[str, str]]:
    """(closes from `start`, symbol -> source): Screener first, NSE for the rest."""
    out, source = {}, {}
    store = nse_prices.screener_store()
    if store is not None and isinstance(store.columns, pd.MultiIndex):
        close = store.xs("Close", axis=1, level=-1)
        close.index = pd.DatetimeIndex(close.index).normalize()
        for s in symbols:
            if s in close.columns and close[s].notna().any():
                out[s] = close[s]
                source[s] = "screener"
    rest = [s for s in symbols if s not in out]
    nse = nse_prices.middle_close(rest) if rest else None
    if nse is not None:
        for s in nse.columns:
            if nse[s].notna().any():
                out[s] = nse[s]
                source[s] = "nse"
    frame = pd.DataFrame(out).sort_index()
    return frame[frame.index >= pd.Timestamp(start)], source


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--indices", nargs="+", default=["NIFTY TOTAL MARKET"])
    ap.add_argument("--only-if-out-of-date", action="store_true",
                    help="rebuild only when the file disagrees with the membership record")
    args = ap.parse_args()

    current = fetch_indices_data(args.indices)["Symbol"].unique().tolist()
    history = load_history()
    needed = sorted(set(symbols_needed(history, current)) | set(nifty_1000_former(history, current)))
    print(f"{len(needed)} former members lack prices in the current {len(current)}-stock universe")
    old = load()
    if args.only_if_out_of_date:
        stale = out_of_date(needed, old.columns, unavailable())
        if not stale:
            print("former-member file is up to date: every former member is priced or listed unavailable")
            return 0
        print(f"former-member file is out of date on: {', '.join(stale)}; rebuilding")
    if args.dry_run or not needed:
        print(", ".join(needed))
        return 0

    adj, source = fetch(needed)
    counts = adj.notna().sum()
    usable = sorted(s for s in adj.columns if counts[s] >= MIN_SESSIONS)
    missing = sorted(set(needed) - set(usable))
    adj = adj[usable].astype("float32").sort_index()
    # Say how much of the existing history the rebuild restates, so a source
    # change (S135: 904 BSE closes replaced by NSE's) shows in the log.
    if not old.empty:
        shared = [c for c in old.columns if c in adj.columns]
        a, b = old[shared], adj[shared].reindex(old.index)
        moved = ((b - a).abs() > 1e-3 * a.abs()) & a.notna() & b.notna()
        print(f"restated {int(moved.to_numpy().sum())} existing closes in "
              f"{int(moved.any().sum())} names: {', '.join(c for c in shared if moved[c].any()) or 'none'}")
    adj.to_parquet(PRICES_FILE)
    META_FILE.write_text(json.dumps({
        "fetched_on": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "source": "Screener closes; NSE closes (split/bonus adjusted) where Screener has none",
        "by_source": {k: sum(1 for s in usable if source.get(s) == k) for k in ("screener", "nse")},
        "symbols": len(usable),
        "first_session": str(adj.index[0].date()), "last_session": str(adj.index[-1].date()),
        "unavailable": missing,
        "note": ("No usable history on Screener or NSE (fewer than %d sessions): names merged "
                 "out of existence, or listed too recently to have that many. They stay "
                 "unpriceable and cannot be selected." % MIN_SESSIONS),
    }, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {PRICES_FILE.name}: {len(usable)} symbols, {len(adj)} sessions; "
          f"unavailable: {missing}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
