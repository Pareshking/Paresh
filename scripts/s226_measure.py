"""S226 (B): what would move if the sector cap read NSE's sector instead of today's labels.

Owner, 24 Nov 2026: "remove trading views sector or Industry and use Screener 4 level for any
filtering". The pages' filters switch on their own (src/loaders/nse_classification.with_nse_levels);
the sector cap does not, because it moves the model plan, the frozen record's replay and every
backtest. This script measures that move and changes nothing: no file is written unless --out
names one, and no rank, book or record is touched.

Three readings, each "today" against "NSE's sector":

  1. Labels: every symbol whose cap group changes, and each group's count before and after
     (today: the record's map, model_record.record_sector_map; on Nano and Combined the live
     plan's map is TradingView's sector, app.py).
  2. The plan: actions.plan_rebalance on a ranking file, struck both ways: the sells, buys,
     holds and weights that differ.
  3. A backtest: backtester.run_backtest on a closes file with the record's rules, both ways:
     its figures (CAGR, total return, max drawdown, Sharpe, alpha) and the names held in each
     period that differ.

"NSE's sector" is the one the Screener shows (nse_classification.sector_map: NSE's own lists
first, then data/reference/nse_classification.csv, in the 750's spelling); a symbol neither
names keeps today's label, and is counted.

    python scripts/s226_measure.py --system nano                     # labels only
    python scripts/s226_measure.py --system nano --ranking rank.parquet --holdings A,B,C
    python scripts/s226_measure.py --system 750 --prices /path/nse_long_close.parquet --months 12
    python scripts/s226_measure.py ... --out docs/archive/S226_MEASURE.json

It refuses (exit 2) while the file covers under 90% of the system's stocks (MIN_COVERAGE), as the
pages do; --force measures anyway, for a trial, and says so in the report.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Callable, Iterable

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.engine import extra_universe as xu  # noqa: E402

TV_FILE = os.path.join(ROOT, "data", "nse_tv_classification.csv")
STATS = ("ann_return", "total_return", "max_drawdown", "sharpe", "alpha")


# ── 1. Labels ─────────────────────────────────────────────────────────────────


def proposed_map(symbols: Iterable[str], current: dict[str, str], sectors: dict[str, str]) -> dict[str, str]:
    """NSE's sector for each symbol where one is known, else today's label (counted by the caller)."""
    return {s: sectors.get(str(s).upper(), current.get(s, "Other")) for s in symbols}


def label_moves(current: dict[str, str], proposed: dict[str, str]) -> pd.DataFrame:
    """One row per symbol whose group changes: Symbol, Today, NSE."""
    rows = [{"Symbol": s, "Today": current.get(s, "Other"), "NSE": proposed[s]}
            for s in sorted(proposed) if proposed[s] != current.get(s, "Other")]
    return pd.DataFrame(rows, columns=["Symbol", "Today", "NSE"])


def group_counts(current: dict[str, str], proposed: dict[str, str]) -> pd.DataFrame:
    """Stocks per cap group, today and under NSE's sector, largest NSE group first."""
    syms = list(proposed)
    now = pd.Series([current.get(s, "Other") for s in syms]).value_counts()
    nse = pd.Series([proposed[s] for s in syms]).value_counts()
    out = pd.DataFrame({"Today": now, "NSE": nse}).fillna(0).astype(int)
    out["Change"] = out["NSE"] - out["Today"]
    return out.sort_values(["NSE", "Today"], ascending=False).rename_axis("Group").reset_index()


def coverage(symbols: Iterable[str], sectors: dict[str, str]) -> tuple[int, int]:
    syms = [str(s).upper() for s in symbols]
    return sum(s in sectors for s in syms), len(syms)


def live_plan_labels(rank_df: pd.DataFrame, system: str, tv: dict[str, str] | None = None) -> dict[str, str]:
    """The sector cap's labels in today's live plan (app.py): TradingView's sector on Nano and
    Combined where it has one, the ranking's Industry otherwise."""
    frame = rank_df.drop_duplicates("Symbol").set_index("Symbol")
    ind = frame["Industry"].astype(str).to_dict() if "Industry" in frame else {}
    if system in (xu.SYSTEM_NANO, xu.SYSTEM_COMBINED):
        tv = _tv_sectors() if tv is None else tv
        return {s: (tv.get(s) or ind.get(s, "")) for s in frame.index}
    return ind


def _tv_sectors() -> dict[str, str]:
    try:
        tv = pd.read_csv(TV_FILE, dtype=str).dropna(subset=["TV_Sector"]).drop_duplicates("Symbol")
    except (OSError, ValueError, KeyError):
        return {}
    return dict(zip(tv["Symbol"].str.strip().str.upper(), tv["TV_Sector"]))


# ── 2. The plan ───────────────────────────────────────────────────────────────


