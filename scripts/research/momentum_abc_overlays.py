"""(Owner, 20 Nov 2026; read-only research, TODO S160; docs/MOMENTUM_ABC_2026-11-20.md.)
Usage: RESMOM_FF=<iima csv> RESMOM_OUT=<dir> python scripts/research/momentum_abc_overlays.py

A (residual momentum) x B (skip 0/5/21 sessions) x C (vol-managed exposure, breadth halt), long-only.

Pass rule fixed BEFORE results:
  Baseline = site composite, skip 0, no overlay (the live signal).
  A variant passes only if in the full period, 2010-17 AND 2018-26:
    CAGR >= baseline - 0.5 pp, worst 12 months no worse, and
    (Sharpe >= baseline + 0.10  OR  max drawdown >= 25% smaller).
  Overlay variants must also pass at the neighbouring settings
  (vol target 20% and 25%; breadth 25% and 35%).

Book: point-in-time Nifty 500, month-end signal, top 20 equal weight among stocks
passing the live gates (above 50-day EMA, within 20% of 52-week high), kept while in
the top 40; buy-and-hold inside the month; 30 bps on every rupee traded.
Cash = arbitrage-fund proxy: IIMA T-bill RF - 0.5% a year (0% as sensitivity).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from residual_momentum import OUT as HERE, ROOT, factors, load  # noqa: E402,F401
from src.engine.rank_history import snapshots  # noqa: E402
from src.engine.metrics import max_drawdown  # noqa: E402

TOPN, BUF, COST = 20, 40, 0.0030
BLOCK, NBLK_REG, NBLK_SCORE = 21, 24, 11


def residual_daily(close, bench, dates, skip):
    """Residual CAPM score on 21-session blocks ending `skip` sessions before each date:
    regress 24 blocks on the Nifty 500, score = sum / std of the last 11 blocks' residuals."""
    px = close.ffill(limit=22)
    bx = bench.reindex(close.index).ffill()
    idx = close.index
    out = {}
    for d in dates:
        p = idx.get_loc(d) - skip
        pos = [p - BLOCK * k for k in range(NBLK_REG, -1, -1)]
        if pos[0] < 0:
            continue
        P = px.iloc[pos].to_numpy()
        R = P[1:] / P[:-1] - 1
        b = bx.iloc[pos].to_numpy()
        m = b[1:] / b[:-1] - 1
        ok = np.isfinite(R).all(0)
        Y = R[:, ok]
        A = np.column_stack([np.ones(len(m)), m])
        beta, *_ = np.linalg.lstsq(A, Y, rcond=None)
        e = (Y - A @ beta)[-NBLK_SCORE:]
        sd = e.std(0, ddof=0)
        out[d] = pd.Series(e.sum(0) / np.where(sd > 0, sd, np.nan), index=close.columns[ok])
    return out


def run(close, dates, score, elig, gated, breadth, cash_d, *, vol_target=None, breadth_cut=None):
    """Daily simulation. Returns daily equity (net) and per-rebalance log."""
    px = close.ffill(limit=22)
    idx = close.index
    held, eq_path, unscaled = [], [], []      # unscaled: the equity sleeve's own daily returns
    nav = 1.0
    w_prev = {}                               # weights (fraction of NAV) just before rebalance
    log = []
    for i, d in enumerate(dates[:-1]):
        d1 = dates[i + 1]
        s = score[d].reindex(elig[d]).dropna()
        s = s[s.index.isin(gated[d])].sort_values(ascending=False)
        rank = pd.Series(np.arange(1, len(s) + 1), index=s.index)
        keep = [h for h in held if rank.get(h, 1e9) <= BUF][:TOPN]
        halt = breadth_cut is not None and breadth[d] < breadth_cut
        new = keep if halt else keep + [x for x in s.index if x not in keep][: TOPN - len(keep)]
        # exposure
        w_eq = 1.0
        if vol_target is not None and len(unscaled) >= 63:
            sig = np.std(unscaled[-63:], ddof=0) * np.sqrt(252)
            w_eq = min(1.0, vol_target / sig) if sig > 0 else 1.0
        target = {x: w_eq / TOPN for x in new}
        traded = sum(abs(target.get(k, 0) - w_prev.get(k, 0)) for k in set(target) | set(w_prev))
        nav *= 1 - COST * traded
        # hold through the month, buy-and-hold
        a, b = idx.get_loc(d), idx.get_loc(d1)
        seg = px.iloc[a: b + 1][new].to_numpy() if new else np.empty((b - a + 1, 0))
        rel = seg / seg[0] if new else seg
        rel = np.where(np.isfinite(rel), rel, np.nan)
        rel = pd.DataFrame(rel).ffill().fillna(1.0).to_numpy()  # a name with no print stays flat
        cash_w = 1 - sum(target.values())
        cr = (1 + cash_d) ** np.arange(b - a + 1)
        port = (rel * (w_eq / TOPN)).sum(1) + cash_w * cr
        sleeve = rel.mean(1) if new else np.ones(b - a + 1)
        unscaled.extend(list(sleeve[1:] / sleeve[:-1] - 1))
        for k in range(1, b - a + 1):
            eq_path.append((idx[a + k], nav * port[k]))
        nav *= port[-1]
        w_prev = {x: (w_eq / TOPN) * rel[-1, j] / port[-1] for j, x in enumerate(new)}
        held = new
        log.append({"date": d, "names": len(new), "w_eq": w_eq, "halt": halt, "traded": traded})
    e = pd.Series(dict(eq_path))
    return e, pd.DataFrame(log)


