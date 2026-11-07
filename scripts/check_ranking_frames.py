#!/usr/bin/env python3
"""Refuse to publish a Screener store the app cannot shape into a ranking frame.

    python scripts/check_ranking_frames.py --store data_cache/screener_prices.parquet
    python scripts/check_ranking_frames.py --published

--published checks the store the site reads now against this checkout's NSE
closes (data/nse_prices): the monthly freeze rewrites that file, the other input
of the same step, and runs this before committing it (S82).

On 2026-10-14 a new store went live (TRIVENIPT's first Screener closes) and
every page load failed in price_source.keep_and_fill: the store passed the
row-count check, and nothing ran the app's own code on it before the site read
it. This runs exactly that code, price_source.ranking_frames with NSE's
closes as the middle source, as the app and the nightly precompute do, on
every symbol in the store. Run before the publish; exit 1 refuses it, the
site keeps the last good store and the failure alert fires.

Fails when:
  the frame cannot be built at all (an exception, or None);
  an NSE fill step raised and keep_and_fill skipped it (PriceFrames.middle_errors):
  the app survives that, but it is a fault to fix, not a night to publish.
"""

from __future__ import annotations

import argparse
import os
import sys
import traceback

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)


def check(store_path: str | None, store=None) -> list[str]:
    """The problems found; empty when the store is safe to publish."""
    from src.loaders import nse_prices, price_source, screener_loader

    if store is None:
        store = screener_loader.load_store(store_path)
    if store is None or store.empty:
        return [f"store {store_path or 'published'} is missing or unreadable"]
    symbols = list(screener_loader.closes(store).columns)
    try:
        src = price_source.ranking_frames(store, symbols, nse_prices.middle_close(symbols))
    except Exception:  # noqa: BLE001
        return ["ranking_frames raised:\n" + traceback.format_exc()]
    if src is None:
        return ["ranking_frames returned None: neither Screener nor NSE can serve"]
    print(f"Ranking frame: source={src.source}, {src.close.shape[0]} sessions x "
          f"{src.close.shape[1]} symbols, last session {src.close.index.max().date()}")
    for note in src.notes:
        print(f"  note: {note}")
    return list(src.middle_errors)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    where = ap.add_mutually_exclusive_group(required=True)
    where.add_argument("--store", help="the Screener store about to be published")
    where.add_argument("--published", action="store_true",
                       help="the store the site reads now, with this checkout's NSE closes")
    args = ap.parse_args()
    if args.published:
        from src.loaders import price_source
        store = price_source.fetch_screener_store()
        if store is None or store.empty:
            print("::error::the published Screener store could not be read")
            return 1
        problems = check(None, store)
    else:
        problems = check(args.store)
    for p in problems:
        print(f"::error::{p}")
    if problems:
        print("Refused: the app could not shape this store cleanly with these NSE closes.")
        return 1
    print("The app's ranking frame builds cleanly from this store.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
