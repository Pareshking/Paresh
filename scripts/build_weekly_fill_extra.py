#!/usr/bin/env python3
"""Daily closes for the stocks NSE's committed file lacks over Screener's weekly stretch.

    python scripts/build_weekly_fill_extra.py --long nse_long_close.parquet --bse bse_daily.parquet

Owner, 2026-10-07 (TODO S23): fill Screener's weekly stretch with daily
closes for these seven too. data/nse_prices (the app's NSE file) has no REIT
rows and starts JSLL in Aug 2025; four stocks traded only on BSE until they
listed on NSE (SGMART Sep 2025, SHILCTECH Nov 2025, TIMEX Apr 2026, PICCADIL
Jul 2025). The stretch (Oct 2024 - Sep 2025) is history, so the file is built
once and committed; price_source.splice_weekly reads it only where NSE's file
has no close, and the same 2% check against Screener's own weekly moves
applies to every interval.

Sources: the long NSE file (release data-latest; adjusted) for BIRET, EMBASSY
and JSLL; BSE's bhavcopy (scripts/bse_bhavcopy.py; raw, as traded) for the
four, the BSE code found by the ISIN in data/reference/nse/equity_l.csv.
Only NSE sessions are kept (the frame's calendar), and only days BSE traded.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "reference" / "weekly_fill_extra.parquet"
FROM_LONG = ("BIRET", "EMBASSY", "JSLL")
FROM_BSE = ("SGMART", "SHILCTECH", "TIMEX", "PICCADIL")
START, END = pd.Timestamp("2024-10-01"), pd.Timestamp("2025-10-01")


def isins(path: Path = ROOT / "data" / "reference" / "nse" / "equity_l.csv") -> dict[str, str]:
    with open(path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    key = next(k for k in rows[0] if k.strip().upper() == "ISIN NUMBER")
    return {r["SYMBOL"].strip(): r[key].strip() for r in rows}


def build(long_close: pd.DataFrame, bse: pd.DataFrame, isin_of: dict[str, str]) -> tuple[pd.DataFrame, list[dict]]:
    sessions = long_close.index[(long_close.index >= START) & (long_close.index <= END)]
    out = pd.DataFrame(index=sessions, dtype=float)
    notes = []
    for s in FROM_LONG:
        out[s] = long_close[s].reindex(sessions)
        notes.append({"symbol": s, "source": "nse_long_close", "days": int(out[s].notna().sum())})
    b = bse.copy()
    b["date"] = pd.to_datetime(b["date"])
    b = b[(b["date"] >= START) & (b["date"] <= END) & (b["shares"] > 0) & (b["close"] > 0)]
    for s in FROM_BSE:
        codes = sorted(set(b.loc[b["isin"].astype("string").str.strip() == isin_of[s], "code"]))
        if len(codes) != 1:
            raise SystemExit(f"{s}: ISIN {isin_of[s]} maps to BSE codes {codes}, not one")
        rows = b[b["code"] == codes[0]].drop_duplicates("date").set_index("date")["close"]
        out[s] = rows.reindex(sessions)
        notes.append({"symbol": s, "source": f"bse code {codes[0]} (ISIN {isin_of[s]})",
                      "days": int(out[s].notna().sum())})
    out.index.name = "date"
    return out.astype("float64"), notes


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--long", type=Path, required=True)
    ap.add_argument("--bse", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args(argv)
    frame, notes = build(pd.read_parquet(args.long),
                         pd.read_parquet(args.bse, columns=["date", "code", "close", "shares", "isin"]), isins())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(args.out)
    for n in notes:
        print(n)
    print(f"wrote {args.out}: {frame.shape[0]} sessions x {frame.shape[1]} stocks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
