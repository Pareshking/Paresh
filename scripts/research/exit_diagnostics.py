"""What the book's own history says about exits, before any exit rule is chosen (owner, 28 Nov 2026, S239: "if we
find good exit strategy that may also lift our return as well as reduce DD ... after looking index and back test
monthly returns").

Baseline: the record's rules, Nifty 500 as it stood, Jan 2010 - Nov 2026 (18.81% a year).
  D1  the book's falls from a peak against the Nifty 500 over the same days: market falls, or the book's own?
  D2  every sale, by reason: what the sold stock did over the next 1 and 3 months against the stocks the book kept
  D3  inside a month: once a holding is down 10 / 15 / 20% from its fill (or from its high since the fill), what it
      did for the rest of the month against the book's other holdings over the same days
  D4  kept by the buffer: holdings ranked 21-40 against the top 20 the next month

    python scripts/research/exit_diagnostics.py <nse_long_close.parquet>
"""
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from rs_supertrend import run  # noqa: E402
from src.engine import index_universe as iu  # noqa: E402


def episodes(eq: pd.Series, bench: pd.Series, min_depth: float = -0.15) -> pd.DataFrame:
    peak = eq.cummax()
    dd = eq / peak - 1
    out, in_dd, start = [], False, None
    for d, v in dd.items():
        if not in_dd and v < 0:
            in_dd, start = True, d
        elif in_dd and v == 0:
            seg = dd[start:d]
            out.append((start, seg.idxmin(), d, seg.min()))
            in_dd = False
    if in_dd:
        seg = dd[start:]
        out.append((start, seg.idxmin(), None, seg.min()))
    rows = []
    for s, t, e, depth in out:
        if depth > min_depth:
            continue
        p = eq.index[max(eq.index.get_loc(s) - 1, 0)]
        rows.append({"peak": p.date(), "low": t.date(), "back": e.date() if e is not None else "not yet",
                     "book fall %": depth * 100, "Nifty 500 same days %": (bench[t] / bench[p] - 1) * 100,
                     "book minus index, pts": depth * 100 - (bench[t] / bench[p] - 1) * 100})
    return pd.DataFrame(rows)


