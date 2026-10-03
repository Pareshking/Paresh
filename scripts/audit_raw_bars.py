"""Checks on NSE's raw rows that the price comparisons cannot make.

    python scripts/audit_raw_bars.py --pack nse_raw_pack.parquet \
        --ours nse_long_close.parquet --actions nse_action_list_api/ --out audit/

The raw pack (nse_raw_pack.parquet on the release, scripts/build_nse_long_prices.py)
holds every equity row NSE printed since 2008: close, previous close, high,
low, volume, value -- no open. Four checks, each its own CSV:

1. bar_integrity_exceptions.csv -- rows breaking a bar's own arithmetic
   (first run, 3 Oct 2026: 240 closes outside the range, all series T0, the
   T+0 window where a handful of shares trade beside EQ and the close is
   EQ's; 1,372 average prices off by rounding on tiny volumes -- none in a
   price the build uses):
   a close outside [low, high], low above high, a non-positive price, a range
   traded on zero volume, or a day's value / volume (its average price)
   outside [low, high] by more than 1%. 2010-2018 rows carry value x 1e5 on
   R2 (the build scales them back by the day's median), so value is judged on
   the same scaled basis.
2. large_dividends.csv -- dividends of 5% of the last close or more, for the
   stocks in the long file. The long file does not adjust dividends (nor do
   Screener and the app's live data), so a stock's ex-date fall here is a
   payout, not a loss: PFIZER's Rs 360 on 5 Dec 2013 (21% of the price) reads
   as -25% that day. Listed for the owner's decision, not adjusted.
3. isin_lineage.csv -- every symbol change NSE lists (symbolchange.csv) for a
   stock in the long file, with the ISIN either side (isin_history.csv): the
   same ISIN is a pure rename; a different one is a split, merger or scheme
   at the rename, which the build must price, not just join.
4. calendar_sync.csv -- sessions the long file holds against the Nifty 50's
   (data/benchmarks.csv) and the raw pack's: a session in one and not the
   other is a dropped day or a stray one.

Nothing here reaches the network.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.loaders import nse_adjusted as na  # noqa: E402
from src.loaders import nse_bundle as nb  # noqa: E402

REF = Path(__file__).resolve().parents[1] / "data" / "reference" / "nse"
BENCHMARKS = Path(__file__).resolve().parents[1] / "data" / "benchmarks.csv"
TOL = 1e-6           # price comparisons: rounding only
VWAP_TOL = 0.01      # value / volume outside [low, high] by more than 1%
DIVIDEND_YIELD = 0.05


def bar_exceptions(pack: pd.DataFrame) -> pd.DataFrame:
    """Rows of the price series whose own numbers contradict each other."""
    p = pack[pack["series"].isin(na.PRICE_SERIES)].copy()
    p["date"] = pd.to_datetime(p["date"])
    c, h, lo, v = p["close"], p["high"], p["low"], p["volume"]
    # The value column's scale per day: rupees, or x 1e5 on R2's 2010-2018 rows.
    ratio = (p["value"] / (c * v)).replace([np.inf, -np.inf], np.nan)
    scale = ratio.groupby(p["date"]).transform("median")
    value = p["value"] / np.where(scale > 1e3, 1e5, 1.0)
    vwap = (value / v).where(v > 0)
    checks = {
        "non-positive price": (c <= 0) | (h <= 0) | (lo <= 0),
        "low above high": lo > h * (1 + TOL),
        "close above high": c > h * (1 + TOL),
        "close below low": c < lo * (1 - TOL),
        "range on zero volume": (v <= 0) & (h != lo),
        "average price outside the range": vwap.notna()
        & ((vwap < lo * (1 - VWAP_TOL)) | (vwap > h * (1 + VWAP_TOL))),
    }
    rows = []
    for name, hit in checks.items():
        hit = hit.fillna(False)
        if hit.any():
            rows.append(p.loc[hit, ["date", "series", "symbol", "close", "high", "low",
                                    "volume"]].assign(check=name, avg_price=vwap[hit].round(4)))
    cols = ["date", "series", "symbol", "check", "close", "high", "low", "avg_price", "volume"]
    if not rows:
        return pd.DataFrame(columns=cols)
    return pd.concat(rows, ignore_index=True)[cols].sort_values(["date", "symbol"])


def read_actions(path: Path) -> pd.DataFrame:
    """symbol, ex_date, purpose: NSE's yearly lists (a folder of y*.json) or a table."""
    if path.is_dir():
        rows = []
        for f in sorted(path.glob("*.json")):
            rows += json.loads(f.read_text(encoding="utf-8"))
        a = pd.DataFrame(rows).rename(columns={"exDate": "ex_date", "subject": "purpose"})
        a["ex_date"] = pd.to_datetime(a["ex_date"], format="%d-%b-%Y", errors="coerce")
    else:
        a = pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_csv(path)
        a["ex_date"] = pd.to_datetime(a["ex_date"], errors="coerce")
    a["symbol"] = a["symbol"].astype(str).str.strip().str.upper()
    return a[["symbol", "ex_date", "purpose"]].dropna().drop_duplicates()


