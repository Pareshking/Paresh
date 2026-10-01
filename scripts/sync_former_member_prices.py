#!/usr/bin/env python3
"""Fetch prices for stocks the index once held and no longer does.

    python scripts/sync_former_member_prices.py            # fetch and write
    python scripts/sync_former_member_prices.py --dry-run  # say what it would fetch

Reads the membership record, takes every name it ever lists as a member that the
current universe lacks, downloads their adjusted closes from Yahoo (the same
origin as the app's deep history) and writes data/former_member_prices.parquet.
Run it before the monthly Track Record update so a name that has just left the
index still has prices for the sale. Idempotent: it rewrites the whole file.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yfinance as yf

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.engine.membership import load_history  # noqa: E402
from src.loaders.former_members import (  # noqa: E402
    META_FILE, MIN_SESSIONS, PRICES_FILE, symbols_needed,
)
from src.loaders.indices_loader import fetch_indices_data  # noqa: E402
from src.loaders.price_loader import extract_ohlcv  # noqa: E402

START = "2024-09-30"   # the deep frame's own start: a 12-month window before 2026
BATCH = 25


def fetch(symbols: list[str], start: str = START) -> pd.DataFrame:
    frames = []
    for i in range(0, len(symbols), BATCH):
        batch = symbols[i:i + BATCH]
        raw = yf.download([s + ".NS" for s in batch], start=start,
                          end=(pd.Timestamp.now() + pd.Timedelta(days=2)).strftime("%Y-%m-%d"),
                          progress=False, auto_adjust=False, group_by="ticker", threads=True)
        print(f"  batch {i // BATCH + 1}: {len(batch)} symbols -> {raw.shape}")
        frames.append(raw)
    return pd.concat(frames, axis=1) if frames else pd.DataFrame()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--indices", nargs="+", default=["NIFTY TOTAL MARKET"])
    args = ap.parse_args()

    current = fetch_indices_data(args.indices)["Symbol"].unique().tolist()
    needed = symbols_needed(load_history(), current)
    print(f"{len(needed)} former members lack prices in the current {len(current)}-stock universe")
    if args.dry_run or not needed:
        print(", ".join(needed))
        return 0

    raw = fetch(needed)
    adj, *_ = extract_ohlcv(raw, needed)
    counts = adj.notna().sum()
    usable = sorted(s for s in adj.columns if counts[s] >= MIN_SESSIONS)
    missing = sorted(set(needed) - set(usable))
    adj = adj[usable].astype("float32").sort_index()
    adj.to_parquet(PRICES_FILE)
    META_FILE.write_text(json.dumps({
        "fetched_on": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "source": "Yahoo Finance (.NS), Adj Close",
        "symbols": len(usable),
        "first_session": str(adj.index[0].date()), "last_session": str(adj.index[-1].date()),
        "unavailable": missing,
        "note": ("No usable history on Yahoo (fewer than %d sessions): names merged out of "
                 "existence. They stay unpriceable and cannot be selected." % MIN_SESSIONS),
    }, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {PRICES_FILE.name}: {len(usable)} symbols, {len(adj)} sessions; "
          f"unavailable: {missing}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
