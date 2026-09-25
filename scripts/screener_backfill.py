"""Fill gaps in the Screener store from another Screener frame. Gaps only.

Screener data only: the source is either an earlier Screener store published
to R2 (`--source-r2-revision`, dataset prices/screener) or the published
release asset (`--source-file`). Yahoo prices are never read here; the two
do not share an adjustment basis and must never meet.

Why it exists (2026-09-25): the 10-year Screener download of 2026-09-21
(R2 revision df03ed6d...) went to the release asset, but the nightly sync
starts from its own Actions-cache copy, which did not have it. The nightly
store has held 718-720 dates since, against 1161 in that download: daily
closes 2025-07-04..2025-09-17 and ~440 older weekly dates are missing.

Rules, per symbol:
- A cell the store already has is never changed (the store wins).
- A symbol is filled only if its closes AGREE with the store on the dates
  both hold: at least MIN_OVERLAP common dates, every one within
  MAX_REL_DIFF -- except up to MAX_CORRECTIONS scattered single days
  (Screener correcting a close; owner-approved 2026-09-25 after checking
  the 8 such symbols against live data). A split or bonus re-adjusted since the source was taken
  shows up as disagreement, and that symbol is skipped and listed, so two
  adjustment bases are never mixed in one series.
- A symbol the store does not carry is not added (nothing to verify it
  against, and the universe is the nightly sync's decision).
- The result must have at least as many cells as the store had.

Dry run unless --apply.

    python scripts/screener_backfill.py --store S.parquet --source-file R.parquet
    python scripts/screener_backfill.py --store S.parquet --source-r2-revision df03ed6d --apply
"""

from __future__ import annotations

import argparse
import json
import os
from typing import Any

import pandas as pd

MIN_OVERLAP = 5
MAX_REL_DIFF = 0.01  # 1%: rounding noise passes, any split/bonus/demerger fails
MAX_CORRECTIONS = 3  # scattered single-day corrections tolerated per symbol


def _symbols(frame: pd.DataFrame) -> list[str]:
    return sorted(set(frame.columns.get_level_values(0)))


def _isolated_corrections(rel: pd.Series, off: pd.Series) -> bool:
    """A few single-day price corrections, not a re-adjusted history.

    Checked 2026-09-25 on the 8 symbols the strict rule skipped: each differed
    on 1-2 days of 249, and on every one Screener's live series matched the
    store -- Screener had corrected a close after the source was taken. A
    split or bonus instead re-adjusts EVERY date before its event, so its
    disagreements are many and run unbroken from the earliest shared date.
    The store's corrected values win either way (gaps only are filled).
    """
    if len(off) > MAX_CORRECTIONS or len(off) > 0.02 * len(rel):
        return False
    # An event just after the start of the overlap would disagree on only the
    # first few shared dates -- and the missing older dates would carry the
    # old basis. Refuse when the disagreements are the leading run.
    leading = rel.index[: len(off)]
    return not off.index.equals(leading)


