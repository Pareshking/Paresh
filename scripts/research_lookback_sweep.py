#!/usr/bin/env python3
"""Offline search over the score's five lookback weights (1, 3, 6, 9, 12 months).

Heavy: one full History-from-2010 backtest per combination, so it runs on a
laptop, not on Streamlit Cloud. Two steps:

    python scripts/research_lookback_sweep.py run --out DIR [--workers 4] [--index nifty_500]
    python scripts/research_lookback_sweep.py report --out DIR

`run` backtests every weight mix on a 0.25 grid (70 mixes: every way to give
four quarters to five windows) plus the live weights and equal weights, with
every other setting at the live system's values. Each run's daily net returns
and its stats are written under DIR/runs, so a stopped run resumes, and
`report` needs no backtest.

`report` does not crown the best row. Trying 72 mixes and keeping the top one
is a search, and the top of any search looks good by luck. It measures how much
the search can be trusted, with tests that need nothing but the saved returns:

  * paired bootstrap of each mix's Sharpe minus the live weights' Sharpe (the
    same days, so the difference is measured far more tightly than either);
  * the probability of backtest overfitting (combinatorially symmetric
    cross-validation: how often the in-sample winner lands in the bottom half
    out of sample);
  * a deflated Sharpe ratio for the winner, allowing for the number of mixes tried;
  * a walk-forward test of the search itself: each year, pick the best mix on
    the years before and hold it for that year, against keeping the live weights;
  * how the result changes across sub-periods and with each window's weight.

Prices, membership, industries and benchmark are those of the Backtest page's
History tab (src/ui/views/backtest_view.py, _history_inputs).
"""

from __future__ import annotations

import argparse
import inspect
import itertools
import json
import logging
import math
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

WINDOWS = (1, 3, 6, 9, 12)
LIVE_WEIGHTS = (0.10, 0.30, 0.30, 0.20, 0.10)

# The live system's settings (Backtest page defaults); only the weights vary.
LIVE = dict(
    top_n=20, rebal_freq=21, ema_period=50, high_pct=0.80, weight_method="Equal Weight",
    stock_cap=0.05, sector_cap=0.40, cost_bps=30.0, buffer_n=40, score_method="sharpe",
)


def grid() -> list[tuple[float, ...]]:
    """Every split of four quarters over five windows, then live and equal weights."""
    mixes = [tuple(q / 4 for q in c) for c in itertools.product(range(5), repeat=5) if sum(c) == 4]
    return sorted(set(mixes)) + [LIVE_WEIGHTS, (0.2,) * 5]


def key(weights: tuple[float, ...]) -> str:
    return "w_" + "_".join(f"{w:.2f}" for w in weights)


def label(weights: tuple[float, ...]) -> str:
    return " / ".join(f"{w:.0%}" for w in weights)


# ── inputs, exactly as the History tab builds them ───────────────────────────
def history_inputs(index_key: str) -> dict:
    from src.core.config import DEFAULT_SECTOR_CAP, DEFAULT_STOCK_CAP
    from src.engine import index_universe as iu
    from src.loaders import former_members, nse_long
    from src.loaders.price_loader import fetch_benchmark_history

    loaded = nse_long.load(with_value=False)
    if loaded is None:
        raise SystemExit("The long NSE price file is not available.")
    close, _value, report = loaded
    membership = iu.index_history(index_key)
    if membership is None:
        raise SystemExit(f"No membership history for {index_key}.")
    first = max(iu.first_month(membership), pd.Period(close.index[0], freq="M") + 13)
    last = pd.Period(close.index[-1], freq="M") - 1
    after = close.index[close.index >= (last + 1).start_time]
    cut = after[0] if len(after) else close.index[-1]
    cols = sorted(iu.ever_members(membership) & set(close.columns))
    frame = close.loc[:cut, cols]

    # The page starts from the live ranking's Industry, which is the index file's.
    idx = pd.read_csv(former_members.INDEX_FILE)
    idx.columns = [str(c).strip() for c in idx.columns]
    sec = dict(zip(idx["Symbol"], idx["Industry"]))
    sec.update(former_members.industry_for([c for c in cols if c not in sec]))
    past_file = ROOT / "data" / "reference" / "historical_industries.csv"
    past = dict(pd.read_csv(past_file)[["NSE_SYMBOL", "SECTOR"]].itertuples(index=False)) \
        if past_file.exists() else {}
    sec.update({c: past[c] for c in cols if sec.get(c, "Other") == "Other" and c in past})
    sec.update({c: f"Unlabelled · {c}" for c in cols if sec.get(c, "Other") == "Other"})

    symbol = "^NSEI" if index_key == "nifty_50" else "^CRSLDX"
    bench = fetch_benchmark_history(period="max", symbol=symbol)
    assert abs(DEFAULT_STOCK_CAP - LIVE["stock_cap"]) < 1e-9 and abs(DEFAULT_SECTOR_CAP - LIVE["sector_cap"]) < 1e-9
    return {
        "close": frame, "membership": membership, "sector_map": sec, "benchmark": bench,
        "start": first, "end": last, "months": (last - first).n + 1,
        "built": report.get("built"), "last_session": report.get("last_session"),
        "index": iu.INDICES[index_key],
    }


