"""Precompute the Nano Cap and Combined rankings, as sync_data does for the 750.

Owner, 2026-09-27: "nightly precompute for all systems". Each table is ranked
by the same function as the 750's (sync_data._precompute_rankings), from the
frame the app would build for that system, and stamped with the same
contract -- so production uses it only when every input matches, and computes
the ranking itself otherwise, exactly as it does without this file.

The frame, as the app builds it (app.load_all_data):
  universe  extra_universe_loader.system_universe over the 750's index list
            and the Nano Cap list
  prices    the 750's published snapshot for the 750, the extra universe's
            Yahoo file for the rest; then Screener first, Yahoo for gaps
  caps      the 750's cached market caps, the Nano Cap list's for the rest

Runs after scripts/sync_data.py and scripts/sync_extra_yahoo.py in the daily
sync; writes data_cache/rankings_<system>.parquet for the publish steps.
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
from src.core.config import PRICES_FILE  # noqa: E402
from src.engine.extra_universe import SYSTEM_COMBINED, SYSTEM_NANO  # noqa: E402
from src.loaders import extra_universe_loader as xl  # noqa: E402
from src.loaders.indices_loader import fetch_indices_data  # noqa: E402
from src.loaders.mcap_loader import fetch_market_caps  # noqa: E402
from src.loaders.ranking_store import asset_name  # noqa: E402

DEFAULT_INDICES = ["NIFTY TOTAL MARKET"]


def frame_for(core: list[str], extra: list[str], snapshot: pd.DataFrame | None,
              extra_prices: pd.DataFrame | None) -> pd.DataFrame:
    """The prices the app joins for this system (extra_universe_loader.join_prices)."""
    ext = (extra_prices.loc[:, [c for c in extra_prices.columns if c[0] in set(extra)]]
           if extra and extra_prices is not None and not extra_prices.empty else None)
    return xl.join_prices(snapshot if core else None, ext, extra)


def run(system: str, extra_path: str) -> None:
    # The 750 has priority even for Nano: effective_nano() removes current 750 members.\n    base = fetch_indices_data(DEFAULT_INDICES)
    idx_info = xl.system_universe(system, base, xl.members())
    if idx_info.empty:
        print(f"[{system}] no universe; skipping.")
        return
    symbols = idx_info["Symbol"].unique().tolist()
    core, extra = xl.split_symbols(system, idx_info)

    here = os.path.dirname(PRICES_FILE)
    snap_path = os.path.join(here, "prices_snapshot.parquet")
    snapshot = pd.read_parquet(snap_path) if core and os.path.exists(snap_path) else None
    extra_prices = pd.read_parquet(extra_path) if extra and os.path.exists(extra_path) else None
    if extra and extra_prices is None:
        print(f"[{system}] no {extra_path}; skipping (the app computes it).")
        return
    raw = frame_for(core, extra, snapshot, extra_prices)
    if raw.empty:
        print(f"[{system}] no prices; skipping.")
        return

    caps = fetch_market_caps(core, force_refresh=False) if core else pd.Series(dtype=float)
    mcaps = pd.concat([caps, xl.list_market_caps(extra)]) if extra else caps
    print(f"[{system}] {len(symbols)} symbols ({len(core)} of the 750, {len(extra)} Nano Cap)")
    _precompute_rankings(symbols, idx_info, mcaps, raw=raw, out_name=asset_name(system))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--extra", default="prices_extra.parquet",
                    help="the extra universe's Yahoo file (scripts/sync_extra_yahoo.py)")
    ap.add_argument("--system", action="append", choices=[SYSTEM_NANO, SYSTEM_COMBINED])
    args = ap.parse_args()
    for system in args.system or [SYSTEM_NANO, SYSTEM_COMBINED]:
        try:
            run(system, args.extra)
        except Exception as exc:
            print(f"[{system}] precompute skipped: {type(exc).__name__}: {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
