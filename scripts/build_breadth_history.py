#!/usr/bin/env python3
"""Breadth on the members of each date, and the Dashboard's signal tests (S150).

    python scripts/build_breadth_history.py

Writes
    data/breadth_history.csv   date, universe, above_200, above_50, net_new_highs, beat_share, beat_gap
                               universe "total_market": the 750 ranked here, members of the day,
                               from NSE's first recorded list (29 Oct 2021); "nifty500": from 2010.
    data/signal_tests.json     src/engine/signal_tests.py's results.

Prices: the backtest's long NSE file (src/loaders/nse_long.py), which holds the
stocks that have since left the index. Run by daily_sync after the membership
record is updated. Exit 0 with a warning when the long file is unreachable: the
committed files are kept.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.engine import market_questions as mq  # noqa: E402
from src.engine import signal_tests  # noqa: E402
from src.engine.index_universe import index_history  # noqa: E402
from src.engine.pit_breadth import member_mask  # noqa: E402
from src.loaders import nse_long  # noqa: E402

OUT = ROOT / "data" / "breadth_history.csv"
TESTS = ROOT / "data" / "signal_tests.json"
FIELDS = ["date", "universe", "above_200", "above_50", "net_new_highs", "beat_share", "beat_gap"]
UNIVERSES = {"total_market": "nifty_total_market", "nifty500": "nifty_500"}
# Prices from a year before the start, so the EMAs and the 52W window are full.
WARMUP = pd.DateOffset(years=2)


def readings(close: pd.DataFrame, history: dict, bench: pd.Series) -> pd.DataFrame:
    start = pd.Timestamp(history["baseline"]["date"])
    px = close.loc[start - WARMUP:]
    mask = member_mask(history, px.index, px.columns)
    keep = mask.any(axis=0)
    px, mask = px.loc[:, keep], mask.loc[:, keep]
    out = pd.DataFrame({"above_200": mq._share_above_ema(px, 200, mask),
                        "above_50": mq._share_above_ema(px, 50, mask),
                        "net_new_highs": mq._net_new_highs(px, members=mask)})
    out = out.loc[start:].dropna(how="all")
    # Every session, so the page can read a month and a year back on any date.
    beat = [mq._beat_index_12m(px, bench, t, mask) for t in out.index]
    out["beat_share"] = [b[0] for b in beat]
    out["beat_gap"] = [b[1] for b in beat]
    return out


def main() -> int:
    got = nse_long.load(with_value=False)
    if got is None:
        print("::warning::The long NSE file is unreachable; breadth_history.csv and signal_tests.json kept.")
        return 0
    close = got[0].sort_index()
    full = json.loads((ROOT / "data" / "membership_history.json").read_text())
    bench = pd.read_csv(ROOT / "data" / "benchmarks.csv", parse_dates=["date"]).set_index("date")["nifty500"]
    bench = pd.to_numeric(bench, errors="coerce").dropna()
    # The 750's "ahead of the market" readings against Nifty Total Market (owner, 21 Nov 2026); they start a year
    # after its first session (Nov 2022). The Nifty 500 universe keeps the Nifty 500 (the signal tests, from 2010).
    from src.ui.views.market_questions_view import total_market
    benches = {"total_market": total_market(), "nifty500": bench}
    parts = {}
    for name, key in UNIVERSES.items():
        h = index_history(key, full)
        if not h:
            print(f"::warning::No membership timeline for {key}")
            continue
        r = readings(close, h, benches[name] if len(benches[name]) else bench)
        parts[name] = r
        print(f"{name}: {len(r)} sessions, {r.index[0]:%d %b %Y} to {r.index[-1]:%d %b %Y}")
    if not parts:
        return 0
    rows = pd.concat([p.assign(universe=k).rename_axis("date").reset_index() for k, p in parts.items()])
    rows[FIELDS].to_csv(OUT, index=False, float_format="%.2f", date_format="%Y-%m-%d")

    spreads = pd.read_csv(ROOT / "data" / "momentum_health.csv")
    fpi = pd.read_csv(ROOT / "data" / "nsdl_fpi_daily.csv", parse_dates=["date"]).set_index("date")["equity_net"]
    through = pd.Period(str(spreads["month"].iloc[-1]), "M")   # the last completed month
    res = signal_tests.all_tests(spreads, bench, pd.to_numeric(fpi, errors="coerce").dropna(),
                                 parts.get("nifty500"), through)
    TESTS.write_text(json.dumps(res, indent=1) + "\n")
    for t in res["tests"].values():
        print(f"{t['name']}: on {t['on']:+.2f} off {t['off']:+.2f} n {t['n_on']}/{t['n']} "
              f"halves {t['halves']} {'PASS' if t['passed'] else 'not confirmed'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
