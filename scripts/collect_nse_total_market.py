#!/usr/bin/env python3
"""Nifty Total Market's daily close from NSE's own archive, from its first session (Breadth, 21 Nov 2026).

    python scripts/collect_nse_total_market.py

NSE publishes every index's close for each session in
https://nsearchives.nseindia.com/content/indices/ind_close_all_DDMMYYYY.csv; Nifty Total Market first appears
in late 2021. Breadth measures "ahead of the market over a year" against it (owner, 21 Nov 2026: "Yes" to Total
Market with the shorter history), which needs every session, not the weekly rows data/benchmark_indices.csv holds
before 2025.

Writes data/nse_total_market.csv (date, close), adding only sessions it does not have. Refuses to write (exit 1)
when a close disagrees with data/benchmark_indices.csv by more than 0.05% on a date both hold.
"""
from __future__ import annotations

import io
import sys
import time
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "nse_total_market.csv"
URL = "https://nsearchives.nseindia.com/content/indices/ind_close_all_{d:%d%m%Y}.csv"
FIRST = date(2021, 10, 1)
TOLERANCE = 0.0005


def parse(raw: bytes) -> tuple[pd.Timestamp, float] | None:
    f = pd.read_csv(io.BytesIO(raw))
    f.columns = [c.strip() for c in f.columns]
    row = f[f["Index Name"].astype(str).str.strip().str.lower() == "nifty total market"]
    if row.empty:
        return None
    d = pd.to_datetime(str(row["Index Date"].iloc[0]).strip(), format="%d-%m-%Y")
    return d, float(row["Closing Index Value"].iloc[0])


def check(frame: pd.DataFrame) -> list[str]:
    """Dates where our Screener-built file and NSE's archive disagree."""
    sys.path.insert(0, str(ROOT))
    from src.loaders import benchmark_indices as bi
    ours = bi.series(bi.TOTAL_MARKET).dropna()
    nse = frame.set_index("date")["close"]
    both = pd.concat([ours.rename("ours"), nse.rename("nse")], axis=1, join="inner").dropna()
    bad = both[(both["ours"] / both["nse"] - 1).abs() > TOLERANCE]
    return [f"{d:%d %b %Y}: ours {r.ours:,.2f}, NSE {r.nse:,.2f}" for d, r in bad.iterrows()]


def main() -> int:
    import requests
    kept = pd.read_csv(OUT, parse_dates=["date"]) if OUT.exists() else pd.DataFrame(columns=["date", "close"])
    have = set(pd.to_datetime(kept["date"]).dt.date)
    rows = []
    for d in pd.bdate_range(FIRST, date.today()):
        if d.date() in have:
            continue
        r = requests.get(URL.format(d=d), headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
        time.sleep(0.3)
        if r.status_code != 200 or len(r.content) < 1000:
            continue                                   # a holiday or not yet published
        got = parse(r.content)
        if got:
            rows.append({"date": got[0], "close": got[1]})
    if not rows:
        print("No new session; nothing written.")
        return 0
    frame = (pd.concat([kept, pd.DataFrame(rows)]).assign(date=lambda f: pd.to_datetime(f["date"]))
             .drop_duplicates("date", keep="last").sort_values("date").reset_index(drop=True))
    bad = check(frame)
    if bad:
        print("::error::Nifty Total Market disagrees with benchmark_indices.csv; nothing written:\n  " + "\n  ".join(bad[:10]))
        return 1
    frame.assign(date=frame["date"].dt.strftime("%Y-%m-%d")).to_csv(OUT, index=False)
    print(f"Wrote {OUT.name}: {len(frame)} sessions, {frame['date'].min():%d %b %Y} to {frame['date'].max():%d %b %Y}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
