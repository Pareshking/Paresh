"""Is the loose-exit result real, or a bug? Two checks that do not reuse the engine's selection code (owner,
28 Nov 2026: "hope your code is correct else output will mislead").

1. AUDIT: every buy, keep and sell the engine logged in the "exit 200D EMA + keep in top 90" run and in the baseline,
   checked against the rule recomputed here from the raw closes at the signal close (the session before the fill):
   a new buy must be above its 50D EMA, within 20% of its 52-week high and ranked within 20; a kept name above its
   exit EMA, within 20% of the high and ranked within the keep band; a "Trend Breakdown" sale below its exit EMA.
2. SECOND IMPLEMENTATION: a book written here from scratch (scores from `rank_history.snapshots`, the app's rank
   history, not the backtester; gates computed here; equal weight, no industry cap, 30 bps on rupees traded,
   bought at the next close). Runs: today's exits, exit EMA 200 alone, keep in top 90 alone, both. The levels
   will differ from the engine (no cap, its own rounding); the question is whether the same pattern appears.

    python scripts/research/verify_exit.py <nse_long_close.parquet>
"""
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from rs_supertrend import run, stats  # noqa: E402
from src.engine import index_universe as iu  # noqa: E402
from src.engine.membership import members_on  # noqa: E402
from src.engine.rank_history import snapshots  # noqa: E402

TOPN, COST = 20, 0.003


def gates(px: pd.DataFrame):
    hi = px.rolling("365D", min_periods=126).max()
    return {50: px.ewm(span=50).mean(), 200: px.ewm(span=200).mean()}, hi


def audit(close, bench, px, label, exit_ema, keep_band, **kw):
    res = run(close, bench, **kw)
    tb = res["tradebook"].copy()
    ema, hi = gates(px)
    dates = px.index
    bad, n = [], 0
    for _, r in tb.iterrows():
        s = r["Symbol"]
        if s not in px.columns:
            continue
        f = dates.get_loc(pd.Timestamp(r["Period Start"]))
        d = dates[f - 1]                                   # the signal close
        p = px.at[d, s]
        act, why = str(r["Action"]), str(r["Reason / Signal"])
        rk = re.search(r"#(\d+)", why)
        rk = int(rk.group(1)) if rk else None
        near = p >= 0.8 * hi.at[d, s]
        n += 1
        if "BUY" in act:
            ok = p > ema[50].at[d, s] and near and (rk is None or rk <= TOPN)
        elif "HOLD" in act:
            ok = p > ema[exit_ema].at[d, s] and near and (rk is None or rk <= keep_band)
        elif "Trend Breakdown" in why:
            ok = not (p > ema[exit_ema].at[d, s])
        elif "Rank Dropped" in why:
            ok = rk is None or rk > keep_band
        else:
            ok = True
        if not ok:
            bad.append((d.date(), s, act, why, round(p, 2), round(ema[exit_ema].at[d, s], 2), round(hi.at[d, s], 2)))
    print(f"  {label}: {n} logged decisions checked, {len(bad)} disagree with the rule recomputed from raw closes")
    for b in bad[:8]:
        print("    ", b)
    return res


def own_book(px, score, members, sig, exit_ema, keep_band):
    ema, hi = gates(px)
    dates = px.index
    held, nav, path = [], 1.0, []
    w_prev: dict[str, float] = {}
    for a, b in zip(sig[:-1], sig[1:], strict=True):
        i, j = dates.get_loc(a), dates.get_loc(b)
        if j + 1 >= len(dates):
            break
        sc = score.get(a)
        if sc is None:
            continue
        p = px.loc[a]
        mem = members[a]
        near = p >= 0.8 * hi.loc[a]
        enter = (p > ema[50].loc[a]) & near & p.index.isin(mem)
        keep = (p > ema[exit_ema].loc[a]) & near & p.index.isin(mem) & p.index.isin(held)
        pool = sc[sc.index.isin(p.index[enter | keep])].dropna().sort_values(ascending=False)
        rank = pd.Series(np.arange(1, len(pool) + 1), index=pool.index)
        kept = [h for h in held if rank.get(h, 1e9) <= keep_band][:TOPN]
        new = kept + [x for x in pool.index if x not in kept][: TOPN - len(kept)]
        tgt = {x: 1 / TOPN for x in new}
        traded = sum(abs(tgt.get(k, 0) - w_prev.get(k, 0)) for k in set(tgt) | set(w_prev))
        nav *= 1 - COST * traded
        seg = px.iloc[i + 1:j + 2][new].to_numpy()        # bought at the next close, held to the next fill
        rel = pd.DataFrame(seg / seg[0]).ffill().fillna(1.0).to_numpy() if new else np.ones((j - i + 1, 0))
        port = rel.sum(1) / TOPN + (1 - len(new) / TOPN)
        for k in range(1, len(port)):
            path.append((dates[i + 1 + k], nav * port[k]))
        nav *= port[-1]
        w_prev = {x: rel[-1, c] / TOPN / port[-1] for c, x in enumerate(new)}
        held = new
    return pd.Series(dict(path))


def main(close_path: str) -> None:
    close = pd.read_parquet(close_path)
    close.index = pd.DatetimeIndex(close.index)
    bench = pd.read_csv(ROOT / "data" / "benchmarks.csv", parse_dates=["date"]).set_index("date")["nifty500"]
    membership = iu.index_history("nifty_500")
    cols = sorted(iu.ever_members(membership) & set(close.columns))
    raw = close.loc[:, cols].astype("float64")
    print("1. AUDIT OF THE ENGINE'S LOGGED DECISIONS")
    audit(close, bench, raw, "baseline (exit 50D EMA, keep in top 40)", 50, 40)
    audit(close, bench, raw, "exit 200D EMA + keep in top 90", 200, 90, exit_ema_period=200, buffer_n=90)

    print("\n2. SECOND IMPLEMENTATION (no industry cap; scores from rank_history.snapshots)")
    dates = raw.index
    ml = pd.DatetimeIndex(pd.Series(dates, index=dates).groupby([dates.year, dates.month]).max().to_numpy())
    sig = [d for d in ml if pd.Timestamp("2009-12-01") <= d]
    snap = snapshots(raw, sig, membership=membership)
    score = {d: pd.Series(g["score"].to_numpy(), index=g["symbol"].to_numpy()) for d, g in snap.groupby("date")}
    members = {d: set(members_on(membership, d)) for d in sig}
    px = raw.ffill(limit=22)
    out = {}
    for label, e, k in (("today's exits (50D, top 40)", 50, 40), ("exit 200D EMA alone", 200, 40),
                        ("keep in top 90 alone", 50, 90), ("both", 200, 90)):
        eq = own_book(px, score, members, sig, e, k)
        eq = eq[eq.index >= "2010-01-01"]
        out[label] = stats(eq / eq.iloc[0])
        x = out[label]
        print(f"  {label:30s} {x['a year %']:.2f}% a year (2010-17 {x['2010-17 %']:.2f}, 2018-26 {x['2018-26 %']:.2f}); "
              f"worst {x['worst fall %']:.1f}%", flush=True)
    b = out["today's exits (50D, top 40)"]
    for label, x in out.items():
        if label.startswith("today"):
            continue
        print(f"  {label:30s} vs today's exits: {x['a year %'] - b['a year %']:+.2f} pts a year "
              f"(2010-17 {x['2010-17 %'] - b['2010-17 %']:+.2f}, 2018-26 {x['2018-26 %'] - b['2018-26 %']:+.2f})")


if __name__ == "__main__":
    main(sys.argv[1])
