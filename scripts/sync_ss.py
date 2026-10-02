"""Download SS daily OHLCV into the compact store (src/loaders/ss_prices.py).

    python scripts/sync_ss.py                       # page 1 (1,000 sessions) for everyone
    python scripts/sync_ss.py --symbols RELIANCE TCS --full
    python scripts/sync_ss.py --limit 20 --dry-run  # fetch and check, write nothing

The universe is every symbol the app has ever needed: the Nifty Total Market
list, the Nano Cap list, every name the point-in-time membership record ever
held (so a backtest can price a stock after it left the index), the Screener
store and NSE's committed file -- plus the Nifty 500 and Nifty 50 indices.

One request per symbol, DELAY_S apart with +/-JITTER_S of jitter. A symbol already stored is checked
against the fresh page: restated history or a session beyond the jump limit
re-downloads its whole history (ss_prices.needs_full_refresh). A page that
fails the quality checks is reported and not stored. HTTP 403/429 stops the
run (after waiting out one Retry-After, if the host sends one); so do
MAX_CONSECUTIVE_FAILURES failures in a row that one PAUSE_S pause does not
clear -- a block can also arrive as a 5xx or a timeout. What was fetched so
far is kept: progress is written every --checkpoint symbols, and
--skip-done resumes. A progress line is printed every --report symbols.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.loaders import ss_prices as ss  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "data_cache" / "ss"
JITTER_S = 0.5
MAX_CONSECUTIVE_FAILURES = 5
PAUSE_S = 60.0


def universe() -> list[str]:
    """Every symbol the app, the backtest or the record may need, sorted."""
    names: set[str] = set()
    try:
        from src.loaders.indices_loader import fetch_indices_data

        names |= set(fetch_indices_data(["NIFTY TOTAL MARKET"])["Symbol"])
    except Exception as exc:  # noqa: BLE001
        print(f"  universe: index list unavailable ({type(exc).__name__})")
    try:
        from src.loaders import extra_universe_loader as xl

        names |= set(xl.members()["Symbol"])
    except Exception as exc:  # noqa: BLE001
        print(f"  universe: Nano Cap list unavailable ({type(exc).__name__})")
    try:
        from src.engine.membership import load_history

        history = load_history()
        names |= _symbols_in(history)
    except Exception as exc:  # noqa: BLE001
        print(f"  universe: membership history unavailable ({type(exc).__name__})")
    for path in (ROOT / "data" / "nse_prices" / "closes.parquet",
                 ROOT / "data" / "former_member_prices.parquet"):
        try:
            names |= set(pd.read_parquet(path).columns)
        except Exception:  # noqa: BLE001
            pass
    try:
        from src.loaders import nse_prices

        store = nse_prices.screener_store()
        if store is not None and isinstance(store.columns, pd.MultiIndex):
            names |= set(store.columns.get_level_values(0))
    except Exception as exc:  # noqa: BLE001
        print(f"  universe: Screener store unavailable ({type(exc).__name__})")
    clean = {str(s).strip().upper() for s in names}
    clean = {s for s in clean if s and " " not in s and not s.startswith("DUMMY")}
    return sorted(clean)


def _symbols_in(obj) -> set[str]:
    """Ticker-like strings anywhere in the membership record."""
    out: set[str] = set()
    if isinstance(obj, dict):
        for value in obj.values():
            out |= _symbols_in(value)
    elif isinstance(obj, (list, tuple, set)):
        for value in obj:
            if isinstance(value, str) and value.isupper() and " " not in value and len(value) <= 20:
                out.add(value)
            else:
                out |= _symbols_in(value)
    return out


def load_manifest(out: Path) -> dict:
    try:
        return json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"symbols": {}, "failed": {}}


def save(out: Path, store: pd.DataFrame, manifest: dict) -> dict[int, int]:
    sizes = ss.write_store(store, out)
    manifest["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    manifest["rows"] = int(len(store))
    manifest["bytes_by_year"] = {str(k): v for k, v in sorted(sizes.items())}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n",
                                       encoding="utf-8")
    return sizes


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--symbols", nargs="+", help="only these (default: the whole universe)")
    ap.add_argument("--full", action="store_true", help="whole history back to listing")
    ap.add_argument("--pages", type=int, default=1, help="pages per symbol (1,000 sessions each)")
    ap.add_argument("--limit", type=int, default=None, help="first N symbols only")
    ap.add_argument("--skip-done", action="store_true",
                    help="skip symbols this store already holds (resume a first batch)")
    ap.add_argument("--delay", type=float, default=ss.DELAY_S)
    ap.add_argument("--checkpoint", type=int, default=100)
    ap.add_argument("--report", type=int, default=10, help="progress line every N symbols")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    symbols = [s.upper() for s in args.symbols] if args.symbols else universe()
    symbols = sorted(set(symbols)) + [s for s in ss.INDEX_SYMBOLS if s not in symbols and not args.symbols]
    manifest = load_manifest(args.out)
    store = ss.read_store(args.out)
    if args.skip_done:
        dead = {s for s, why in manifest.get("failed", {}).items() if "no prices" in str(why)}
        symbols = [s for s in symbols if s not in manifest["symbols"] and s not in dead]
    if args.limit:
        symbols = symbols[: args.limit]
    print(f"SS: {len(symbols)} symbols, {'full history' if args.full else f'{args.pages} page(s)'} "
          f"each, {args.delay:g}s apart; store holds {len(store):,} rows")

    session = requests.Session()
    fetched, refreshed, failed, pending = [], [], {}, []
    started = time.time()
    streak, paused, waited = 0, False, False
    stop = False
    for i, symbol in enumerate(symbols):
        if stop:
            break
        if i:
            time.sleep(max(0.5, args.delay + random.uniform(-JITTER_S, JITTER_S)))
        try:
            pages = None if args.full else args.pages
            fresh, more = ss.fetch_history(symbol, pages, session=session, delay_s=args.delay)
            problems = ss.quality_problems(fresh)
            if problems:
                failed[symbol] = "; ".join(problems)
                continue
            stored = store[store["symbol"] == symbol] if len(store) else store
            reason = None if args.full else ss.needs_full_refresh(ss.to_rupees(stored), fresh)
            if reason:
                time.sleep(args.delay)
                fresh, more = ss.fetch_history(symbol, None, session=session, delay_s=args.delay)
                if ss.quality_problems(fresh):
                    failed[symbol] = f"full refresh failed checks ({reason})"
                    continue
                refreshed.append(f"{symbol}: {reason}")
            rows = ss.to_paise(fresh)
            full = args.full or bool(reason) or not more
            pending.append((symbol, rows, full))
            manifest["symbols"][symbol] = {
                "first": str(fresh["date"].min()), "last": str(fresh["date"].max()),
                "rows_fetched": int(len(fresh)), "full_history": full, "more_available": bool(more),
                "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                **({"refresh_reason": reason} if reason else {}),
            }
            manifest["failed"].pop(symbol, None)
            fetched.append(symbol)
            streak, paused, waited = 0, False, False
        except ss.SSBlocked as exc:
            if exc.retry_after and not waited:
                print(f"  {symbol}: {exc}; waiting {exc.retry_after:.0f}s as asked, then one retry")
                time.sleep(exc.retry_after)
                waited = True
                symbols.insert(i + 1, symbol)
                continue
            print(f"::warning::SS refused ({exc}); stopping after {len(fetched)} symbols. "
                  "Resume later with --skip-done.")
            stop = True
        except (ss.SSError, requests.RequestException, ValueError) as exc:
            failed[symbol] = f"{type(exc).__name__}: {str(exc)[:120]}"
            # "no prices" is an unknown ticker (a rename), not trouble with the host.
            if "no prices" not in str(exc):
                streak += 1
                print(f"  {symbol}: {failed[symbol]} (failure {streak} in a row)")
            if streak >= MAX_CONSECUTIVE_FAILURES:
                if paused:
                    print(f"::warning::{streak} failures in a row after a {PAUSE_S:.0f}s pause; "
                          f"stopping after {len(fetched)} symbols. Resume later with --skip-done.")
                    stop = True
                else:
                    print(f"  {streak} failures in a row: pausing {PAUSE_S:.0f}s")
                    time.sleep(PAUSE_S)
                    paused, streak = True, 0
        if args.report and (i + 1) % args.report == 0:
            elapsed = time.time() - started
            print(f"  [{time.strftime('%H:%M:%S')}] {i + 1}/{len(symbols)} asked, "
                  f"{len(fetched)} ok, {len(failed)} failed, {elapsed / (i + 1):.1f}s per symbol")
        if pending and (len(pending) >= args.checkpoint or i == len(symbols) - 1 or stop):
            store = _flush(store, pending)
            pending = []
            if not args.dry_run:
                manifest["failed"].update(failed)
                save(args.out, store, manifest)
            rate = (i + 1) / max(time.time() - started, 1e-9) * 60
            print(f"  {i + 1}/{len(symbols)} done, {len(failed)} failed, "
                  f"{len(store):,} rows stored ({rate:.0f} symbols/min)")
    if pending:
        store = _flush(store, pending)
    manifest["failed"].update(failed)
    sizes = {} if args.dry_run else save(args.out, store, manifest)

    print(f"SS fetched={len(fetched)} refreshed={len(refreshed)} failed={len(failed)} "
          f"rows={len(store):,} bytes={sum(sizes.values()):,} "
          f"symbols_stored={store['symbol'].nunique() if len(store) else 0}")
    for line in refreshed:
        print(f"  REFRESHED {line}")
    for symbol, why in sorted(failed.items()):
        print(f"  FAILED {symbol}: {why}")
    return 0 if fetched or not symbols else 1


def _flush(store: pd.DataFrame, pending: list) -> pd.DataFrame:
    new = pd.concat([rows for _, rows, _ in pending], ignore_index=True)
    replace = [symbol for symbol, _, full in pending if full]
    return ss.upsert(store, new, replace_symbols=replace)


if __name__ == "__main__":
    raise SystemExit(main())
