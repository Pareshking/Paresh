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

Finding the BSE scrip code: by ISIN where BSE's file carries one (2024 onward,
against data/reference/nse/isin_history.csv); otherwise by price, the code whose
BSE close is within 2% of NSE's raw close on at least 60% of the stock's last 8
NSE sessions before the gap. "(ambiguous)" marks a second code that fits as
well. Sessions BSE has no file for are left out of the count, not counted as
"did not trade". Stocks renamed on NSE usually have no NSE close under the new
symbol, so they stay "not checked": a name match or the rename chain would fix
that (open item in docs/TODO.md).

Writes bse_gap_verify.csv: one row per gap.
"""

from __future__ import annotations

import argparse
import os

import numpy as np
import pandas as pd

MIN_GAP = 5
PRICE_SERIES = ["EQ", "BE", "BZ", "SM", "ST", "SZ", "T0"]
TOLERANCE = 0.02


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


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--long", required=True, help="nse_long_close.parquet")
    ap.add_argument("--pack", required=True, help="nse_raw_pack.parquet (raw NSE rows)")
    ap.add_argument("--bse", required=True, help="bse_daily.parquet from scripts/bse_bhavcopy.py build")
    ap.add_argument("--isin-history", default="data/reference/nse/isin_history.csv")
    ap.add_argument("--min-gap", type=int, default=MIN_GAP)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    long = pd.read_parquet(args.long)
    idx = long.index
    bse = pd.read_parquet(args.bse)
    bse["isin"] = bse["isin"].replace("nan", np.nan)
    pack = pd.read_parquet(args.pack, columns=["date", "symbol", "series", "close"])
    pack["date"] = pd.to_datetime(pack["date"])
    pack = pack[pack.series.isin(PRICE_SERIES)].sort_values("series").drop_duplicates(["symbol", "date"])
    hist = pd.read_csv(args.isin_history, parse_dates=["first", "last"])

    bse_days = set(bse.date.unique())
    isin_to_code = bse.dropna(subset=["isin"]).drop_duplicates("isin").set_index("isin").code.to_dict()
    by_date = dict(tuple(bse[["date", "code", "close", "shares"]].groupby("date")))
    shares_by_code = {c: g.set_index("date").shares for c, g in bse.groupby("code")}

    def code_for(sym, last, pos):
        near = hist[(hist.symbol == sym) & (hist["first"] <= last + pd.Timedelta(days=30))
                    & (hist["last"] >= last - pd.Timedelta(days=30))]
        for isin in near["isin"][::-1]:
            if isin in isin_to_code:
                return int(isin_to_code[isin]), "isin"
        days = [idx[j] for j in range(max(0, pos - 7), pos + 1)]
        nse = pack[(pack.symbol == sym) & (pack.date.isin(days))][["date", "close"]].rename(columns={"close": "nse"})
        if len(nse) < 3:
            return None, "no NSE close to match"
        parts = [by_date[d].merge(nse[nse.date == d], on="date") for d in nse.date if d in by_date]
        if not parts:
            return None, "no BSE file"
        m = pd.concat(parts)
        m = m[m.nse > 0]
        m["gap"] = (m.close / m.nse - 1).abs()
        score = m.groupby("code").agg(hits=("gap", lambda v: (v < TOLERANCE).sum()),
                                      med=("gap", "median")).sort_values(["hits", "med"], ascending=[False, True])
        if score.empty or score.iloc[0].hits < max(3, 0.6 * len(nse)):
            return None, "no BSE price match"
        tie = len(score) > 1 and score.iloc[1].hits == score.iloc[0].hits and score.iloc[1].med < 2 * score.iloc[0].med + 1e-9
        return int(score.index[0]), "price match" + (" (ambiguous)" if tie else "")

    rows = []
    for sym, last, nxt, missing, p0, p1 in find_gaps(long, args.min_gap):
        code, how = code_for(sym, last, p0)
        sessions = [d for d in (idx[j] for j in range(p0 + 1, p1)) if d in bse_days]
        traded = 0
        if code is not None and code in shares_by_code:
            s = shares_by_code[code]
            traded = sum(1 for d in sessions if d in s.index and s.loc[d] > 0)
        share = traded / len(sessions) if sessions else None
        v = verdict(share, code is not None)
        if code is None:
            v = f"not checked: {how}"
        rows.append((sym, last.date(), nxt.date(), missing, code, how, None if share is None else round(share, 3),
                     traded, len(sessions), v))
    out = pd.DataFrame(rows, columns=["symbol", "last_before", "first_after", "missing_sessions", "bse_code",
                                      "mapped_by", "bse_trading_share", "bse_traded_sessions",
                                      "sessions_with_bse_file", "verdict"])
    os.makedirs(args.out, exist_ok=True)
    out.to_csv(os.path.join(args.out, "bse_gap_verify.csv"), index=False)
    print(out.groupby("verdict").agg(gaps=("symbol", "size"), stocks=("symbol", "nunique"),
                                     missing_sessions=("missing_sessions", "sum")).to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