def stats(eq, rf_m, lo, hi):
    m = eq.resample("ME").last()
    m = pd.concat([pd.Series([1.0], index=[m.index[0] - pd.offsets.MonthEnd(1)]), m])
    r = m.pct_change().dropna()
    r.index = r.index.to_period("M")
    r = r[(r.index >= pd.Period(lo, "M")) & (r.index <= pd.Period(hi, "M"))]
    q = (1 + r).cumprod()
    rf = rf_m.reindex(r.index).fillna(rf_m.dropna().iloc[-1])
    return {"cagr": q.iloc[-1] ** (12 / len(r)) - 1, "vol": r.std(ddof=0) * np.sqrt(12),
            "sharpe": (r - rf).mean() / r.std(ddof=0) * np.sqrt(12), "maxdd": max_drawdown(q),
            "worst12": ((1 + r).rolling(12).apply(np.prod, raw=True) - 1).min(), "n": len(r)}


def main():
    close, mem, ends = load()
    ff, bm = factors(ends)
    bench = pd.read_csv(ROOT / "data/benchmarks.csv", parse_dates=["date"]).set_index("date")["nifty500"]
    dates = [d for d in ends if d >= pd.Timestamp("2009-12-01")]
    idx = close.index
    # gates and eligibility at d; composite score at d - skip
    snap = snapshots(close, dates, membership=mem)
    elig, gated = {}, {}
    for d, g in snap.groupby("date"):
        g = g[g["in_index"] & close.loc[d].reindex(g["symbol"]).notna().to_numpy()]
        elig[d], gated[d] = list(g["symbol"]), set(g.loc[g["qualifies"], "symbol"])
    # breadth: share of PIT members above their 200-day average
    dma = close.ffill(limit=22).rolling(200, min_periods=150).mean()
    breadth = {d: float((close.ffill(limit=22).loc[d, elig[d]] > dma.loc[d, elig[d]]).mean()) for d in dates}
    signals = {}
    for skip in (0, 5, 21):
        sd = {d: idx[idx.get_loc(d) - skip] for d in dates}
        sn = snapshots(close, list(sd.values()), membership=mem)
        by = {k: pd.Series(g["score"].to_numpy(), index=g["symbol"].to_numpy()) for k, g in sn.groupby("date")}
        signals[("composite", skip)] = {d: by[sd[d]] for d in dates if sd[d] in by}
        signals[("residual", skip)] = residual_daily(close, bench, dates, skip)
        print("signals skip", skip, flush=True)
    common = [d for d in dates if all(d in s for s in signals.values())]
    rf_m = ff["RF"].copy()
    def cash_daily(arb_spread=0.005, zero=False):
        return 0.0 if zero else ((1 + rf_m.dropna().mean() * 12 - arb_spread) ** (1 / 252) - 1)
    overlays = {"none": {}, "C1 vol 22.5%": {"vol_target": 0.225}, "C2 breadth<30% halt": {"breadth_cut": 0.30},
                "C1+C2": {"vol_target": 0.225, "breadth_cut": 0.30},
                "C1 vol 20%": {"vol_target": 0.20}, "C1 vol 25%": {"vol_target": 0.25},
                "C2 breadth<25%": {"breadth_cut": 0.25}, "C2 breadth<35%": {"breadth_cut": 0.35},
                "C1+C2 20%/25%": {"vol_target": 0.20, "breadth_cut": 0.25},
                "C1+C2 25%/35%": {"vol_target": 0.25, "breadth_cut": 0.35}}
    cd = cash_daily()
    rows, logs = [], {}
    for (sig, skip), sc in signals.items():
        for oname, kw in overlays.items():
            for cash_label, c in [("arb", cd), ("zero", 0.0)]:
                if cash_label == "zero" and oname == "none":
                    continue
                if cash_label == "zero" and not oname in ("C1 vol 22.5%", "C2 breadth<30% halt", "C1+C2"):
                    continue
                eq, lg = run(close, common, sc, elig, gated, breadth, c, **kw)
                logs[(sig, skip, oname, cash_label)] = lg
                for per, lo, hi in [("all", "2010-01", "2026-12"), ("2010-17", "2010-01", "2017-12"),
                                    ("2018-26", "2018-01", "2026-12")]:
                    rows.append({"signal": sig, "skip": skip, "overlay": oname, "cash": cash_label, "period": per,
                                 **stats(eq, rf_m, lo, hi), "avg_eq": lg["w_eq"].mean(),
                                 "halt_months": int(lg["halt"].sum()), "turnover": lg["traded"].mean()})
            print(sig, skip, oname, flush=True)
    res = pd.DataFrame(rows)
    res.to_csv(HERE / "results2.csv", index=False)
    br = pd.Series(breadth)
    info = {"first": str(common[0].date()), "last": str(common[-1].date()), "months": len(common) - 1,
            "breadth_below_30": [str(d.date()) for d, v in br.items() if v < 0.30 and d in common],
            "cash_daily_arb": cd}
    (HERE / "summary2.json").write_text(json.dumps(info, indent=1))
    print(json.dumps(info, indent=1))


if __name__ == "__main__":
    main()
