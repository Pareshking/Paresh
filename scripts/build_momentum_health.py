#!/usr/bin/env python3
"""Rebuild data/momentum_health.csv: momentum's monthly spread from our ranking (S91).

    python scripts/build_momentum_health.py [--check-against IIMA_MONTHLY.csv]

Each month-end the Nifty 500's point-in-time members (src/engine/index_universe)
are ranked by the site's composite score on NSE's long adjusted closes
(src/loaders/nse_long); the next month's top-fifth minus bottom-fifth return
is that month's spread (src/engine/momentum_health.py). Runs monthly
(.github/workflows/momentum_health.yml). Refuses to write (exit 1) when:
  fewer than 24 months, the newest month older than two months, a month with
  fewer than 100 stocks scored, or a spread that is not a number.
--check-against prints the correlation with IIMA's WML factor (the
independent check in docs/MOMENTUM_HEALTH.md).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "data" / "momentum_health.csv"
# The newest month-end's qualified share, which needs no next month
# (audit U-M8): the spreads can only carry a month once its return
# is in, so the card read September on a 9 Nov page.
LATEST = ROOT / "data" / "momentum_health_latest.json"
INDEX_KEY = "nifty_500"


def build_latest() -> dict | None:
    """The newest month-end's qualified share, for the card's headline."""
    from src.engine import index_universe as iu
    from src.engine.momentum_health import latest_qualified
    from src.loaders import nse_long

    loaded = nse_long.load(with_value=False)
    if loaded is None:
        return None
    close = loaded[0]
    membership = iu.index_history(INDEX_KEY)
    cols = sorted(iu.ever_members(membership) & set(close.columns))
    return latest_qualified(close[cols].astype("float64"), membership,
                            first_month=iu.first_month(membership))


def build() -> pd.DataFrame:
    from src.engine import index_universe as iu
    from src.engine.momentum_health import monthly_spreads
    from src.loaders import nse_long

    loaded = nse_long.load(with_value=False)
    if loaded is None:
        raise SystemExit("::error::NSE's long file could not be read")
    close = loaded[0]
    membership = iu.index_history(INDEX_KEY)
    cols = sorted(iu.ever_members(membership) & set(close.columns))
    sp = monthly_spreads(close[cols].astype("float64"), membership,
                         first_month=iu.first_month(membership))
    # Our strategy's own monthly returns beside the factor's (owner, 8 Nov 2026,
    # TODO S110): Dashboard evidence must hold for the book. A failure here
    # keeps the spreads and writes the file without these two columns.
    try:
        from src.engine.portfolio_history import portfolio_months
        bench = pd.read_csv(ROOT / "data" / "benchmarks.csv", parse_dates=["date"]).set_index("date")["nifty500"]
        sp = sp.merge(portfolio_months(close, bench, INDEX_KEY), on="month", how="left")
    except Exception as exc:  # noqa: BLE001
        print(f"::warning::portfolio months not written: {type(exc).__name__}: {exc}")
    return sp


def problems(sp: pd.DataFrame, today: pd.Timestamp) -> list[str]:
    out = []
    if len(sp) < 24:
        out.append(f"only {len(sp)} months")
        return out
    newest = pd.Period(sp["month"].iloc[-1], freq="M")
    if (pd.Period(today, freq="M") - newest).n > 2:
        out.append(f"newest month {newest} is more than two months old")
    if (sp["n"] < 100).any():
        out.append("a month has fewer than 100 stocks scored")
    if not np.isfinite(sp["spread"].to_numpy(dtype=float)).all():
        out.append("a spread is not a number")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check-against", help="IIMA's monthly four-factor CSV")
    args = ap.parse_args()
    sp = build()
    bad = problems(sp, pd.Timestamp.today())
    for b in bad:
        print(f"::error::{b}")
    if bad:
        return 1
    if args.check_against:
        iima = pd.read_csv(args.check_against)
        m = sp.merge(iima.rename(columns={"Date": "month"})[["month", "WML"]], on="month")
        r12 = m[["spread", "WML"]].rolling(12).sum().dropna()
        print(f"IIMA WML: {len(m)} months {m['month'].iloc[0]}..{m['month'].iloc[-1]}, "
              f"correlation {m['spread'].corr(m['WML']):.3f} monthly, {r12['spread'].corr(r12['WML']):.3f} "
              f"over 12 months, same sign {(np.sign(m['spread']) == np.sign(m['WML'])).mean():.0%}")
    out = sp.copy()
    out["date"] = pd.to_datetime(out["date"]).dt.strftime("%Y-%m-%d")
    out.round({"top": 4, "bottom": 4, "spread": 4, "qualified": 4, "portfolio": 4, "nifty500": 4, "ew": 4}).to_csv(OUT, index=False)
    print(f"{len(out)} months {out['month'].iloc[0]}..{out['month'].iloc[-1]} -> {OUT}")
    # Written separately, so a failure here cannot cost the spreads.
    try:
        latest = build_latest()
        if latest:
            LATEST.write_text(json.dumps(latest, indent=1) + "\n", encoding="utf-8")
            print(f"latest qualified {latest['qualified']:.1%} at {latest['date']} -> {LATEST}")
    except Exception as exc:  # noqa: BLE001
        print(f"::warning::latest qualified share not written: {type(exc).__name__}: {exc}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
