"""Which momentum-health measure describes a LONG-ONLY book? (owner, 8 Nov 2026;
read-only research, TODO S110).

The Dashboard's Momentum health is winners minus losers (top fifth minus bottom
fifth of the Nifty 500, ranked by our score): the academic factor. The book
never shorts, so only the winners' leg is earned. Candidates, each month:

  wml        top fifth minus bottom fifth (today's measure)
  long_ew    top fifth minus the equal-weighted average of all scored members
             (the long leg against the universe it is picked from)
  long_n500  top fifth minus the Nifty 500 index (the long leg against what the
             book is judged against; mixes in the small-stock effect, since the
             top fifth is equal-weighted and the index is cap-weighted)
  short_ew   the equal-weighted average minus the bottom fifth (the leg the
             book cannot earn); long_ew + short_ew = wml
  book       our portfolio minus the Nifty 500 (data/momentum_health.csv)

It reports how much of WML each leg earned, in 5-year blocks, and how well each
measure's trailing 12 months tracks the book's trailing 12-month lead.

    python scripts/research/long_only_momentum_health.py <nse_long_close.parquet>
"""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.engine import index_universe as iu  # noqa: E402
from src.engine import momentum_health as mh  # noqa: E402
from src.engine.rank_history import snapshots  # noqa: E402


def legs(prices: pd.DataFrame, membership, first_month) -> pd.DataFrame:
    ends = [d for d in mh.month_ends(prices) if pd.Period(d, freq="M") >= first_month]
    if ends and not mh._complete(ends[-1]):
        ends = ends[:-1]
    snaps = snapshots(prices, ends[:-1], membership=membership)
    rows = []
    for t0, t1 in zip(ends[:-1], ends[1:]):
        day = snaps[(snaps["date"] == t0) & snaps["in_index"] & snaps["score"].notna()]
        ret = (prices.loc[t1] / prices.loc[t0] - 1.0).reindex(day["symbol"].to_numpy())
        scored = pd.Series(day["score"].to_numpy(), index=day["symbol"].to_numpy())[ret.notna()]
        if len(scored) < mh.MIN_STOCKS:
            continue
        k = max(int(len(scored) * mh.TOP_FRACTION), 1)
        order = scored.sort_values(ascending=False)
        r = ret[scored.index]
        rows.append({"month": str(pd.Period(t1, freq="M")), "top": r[order.index[:k]].mean() * 100,
                     "bottom": r[order.index[-k:]].mean() * 100, "ew": r.mean() * 100})
    return pd.DataFrame(rows)


def main(path: str) -> None:
    close = pd.read_parquet(path)
    if "date" in close.columns:
        close = close.set_index("date")
    close.index = pd.DatetimeIndex(close.index)
    membership = iu.index_history("nifty_500")
    cols = sorted(iu.ever_members(membership) & set(close.columns))
    d = legs(close[cols].astype("float64"), membership, iu.first_month(membership))
    h = pd.read_csv(ROOT / "data" / "momentum_health.csv")
    m = d.merge(h[["month", "spread", "portfolio", "nifty500"]], on="month")
    m["wml"] = m["top"] - m["bottom"]
    m["long_ew"] = m["top"] - m["ew"]
    m["short_ew"] = m["ew"] - m["bottom"]
    m["long_n500"] = m["top"] - m["nifty500"]
    m["book"] = m["portfolio"] - m["nifty500"]
    print(f"months {len(m)} {m['month'].iloc[0]}..{m['month'].iloc[-1]}; "
          f"wml equals the published spread: {(m['wml'] - m['spread']).abs().max():.4f} max gap")
    m["block"] = pd.cut(m["month"].str[:4].astype(int), [2009, 2014, 2019, 2024, 2030],
                        labels=["2010-14", "2015-19", "2020-24", "2025-26"])
    g = m.groupby("block", observed=True)
    out = pd.DataFrame({"months": g.size(), "wml": g["wml"].mean(), "long_ew": g["long_ew"].mean(),
                        "short_ew": g["short_ew"].mean(), "long_n500": g["long_n500"].mean(), "book": g["book"].mean()})
    out.loc["all"] = [len(m), m["wml"].mean(), m["long_ew"].mean(), m["short_ew"].mean(),
                      m["long_n500"].mean(), m["book"].mean()]
    out["long share of wml"] = out["long_ew"] / out["wml"]
    print("\nmean per month, pts:")
    print(out.round(2).to_string())
    r12 = m.set_index("month")[["wml", "long_ew", "long_n500", "short_ew", "book"]].rolling(12).sum().dropna()
    print("\ntrailing 12 months: correlation with the book's 12-month lead (level, and same sign):")
    for c in ("wml", "long_ew", "long_n500", "short_ew"):
        same = ((r12[c] > 0) == (r12["book"] > 0)).mean()
        print(f"  {c:10s} {r12[c].corr(r12['book']):+.2f}   same sign {same:.0%}")
    print("\nmonthly correlation with the book's lead:")
    for c in ("wml", "long_ew", "long_n500", "short_ew"):
        print(f"  {c:10s} {m[c].corr(m['book']):+.2f}")
    print("\nlatest 12 months, sums:", r12.iloc[-1].round(1).to_dict())
    m.to_csv(Path(path).with_name("long_only_momentum_health.csv"), index=False)


if __name__ == "__main__":
    main(sys.argv[1])
