#!/usr/bin/env python3
"""The long NSE price file for backtests from 2010: adjusted closes and traded value, 2008 to date.

    python scripts/build_nse_long_prices.py --out data_cache/nse_long          # needs the R2 secrets

Owner, 2026-10-03: backtest any index from Jan 2010. Reads every session in R2's
nse/prices_daily (NSE's bhavcopy, 2008 on) and the corporate actions (daily Bc
files and NSE's yearly list), keeps every stock any index ever listed
(data/membership_history.json) plus the old tickers of its renames, and writes:

    nse_long_close.parquet   closes adjusted for splits, bonuses, consolidations
                             and demergers, each confirmed by the price
                             (nse_prices.adjusted_close); renames joined under
                             today's ticker. No dividends, no rights issues
                             (owner, 2026-10-03).
    nse_long_value.parquet   traded value per session, in Rs crore (NSE's own
                             TOTTRDVAL, which no split changes), joined the same way.
    nse_long_report.json     what was built: sessions, symbols, unpriced names,
                             renames joined and refused.

Read only on R2. The workflow nse_long_prices.yml uploads the three files to
the data-latest release, which src/loaders/nse_long.py reads.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import src.engine.pipeline  # noqa: E402,F401  (import order: avoids a circular import)
from scripts.nse_history_audit import read_actions, read_history  # noqa: E402
from src.engine.backtester import SAME_COMPANY  # noqa: E402
from src.engine.index_universe import all_ever_members  # noqa: E402
from src.loaders import nse_adjusted as na  # noqa: E402
from src.loaders import nse_history as nh  # noqa: E402
from src.loaders import nse_prices as npx  # noqa: E402

CLOSE_FILE = "nse_long_close.parquet"
VALUE_FILE = "nse_long_value.parquet"
REPORT_FILE = "nse_long_report.json"
CRORE = 1e7


def wanted_symbols(notes: dict, renames: dict) -> tuple[list[str], set[str]]:
    """(the symbols the file keeps, the raw tickers to read for them).

    The raw set adds the old ticker of every rename into a kept name, so the
    years before a ticker change are read and joined.
    """
    keep = all_ever_members() | set(SAME_COMPANY) | set(notes.get("renames") or {})
    succ = {old: (a["new_symbol"] if isinstance(a, dict) else str(a)) for old, a in renames.items()}
    keep |= {succ[s] for s in keep if s in succ}
    raw = set(keep) | {old for old, new in succ.items() if new in keep}
    return sorted(keep), raw


def joined_renames(renames: dict, refused: list[str]) -> dict[str, dict]:
    """The renames the price join accepted, for joining another field the same way."""
    no = {r.split("->", 1)[0] for r in refused}
    return {old: {"new_symbol": a["new_symbol"] if isinstance(a, dict) else str(a)}
            for old, a in renames.items() if old not in no}


def build(prices: pd.DataFrame, actions: pd.DataFrame, notes: dict, renames: dict,
          keep: list[str]) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """(adjusted closes, traded value in Rs Cr, report) for `keep`, from NSE's raw rows."""
    w = na.wide(prices)
    close, value = w["close"], w["value"]
    close.index = value.index = pd.DatetimeIndex(close.index)
    adj, report = npx.adjusted_close(close, actions, keep, notes=notes)
    # Traded value is not adjusted (a split changes the share count, not the rupees
    # traded); it is joined across renames exactly as the closes were.
    val = npx.chain_symbols(value, joined_renames(renames, report["renames_not_joined"]))
    for s in adj.columns:
        if s not in val.columns:
            a = renames.get(s)
            succ = (a["new_symbol"] if isinstance(a, dict) else a) if a is not None else None
            if succ in val.columns:
                val[s] = val[succ]
    val = (val.reindex(index=adj.index, columns=adj.columns) / CRORE).astype("float32")
    # Units check: NSE's value over close x volume is ~1 (the day's average price
    # over its close) whatever the file format; a year far from 1 means a unit slip.
    ratio = (value / (close * w["volume"].set_axis(close.index))).stack()
    ratio = ratio[(ratio > 0) & (ratio < 100)]
    report["value_over_close_x_volume_by_year"] = {
        int(y): round(float(r), 3) for y, r in ratio.groupby(ratio.index.get_level_values(0).year).median().items()}
    return adj, val, report


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--since", type=date.fromisoformat, default=date(2008, 1, 1))
    ap.add_argument("--until", type=date.fromisoformat, default=None)
    ap.add_argument("--out", type=Path, default=Path("data_cache/nse_long"))
    ap.add_argument("--workers", type=int, default=16)
    args = ap.parse_args(argv)

    from src.loaders.nse_identity import auto_renames
    from src.storage.r2 import R2Archive, R2Config
    from src.storage.reader import R2DatasetReader

    archive = R2Archive(R2Config.from_env())
    reader = R2DatasetReader(archive)
    until = args.until or date.today() - timedelta(days=1)
    notes = json.loads((npx.DIR / "notes.json").read_text(encoding="utf-8"))
    days = sorted(d for d in nh.r2_days(archive, nh.R2_PRICES) if args.since <= d <= until)
    print(f"R2 holds {len(days)} sessions in [{args.since}, {until}]")

    prices = read_history(reader, days, args.workers)
    renames = {**auto_renames(set(prices["symbol"].dropna().unique())), **(notes.get("renames") or {})}
    keep, raw = wanted_symbols(notes, renames)
    prices = prices[prices["symbol"].isin(raw)]
    actions = read_actions(reader, archive, args.since, until)
    actions = actions[actions["symbol"].isin(raw)] if len(actions) else actions
    print(f"keeping {len(keep)} symbols ({len(raw)} raw tickers): "
          f"{len(prices):,} price rows, {len(actions):,} actions")

    close, value, report = build(prices, actions, notes, renames, keep)
    args.out.mkdir(parents=True, exist_ok=True)
    close.to_parquet(args.out / CLOSE_FILE, compression="zstd")
    value.to_parquet(args.out / VALUE_FILE, compression="zstd")
    report = {**report, "built": date.today().isoformat(), "since": str(args.since),
              "until": str(until), "sessions_on_r2": len(days),
              "basis": "nse_raw_adjusted_split_bonus_consolidation_demerger"}
    (args.out / REPORT_FILE).write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    sizes = {f: round((args.out / f).stat().st_size / 1e6, 1) for f in (CLOSE_FILE, VALUE_FILE)}
    print(f"wrote {close.shape[1]} symbols x {len(close)} sessions "
          f"({report['first_session']} to {report['last_session']}); MB {sizes}; "
          f"{len(report['unpriced'])} unpriced; {len(report['renames_not_joined'])} renames refused")
    return 0


if __name__ == "__main__":
    sys.exit(main())