def plan_moves(rank_df: pd.DataFrame, holdings: list[str], current: dict[str, str], proposed: dict[str, str],
               cfg: dict, plan: Callable | None = None) -> dict:
    """The plan struck with today's labels and with NSE's: what differs, and each weight that moves."""
    if plan is None:
        from src.engine.actions import plan_rebalance as plan

    def strike(labels: dict[str, str]):
        frame = rank_df.assign(Industry=rank_df["Symbol"].map(labels).fillna(rank_df.get("Industry")))
        return plan(frame, holdings, top_n=int(cfg["top_n"]), buffer_n=int(cfg["buffer_n"]),
                    stock_cap=float(cfg["stock_cap"]), sector_cap=float(cfg["sector_cap"]))

    a, b = strike(current), strike(proposed)
    names = sorted(set(a.weights.index) | set(b.weights.index))
    w = pd.DataFrame({"Today %": a.weights.reindex(names).fillna(0.0) * 100,
                      "NSE %": b.weights.reindex(names).fillna(0.0) * 100})
    w["Change"] = w["NSE %"] - w["Today %"]
    moved = w[w["Change"].abs() > 1e-6].round(3)
    return {"sells_only_today": sorted(set(a.sells) - set(b.sells)),
            "sells_only_nse": sorted(set(b.sells) - set(a.sells)),
            "buys_only_today": sorted(set(a.buys) - set(b.buys)),
            "buys_only_nse": sorted(set(b.buys) - set(a.buys)),
            "weights_moved": moved.rename_axis("Symbol").reset_index().to_dict("records")}


# ── 3. A backtest ─────────────────────────────────────────────────────────────


def held_by_period(tradebook: pd.DataFrame | None) -> dict[str, set[str]]:
    """{period: names held with a weight} from a run's tradebook."""
    if tradebook is None or tradebook.empty or "Period" not in tradebook:
        return {}
    tb = tradebook[pd.to_numeric(tradebook["Weight %"], errors="coerce").fillna(0) > 0]
    return {str(p): set(g["Symbol"].astype(str)) for p, g in tb.groupby("Period")}


def backtest_moves(run: Callable, kwargs: dict, current: dict[str, str], proposed: dict[str, str]) -> dict:
    """`run(sector_map=..., **kwargs)` both ways: the figures and the names held that differ."""
    a = run(sector_map=current, **kwargs) or {}
    b = run(sector_map=proposed, **kwargs) or {}
    sa, sb = a.get("stats") or {}, b.get("stats") or {}
    figures = {k: {"today": sa.get(k), "nse": sb.get(k),
                   "change": (None if sa.get(k) is None or sb.get(k) is None else float(sb[k]) - float(sa[k]))}
               for k in STATS}
    ha, hb = held_by_period(a.get("tradebook")), held_by_period(b.get("tradebook"))
    periods = []
    for p in sorted(set(ha) | set(hb)):
        x, y = ha.get(p, set()), hb.get(p, set())
        if x != y:
            periods.append({"period": p, "only_today": sorted(x - y), "only_nse": sorted(y - x)})
    return {"figures": figures, "periods_that_differ": periods}


def _record_run(prices: pd.DataFrame, system: str, months: int, bench: pd.Series | None) -> tuple[Callable, dict]:
    from src.engine.backtester import run_backtest
    from src.engine.systems import membership_for
    from src.engine.track_record import TRACK_RECORD_CONFIG, run_backtest_kwargs

    membership = membership_for(system)
    kwargs = dict(run_backtest_kwargs(TRACK_RECORD_CONFIG), _membership=membership, backtest_months=months,
                  _benchmark_close=bench, _actions=[])
    calls = iter(range(10))

    def run(sector_map, **kw):
        # A key per call: run_backtest is cached on its first argument.
        return run_backtest(f"s226_{system}_{months}_{next(calls)}", prices, sector_map=sector_map, **kw)

    return run, kwargs


# ── CLI ───────────────────────────────────────────────────────────────────────


def _read(path: str) -> pd.DataFrame:
    return pd.read_parquet(path) if path.endswith(".parquet") else pd.read_csv(path)


def measure(system: str, symbols: list[str], current: dict[str, str], sectors: dict[str, str],
            min_coverage: float, force: bool) -> dict:
    known, n = coverage(symbols, sectors)
    proposed = proposed_map(symbols, current, sectors)
    report = {"system": system, "stocks": n, "nse_sector_known": known,
              "coverage": round(known / n, 4) if n else 0.0, "min_coverage": min_coverage,
              "trial_below_coverage": bool(n and known / n < min_coverage and force),
              "kept_todays_label": n - known}
    moves = label_moves(current, proposed)
    report["labels_moved"] = len(moves)
    report["label_moves"] = moves.to_dict("records")
    report["groups"] = group_counts(current, proposed).to_dict("records")
    return report