def large_dividends(pack: pd.DataFrame, actions: pd.DataFrame, symbols: set[str],
                    floor: float = DIVIDEND_YIELD) -> pd.DataFrame:
    """Dividends of `floor` of the last close or more, with the ex-date's own move."""
    a = actions[actions["symbol"].isin(symbols)].copy()
    info = pd.DataFrame([nb.classify_purpose(t) for t in a["purpose"]], index=a.index)
    # "Rht1:5@Prem-Rs100/Div-Rs2" (JMCPROJECT 2009): a rights premium is not a payout.
    payout = (info["kind"] == "dividend") & ~a["purpose"].str.upper().str.contains(r"RI?GH?TS?\b|\bRHT")
    a = a[payout & info["amount"].notna()].assign(amount=info["amount"])
    # Several amounts in one text ("Rs 12.50 + Special Rs 20"): add every one.
    a["amount"] = [sum(float(x) for x in nb._AMOUNT.findall(t.upper())) or amt
                   for t, amt in zip(a["purpose"], a["amount"])]
    w = na.wide(pack.assign(date=pd.to_datetime(pack["date"])))["close"]
    rows = []
    for r in a.itertuples(index=False):
        if r.symbol not in w.columns:
            continue
        s = w[r.symbol].dropna()
        before, after = s[s.index < r.ex_date], s[s.index >= r.ex_date]
        if before.empty or after.empty or (after.index[0] - r.ex_date).days > 7:
            continue
        last = float(before.iloc[-1])
        y = r.amount / last
        if y >= floor:
            rows.append({"symbol": r.symbol, "ex_date": r.ex_date.date(), "amount": r.amount,
                         "close_before": last, "yield": round(y, 4),
                         "ex_day_move": round(float(after.iloc[0]) / last, 4),
                         "purpose": r.purpose})
    cols = ["symbol", "ex_date", "amount", "close_before", "yield", "ex_day_move", "purpose"]
    return pd.DataFrame(rows, columns=cols).sort_values("yield", ascending=False)


