"""Skip 0-21 sessions on the site score, simplified monthly book (owner, 20 Nov 2026; TODO S160).

Usage: RESMOM_FF=<iima csv> RESMOM_OUT=<dir> python scripts/research/score_skip_sim.py
"""
import sys
from pathlib import Path
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent))
from residual_momentum import OUT, factors, load
from momentum_abc_overlays import run, stats
from src.engine.rank_history import snapshots
close, mem, ends = load(); ff, bm = factors(ends)
dates = [d for d in ends if d >= pd.Timestamp("2010-02-01")]
idx = close.index
snap = snapshots(close, dates, membership=mem)
elig, gated = {}, {}
for d, g in snap.groupby("date"):
    g = g[g["in_index"] & close.loc[d].reindex(g["symbol"]).notna().to_numpy()]
    elig[d], gated[d] = list(g["symbol"]), set(g.loc[g["qualifies"], "symbol"])
rows=[]; yr={}
for skip in (0,1,2,3,4,5,6,7,8,10,12,15,21):
    sd = {d: idx[idx.get_loc(d) - skip] for d in dates}
    sn = snapshots(close, list(sd.values()), membership=mem)
    by = {k: pd.Series(g["score"].to_numpy(), index=g["symbol"].to_numpy()) for k, g in sn.groupby("date")}
    sc = {d: by[sd[d]] for d in dates}
    eq, lg = run(close, dates, sc, elig, gated, {}, 0.00024)
    m = eq.resample("ME").last(); y = eq.resample("YE").last()
    y = pd.concat([pd.Series([1.0]), y.reset_index(drop=True)]).pct_change().dropna()
    yr[skip] = (y.to_numpy()*100).round(1)
    for per, lo, hi in [("all","2010-01","2026-12"),("2010-17","2010-01","2017-12"),("2018-26","2018-01","2026-12")]:
        rows.append({"skip":skip,"period":per,**stats(eq, ff["RF"], lo, hi),"turn":lg.traded.mean()})
    print(skip, flush=True)
r=pd.DataFrame(rows); r.to_csv(OUT / "skips.csv", index=False)
pd.DataFrame(yr, index=range(2010,2010+len(yr[0]))).to_csv(OUT / "skips_years.csv")
