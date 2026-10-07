#!/usr/bin/env python3
"""Run History from 2010 once per index with the Backtest page's defaults; write history_backtests.zip.

    python scripts/precompute_history.py --long data_cache/nse_long --rankings rankings.parquet --out history_backtests.zip

Owner, 2026-10-07: keep the app inside the free plan's memory. Run by
nse_long_prices.yml right after the long file is published. The page serves
these only when its settings equal them (src/loaders/history_store.py).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import src.engine.pipeline  # noqa: E402,F401  (import order: avoids a circular import)
from src.core import config as cfg  # noqa: E402
from src.engine import history_run as hr  # noqa: E402
from src.engine import index_universe as iu  # noqa: E402
from src.engine.liquidity import DEFAULT_FLOOR_CR  # noqa: E402

# The page's floor is off by default (Configuration, cfg_lf) and the usual floor
# when it is on: both are stored.
FLOORS = (0.0, float(DEFAULT_FLOOR_CR))
from src.loaders import benchmark_store, history_store  # noqa: E402

HISTORICAL = ROOT / "data" / "reference" / "historical_industries.csv"


def default_settings() -> dict:
    """The Backtest page's defaults (backtest_view: 20 holdings, monthly, equal weight, top 2x kept)."""
    return hr.settings(top_n=20, rebal_freq=21, weight_method="Equal Weight",
                       weights=cfg.DEFAULT_LOOKBACK_WEIGHTS, stock_cap=cfg.DEFAULT_STOCK_CAP,
                       sector_cap=cfg.DEFAULT_SECTOR_CAP, cost_bps=cfg.DEFAULT_TRANSACTION_COST_BPS,
                       buffer_n=40)


def request(key: str, start, end, floor: float, s: dict, report: dict) -> dict:
    """What a stored run answers: the page asks with the same dict."""
    return {"index": key, "start": str(start), "end": str(end), "floor": round(float(floor), 6),
            "settings": s, "long_last_session": str(report.get("last_session")),
            "long_built": str(report.get("built"))}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--long", type=Path, required=True, help="folder with nse_long_close/value.parquet, report")
    ap.add_argument("--rankings", type=Path, required=True, help="rankings.parquet (industries)")
    ap.add_argument("--out", type=Path, default=Path(history_store.ASSET))
    args = ap.parse_args(argv)

    close = pd.read_parquet(args.long / "nse_long_close.parquet")
    value = pd.read_parquet(args.long / "nse_long_value.parquet")
    report = json.loads((args.long / "nse_long_report.json").read_text(encoding="utf-8"))
    rank = pd.read_parquet(args.rankings)
    rank_industry = rank.set_index("Symbol")["Industry"].to_dict() if "Industry" in rank.columns else {}
    past = pd.read_csv(HISTORICAL)
    historical = dict(zip(past["NSE_SYMBOL"], past["SECTOR"]))
    s = default_settings()
    runs, meta = {}, {"engine": history_store.engine_fingerprint(), "runs": {},
                      "built": pd.Timestamp.now(tz="UTC").isoformat()}
    for key in iu.INDICES:
        membership = iu.index_history(key)
        months = hr.month_range(close.index, membership) if membership else []
        if not months:
            print(f"{key}: no completed month")
            continue
        for floor in FLOORS:
            t0 = time.time()
            prep = hr.prepare(close, value, key, months[0], months[-1], floor, rank_industry, historical)
            res = hr.run(prep, s, benchmark_store.history(period="max", symbol=prep["benchmark"][0]))
            if res is None:
                print(f"{key}, floor {floor:g}: the engine returned nothing")
                continue
            name = history_store.run_name(key, floor)
            runs[name] = res
            meta["runs"][name] = {"request": request(key, months[0], months[-1], floor, s, report),
                                  "months": [str(months[0]), str(months[-1])], "unlabelled": prep["unlabelled"],
                                  "total_return": res["stats"].get("total_return"),
                                  "seconds": round(time.time() - t0)}
            print(f"{key}, floor {floor:g}: {months[0]} - {months[-1]}, total "
                  f"{res['stats'].get('total_return'):.3f}, {time.time() - t0:.0f}s")
    args.out.write_bytes(history_store.pack(runs, meta))
    print(f"wrote {args.out}: {len(runs)} runs, {args.out.stat().st_size / 1e6:.1f} MB")
    return 0 if runs else 1


if __name__ == "__main__":
    sys.exit(main())