_INPUTS: dict | None = None


def _init_worker(index_key: str) -> None:
    global _INPUTS
    logging.disable(logging.WARNING)
    _INPUTS = history_inputs(index_key)


def _run_one(weights: tuple[float, ...], out: str) -> tuple[str, float]:
    from src.engine.backtester import run_backtest

    t0 = time.perf_counter()
    inp = _INPUTS
    raw = inspect.unwrap(run_backtest)  # no Streamlit cache: memory stays flat
    res = raw(
        f"research-{key(weights)}", inp["close"], _benchmark_close=inp["benchmark"],
        config_weights=weights, sector_map=inp["sector_map"], _membership=inp["membership"],
        backtest_months=inp["months"], stateful_history=True,
        history_start=inp["start"].start_time, _actions=[], **LIVE,
    )
    if not res or not res.get("stats"):
        raise RuntimeError(f"{label(weights)}: no result")
    eq = res["equity_curve"]
    daily = eq.pct_change().iloc[1:].rename("net")
    runs = Path(out) / "runs"
    daily.to_frame().to_parquet(runs / f"{key(weights)}.parquet")
    bench_path = Path(out) / "benchmark_daily.parquet"
    if res.get("benchmark") is not None and not bench_path.exists():
        bench = res["benchmark"].reindex(eq.index).ffill().pct_change().iloc[1:]
        bench.rename("bench").to_frame().to_parquet(bench_path)
    stats = {k: (float(v) if isinstance(v, (int, float, np.floating, np.integer)) else str(v))
             for k, v in res["stats"].items() if not isinstance(v, (list, dict))}
    (runs / f"{key(weights)}.json").write_text(json.dumps({"weights": weights, "stats": stats}))
    return key(weights), time.perf_counter() - t0


def cmd_run(args: argparse.Namespace) -> None:
    out = Path(args.out)
    (out / "runs").mkdir(parents=True, exist_ok=True)
    mixes = ([tuple(float(x) for x in m.split(",")) for m in args.mixes.split(";")]
             if args.mixes else grid())
    todo = [w for w in mixes if not (out / "runs" / f"{key(w)}.json").exists()]
    if args.limit:
        todo = todo[: args.limit]
    meta = history_inputs(args.index)
    (out / "meta.json").write_text(json.dumps({
        "index": meta["index"], "start": str(meta["start"]), "end": str(meta["end"]),
        "months": meta["months"], "built": meta["built"], "last_session": meta["last_session"],
        "settings": LIVE, "live_weights": LIVE_WEIGHTS, "combinations": len(mixes),
    }, indent=2))
    del meta
    print(f"{len(mixes)} mixes, {len(todo)} to run, {args.workers} workers", flush=True)
    t0 = time.perf_counter()
    with ProcessPoolExecutor(args.workers, initializer=_init_worker, initargs=(args.index,)) as pool:
        futures = {pool.submit(_run_one, w, str(out)): w for w in todo}
        for i, fut in enumerate(as_completed(futures), 1):
            w = futures[fut]
            try:
                _, secs = fut.result()
                print(f"[{i}/{len(todo)}] {label(w)} in {secs:.0f}s "
                      f"(elapsed {(time.perf_counter() - t0) / 60:.1f} min)", flush=True)
            except Exception as exc:  # noqa: BLE001 - report and carry on
                print(f"[{i}/{len(todo)}] {label(w)} FAILED: {type(exc).__name__}: {exc}", flush=True)


# ── report ───────────────────────────────────────────────────────────────────
TRADING_DAYS = 252


