#!/usr/bin/env python3
"""Print NSE's raw rows around a few dated events, read from R2 (diagnostic only).

    python scripts/investigate_raw.py

For the price-history items that need NSE's raw files (docs/TODO.md S25, S44):
the raw closes on each side of a join or ex-date and the corporate actions filed
around it. Reads R2, writes nothing, prints to the job log
(.github/workflows/investigate_raw.yml).
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

# (label, symbols, first day, last day)
EVENTS = [
    ("S44 ANDHRAPAP rights 3:11 at Rs 50, ex 23 Feb 2010", ["ANDHRAPAP"], date(2010, 2, 12), date(2010, 3, 5)),
]
RENAMES_TO = ["PAISALO", "NDL", "SIGIND"]   # S25, looked up by the new ticker


def main() -> int:
    from nse_history_audit import read_actions, read_history

    from src.loaders import nse_history as nh
    from src.loaders.nse_identity import symbol_changes
    from src.storage.r2 import R2Archive, R2Config
    from src.storage.reader import R2DatasetReader

    archive = R2Archive(R2Config.from_env())
    reader = R2DatasetReader(archive)
    held = sorted(nh.r2_days(archive, nh.R2_PRICES))
    ch = symbol_changes()
    events = list(EVENTS)
    for new in RENAMES_TO:
        rows = ch[ch["new"] == new]
        if rows.empty:
            print(f"S25: no symbol-change row for {new} (an ISIN-matched rename); not looked up")
        for _, r in rows.iterrows():
            d = r["date"].date()
            events.append((f"S25 rename {r['old']} -> {new} on {d}", [r["old"], new],
                           d - timedelta(days=14), d + timedelta(days=14)))
    pd.set_option("display.width", 200)
    for label, syms, a, b in events:
        print(f"\n===== {label}")
        days = [d for d in held if a <= d <= b]
        px = read_history(reader, days, workers=8)
        px = px[px["symbol"].isin(syms)].sort_values(["symbol", "date"])
        print(px[["date", "symbol", "series", "prev_close", "close"]].to_string(index=False) if len(px) else "no price rows")
        acts = read_actions(reader, archive, a - timedelta(days=40), b + timedelta(days=40))
        if len(acts):
            acts = acts[acts["symbol"].isin(syms)]
            cols = [c for c in ("symbol", "ex_date", "purpose", "kind", "price_factor", "source") if c in acts.columns]
            print(acts[cols].to_string(index=False) if len(acts) else "no actions filed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
