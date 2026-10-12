#!/usr/bin/env python3
"""Which settings work best in which market conditions? (owner, 12 Oct 2026)

Heavy: one History-from-2010 backtest per combination, about 2 hours on 4
workers for the full grid, so it runs on a laptop. Two steps:

    python scripts/research_regime_sweep.py run --out DIR [--workers 4]
    python scripts/research_regime_sweep.py report --out DIR

`run` backtests every combination of six settings on the Backtest page's
History tab (Nifty 500, point in time, Jan 2010 on):

    lookback weights   6 mixes (live, short, mid, long, equal, 12M alone)
    holdings           10, 20, 30
    keep while ranked  1x, 2x, 3x the holdings
    EMA filter         20, 50, 100, 200 sessions
    52-week-high rule  within 10%, 20%, 30%, 50%
    score              Sharpe (live) or plain return

1,728 runs. The stock cap is the live 5%, raised to 1/holdings where 5% could
not fill the book (10 holdings: 10%), so a 10-stock book is not half cash.
Each run's daily net returns are saved, so a stopped run resumes.

`report` labels every month by the market it began in, from what was known at
its signal (the last close before the month): trend (Nifty 500 above or below
its 200-day average, the header's regime), volatility (63-session volatility
above or below its median over the five years before) and breadth (share of the index's stocks
above their 50-day EMA, above or below half). Then, in order of how far each
can be trusted:

  1. Within each condition, which settings did best, and do the two halves of
     the history agree (Spearman rho of the settings' Sharpe)?
  2. Which way each setting leans in each condition: the average Sharpe of
     every combination with that value.
  3. Walk-forward, the only test of picking by condition: each year from 2014,
     learn "best combination per condition" from the years before, apply it
     month by month that year. Against the live settings and against the best
     single combination learned the same way, with block-bootstrap ranges.

Chaining months from different runs ignores the trades a switch would cause
and the holdings each run carries, so a switching rule that wins here still
needs a backtest that switches before it is believed.
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

from scripts.research_lookback_sweep import (  # noqa: E402
    LIVE,
    LIVE_WEIGHTS,
    TRADING_DAYS,
    deflated_sharpe,
    history_inputs,
    paired_bootstrap,
    pbo_cscv,
    sharpe,
)

WEIGHTS: dict[str, tuple[float, ...]] = {
    "live": LIVE_WEIGHTS,
    "short": (0.30, 0.40, 0.20, 0.10, 0.00),
    "mid": (0.00, 0.25, 0.50, 0.25, 0.00),
    "long": (0.00, 0.00, 0.30, 0.30, 0.40),
    "equal": (0.20,) * 5,
    "12M": (0.00, 0.00, 0.00, 0.00, 1.00),
}
HOLDINGS = (10, 20, 30)
KEEP = (1.0, 2.0, 3.0)
EMAS = (20, 50, 100, 200)
HIGHS = (0.9, 0.8, 0.7, 0.5)
SCORES = ("sharpe", "return")
VARIABLES = ("weights", "top_n", "keep", "ema", "high", "score")
LIVE_COMBO = {"weights": "live", "top_n": 20, "keep": 2.0, "ema": 50, "high": 0.8, "score": "sharpe"}


def grid() -> list[dict]:
    return [dict(zip(VARIABLES, v))
            for v in itertools.product(WEIGHTS, HOLDINGS, KEEP, EMAS, HIGHS, SCORES)]


def key(c: dict) -> str:
    return (f"{c['weights']}_n{c['top_n']}_k{c['keep']:g}_e{c['ema']}"
            f"_h{round(c['high'] * 100)}_{c['score']}")


def settings(c: dict) -> dict:
    """run_backtest keywords for one combination; the rest stay at LIVE."""
    s = dict(LIVE)
    s.update(top_n=c["top_n"], buffer_n=int(round(c["top_n"] * c["keep"])),
             ema_period=c["ema"], high_pct=c["high"], score_method=c["score"],
             stock_cap=max(LIVE["stock_cap"], 1.0 / c["top_n"]))
    return s


_INPUTS: dict | None = None


def _init_worker(index_key: str) -> None:
    global _INPUTS
    logging.disable(logging.WARNING)
    _INPUTS = history_inputs(index_key)


def _run_one(c: dict, out: str) -> tuple[str, float]:
    from src.engine.backtester import run_backtest

    t0 = time.perf_counter()
    inp = _INPUTS
    raw = inspect.unwrap(run_backtest)  # no Streamlit cache: memory stays flat
    res = raw(
        f"regime-{key(c)}", inp["close"], _benchmark_close=inp["benchmark"],
        config_weights=WEIGHTS[c["weights"]], sector_map=inp["sector_map"],
        _membership=inp["membership"], backtest_months=inp["months"],
        stateful_history=True, history_start=inp["start"].start_time, _actions=[],
        **settings(c),
    )
    if not res or not res.get("stats"):
        raise RuntimeError(f"{key(c)}: no result")
    runs = Path(out) / "runs"
    eq = res["equity_curve"]
    eq.pct_change().iloc[1:].rename("net").to_frame().to_parquet(runs / f"{key(c)}.parquet")
    stats = {k: (float(v) if isinstance(v, (int, float, np.floating, np.integer)) else str(v))
             for k, v in res["stats"].items() if not isinstance(v, (list, dict))}
    (runs / f"{key(c)}.json").write_text(json.dumps({"combo": c, "stats": stats}))
    return key(c), time.perf_counter() - t0


def cmd_run(args: argparse.Namespace) -> None:
    out = Path(args.out)
    (out / "runs").mkdir(parents=True, exist_ok=True)
    combos = grid()
    assert settings(LIVE_COMBO) == LIVE, "the live combination must be the live settings"
    todo = [c for c in combos if not (out / "runs" / f"{key(c)}.json").exists()]
    todo.sort(key=lambda c: c != LIVE_COMBO)  # the live run first: it checks the page
    if args.limit:
        todo = todo[: args.limit]
    meta = history_inputs(args.index)
    (out / "meta.json").write_text(json.dumps({
        "index": meta["index"], "start": str(meta["start"]), "end": str(meta["end"]),
        "months": meta["months"], "built": meta["built"], "last_session": meta["last_session"],
        "combinations": len(combos), "live_combo": LIVE_COMBO,
        "grid": {"weights": {k: list(v) for k, v in WEIGHTS.items()}, "top_n": HOLDINGS,
                 "keep": KEEP, "ema": EMAS, "high": HIGHS, "score": SCORES},
    }, indent=2))
    del meta
    print(f"{len(combos)} combinations, {len(todo)} to run, {args.workers} workers", flush=True)
    t0 = time.perf_counter()
    with ProcessPoolExecutor(args.workers, initializer=_init_worker, initargs=(args.index,)) as pool:
        futures = {pool.submit(_run_one, c, str(out)): c for c in todo}
        for i, fut in enumerate(as_completed(futures), 1):
            c = futures[fut]
            try:
                _, secs = fut.result()
                if i % 25 == 0 or i == len(todo):
                    print(f"[{i}/{len(todo)}] {key(c)} in {secs:.0f}s "
                          f"(elapsed {(time.perf_counter() - t0) / 60:.1f} min)", flush=True)
            except Exception as exc:  # noqa: BLE001 - report and carry on
                print(f"[{i}/{len(todo)}] {key(c)} FAILED: {type(exc).__name__}: {exc}", flush=True)


# ── conditions, from what was known at each month's signal ──────────────────
def conditions(index_key: str, months: pd.PeriodIndex) -> pd.DataFrame:
    from src.engine.membership import members_on

    inp = history_inputs(index_key)
    close, membership = inp["close"], inp["membership"]
    bench = pd.to_numeric(inp["benchmark"], errors="coerce").dropna().sort_index()
    sma200 = bench.rolling(200, min_periods=100).mean()
    vol63 = bench.pct_change().rolling(63, min_periods=40).std() * math.sqrt(TRADING_DAYS)
    # Against the last five years, not all years to date: the 2008 crash in the
    # file's first year would otherwise call almost every later month calm.
    vol_median = vol63.rolling(5 * TRADING_DAYS, min_periods=TRADING_DAYS).median()
    ema50 = close.ewm(span=50, min_periods=30, adjust=False).mean()
    rows = []
    for m in months:
        before = bench.index[bench.index < m.start_time]
        if not len(before):
            continue
        sig = before[-1]
        members = members_on(membership, sig, canonical=True) or set()
        cols = [c for c in members if c in close.columns]
        px, ema = close.loc[:sig, cols].iloc[-1], ema50.loc[:sig, cols].iloc[-1]
        ok = px.notna() & ema.notna()
        breadth = float((px[ok] > ema[ok]).mean()) if ok.any() else np.nan
        v, vm = vol63.loc[sig], vol_median.loc[sig]
        rows.append({
            "month": m, "signal": sig.date(),
            "trend": "up" if bench.loc[sig] >= sma200.loc[sig] else "down",
            "volatility": "calm" if (pd.isna(vm) or v <= vm) else "stormy",
            "breadth": "broad" if breadth >= 0.5 else "narrow",
            "breadth_share": round(breadth, 3), "vol63": round(float(v), 4),
        })
    out = pd.DataFrame(rows).set_index("month")
    out["trend_vol"] = out["trend"] + "/" + out["volatility"]
    return out


def load_runs(out: Path) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    cols, combos = {}, []
    for js in sorted((out / "runs").glob("*.json")):
        rec = json.loads(js.read_text())
        k = key(rec["combo"])
        cols[k] = pd.read_parquet(js.with_suffix(".parquet"))["net"]
        combos.append({"key": k, **rec["combo"],
                       **{f"stat_{s}": rec["stats"].get(s) for s in
                          ("sharpe", "ann_return", "max_drawdown", "avg_turnover", "risk_free_rate")}})
    return pd.DataFrame(cols).dropna(), pd.DataFrame(combos).set_index("key"), json.loads(
        (out / "meta.json").read_text())


def _rho(a: pd.Series, b: pd.Series) -> float:
    return float(a.rank().corr(b.rank()))


def cmd_report(args: argparse.Namespace) -> None:
    out = Path(args.out)
    r, combos, meta = load_runs(out)
    rf = float(combos["stat_risk_free_rate"].iloc[0])
    live = key(LIVE_COMBO)
    if live not in r.columns:
        raise SystemExit("The live combination's run is missing; run `run` first.")
    month_of_day = r.index.to_period("M")
    cond = conditions(args.index, pd.PeriodIndex(sorted(set(month_of_day))))
    cond.to_csv(out / "conditions.csv")
    day_cond = cond.reindex(month_of_day)
    day_cond.index = r.index

    summary: dict = {"meta": meta, "days": len(r), "combinations": len(r.columns),
                     "risk_free": rf, "months_by_condition": {}}
    full = pd.Series(sharpe(r, rf), index=r.columns)
    summary["live_sharpe"] = float(full[live])
    summary["live_rank"] = int((full > full[live]).sum() + 1)
    summary["best"] = {"combo": full.idxmax(), "sharpe": float(full.max())}
    pbo, _ = pbo_cscv(r, rf)
    summary["pbo"] = pbo
    summary["deflated_sharpe"] = deflated_sharpe(r, full.idxmax())

    lines = [f"# Settings by market condition: {meta['index']}, {meta['start']} to {meta['end']}",
             "", f"{len(r.columns)} combinations, {len(r)} sessions. Live settings: Sharpe "
             f"{full[live]:.2f}, rank {summary['live_rank']} of {len(full)}. Best: {full.idxmax()} "
             f"at {full.max():.2f}. Probability of backtest overfitting: {pbo:.0%}.", ""]

    # 1 and 2: within each condition.
    marginal_rows = []
    for dim in ("trend", "volatility", "breadth", "trend_vol"):
        for value in sorted(cond[dim].dropna().unique()):
            mask = (day_cond[dim] == value).to_numpy()
            n_months = int((cond[dim] == value).sum())
            summary["months_by_condition"][f"{dim}={value}"] = n_months
            if mask.sum() < TRADING_DAYS:
                continue
            s = pd.Series(sharpe(r[mask], rf), index=r.columns)
            months_here = cond.index[cond[dim] == value]
            half = months_here[len(months_here) // 2]
            m1 = mask & (month_of_day < half)
            m2 = mask & (month_of_day >= half)
            rho = _rho(pd.Series(sharpe(r[m1], rf), index=r.columns),
                       pd.Series(sharpe(r[m2], rf), index=r.columns))
            top = s.nlargest(10)
            lines += [f"## {dim} = {value}: {n_months} months", "",
                      f"Live: Sharpe {s[live]:.2f}, rank {int((s > s[live]).sum() + 1)} of {len(s)}; "
                      f"median {s.median():.2f}. Halves agree: rho {rho:+.2f}.", "",
                      "| Combination | Sharpe |", "|---|---|"]
            lines += [f"| {k} | {v:.2f} |" for k, v in top.items()] + [""]
            for var in VARIABLES:
                g = s.groupby(combos.loc[s.index, var]).mean()
                for val, mean in g.items():
                    marginal_rows.append({"dimension": dim, "condition": value, "variable": var,
                                          "value": val, "mean_sharpe": round(float(mean), 3),
                                          "months": n_months, "halves_rho": round(rho, 3)})
    marginal = pd.DataFrame(marginal_rows)
    marginal.to_csv(out / "marginal_by_condition.csv", index=False)

    # 3: walk-forward, static and by condition.
    def pick(train_mask: np.ndarray) -> str:
        return pd.Series(sharpe(r[train_mask], rf), index=r.columns).idxmax()

    years = range(args.first_test_year, r.index[-1].year + 1)
    picks: dict[str, list] = {}
    chains: dict[str, list[pd.Series]] = {"static": [], "live": []}
    for dim in ("trend", "volatility", "breadth", "trend_vol"):
        chains[dim] = []
    for year in years:
        train = (r.index < pd.Timestamp(f"{year}-01-01"))
        test = (r.index >= pd.Timestamp(f"{year}-01-01")) & (r.index < pd.Timestamp(f"{year + 1}-01-01"))
        if train.sum() < 2 * TRADING_DAYS or not test.any():
            continue
        static = pick(train)
        chains["static"].append(r.loc[test, static])
        chains["live"].append(r.loc[test, live])
        picks.setdefault("static", []).append({"year": year, "pick": static})
        for dim in ("trend", "volatility", "breadth", "trend_vol"):
            parts = []
            for value in day_cond.loc[test, dim].dropna().unique():
                here = (day_cond[dim] == value).to_numpy()
                cell = train & here
                # Too little history in this condition: fall back to the static pick.
                choice = pick(cell) if cell.sum() >= 24 * 21 else static
                parts.append(r.loc[test & here, choice])
                picks.setdefault(dim, []).append({"year": year, "condition": value, "pick": choice})
            chains[dim].append(pd.concat(parts).sort_index())
    wf = pd.DataFrame({name: pd.concat(parts) for name, parts in chains.items()}).dropna()
    boot = {name: paired_bootstrap(wf[[name, "live"]], "live", rf).loc[name].to_dict()
            for name in wf.columns if name != "live"}
    vs_static = {name: paired_bootstrap(wf[[name, "static"]], "static", rf).loc[name].to_dict()
                 for name in ("trend", "volatility", "breadth", "trend_vol")}
    wf_sharpe = pd.Series(sharpe(wf, rf), index=wf.columns)
    summary["walk_forward"] = {
        "from": int(min(years)), "days": len(wf),
        "sharpe": {k: round(float(v), 3) for k, v in wf_sharpe.items()},
        "minus_live": {k: {m: round(float(x), 3) for m, x in v.items()} for k, v in boot.items()},
        "minus_static": {k: {m: round(float(x), 3) for m, x in v.items()} for k, v in vs_static.items()},
        "picks": picks,
    }
    lines += ["## Walk-forward: pick each year from the years before", "",
              f"{len(wf)} sessions from {min(years)}.", "",
              "| Rule | Sharpe | vs live (90% range) | vs one best setting (90% range) |", "|---|---|---|---|"]
    for name in wf.columns:
        a = boot.get(name)
        b = vs_static.get(name)
        lines.append(f"| {name} | {wf_sharpe[name]:.2f} | "
                     + (f"{a['dSharpe']:+.2f} ({a['lo90']:+.2f} to {a['hi90']:+.2f})" if a else "—")
                     + " | "
                     + (f"{b['dSharpe']:+.2f} ({b['lo90']:+.2f} to {b['hi90']:+.2f})" if b else "—")
                     + " |")
    (out / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (out / "summary.json").write_text(json.dumps(summary, indent=2, default=str))
    print("\n".join(lines[:4]))
    print(json.dumps({k: summary[k] for k in ("months_by_condition", "walk_forward")}, indent=1,
                     default=str)[:6000])


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    pr = sub.add_parser("run")
    pr.add_argument("--out", required=True)
    pr.add_argument("--workers", type=int, default=4)
    pr.add_argument("--index", default="nifty_500")
    pr.add_argument("--limit", type=int, default=0, help="run only this many (for a timing test)")
    pr.set_defaults(func=cmd_run)
    rp = sub.add_parser("report")
    rp.add_argument("--out", required=True)
    rp.add_argument("--index", default="nifty_500")
    rp.add_argument("--first-test-year", type=int, default=2014)
    rp.set_defaults(func=cmd_report)
    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
