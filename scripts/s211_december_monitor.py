#!/usr/bin/env python3
"""December 2026 only (S211, owner 23 Nov 2026: "from December we can monitor and from Jan onwards
records are straight"): rank the 750 on the night's long NSE file under the new window rule (on or
before, a calendar 52-week high) and the old one (on or after, 252 rows), and append one line to
data/s211_monitor.jsonl: ranks moved, the largest move, top-20 changes.

Read by: the owner and the coordinator session in December (docs/HANDOVER.md, TODO S211).
Removed after the 31 Dec 2026 rebalance, with the file. Outside December 2026 it does nothing.
Inputs approximate the production run (no market caps, no corporate-action pass): a monitor, not a record.

    python scripts/s211_december_monitor.py [--force]
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.engine import calendar_momentum as cm  # noqa: E402
from src.engine import membership  # noqa: E402
from src.engine import momentum as mo  # noqa: E402
from src.engine.index_universe import index_history  # noqa: E402

OUT = ROOT / "data" / "s211_monitor.jsonl"
NEW_START, NEW_YEAR = cm.calendar_start_positions, cm.year_window_start


def _old_start(index, months, *, latest_as_of=None):
    """The rule before S211: the first session on or after the date `months` back."""
    idx = pd.DatetimeIndex(index)
    as_of = idx.normalize().to_series(index=np.arange(len(idx)))
    as_of.iloc[-1] = pd.Timestamp(latest_as_of).normalize() if latest_as_of is not None else cm.latest_as_of_date(idx)
    targets = pd.DatetimeIndex(as_of.to_numpy()) - pd.DateOffset(months=months)
    return np.searchsorted(idx.values, targets.values, side="left")


def _old_year(index, end_pos, months=12):
    return max(0, end_pos - 251)


def _ranks(close: pd.DataFrame, members: set, as_of: pd.Timestamp, old: bool) -> pd.Series:
    cm.calendar_start_positions = mo.calendar_start_positions = _old_start if old else NEW_START
    cm.year_window_start = _old_year if old else NEW_YEAR
    try:
        px = close.loc[:as_of, [c for c in close.columns if c in members]].iloc[-420:]
        info = pd.DataFrame({"Symbol": px.columns, "Industry": "x", "Company Name": px.columns})
        r = mo.MomentumEngine(px).get_rankings(info, pd.Series(1e11, index=px.columns))
        return r.set_index("Symbol")["Rank"]
    finally:
        cm.calendar_start_positions = mo.calendar_start_positions = NEW_START
        cm.year_window_start = NEW_YEAR


def reading(close: pd.DataFrame, history: dict) -> dict:
    as_of = pd.Timestamp(close.index[-1])
    members = membership.members_on(history, as_of, canonical=True) or set()
    new, old = _ranks(close, members, as_of, False), _ranks(close, members, as_of, True)
    both = new.index.intersection(old.index)
    diff = (new[both] - old[both]).abs()
    top_new, top_old = set(new[new <= 20].index), set(old[old <= 20].index)
    return {"date": f"{as_of:%Y-%m-%d}", "ranked": int(len(both)), "moved": int((diff > 0).sum()),
            "max_move": int(diff.max()) if len(diff) else 0,
            "top20_in": sorted(top_new - top_old), "top20_out": sorted(top_old - top_new)}


def main() -> int:
    today = date.today()
    if not (today.year == 2026 and today.month == 12) and "--force" not in sys.argv:
        print("S211 monitor: December 2026 only; nothing to do.")
        return 0
    from src.loaders import nse_long
    got = nse_long.load(with_value=False)
    if got is None:
        print("::warning::The long NSE file is unreachable; no S211 reading tonight.")
        return 0
    full = json.loads((ROOT / "data" / "membership_history.json").read_text())
    line = reading(got[0].sort_index(), index_history("nifty_total_market", full))
    with OUT.open("a") as f:
        f.write(json.dumps(line) + "\n")
    print("S211 monitor:", line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