def load_runs(out: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series, dict]:
    stats, cols = [], {}
    for js in sorted((out / "runs").glob("*.json")):
        rec = json.loads(js.read_text())
        w = tuple(rec["weights"])
        cols[label(w)] = pd.read_parquet(js.with_suffix(".parquet"))["net"]
        stats.append({"mix": label(w), **{f"w{m}": x for m, x in zip(WINDOWS, w)}, **rec["stats"]})
    returns = pd.DataFrame(cols).dropna()
    bench = pd.read_parquet(out / "benchmark_daily.parquet")["bench"].reindex(returns.index)
    meta = json.loads((out / "meta.json").read_text())
    return returns, pd.DataFrame(stats).set_index("mix"), bench, meta


def sharpe(r: np.ndarray | pd.DataFrame, rf: float) -> np.ndarray:
    """The page's Sharpe: annualised mean daily return less rf, over annualised volatility."""
    r = np.asarray(r)
    return (r.mean(axis=0) * TRADING_DAYS - rf) / (r.std(axis=0, ddof=1) * math.sqrt(TRADING_DAYS))


def paired_bootstrap(r: pd.DataFrame, base: str, rf: float, n: int = 2000, block: int = 63,
                     seed: int = 7) -> pd.DataFrame:
    """Each mix's Sharpe minus the base's, resampling whole 63-session blocks of days."""
    x = r.to_numpy()
    t = len(x)
    rng = np.random.default_rng(seed)
    b = list(r.columns).index(base)
    diffs = np.empty((n, x.shape[1]))
    starts_per = math.ceil(t / block)
    for i in range(n):
        starts = rng.integers(0, t - block, starts_per)
        idx = (starts[:, None] + np.arange(block)).ravel()[:t]
        s = sharpe(x[idx], rf)
        diffs[i] = s - s[b]
    obs = sharpe(x, rf)
    return pd.DataFrame({
        "dSharpe": obs - obs[b],
        "lo90": np.percentile(diffs, 5, axis=0),
        "hi90": np.percentile(diffs, 95, axis=0),
        "p_better": (diffs > 0).mean(axis=0),
    }, index=r.columns)


