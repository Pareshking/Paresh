"""Every hole in the long NSE price file, checked against BSE.

    python scripts/audit_gaps_against_bse.py --long nse_long_close.parquet \
        --pack nse_raw_pack.parquet --bse data_cache/bse_daily.parquet --out audit/

The price comparisons (audit_long_prices.py) look only at days both sources
have, so a stretch NSE has no rows for is invisible to them. This finds each
gap of MIN_GAP sessions or more between two priced days of a stock, finds the
stock on BSE, and counts the gap's sessions it traded there:

  NSE-only gap: BSE traded     NSE published nothing, BSE had trades. First found:
                               26 Oct 2023 - 17 Apr 2026, GOODYEAR, NOVARTIND,
                               KENNAMET, KIRLFER, GRAUWEIL (NSE withdrew dealings in
                               securities under "Permitted to Trade", effective
                               26 Oct 2023: NSE Indices press release of 17 Oct 2023
                               citing circular NSE/CML/58560; FORCEMOT to 14 Feb 2024).
  no BSE trading either        a real suspension
  partly traded on BSE         between the two
  not checked: ...             no BSE scrip code could be found (see below)

Finding the BSE scrip code: the rule the BSE fill uses
(src/loaders/bse_fill.map_code), so the audit and the fill agree on which company
a gap belongs to. NSE's ISIN for the symbol near the gap
(data/reference/nse/isin_history.csv, 2011 - 2021, and today's equity_l.csv after
that), else an ISIN NSE gave the symbol in another period; BSE's file carries
ISINs from July 2024, so an ISIN finds a code that traded since then. Only when
no ISIN finds a code, the price match: the code whose BSE close is within 2% of
NSE's raw close on at least 60% of the stock's last 8 NSE sessions before the
gap. Not checked: an ISIN on two BSE codes, an ambiguous price match, and a code
whose ISIN names another issuer than any ISIN NSE gave the symbol (the price-only
match of 3 Oct 2026 picked another company for 47 of its 147 "NSE-only" gaps:
MBAPL matched eleven codes, BHARATRAS 2008 Indian Card Clothing). Sessions BSE
has no file for are left out of the count, not counted as "did not trade".
Stocks renamed on NSE usually have no NSE close under the new symbol, so they
stay "not checked": a name match or the rename chain would fix that (TODO S35).

Writes bse_gap_verify.csv: one row per gap.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.loaders import bse_fill  # noqa: E402

MIN_GAP = 5
PRICE_SERIES = ["EQ", "BE", "BZ", "SM", "ST", "SZ", "T0"]
TOLERANCE = bse_fill.TOLERANCE
COLUMNS = ["symbol", "last_before", "first_after", "missing_sessions", "bse_code", "bse_name", "mapped_by",
           "bse_trading_share", "bse_traded_sessions", "sessions_with_bse_file", "verdict", "detail"]


def find_gaps(long: pd.DataFrame, min_gap: int = MIN_GAP) -> list[tuple]:
    """(symbol, last priced day, next priced day, sessions missing, position of each)."""
    pos = pd.Series(np.arange(len(long.index)), index=long.index)
    gaps = []
    for sym in long.columns:
        priced = long[sym].dropna()
        if len(priced) < 2:
            continue
        p = pos[priced.index].values
        missing = np.diff(p) - 1
        for i in np.where(missing >= min_gap)[0]:
            gaps.append((sym, priced.index[i], priced.index[i + 1], int(missing[i]), int(p[i]), int(p[i + 1])))
    return gaps


def verdict(share: float | None, mapped: bool) -> str:
    if not mapped:
        return "not checked"
    if share is None:
        return "not checked: no BSE file for any session of the gap"
    if share >= 0.5:
        return "NSE-only gap: BSE traded"
    return "no BSE trading either" if share <= 0.1 else "partly traded on BSE"


def audit(long: pd.DataFrame, raw: pd.DataFrame, bse: pd.DataFrame | dict, *,
          history: pd.DataFrame | None = None, current: dict[str, str] | None = None,
          min_gap: int = MIN_GAP) -> pd.DataFrame:
    """One row per gap of `long` (sessions x symbols, any closes): the BSE code and its verdict.

    `raw` is NSE's raw closes (sessions x symbols) the price match compares BSE's
    with; `bse` BSE's table or bse_fill.prepare()'s result; `history` and `current`
    NSE's symbol-ISIN pairs and today's {symbol: isin}, as for bse_fill.fill.
    """
    b = bse if isinstance(bse, dict) else bse_fill.prepare(bse)
    idx = long.index
    rows = []
    for sym, last, nxt, missing, p0, p1 in find_gaps(long, min_gap):
        days = [idx[j] for j in range(max(0, p0 - bse_fill.MATCH_DAYS + 1), p0 + 1)]
        tail = (raw[sym].reindex(days) if sym in raw.columns else pd.Series(np.nan, index=days)).dropna()
        code, how, refusal, detail = bse_fill.map_code(sym, last, nxt, b, tail, history=history, current=current)
        sessions = [d for d in (idx[j] for j in range(p0 + 1, p1)) if d in b["days"]]
        traded, share = 0, None
        if refusal is None:
            s = b["shares"].get(code)
            traded_days = [d for d in sessions if s is not None and d in s.index]
            traded = len(traded_days)
            share = traded / len(sessions) if sessions else None
            wrong = bse_fill.wrong_issuer_sessions(sym, code, traded_days, b, history=history, current=current)
            if wrong:
                refusal, detail = "ISIN mismatch", f"BSE rows of {len(wrong)} sessions carry another issuer's ISIN"
        v = verdict(share, True) if refusal is None else f"not checked: {refusal}"
        rows.append((sym, last.date(), nxt.date(), missing, code, b["name"].get(code) if code is not None else None,
                     how, None if share is None else round(share, 3), traded, len(sessions), v, detail))
    return pd.DataFrame(rows, columns=COLUMNS)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--long", required=True, help="nse_long_close.parquet")
    ap.add_argument("--pack", required=True, help="nse_raw_pack.parquet (raw NSE rows)")
    ap.add_argument("--bse", required=True, help="bse_daily.parquet from scripts/bse_bhavcopy.py build")
    ap.add_argument("--isin-history", default="data/reference/nse/isin_history.csv")
    ap.add_argument("--equity-list", default="data/reference/nse/equity_l.csv",
                    help="NSE's list of equities today (symbol, ISIN)")
    ap.add_argument("--min-gap", type=int, default=MIN_GAP)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    from src.loaders.nse_identity import current_isins, isin_history

    long = pd.read_parquet(args.long)
    long.index = pd.DatetimeIndex(long.index)
    bse = pd.read_parquet(args.bse, columns=["date", "code", "name", "close", "shares", "isin"])
    pack = pd.read_parquet(args.pack, columns=["date", "symbol", "series", "close"])
    pack["date"] = pd.to_datetime(pack["date"]).astype("datetime64[ns]")
    pack = pack[pack["series"].isin(PRICE_SERIES)]
    # One close a day, the best series first (EQ before BE ...), not alphabetically.
    pack = (pack.assign(rank=pack["series"].map(PRICE_SERIES.index)).sort_values("rank")
            .drop_duplicates(["symbol", "date"]))
    raw = pack.pivot(index="date", columns="symbol", values="close")
    hist = isin_history(Path(args.isin_history))
    current = {sym: isin for isin, sym in current_isins(Path(args.equity_list)).items()}

    out = audit(long, raw, bse, history=hist, current=current, min_gap=args.min_gap)
    os.makedirs(args.out, exist_ok=True)
    out.to_csv(os.path.join(args.out, "bse_gap_verify.csv"), index=False)
    print(out.groupby("verdict").agg(gaps=("symbol", "size"), stocks=("symbol", "nunique"),
                                     missing_sessions=("missing_sessions", "sum")).to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