def backfill(store: pd.DataFrame, source: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    """The store with its gaps filled from `source`, and what was done."""
    store = store.sort_index()
    source = source.sort_index()
    filled_symbols, skipped = [], {}
    pieces = []
    for sym in _symbols(store):
        mine = store[sym]
        if sym not in source.columns.get_level_values(0):
            pieces.append(mine.set_axis(pd.MultiIndex.from_product([[sym], mine.columns]), axis=1))
            continue
        theirs = source[sym].reindex(columns=mine.columns)
        a = mine["Close"].dropna()
        b = theirs["Close"].dropna()
        common = a.index.intersection(b.index)
        reason = None
        if len(common) < MIN_OVERLAP:
            reason = f"only {len(common)} common dates"
        else:
            rel = (a.loc[common] / b.loc[common] - 1.0).abs()
            off = rel[rel > MAX_REL_DIFF]
            if len(off) and not _isolated_corrections(rel, off):
                worst = rel.idxmax()
                reason = (f"closes disagree on {len(off)} of {len(common)} shared dates "
                          f"(e.g. {worst.date()}: store {a.loc[worst]:.2f} vs source "
                          f"{b.loc[worst]:.2f}) -- looks like a re-adjustment")
        if reason:
            skipped[sym] = reason
            merged = mine
        else:
            merged = mine.combine_first(theirs)
            if int(merged.notna().sum().sum()) > int(mine.notna().sum().sum()):
                filled_symbols.append(sym)
        pieces.append(merged.set_axis(pd.MultiIndex.from_product([[sym], merged.columns]), axis=1))

    out = pd.concat(pieces, axis=1, sort=True).sort_index()
    out = out.loc[:, store.columns]  # same columns, same order as the store
    before = int(store.notna().sum().sum())
    after = int(out.notna().sum().sum())
    if after < before:
        raise RuntimeError(f"backfill would shrink the store ({before} -> {after} cells)")
    new_dates = out.index.difference(store.index)
    report = {
        "store_dates_before": int(len(store.index)),
        "store_dates_after": int(len(out.index)),
        "dates_added": int(len(new_dates)),
        "first_date_after": str(out.index.min().date()) if len(out) else None,
        "cells_added": after - before,
        "symbols_filled": len(filled_symbols),
        "symbols_skipped": len(skipped),
        "skipped": skipped,
    }
    return out, report


def _read_r2_revision(prefix: str) -> pd.DataFrame:
    from src.storage.r2 import R2Archive, R2Config
    from src.storage.reader import R2DatasetReader

    archive = R2Archive(R2Config.from_env())
    root = "archive/manifests/prices/screener/"
    matches = [
        k for k in archive.list_keys(root)
        if k.endswith(".json") and "/revisions/" in k
        and k.count("/") == root.count("/") + 2  # not the nested bootstrap dataset
        and k.rsplit("/", 1)[-1].startswith(prefix)
    ]
    if len(matches) != 1:
        raise SystemExit(f"revision prefix {prefix!r} matched {len(matches)} manifests: {matches}")
    as_of, _, name = matches[0][len(root):].split("/")
    reader = R2DatasetReader(archive)
    ref = reader.resolve_revision("prices/screener", as_of, name[:-5])  # verifies SHA + size
    print(f"SOURCE r2 prices/screener as_of={as_of} revision={ref.revision_sha256} "
          f"pipeline={ref.manifest.get('pipeline_version')}")
    return reader.read_parquet(ref)


def explain(store: pd.DataFrame, source: pd.DataFrame, symbol: str,
            live: pd.Series | None = None) -> dict[str, Any]:
    """Why a symbol's two copies disagree. Read-only.

    A split or bonus re-adjusts the WHOLE history before its date by one
    factor, so the store/source ratio is one constant on every shared date
    before it and 1.0 after. A data correction changes a few scattered days.
    `live` (tonight's Screener series) says which copy Screener stands by now.
    """
    a = store[symbol]["Close"].dropna()
    b = source[symbol]["Close"].dropna()
    common = a.index.intersection(b.index)
    ratio = (a.loc[common] / b.loc[common])
    off = ratio[(ratio - 1).abs() > MAX_REL_DIFF]
    out: dict[str, Any] = {
        "symbol": symbol, "common_dates": int(len(common)),
        "disagreeing_dates": int(len(off)),
        "first_disagreement": str(off.index.min().date()) if len(off) else None,
        "last_disagreement": str(off.index.max().date()) if len(off) else None,
        "ratio_min": round(float(off.min()), 4) if len(off) else None,
        "ratio_max": round(float(off.max()), 4) if len(off) else None,
        "worst": [f"{d.date()} store={a.loc[d]:.2f} source={b.loc[d]:.2f}"
                  for d in (off - 1).abs().sort_values(ascending=False).index[:5]],
    }
    if len(off):
        # One constant factor on every shared date up to the last disagreement
        # is the fingerprint of a corporate-action re-adjustment.
        before = ratio.loc[:off.index.max()]
        out["looks_like_adjustment"] = bool(
            len(off) == len(before) and float(off.max() / off.min()) < 1.002)
    if live is not None and len(off):
        live = live.dropna()
        days = [d for d in off.index if d in live.index]
        store_hits = sum(abs(a.loc[d] / live.loc[d] - 1) <= 0.002 for d in days)
        source_hits = sum(abs(b.loc[d] / live.loc[d] - 1) <= 0.002 for d in days)
        out["live_checked_dates"] = len(days)
        out["live_matches_store"] = int(store_hits)
        out["live_matches_source"] = int(source_hits)
    return out


def _live_closes(symbols: list[str]) -> dict[str, pd.Series]:
    """Tonight's Screener series for a handful of symbols (one request each)."""
    import time

    import requests

    from src.loaders import screener_loader as sl

    ids = sl.load_ids()
    session = requests.Session()
    out = {}
    for sym in symbols:
        cid = ids.get(sym) or sl.resolve_id(sym, session)
        got = sl.fetch_series(cid, session) if cid else None
        if got is not None:
            out[sym] = got[0]
        time.sleep(1.5)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--store", required=True, help="the Screener store to fill (written only with --apply)")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--source-file", help="another Screener store, e.g. the release asset")
    src.add_argument("--source-r2-revision", help="prefix of a prices/screener revision SHA in R2")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--explain", default="",
                    help="comma-separated symbols: report why their copies disagree "
                         "(and what Screener serves live), then exit without writing")
    args = ap.parse_args()

    if args.source_file:
        source = pd.read_parquet(args.source_file)
        print(f"SOURCE file {args.source_file}")
    else:
        source = _read_r2_revision(args.source_r2_revision)

    if args.explain:
        symbols = [x.strip().upper() for x in args.explain.split(",") if x.strip()]
        store = pd.read_parquet(args.store)
        live = _live_closes(symbols)
        for sym in symbols:
            print("EXPLAIN " + json.dumps(explain(store, source, sym, live.get(sym)),
                                          sort_keys=True))
        return 0

    if not os.path.exists(args.store):
        # No store at all (the Actions cache expired or was never written):
        # the source is the whole of what we know.
        print(f"STORE {args.store} missing; the source becomes the store.")
        store_frame, report = source.sort_index(), {"store_dates_before": 0,
                                                    "store_dates_after": len(source.index)}
    else:
        store_frame, report = backfill(pd.read_parquet(args.store), source)

    for sym, why in sorted(report.get("skipped", {}).items()):
        print(f"  SKIPPED {sym}: {why}")
    summary = {k: v for k, v in report.items() if k != "skipped"}
    print("SCREENER_BACKFILL " + json.dumps(summary, sort_keys=True))

    if not args.apply:
        print("DRY RUN: store not written.")
        return 0
    os.makedirs(os.path.dirname(args.store) or ".", exist_ok=True)
    store_frame.to_parquet(args.store, compression="zstd")
    print(f"WRITTEN {args.store}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
