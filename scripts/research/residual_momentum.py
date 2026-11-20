"""(Owner, 20 Nov 2026; read-only research, TODO S160; docs/MOMENTUM_ABC_2026-11-20.md.)
Residual momentum vs total-return momentum vs the site's composite, Nifty 500 PIT, 2010-2026.

Usage: RESMOM_FF=<iima csv> RESMOM_OUT=<dir> python scripts/research/residual_momentum.py [24|36]

Pass rule fixed BEFORE results (written into the report as-is):
  Residual momentum "holds on our data" only if, on the top-20 book with the live
  strategy's shape (gates + keep-in-top-40, 30 bps), it beats the site's composite
  score's book on Sharpe by >= 0.15 AND has a max drawdown no worse, in 2010-17 AND
  2018-26 separately; and its top-minus-bottom-fifth spread has the higher Sharpe in
  both halves too.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
# Outputs and the IIM Ahmedabad factor file live outside the repository:
#   RESMOM_OUT  a directory for the CSV/JSON tables (default: the current directory)
#   RESMOM_FF   2025-12_FourFactors_and_Market_Returns_Monthly_SurvivorshipBiasAdjusted.csv
#               from https://faculty.iima.ac.in/iffm/Indian-Fama-French-Momentum/
OUT = Path(os.environ.get("RESMOM_OUT", "."))
FF_CSV = Path(os.environ.get("RESMOM_FF", "2025-12_FourFactors_and_Market_Returns_Monthly_SurvivorshipBiasAdjusted.csv"))

from src.engine import index_universe as iu  # noqa: E402
from src.engine.metrics import max_drawdown  # noqa: E402
from src.engine.momentum_health import month_ends, _complete  # noqa: E402
from src.engine.rank_history import snapshots  # noqa: E402
from src.engine.model_record import record_sector_map  # noqa: E402
from src.loaders import nse_long  # noqa: E402

WIN = int(sys.argv[1]) if len(sys.argv) > 1 else 24      # regression window, months
TOPN, BUF, COST = 20, 40, 0.0030


def load():
    close = nse_long.load(with_value=False)[0]
    mem = iu.index_history("nifty_500")
    cols = sorted(iu.ever_members(mem) & set(close.columns))
    close = close[cols].astype("float64")
    ends = month_ends(close)
    if not _complete(ends[-1]):
        ends = ends[:-1]
    return close, mem, pd.DatetimeIndex(ends)


def monthly(close, ends):
    # last traded close on or before each month-end (no look-ahead), ffill <= 1 month
    m = close.ffill(limit=22).reindex(ends)
    return m.pct_change(fill_method=None)


def factors(ends):
    ff = pd.read_csv(FF_CSV, na_values="NA")
    ff["m"] = pd.PeriodIndex(ff["Date"], freq="M")
    ff = ff.set_index("m")[["MF", "SMB", "HML", "RF"]] / 100
    b = pd.read_csv(ROOT / "data/benchmarks.csv", parse_dates=["date"]).set_index("date")["nifty500"]
    bm = b.reindex(b.index.union(ends)).ffill().reindex(ends).pct_change()
    bm.index = bm.index.to_period("M")
    return ff, bm


def residual_scores(R, X, rf, ends, win):
    """{formation date: (res_scaled, res_sum)} -- regress over months m-win+1..m,
    score on residuals of months m-11..m-1 (skip m), Blitz-Huij-Martens."""
    per = R.index.to_period("M")
    out = {}
    for i in range(win, len(ends)):
        wper = per[i - win + 1: i + 1]
        if not set(wper) <= set(X.index):
            continue
        Y = R.iloc[i - win + 1: i + 1]
        ok = Y.notna().all()
        Y = Y.loc[:, ok].to_numpy()
        if Y.shape[1] == 0:
            continue
        x = X.loc[wper].to_numpy()
        r = rf.reindex(wper).fillna(0).to_numpy()[:, None] if rf is not None else 0.0
        Yx = Y - r
        A = np.column_stack([np.ones(len(x)), x])
        beta, *_ = np.linalg.lstsq(A, Yx, rcond=None)
        e = Yx - A @ beta
        e12 = e[-12:-1]                        # m-11 .. m-1
        s = e12.sum(0)
        sd = e12.std(0, ddof=0)
        names = R.columns[ok.to_numpy()]
        out[ends[i]] = (pd.Series(s / np.where(sd > 0, sd, np.nan), index=names),
                        pd.Series(s, index=names),
                        pd.Series(beta[1], index=names))
    return out


def stats(r, rf=None):
    r = pd.Series(r).dropna()
    if len(r) < 12:
        return {}
    ex = r - (rf.reindex(r.index).fillna(rf.dropna().iloc[-1]) if rf is not None else 0)
    eq = (1 + r).cumprod()
    yrs = len(r) / 12
    roll12 = (1 + r).rolling(12).apply(np.prod, raw=True) - 1
    return {"cagr": eq.iloc[-1] ** (1 / yrs) - 1, "vol": r.std(ddof=0) * np.sqrt(12),
            "sharpe": ex.mean() / r.std(ddof=0) * np.sqrt(12),
            "maxdd": max_drawdown(eq), "worst12": roll12.min(), "worst1": r.min(), "n": len(r)}


def book(scores, rets, elig, gated=None, buffer=True):
    """Top-N equal weight, monthly; keep holdings while in top BUF; 30 bps on turnover."""
    held, out = [], {}
    dates = sorted(scores)
    for t0 in dates:
        if t0 not in rets.index:
            continue
        s = scores[t0].reindex(elig[t0]).dropna()
        if gated is not None:
            s = s[s.index.isin(gated.get(t0, set()))]
        s = s.sort_values(ascending=False)
        if len(s) == 0 and gated is None:
            continue
        rank = pd.Series(np.arange(1, len(s) + 1), index=s.index)
        keep = [h for h in held if buffer and rank.get(h, 1e9) <= BUF][:TOPN]
        new = keep + [x for x in s.index if x not in keep][: TOPN - len(keep)]
        turn = len(set(new) - set(held)) / TOPN if held else 1.0
        # fewer than TOPN qualifiers: each name 1/TOPN, the rest cash at 0
        r = rets.loc[t0].reindex(new).fillna(0.0).sum() / TOPN
        turn = len(set(new) ^ set(held)) / (2 * TOPN) if held else len(new) / TOPN
        out[t0] = r - COST * turn * 2          # sell + buy
        held = new
    s = pd.Series(out)
    s.index = pd.DatetimeIndex(s.index).to_period("M") + 1   # month earned
    return s, held


def main():
    close, mem, ends = load()
    R = monthly(close, ends)
    fwd = R.shift(-1)                         # return earned in the month after t0
    fwd.index = ends
    ff, bm = factors(ends)
    first = iu.first_month(mem)
    dates = [d for d in ends[:-1] if pd.Period(d, "M") >= max(first, pd.Period("2009-12", "M"))]

    # Eligible: PIT Nifty 500 members with a price at t0
    snap = snapshots(close, dates, membership=mem)
    elig, gated, comp = {}, {}, {}
    for d, g in snap.groupby("date"):
        g = g[g["in_index"]]
        g = g[close.loc[d].reindex(g["symbol"]).notna().to_numpy()]
        elig[d] = list(g["symbol"])
        gated[d] = set(g.loc[g["qualifies"], "symbol"])
        comp[d] = pd.Series(g["score"].to_numpy(), index=g["symbol"].to_numpy())

    res_capm = residual_scores(R, bm.to_frame("mkt"), None, ends, WIN)
    res_ff3 = residual_scores(R, ff[["MF", "SMB", "HML"]], ff["RF"], ends, WIN)

    tot, tot_sc = {}, {}
    for i, d in enumerate(ends):
        if i < 12:
            continue
        w = R.iloc[i - 11: i]                 # m-11..m-1
        okc = w.notna().all()
        tot[d] = ((1 + w.loc[:, okc]).prod() - 1)
        tot_sc[d] = w.loc[:, okc].mean() / w.loc[:, okc].std(ddof=0)

    sigs = {
        "composite (site)": comp,
        "total 12-1": tot,
        "total 12-1 / vol": tot_sc,
        "residual CAPM (Nifty 500)": {d: v[0] for d, v in res_capm.items()},
        "residual CAPM, unscaled": {d: v[1] for d, v in res_capm.items()},
        "residual FF3 (IIMA)": {d: v[0] for d, v in res_ff3.items()},
    }
    # blend: z(composite) + z(residual CAPM)
    blend = {}
    for d in dates:
        a, b = comp.get(d), sigs["residual CAPM (Nifty 500)"].get(d)
        if a is None or b is None:
            continue
        j = pd.concat([a, b], axis=1).dropna()
        j = (j - j.mean()) / j.std(ddof=0)
        blend[d] = j.mean(axis=1)
    sigs["blend composite + residual"] = blend

    # Common sample: dates and stocks where every signal exists (FF3 stops after Dec 2025 formation)
    common_d = [d for d in dates if all(d in s for k, s in sigs.items() if "FF3" not in k)]
    elig_c = {}
    for d in common_d:
        names = set(elig[d])
        for k, s in sigs.items():
            if "FF3" in k:
                continue
            names &= set(s[d].dropna().index)
        elig_c[d] = sorted(names)

    rf = ff["RF"].copy()
    mkt = bm.copy()
    rows, ls_series, books = [], {}, {}
    for k, s in sigs.items():
        sd = {d: s[d] for d in common_d if d in s}
        # factor level: top/bottom fifth among common names
        ls, top = {}, {}
        for d, sc in sd.items():
            x = sc.reindex(elig_c[d]).dropna().sort_values(ascending=False)
            fr = fwd.loc[d].reindex(x.index)
            x = x[fr.notna()]
            q = max(len(x) // 5, 1)
            ls[pd.Period(d, "M") + 1] = fwd.loc[d, x.index[:q]].mean() - fwd.loc[d, x.index[-q:]].mean()
            top[pd.Period(d, "M") + 1] = fwd.loc[d, x.index[:q]].mean()
        ls, top = pd.Series(ls), pd.Series(top)
        ls_series[k] = ls
        b_plain, _ = book(sd, fwd, elig_c, None, buffer=False)
        b_live, held = book(sd, fwd, elig_c, gated, buffer=True)
        books[k] = b_live
        for label, ser in [("L/S fifths", ls), ("top fifth", top), ("top-20 plain", b_plain), ("top-20 live-shape", b_live)]:
            for per, lo, hi in [("all", "2010-01", "2026-12"), ("2010-17", "2010-01", "2017-12"), ("2018-26", "2018-01", "2026-12")]:
                ss = ser[(ser.index >= pd.Period(lo, "M")) & (ser.index <= pd.Period(hi, "M"))]
                st = stats(ss, rf if label != "L/S fifths" else None)
                if not st:
                    continue
                # crash beta: L/S on market in down vs up months
                m_ = mkt.reindex(ss.index)
                dn, up = m_ < 0, m_ >= 0
                bd = np.polyfit(m_[dn], ss[dn], 1)[0] if dn.sum() > 5 else np.nan
                bu = np.polyfit(m_[up], ss[up], 1)[0] if up.sum() > 5 else np.nan
                rows.append({"signal": k, "test": label, "period": per, **st, "beta_down": bd, "beta_up": bu,
                             "from": str(ss.index.min()), "to": str(ss.index.max())})
        print(k, "done", flush=True)
    res = pd.DataFrame(rows)
    res.to_csv(OUT / f"results_win{WIN}.csv", index=False)
    pd.DataFrame(ls_series).to_csv(OUT / f"ls_win{WIN}.csv")
    pd.DataFrame(books).to_csv(OUT / f"books_win{WIN}.csv")

    # rank correlation composite vs residual, and sector concentration of the plain top-20
    rc = [pd.concat([comp[d], sigs["residual CAPM (Nifty 500)"][d]], axis=1).reindex(elig_c[d]).corr("spearman").iloc[0, 1]
          for d in common_d]
    rc_tot = [pd.concat([tot[d], sigs["residual CAPM (Nifty 500)"][d]], axis=1).reindex(elig_c[d]).corr("spearman").iloc[0, 1]
              for d in common_d]
    sec = record_sector_map(close.columns)
    conc = []
    for k in ["composite (site)", "total 12-1", "residual CAPM (Nifty 500)", "blend composite + residual"]:
        for d in common_d:
            x = sigs[k][d].reindex(elig_c[d]).dropna().sort_values(ascending=False).index[:TOPN]
            labs = pd.Series([sec.get(s, "?") for s in x])
            vc = labs.value_counts()
            conc.append({"signal": k, "date": d, "top_sector": vc.index[0], "top_share": vc.iloc[0] / TOPN,
                         "capgoods": (labs == "Capital Goods").mean(),
                         "beta": res_capm[d][2].reindex(x).mean() if d in res_capm else np.nan})
    conc = pd.DataFrame(conc)
    conc.to_csv(OUT / f"concentration_win{WIN}.csv", index=False)
    summ = {"win": WIN, "months": len(common_d), "first": str(common_d[0].date()), "last": str(common_d[-1].date()),
            "rankcorr_comp_res_median": float(np.nanmedian(rc)), "rankcorr_tot_res_median": float(np.nanmedian(rc_tot)),
            "avg_names": float(np.mean([len(v) for v in elig_c.values()])),
            "sector_labels": pd.Series(sec).value_counts().head(12).to_dict()}
    (OUT / f"summary_win{WIN}.json").write_text(json.dumps(summ, indent=1, default=str))
    print(json.dumps(summ, indent=1, default=str))


if __name__ == "__main__":
    main()