def isin_lineage(symbols: set[str], changes: Path = REF / "symbolchange.csv",
                 isins: Path = REF / "isin_history.csv") -> pd.DataFrame:
    """Every NSE symbol change touching the long file, with the ISIN either side."""
    ch = pd.read_csv(changes, header=None, names=["company", "old", "new", "date"],
                     skipinitialspace=True, dtype=str)
    ch = ch.apply(lambda c: c.str.strip())
    ch["date"] = pd.to_datetime(ch["date"], format="%d-%b-%Y", errors="coerce")
    ch = ch[ch["old"].isin(symbols) | ch["new"].isin(symbols)]
    ih = pd.read_csv(isins, parse_dates=["first", "last"])

    def isin_at(sym: str, day: pd.Timestamp, side: str) -> str | None:
        h = ih[ih["symbol"] == sym]
        if h.empty:
            return None
        h = h[h["last"] < day] if side == "before" else h[h["first"] >= day - pd.Timedelta(days=7)]
        if h.empty:
            return None
        return (h.sort_values("last").iloc[-1] if side == "before"
                else h.sort_values("first").iloc[0])["isin"]

    rows = []
    for r in ch.itertuples(index=False):
        old_isin = isin_at(r.old, r.date, "before") or isin_at(r.new, r.date, "before")
        new_isin = isin_at(r.new, r.date, "after")
        verdict = ("no ISIN history" if not (old_isin and new_isin)
                   else "same ISIN" if old_isin == new_isin else "ISIN changed")
        rows.append({"old": r.old, "new": r.new, "date": r.date.date() if pd.notna(r.date) else None,
                     "company": r.company, "isin_before": old_isin, "isin_after": new_isin,
                     "verdict": verdict})
    return pd.DataFrame(rows)


def calendar_sync(ours: pd.Index, pack: pd.DataFrame, benchmarks: Path = BENCHMARKS) -> pd.DataFrame:
    """Sessions held by one of the long file, the raw pack and the Nifty 50, not all three."""
    b = pd.read_csv(benchmarks, parse_dates=["date"])
    nifty = set(b.loc[b["nifty50"].notna(), "date"])
    raw = set(pd.to_datetime(pack["date"]).unique())
    first, last = ours.min(), ours.max()
    days = sorted(d for d in (set(ours) | nifty | raw) if first <= d <= last)
    held = set(ours)
    rows = [{"date": d.date(), "weekday": d.day_name(), "long_file": d in held, "raw_pack": d in raw,
             "nifty50": d in nifty} for d in days if not (d in held and d in raw and d in nifty)]
    out = pd.DataFrame(rows, columns=["date", "weekday", "long_file", "raw_pack", "nifty50"])
    if len(out):
        out["reading"] = np.select(
            [out["raw_pack"] & ~out["long_file"],
             ~out["raw_pack"] & out["nifty50"],
             out["long_file"] & ~out["nifty50"]],
            ["dropped by the build (a holiday copy?)", "a session NSE traded that R2 lacks",
             "a session the Nifty 50 history lacks"], default="")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pack", type=Path, required=True)
    ap.add_argument("--ours", type=Path, required=True, help="nse_long_close.parquet")
    ap.add_argument("--actions", type=Path, required=True,
                    help="NSE's yearly action lists (folder of *.json) or a table with symbol, ex_date, purpose")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)

    pack = pd.read_parquet(args.pack)
    ours = pd.read_parquet(args.ours)
    symbols = set(ours.columns)
    summary: dict = {"raw_rows": int(len(pack))}

    bars = bar_exceptions(pack)
    bars.to_csv(args.out / "bar_integrity_exceptions.csv", index=False)
    summary["bar_exceptions"] = bars["check"].value_counts().to_dict()
    summary["bar_exceptions_long_file_stocks"] = int(bars["symbol"].isin(symbols).sum())

    divs = large_dividends(pack, read_actions(args.actions), symbols)
    divs.to_csv(args.out / "large_dividends.csv", index=False)
    summary["dividends_5pct_or_more"] = int(len(divs))
    summary["dividends_10pct_or_more"] = int((divs["yield"] >= 0.10).sum())

    lin = isin_lineage(symbols)
    lin.to_csv(args.out / "isin_lineage.csv", index=False)
    summary["symbol_changes"] = lin["verdict"].value_counts().to_dict() if len(lin) else {}

    cal = calendar_sync(pd.DatetimeIndex(ours.index), pack)
    cal.to_csv(args.out / "calendar_sync.csv", index=False)
    summary["calendar"] = cal["reading"].value_counts().to_dict() if len(cal) else {}

    (args.out / "raw_summary.json").write_text(json.dumps(summary, indent=1, default=str) + "\n",
                                               encoding="utf-8")
    print(json.dumps(summary, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
