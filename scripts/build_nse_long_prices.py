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

import numpy as np
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


TEJHQ_ACTIONS = Path(__file__).resolve().parents[1] / "data" / "reference" / "tejhq_actions.csv"
PRICE_KINDS = ("split", "bonus", "consolidation", "demerger", "bonus_preference")


def with_tejhq(actions: pd.DataFrame, path: Path = TEJHQ_ACTIONS,
               days: int = 5) -> tuple[pd.DataFrame, int]:
    """NSE's actions plus TejHQ's where NSE lists none for that stock nearby.

    Gaps only (scripts/build_tejhq_actions.py): one event worded two ways must
    not multiply into a factor no price confirms (#348). Each added row still
    has to be confirmed by the price, like every action.
    """
    try:
        t = pd.read_csv(path, parse_dates=["ex_date"])
    except OSError:
        return actions, 0
    ours = actions[actions["kind"].isin(PRICE_KINDS)] if len(actions) else actions
    near: dict[str, list[pd.Timestamp]] = {}
    for sym, ex in zip(ours.get("symbol", []), pd.to_datetime(ours.get("ex_date", []), errors="coerce")):
        if pd.notna(ex):
            near.setdefault(sym, []).append(ex)
    gap = pd.Timedelta(days=days)
    add = t[[not any(abs(ex - e) <= gap for e in near.get(sym, []))
             for sym, ex in zip(t["symbol"], t["ex_date"])]]
    rows = add.assign(series="EQ", date=add["ex_date"])[
        ["date", "series", "symbol", "ex_date", "purpose", "kind", "price_factor"]]
    return pd.concat([actions, rows], ignore_index=True), int(len(rows))


def build(prices: pd.DataFrame, actions: pd.DataFrame, notes: dict, renames: dict,
          keep: list[str]) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """(adjusted closes, traded value in Rs Cr, report) for `keep`, from NSE's raw rows."""
    w = na.wide(prices)
    for k in w:
        w[k].index = pd.DatetimeIndex(w[k].index)
    # A holiday stored as a copy of the session before is not a trading day: it
    # would add a zero-return day to every window (nse_adjusted.copied_sessions).
    copies = na.copied_sessions(w["close"], w["volume"])
    w = {k: f.drop(index=copies.index, errors="ignore") for k, f in w.items()}
    close, value = w["close"], w["value"]
    # Rupees on every day: R2's mirror rows for 2010-2018 carry value x 1e5
    # (the mirror's TURNOVER_LACS held rupees then); a day's value over close x
    # volume is ~1, so a day near 1e5 is scaled back. R2 is never rewritten.
    day_ratio = (value / (close * w["volume"])).replace([np.inf, -np.inf], np.nan).median(axis=1)
    rescaled = day_ratio[day_ratio > 1e3].index
    value = value.copy()
    value.loc[rescaled] = value.loc[rescaled] / 1e5
    adj, report = npx.adjusted_close(close, actions, keep, notes=notes)
    report["copied_sessions_dropped"] = [str(d.date()) for d in copies.index]
    # Left after that, a day NSE cannot have traded (src/loaders/nse_calendar.py):
    # an announced special session missing from its list, or a new kind of error.
    from src.loaders.nse_calendar import impossible_sessions

    report["calendar_flags"] = {str(d): why for d, why in impossible_sessions(close.index).items()}
    # Traded value is not adjusted (a split changes the share count, not the rupees
    # traded); it is joined across renames exactly as the closes were.
    val = npx.join_landed(value, report["renames_landed"])
    for s in adj.columns:
        if s not in val.columns:
            succ = npx.landed_in(report["renames_landed"], s)
            if succ in val.columns:
                val[s] = val[succ]
    val = (val.reindex(index=adj.index, columns=adj.columns) / CRORE).astype("float32")
    # Units check: NSE's value over close x volume is ~1 (the day's average price
    # over its close) whatever the file format; a year far from 1 means a unit slip.
    # No filter on the ratio: a unit slip must show in the table, not drop out of it.
    ratio = (value / (close * w["volume"])).replace([np.inf, -np.inf], np.nan).stack()
    ratio = ratio[ratio > 0]
    report["value_days_rescaled_from_x1e5"] = int(len(rescaled))
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
    actions, from_tejhq = with_tejhq(read_actions(reader, archive, args.since, until))
    actions = actions[actions["symbol"].isin(raw)] if len(actions) else actions
    print(f"keeping {len(keep)} symbols ({len(raw)} raw tickers): "
          f"{len(prices):,} price rows, {len(actions):,} actions")

    close, value, report = build(prices, actions, notes, renames, keep)
    args.out.mkdir(parents=True, exist_ok=True)
    close.to_parquet(args.out / CLOSE_FILE, compression="zstd")
    value.to_parquet(args.out / VALUE_FILE, compression="zstd")
    report = {**report, "actions_from_tejhq": from_tejhq,
              "built": date.today().isoformat(), "since": str(args.since),
              "until": str(until), "sessions_on_r2": len(days),
              "basis": "nse_raw_adjusted_split_bonus_consolidation_demerger"}
    (args.out / REPORT_FILE).write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    sizes = {f: round((args.out / f).stat().st_size / 1e6, 1) for f in (CLOSE_FILE, VALUE_FILE)}
    print(f"wrote {close.shape[1]} symbols x {len(close)} sessions "
          f"({report['first_session']} to {report['last_session']}); MB {sizes}; "
          f"{len(report['unpriced'])} unpriced; {len(report['renames_not_joined'])} renames refused; "
          f"{len(report['copied_sessions_dropped'])} copied sessions (holidays) dropped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