def pbo_cscv(r: pd.DataFrame, rf: float, blocks: int = 16) -> tuple[float, np.ndarray]:
    """Probability of backtest overfitting by combinatorially symmetric cross-validation."""
    x = r.to_numpy()
    t = (len(x) // blocks) * blocks
    parts = np.array_split(x[-t:], blocks)
    s1 = np.stack([p.sum(axis=0) for p in parts])
    s2 = np.stack([(p ** 2).sum(axis=0) for p in parts])
    m = np.array([len(p) for p in parts])
    n_mix = x.shape[1]
    lambdas = []
    for ins in itertools.combinations(range(blocks), blocks // 2):
        mask = np.zeros(blocks, bool)
        mask[list(ins)] = True

        def sr(sel):
            k = m[sel].sum()
            mean = s1[sel].sum(axis=0) / k
            var = (s2[sel].sum(axis=0) - k * mean ** 2) / (k - 1)
            return (mean * TRADING_DAYS - rf) / np.sqrt(var * TRADING_DAYS)

        best = int(np.argmax(sr(mask)))
        oos = sr(~mask)
        rank = (oos < oos[best]).sum() + 1          # 1 = worst ... n = best
        w = rank / (n_mix + 1)
        lambdas.append(math.log(w / (1 - w)))
    lam = np.array(lambdas)
    return float((lam <= 0).mean()), lam


def deflated_sharpe(r: pd.DataFrame, best: str) -> dict:
    """Bailey and Lopez de Prado's deflated Sharpe ratio, per-day figures, N = mixes tried."""
    from statistics import NormalDist

    nd = NormalDist()
    x = r.to_numpy()
    srs = x.mean(axis=0) / x.std(axis=0, ddof=1)           # per-day, rf ignored as in the paper
    n = x.shape[1]
    gamma = 0.5772156649
    sr0 = math.sqrt(srs.var(ddof=1)) * ((1 - gamma) * nd.inv_cdf(1 - 1 / n)
                                        + gamma * nd.inv_cdf(1 - 1 / (n * math.e)))
    y = r[best].to_numpy()
    sr = y.mean() / y.std(ddof=1)
    skew = float(pd.Series(y).skew())
    kurt = float(pd.Series(y).kurt()) + 3.0
    z = (sr - sr0) * math.sqrt(len(y) - 1) / math.sqrt(1 - skew * sr + (kurt - 1) / 4 * sr ** 2)
    return {"sr_day": sr, "sr0_day": sr0, "dsr": nd.cdf(z), "n": n}


def walk_forward(r: pd.DataFrame, base: str, rf: float, first_test_year: int) -> tuple[pd.DataFrame, pd.Series]:
    """Each calendar year, hold the mix with the best Sharpe on every earlier day."""
    rows, chained = [], []
    for year in range(first_test_year, r.index[-1].year + 1):
        past = r[r.index < pd.Timestamp(f"{year}-01-01")]
        now = r[(r.index >= pd.Timestamp(f"{year}-01-01")) & (r.index < pd.Timestamp(f"{year + 1}-01-01"))]
        if len(past) < TRADING_DAYS * 2 or now.empty:
            continue
        s = pd.Series(sharpe(past, rf), index=r.columns)
        pick = s.idxmax()
        chained.append(now[pick])
        rows.append({"year": year, "picked": pick,
                     "picked return": float((1 + now[pick]).prod() - 1),
                     "live return": float((1 + now[base]).prod() - 1)})
    return pd.DataFrame(rows), pd.concat(chained)


def neighbours(weights: pd.DataFrame) -> dict[str, list[str]]:
    """Mixes one step apart: a quarter moved from one window to another."""
    w = (weights * 4).round().astype(int)
    grid_rows = {tuple(v): k for k, v in zip(w.index, w.to_numpy()) if abs(sum(v) - 4) < 1e-9}
    out = {}
    for quarters, name in grid_rows.items():
        near = []
        for i, j in itertools.permutations(range(5), 2):
            if quarters[i] > 0:
                u = list(quarters)
                u[i] -= 1
                u[j] += 1
                if tuple(u) in grid_rows:
                    near.append(grid_rows[tuple(u)])
        out[name] = near
    return out


def cmd_report(args: argparse.Namespace) -> None:
    out = Path(args.out)
    r, st, bench, meta = load_runs(out)
    rf = float(st["risk_free_rate"].iloc[0])
    base = label(LIVE_WEIGHTS)
    if base not in r.columns:
        raise SystemExit("The live weights' run is missing; run `run` first.")
    on_grid = [c for c in r.columns if c not in (base, label((0.2,) * 5))]

    table = st[["sharpe", "ann_return", "total_return", "alpha", "max_drawdown", "calmar",
                "avg_turnover", "beat_rate"]].copy()
    table["sharpe (check)"] = sharpe(r[table.index], rf)
    boot = paired_bootstrap(r, base, rf)
    table = table.join(boot)
    near = neighbours(st[[f"w{m}" for m in WINDOWS]])
    table["neighbour sharpe"] = [np.mean([table.loc[n, "sharpe"] for n in near.get(k, [])])
                                 if near.get(k) else np.nan for k in table.index]
    subs = [("2010-2015", None, "2016-01-01"), ("2016-2020", "2016-01-01", "2021-01-01"),
            ("2021-2026", "2021-01-01", None)]
    for name, a, b in subs:
        keep = np.ones(len(r), bool)
        if a:
            keep &= r.index >= pd.Timestamp(a)
        if b:
            keep &= r.index < pd.Timestamp(b)
        table[f"sharpe {name}"] = sharpe(r.loc[keep, table.index], rf)
    table = table.sort_values("sharpe", ascending=False)
    table.to_csv(out / "results.csv")

    grid_r = r[on_grid]
    pbo, lam = pbo_cscv(grid_r, rf)
    best = table.loc[on_grid, "sharpe"].idxmax()
    dsr = deflated_sharpe(grid_r, best)
    wf, wf_r = walk_forward(r, base, rf, args.first_test_year)
    wf_days = wf_r.index
    wf_sharpe = float(sharpe(wf_r.to_frame(), rf)[0])
    live_same = float(sharpe(r.loc[wf_days, [base]], rf)[0])
    equal_same = float(sharpe(r.loc[wf_days, [label((0.2,) * 5)]], rf)[0])
    wf_boot = paired_bootstrap(
        pd.concat([wf_r.rename("search"), r.loc[wf_days, base].rename("live")], axis=1), "live", rf
    ).loc["search"]

    # Does the ranking persist? Spearman's rho of the grid's Sharpe, first half against second.
    mid = r.index[len(r) // 2]
    first_half = pd.Series(sharpe(grid_r[grid_r.index < mid], rf), index=on_grid)
    second_half = pd.Series(sharpe(grid_r[grid_r.index >= mid], rf), index=on_grid)
    rho = float(first_half.rank().corr(second_half.rank()))
    top10_first = set(first_half.nlargest(10).index)
    top10_kept = len(top10_first & set(second_half.nlargest(10).index))

    by_window = {}
    for m in WINDOWS:
        g = table.loc[on_grid].groupby(st.loc[on_grid, f"w{m}"])["sharpe"].mean()
        by_window[f"{m}M"] = {f"{k:.0%}": round(float(v), 3) for k, v in g.items()}

    summary = {
        "meta": meta, "risk_free": rf, "days": len(r), "mixes": len(r.columns),
        "best_on_grid": best, "best_sharpe": float(table.loc[best, "sharpe"]),
        "live_sharpe": float(table.loc[base, "sharpe"]),
        "pbo": pbo, "pbo_splits": len(lam), "deflated_sharpe": dsr,
        "walk_forward": {"first_year": int(wf["year"].min()), "days": len(wf_days),
                         "search_sharpe": wf_sharpe, "live_sharpe_same_days": live_same,
                         "equal_sharpe_same_days": equal_same,
                         "search_minus_live": float(wf_boot["dSharpe"]),
                         "search_minus_live_lo90": float(wf_boot["lo90"]),
                         "search_minus_live_hi90": float(wf_boot["hi90"]),
                         "search_better_share": float(wf_boot["p_better"]),
                         "years": wf.to_dict(orient="records")},
        "halves": {"split": str(mid.date()), "spearman_rho": rho, "top10_kept": top10_kept},
        "mean_sharpe_by_window_weight": by_window,
        "sharpe_spread": {"min": float(table["sharpe"].min()), "median": float(table["sharpe"].median()),
                          "max": float(table["sharpe"].max())},
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2, default=str))
    pd.set_option("display.width", 220)
    cols = ["sharpe", "dSharpe", "lo90", "hi90", "p_better", "neighbour sharpe", "ann_return",
            "max_drawdown", "avg_turnover", "sharpe 2010-2015", "sharpe 2016-2020", "sharpe 2021-2026"]
    print(table[cols].head(15).round(3).to_string())
    print("...")
    print(table.loc[[base], cols].round(3).to_string())
    print(json.dumps({k: v for k, v in summary.items() if k != "meta"}, indent=2, default=str))


def cmd_compare(args: argparse.Namespace) -> None:
    """A few chosen mixes on other indexes: each against the live weights, same days."""
    rows = []
    for d in args.out:
        r, st, _bench, meta = load_runs(Path(d))
        rf = float(st["risk_free_rate"].iloc[0])
        base = label(LIVE_WEIGHTS)
        boot = paired_bootstrap(r, base, rf)
        for mix in r.columns:
            rows.append({
                "index": meta["index"], "from": meta["start"], "mix": mix,
                "sharpe": float(st.loc[mix, "sharpe"]), "dSharpe": boot.loc[mix, "dSharpe"],
                "lo90": boot.loc[mix, "lo90"], "hi90": boot.loc[mix, "hi90"],
                "ann_return": float(st.loc[mix, "ann_return"]),
                "max_drawdown": float(st.loc[mix, "max_drawdown"]),
                "turnover": float(st.loc[mix, "avg_turnover"]),
            })
    table = pd.DataFrame(rows)
    pd.set_option("display.width", 220)
    print(table.round(3).to_string(index=False))
    if args.csv:
        table.to_csv(args.csv, index=False)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    pr = sub.add_parser("run")
    pr.add_argument("--out", required=True)
    pr.add_argument("--workers", type=int, default=4)
    pr.add_argument("--index", default="nifty_500")
    pr.add_argument("--limit", type=int, default=0, help="run only this many (for a timing test)")
    pr.add_argument("--mixes", default="", help='only these, e.g. "0,0.25,0.5,0.25,0;0.1,0.3,0.3,0.2,0.1"')
    pr.set_defaults(func=cmd_run)
    rp = sub.add_parser("report")
    rp.add_argument("--out", required=True)
    rp.add_argument("--first-test-year", type=int, default=2014)
    rp.set_defaults(func=cmd_report)
    cp = sub.add_parser("compare")
    cp.add_argument("--out", nargs="+", required=True)
    cp.add_argument("--csv", default="")
    cp.set_defaults(func=cmd_compare)
    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
