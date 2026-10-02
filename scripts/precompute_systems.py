"""Precompute the Nano Cap and Combined rankings, as sync_data does for the 750.

Owner, 2026-09-27: "nightly precompute for all systems". Each table is ranked
by the same function as the 750's (sync_data._precompute_rankings), from the
frame the app would build for that system, and stamped with the same
contract -- so production uses it only when every input matches, and computes
the ranking itself otherwise, exactly as it does without this file.

The frame, as the app builds it (app.load_all_data):
  universe  extra_universe_loader.system_universe over the 750's index list
            and the Nano Cap list
  prices    price_source.ranking_frames: Screener's store (it holds both the
            750 and the Nano Cap list), NSE for what it lacks; no Yahoo
  caps      the 750's cached market caps, the Nano Cap list's for the rest

Runs after scripts/sync_data.py in the daily sync; writes
data_cache/rankings_<system>.parquet for the publish steps.
Strictly an accelerator: a failure here costs a slower first load, nothing
else.
"""

from __future__ import annotations

import argparse
import os
import sys

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from scripts.sync_data import _precompute_rankings  # noqa: E402
from src.engine.extra_universe import SYSTEM_COMBINED, SYSTEM_NANO  # noqa: E402
from src.loaders import extra_universe_loader as xl  # noqa: E402
from src.loaders.indices_loader import fetch_indices_data  # noqa: E402
from src.loaders.mcap_loader import fetch_market_caps  # noqa: E402
from src.loaders.ranking_store import asset_name  # noqa: E402

DEFAULT_INDICES = ["NIFTY TOTAL MARKET"]


def run(system: str) -> None:
    # The 750 has priority even for Nano: effective_nano() removes current 750 members.
    base = fetch_indices_data(DEFAULT_INDICES)
    idx_info = xl.system_universe(system, base, xl.members())
    if idx_info.empty:
        print(f"[{system}] no universe; skipping.")
        return
    symbols = idx_info["Symbol"].unique().tolist()
    core, extra = xl.split_symbols(system, idx_info)

    caps = fetch_market_caps(core, force_refresh=False) if core else pd.Series(dtype=float)
    mcaps = pd.concat([caps, xl.list_market_caps(extra)]) if extra else caps
    print(f"[{system}] {len(symbols)} symbols ({len(core)} of the 750, {len(extra)} Nano Cap)")
    _precompute_rankings(symbols, idx_info, mcaps, out_name=asset_name(system))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--extra", default=None,
                    help="ignored; kept so older workflow calls still parse")
    ap.add_argument("--system", action="append", choices=[SYSTEM_NANO, SYSTEM_COMBINED])
    args = ap.parse_args()
    for system in args.system or [SYSTEM_NANO, SYSTEM_COMBINED]:
        try:
            run(system)
        except Exception as exc:
            print(f"[{system}] precompute skipped: {type(exc).__name__}: {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