def main(close_path: str) -> None:
    pd.set_option("display.width", 200)
    close = pd.read_parquet(close_path)
    close.index = pd.DatetimeIndex(close.index)
    bench = pd.read_csv(ROOT / "data" / "benchmarks.csv", parse_dates=["date"]).set_index("date")["nifty500"]
    cols = sorted(iu.ever_members(iu.index_history("nifty_500")) & set(close.columns))
    pf = close.loc[:, cols].astype("float64").ffill()
    b = bench.reindex(pf.index).ffill()
    res = run(close, bench)
    eq = pd.Series(res["equity_curve"]).dropna()
    eq.index = pd.DatetimeIndex(eq.index)
    tb = res["tradebook"].copy()
    tb["s"] = pd.to_datetime(tb["Period Start"])
    tb["e"] = pd.to_datetime(tb["Period"].str.split("→").str[1].str.strip(), format="%d %b %Y")
    dates = pf.index

    print("D1. FALLS OF 15% OR MORE: the book against the Nifty 500 over the same days")
    print(episodes(eq, b).round(1).to_string(index=False))
    m = eq.resample("ME").last().pct_change().dropna() * 100
    bm = b.resample("ME").last().pct_change().reindex(m.index) * 100
    worst = pd.DataFrame({"book %": m, "Nifty 500 %": bm, "gap": m - bm}).sort_values("book %").head(12)
    print("\n  the 12 worst months:")
    print(worst.round(1).to_string())
    print(f"  months the book fell more than 5%: {int((m < -5).sum())}; in them the index fell more than 5% in "
          f"{int(((m < -5) & (bm < -5)).sum())}")
    up = bm > 0
    print(f"  capture: index up months, book {m[up].mean():+.2f}% vs index {bm[up].mean():+.2f}%; "
          f"index down months, book {m[~up].mean():+.2f}% vs index {bm[~up].mean():+.2f}%")

    print("\nD2. EVERY SALE, BY REASON: the sold stock over the next 1 and 3 months minus the kept holdings' average")
    held = tb[tb["Action"].str.contains("BUY|HOLD")]
    sells = tb[tb["Action"].str.contains("SELL")]
    rows = []
    for _, r in sells.iterrows():
        if r["Symbol"] not in pf.columns:
            continue
        i = dates.get_loc(r["s"])
        keep = [x for x in held.loc[held["s"] == r["s"], "Symbol"] if x in pf.columns]
        rec = {"reason": re.sub(r"\s*\(.*", "", str(r["Reason / Signal"])).strip()}
        for n, k in (("1M", 21), ("3M", 63)):
            if i + k >= len(dates):
                rec[n] = np.nan
                continue
            sold = pf[r["Symbol"]].iloc[i + k] / pf[r["Symbol"]].iloc[i] - 1
            kept = (pf[keep].iloc[i + k] / pf[keep].iloc[i] - 1).mean() if keep else np.nan
            rec[n] = (sold - kept) * 100
        rows.append(rec)
    d2 = pd.DataFrame(rows)
    g = d2.groupby("reason").agg(sales=("1M", "size"), **{"1M mean": ("1M", "mean"), "1M median": ("1M", "median"),
                                                          "3M mean": ("3M", "mean"), "3M median": ("3M", "median")})
    g.loc["ALL"] = [len(d2), d2["1M"].mean(), d2["1M"].median(), d2["3M"].mean(), d2["3M"].median()]
    print("  (negative = the sale was right: the sold stock did worse than what the book kept)")
    print(g.round(2).to_string())

    print("\nD3. INSIDE THE MONTH: after a holding first falls X% from its fill (or from its high since), the rest of the")
    print("    month for that stock minus the book's other holdings over the same days, pts")
    hb = held.copy()
    rows = []
    for (s, e), grp in hb.groupby(["s", "e"]):
        i, j = dates.get_loc(s), dates.get_loc(e)
        syms = [x for x in grp["Symbol"] if x in pf.columns]
        if j - i < 3 or not syms:
            continue
        px = pf[syms].iloc[i:j + 1].to_numpy()
        rel = px / px[0]
        trail = px / np.maximum.accumulate(px, axis=0)
        for kind, path in (("from fill", rel - 1), ("from high since fill", trail - 1)):
            for thr in (-0.10, -0.15, -0.20):
                for k, _sym in enumerate(syms):
                    hit = np.where(path[:, k] <= thr)[0]
                    hit = hit[hit < len(rel) - 1]
                    if not len(hit):
                        continue
                    t = hit[0]
                    rest = px[-1, k] / px[t, k] - 1
                    others = np.delete(px[-1] / px[t] - 1, k)
                    rows.append({"kind": kind, "threshold": f"{int(thr * 100)}%", "rest": rest * 100,
                                 "vs others": (rest - np.nanmean(others)) * 100, "days left": len(rel) - 1 - t})
    d3 = pd.DataFrame(rows)
    out = d3.groupby(["kind", "threshold"]).agg(cases=("rest", "size"), **{"rest mean %": ("rest", "mean"),
                                                                           "rest median %": ("rest", "median"),
                                                                           "vs others mean": ("vs others", "mean"),
                                                                           "vs others median": ("vs others", "median"),
                                                                           "days left": ("days left", "median")})
    out["rose %"] = d3.groupby(["kind", "threshold"])["rest"].apply(lambda x: (x > 0).mean() * 100)
    out["holding-months"] = len(hb)
    print(out.round(2).to_string())

    print("\nD4. THE BUFFER: holdings kept at rank 21-40 against those ranked 1-20, the month after")
    rows = []
    for (s, e), grp in hb.groupby(["s", "e"]):
        i, j = dates.get_loc(s), dates.get_loc(e)
        for _, r in grp.iterrows():
            mm = re.search(r"#(\d+)", str(r["Reason / Signal"]))
            if not mm or r["Symbol"] not in pf.columns:
                continue
            rows.append({"rank": int(mm.group(1)), "ret": (pf[r["Symbol"]].iloc[j] / pf[r["Symbol"]].iloc[i] - 1) * 100,
                         "s": s})
    d4 = pd.DataFrame(rows)
    d4["band"] = np.where(d4["rank"] <= 20, "rank 1-20", "rank 21-40")
    per = d4.groupby(["s", "band"])["ret"].mean().unstack().dropna()
    diff = per["rank 21-40"] - per["rank 1-20"]
    print(f"  months with both: {len(per)}; rank 21-40 minus rank 1-20: mean {diff.mean():+.2f} pts a month, "
          f"median {diff.median():+.2f}, t {diff.mean() / (diff.std(ddof=0) / np.sqrt(len(diff))):+.2f}; holdings "
          f"{(d4['band'] == 'rank 21-40').sum()} of {len(d4)} at rank 21-40")


if __name__ == "__main__":
    main(sys.argv[1])
