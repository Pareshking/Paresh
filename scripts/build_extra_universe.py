"""Build the extra universe list (src/engine/extra_universe.py) from NSE's market caps.

Runs every night in the daily sync; does nothing unless a new month-end
session has arrived in R2. When one has, it writes

  data/indices/ind_nanocap_list.csv   the current list, NSE index-file columns
  data/nanocap_membership.json        every month's list, point in time

and prints who joined and who left. The market caps are NSE's own file for
that session, read from R2 (nse/market_caps, written by nse_collect.py).

    python scripts/build_extra_universe.py            # only if due
    python scripts/build_extra_universe.py --force    # rebuild the current month
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

from scripts.nse_collect import DATASETS, present_dates
from src.core.market_time import ist_today
from src.core.tickers import is_tradeable_symbol
from src.engine import extra_universe as xu

ROOT = Path(__file__).resolve().parents[1]
LIST_PATH = ROOT / "data" / "indices" / "ind_nanocap_list.csv"
HISTORY_PATH = ROOT / "data" / "nanocap_membership.json"
TOTAL_MARKET = ROOT / "data" / "indices" / "ind_niftytotalmarket_list.csv"
TV_FILE = ROOT / "data" / "nse_tv_classification.csv"


def _total_market() -> set[str]:
    frame = pd.read_csv(TOTAL_MARKET)
    frame.columns = [c.strip() for c in frame.columns]
    syms = frame["Symbol"].astype(str).str.strip().str.upper()
    return {s for s in syms if is_tradeable_symbol(s)}


def _classification() -> dict[str, dict[str, str]]:
    if not TV_FILE.exists():
        return {}
    frame = pd.read_csv(TV_FILE)
    frame["Symbol"] = frame["Symbol"].astype(str).str.strip().str.upper()
    return frame.drop_duplicates("Symbol").set_index("Symbol")[
        ["TV_Sector", "TV_Industry"]].to_dict("index")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args(argv)

    from src.storage.r2 import R2Archive, R2Config
    from src.storage.reader import R2DatasetReader

    archive = R2Archive(R2Config.from_env())
    dataset = DATASETS["market_caps"][0]
    day = xu.membership_day(present_dates(archive, dataset), ist_today())
    if day is None:
        print("NANOCAP no month-end market caps in R2 yet; nothing built")
        return 0

    history = json.loads(HISTORY_PATH.read_text()) if HISTORY_PATH.exists() else {
        "schema_version": 1, "name": xu.NAME, "floor_cr": xu.FLOOR_RUPEES / 1e7, "months": {}}
    months = history["months"]
    if day.isoformat() in months and LIST_PATH.exists() and not args.force:
        print(f"NANOCAP up to date: list from {day}, "
              f"in use since {months[day.isoformat()]['effective_from']}")
        return 0

    reader = R2DatasetReader(archive)
    caps = reader.read_parquet(reader.resolve_current(dataset, as_of=day.isoformat()))
    listed = xu.members(caps, _total_market(), _classification())
    if listed.empty:
        print(f"::error::NANOCAP the market caps for {day} gave an empty list; keeping the old one")
        return 1

    LIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    listed.to_csv(LIST_PATH, index=False)

    previous = [v for k, v in sorted(months.items()) if k < day.isoformat()]
    before = set(previous[-1]["symbols"]) if previous else set()
    now = list(listed["Symbol"])
    unclassified = int((listed["Industry"] == xu.UNCLASSIFIED).sum())
    months[day.isoformat()] = {
        "effective_from": xu.effective_from(day).isoformat(),
        "count": len(now),
        "unclassified": unclassified,
        "symbols": now,
    }
    HISTORY_PATH.write_text(json.dumps(history, indent=1) + "\n", encoding="utf-8")

    joined, left = sorted(set(now) - before), sorted(before - set(now))
    print(f"NANOCAP built from {day} market caps: {len(now)} stocks "
          f"≥ ₹{xu.FLOOR_RUPEES / 1e7:,.0f} Cr outside the 750, in use from "
          f"{xu.effective_from(day)}; {unclassified} without a TradingView sector")
    print(f"  largest {listed['Symbol'].iloc[0]} ₹{listed['MarketCapCr'].iloc[0]:,.0f} Cr, "
          f"smallest {listed['Symbol'].iloc[-1]} ₹{listed['MarketCapCr'].iloc[-1]:,.0f} Cr")
    if previous:
        print(f"  joined {len(joined)}: {', '.join(joined[:40])}")
        print(f"  left {len(left)}: {', '.join(left[:40])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
