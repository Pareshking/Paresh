"""Our RRG quadrants for NSE sector indices against StockCharts' weekly India
RRG (benchmark CNX500), on five dated notes. Four choose the method; the
latest (17 Oct 2026) is held out.

Sources (articles.stockcharts.com, "Week Ahead", the RRG paragraph):
  2026-02-07 week-ahead-nifty-near-a-tactical-inflection-point
  2026-07-12 week-ahead-nifty-stays-in-a-range-moving-past-this-level-...
  2026-08-16 week-ahead-directional-move-eludes-nifty-index-yet-to-navigate-...
  2026-08-22 week-ahead-nifty-awaits-a-trigger-as-key-support-and-resistance-...
  2026-10-17 week-ahead-nifty-avoids-a-structural-breakdown-recovery-faces-...
Each note is dated the weekend after the Friday whose close it charts.
"""
import itertools
import sys

import pandas as pd

L, W, G, I = "Leading", "Weakening", "Lagging", "Improving"
TRUTH = {
    "2026-02-06": {L: "FINSERV IT BANK SERVICES METAL PSUBANK", W: "MIDCAP100 AUTO INFRA",
                   G: "REALTY FMCG", I: "ENERGY MEDIA"},
    "2026-07-10": {L: "PHARMA MIDCAP100 MEDIA REALTY", W: "INFRA PSE METAL ENERGY",
                   G: "FMCG IT PSUBANK SERVICES FINSERV", I: "AUTO BANK"},
    "2026-08-14": {L: "AUTO REALTY MEDIA PSUBANK", W: "PHARMA MIDCAP100 ENERGY METAL",
                   G: "INFRA PSE FMCG", I: "IT FINSERV SERVICES BANK"},
    "2026-08-21": {L: "NIFTY50 REALTY MEDIA", W: "PHARMA MIDCAP100 ENERGY",
                   G: "METAL PSE INFRA FMCG", I: "PSUBANK IT FINSERV BANK SERVICES"},
    "2026-10-16": {L: "BANK METAL MEDIA PHARMA IT", W: "REALTY MIDCAP100 AUTO",
                   G: "FMCG ENERGY INFRA", I: "FINSERV PSUBANK PSE SERVICES"},
}
HOLDOUT = "2026-10-16"
truth = {d: {s: q for q, names in t.items() for s in names.split()} for d, t in TRUTH.items()}


def quadrant(ratio_up: bool, mom_up: bool) -> str:
    return L if ratio_up and mom_up else W if ratio_up else I if mom_up else G


def rrg(weekly: pd.DataFrame, bench: str, kind: str, n: int, m: int):
    """(ratio_up, mom_up) per week per index, for one method."""
    rs = 100 * weekly.drop(columns=[bench]).div(weekly[bench], axis=0)
    if kind == "zscore":      # z-score of RS against its own n-week mean, then of the ratio
        ratio = 100 + (rs - rs.rolling(n).mean()) / rs.rolling(n).std()
        mom = 100 + (ratio - ratio.rolling(m).mean()) / ratio.rolling(m).std()
    elif kind == "sma":       # RS over its n-week SMA; ratio over its m-week SMA
        ratio = 100 * rs / rs.rolling(n).mean()
        mom = 100 * ratio / ratio.rolling(m).mean()
    elif kind == "ema":       # the same with exponential averages
        ratio = 100 * rs / rs.ewm(span=n, adjust=False).mean()
        mom = 100 * ratio / ratio.ewm(span=m, adjust=False).mean()
    elif kind == "roc":       # ratio as sma; momentum as the ratio's m-week change
        ratio = 100 * rs / rs.rolling(n).mean()
        mom = 100 + (ratio - ratio.shift(m))
    elif kind == "jdk":       # open JdK reimplementations: z-score of RS; z-score of the ratio's 1-week change
        ratio = 100 + (rs - rs.rolling(n).mean()) / rs.rolling(n).std()
        roc = 100 * (ratio / ratio.shift(1) - 1)
        mom = 100 + (roc - roc.rolling(m).mean()) / roc.rolling(m).std()
    elif kind == "jdks":      # the same on RS smoothed by a 5-week EMA first
        rs5 = rs.ewm(span=5, adjust=False).mean()
        ratio = 100 + (rs5 - rs5.rolling(n).mean()) / rs5.rolling(n).std()
        roc = 100 * (ratio / ratio.shift(1) - 1)
        mom = 100 + (roc - roc.rolling(m).mean()) / roc.rolling(m).std()
    # Missing stays missing: NaN >= 100 is False, which scored a series with
    # no data (SERVICES) as Lagging.
    return (ratio >= 100).where(ratio.notna()), (mom >= 100).where(mom.notna())


def score(up_r, up_m, dates):
    hit = tot = 0
    misses = []
    for d in dates:
        day = pd.Timestamp(d)
        if day not in up_r.index:
            continue
        for s, q in truth[d].items():
            if s not in up_r.columns or pd.isna(up_r.at[day, s]) or pd.isna(up_m.at[day, s]):
                continue
            ours = quadrant(bool(up_r.at[day, s]), bool(up_m.at[day, s]))
            tot += 1
            if ours == q:
                hit += 1
            else:
                misses.append(f"{d} {s}: ours {ours}, StockCharts {q}")
    return hit, tot, misses


closes = pd.read_parquet(sys.argv[1])
closes.index = pd.DatetimeIndex(closes.index)
weekly = closes.resample("W-FRI").last().ffill(limit=1)
print("weekly rows", len(weekly), weekly.index[0].date(), "..", weekly.index[-1].date())
print("indices", sorted(c for c in weekly.columns if c != "NIFTY500"))

fit = [d for d in TRUTH if d != HOLDOUT]
results = []
for kind, n, m in itertools.product(["zscore", "sma", "ema", "roc", "jdk", "jdks"], [8, 10, 12, 14, 20, 26, 40, 52], [1, 2, 4, 6, 8, 10, 14, 26]):
    if kind != "roc" and m == 1:
        continue
    up_r, up_m = rrg(weekly, "NIFTY500", kind, n, m)
    h, t, _ = score(up_r, up_m, fit)
    if t:
        results.append((h / t, h, t, kind, n, m))
results.sort(reverse=True)
print("\nbest on the four fitting notes:")
for r in results[:10]:
    print(f"  {r[0]:.0%} ({r[1]}/{r[2]})  {r[3]} n={r[4]} m={r[5]}")
best = results[0]
up_r, up_m = rrg(weekly, "NIFTY500", best[3], best[4], best[5])
h, t, miss = score(up_r, up_m, [HOLDOUT])
print(f"\nHOLDOUT {HOLDOUT} with {best[3]} n={best[4]} m={best[5]}: {h}/{t} = {h / t:.0%}")
for x in miss:
    print("  miss:", x)
h, t, miss = score(up_r, up_m, fit)
print(f"fitting notes: {h}/{t} = {h / t:.0%}")
for x in miss:
    print("  miss:", x)
# How sensitive: the holdout score of the top five methods
print("\nholdout for the top 5 fitting methods:")
for r in results[:5]:
    a, b = rrg(weekly, "NIFTY500", r[3], r[4], r[5])
    h, t, _ = score(a, b, [HOLDOUT])
    print(f"  {r[3]} n={r[4]} m={r[5]}: fit {r[0]:.0%}, holdout {h}/{t} = {h / t:.0%}")