def main(argv: list[str] | None = None) -> int:
    from src.loaders import nse_classification as nc

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--system", default=xu.SYSTEM_NANO, choices=list(xu.SYSTEMS))
    ap.add_argument("--classification", default=nc.CLASSIFICATION_PATH)
    ap.add_argument("--ranking", help="a ranking file (csv or parquet) with Symbol, Rank, Industry and the filters")
    ap.add_argument("--holdings", default="", help="the book's symbols, comma-separated, for the plan")
    ap.add_argument("--prices", help="adjusted closes (parquet, dates x symbols) for the backtest")
    ap.add_argument("--benchmark", help="a benchmark close (csv with date and close) for the backtest's alpha")
    ap.add_argument("--months", type=int, default=12)
    ap.add_argument("--force", action="store_true", help="measure below the 90%% coverage guard (a trial)")
    ap.add_argument("--out", help="write the report as JSON here")
    args = ap.parse_args(argv)

    from src.engine.model_record import record_sector_map
    from src.engine.track_record import TRACK_RECORD_CONFIG

    sectors = nc.sector_map(args.classification)
    ranking = _read(args.ranking) if args.ranking else None
    prices = pd.read_parquet(args.prices) if args.prices else None
    if ranking is not None:
        symbols = ranking["Symbol"].astype(str).tolist()
    elif prices is not None:
        symbols = [str(c) for c in prices.columns]
    else:
        from src.loaders.extra_universe_loader import extra_members
        idx = pd.read_csv(os.path.join(ROOT, "data", "indices", "ind_niftytotalmarket_list.csv"))
        idx.columns = [str(c).strip() for c in idx.columns]
        base = [] if args.system == xu.SYSTEM_NANO else idx["Symbol"].astype(str).tolist()
        extra = [] if args.system == xu.SYSTEM_750 else extra_members(args.system)["Symbol"].astype(str).tolist()
        symbols = sorted(set(base) | set(extra))

    current = record_sector_map(symbols, args.system)
    report = {"record": measure(args.system, symbols, current, sectors, nc.MIN_COVERAGE, args.force)}
    rec = report["record"]
    if rec["coverage"] < nc.MIN_COVERAGE and not args.force:
        print(f"S226 NSE's sector is known for {rec['nse_sector_known']} of {rec['stocks']} stocks "
              f"({rec['coverage']:.0%}), under {nc.MIN_COVERAGE:.0%}: run the full Screener sweep first, "
              "or pass --force for a trial.")
        return 2

    proposed = proposed_map(symbols, current, sectors)
    if ranking is not None:
        live = live_plan_labels(ranking, args.system)
        live_nse = proposed_map(live, live, sectors)
        report["live_plan"] = measure(args.system, list(live), live, sectors, nc.MIN_COVERAGE, args.force)
        holdings = [h.strip() for h in args.holdings.split(",") if h.strip()]
        report["plan"] = plan_moves(ranking, holdings, live, live_nse, TRACK_RECORD_CONFIG)
    if prices is not None:
        bench = None
        if args.benchmark:
            b = pd.read_csv(args.benchmark, parse_dates=[0], index_col=0)
            bench = pd.to_numeric(b.iloc[:, 0], errors="coerce")
        run, kwargs = _record_run(prices, args.system, args.months, bench)
        report["backtest"] = backtest_moves(run, kwargs, current, proposed)

    _print(report)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=1, default=str)
        print(f"Wrote {args.out}")
    return 0


def _print(report: dict) -> None:
    for part in ("record", "live_plan"):
        r = report.get(part)
        if not r:
            continue
        print(f"\n{part}: {r['system']}, NSE's sector known for {r['nse_sector_known']} of {r['stocks']} "
              f"({r['coverage']:.0%}){' [TRIAL, below the guard]' if r['trial_below_coverage'] else ''}; "
              f"{r['labels_moved']} change group")
        for row in r["label_moves"][:40]:
            print(f"  {row['Symbol']:<14} {row['Today']:<34} -> {row['NSE']}")
        if len(r["label_moves"]) > 40:
            print(f"  ... and {len(r['label_moves']) - 40} more")
    if "plan" in report:
        p = report["plan"]
        print("\nplan:", {k: v for k, v in p.items() if k != "weights_moved"})
        for row in p["weights_moved"]:
            print(f"  {row['Symbol']:<14} {row['Today %']:>7.2f}% -> {row['NSE %']:>7.2f}%")
    if "backtest" in report:
        b = report["backtest"]
        print("\nbacktest figures:")
        for k, v in b["figures"].items():
            print(f"  {k:<14} today {v['today']}  nse {v['nse']}  change {v['change']}")
        print(f"  {len(b['periods_that_differ'])} periods hold different names")
        for row in b["periods_that_differ"][:24]:
            print(f"  {row['period']}: out {row['only_today']} in {row['only_nse']}")


if __name__ == "__main__":
    raise SystemExit(main())
