#!/usr/bin/env python3
"""Frozen outputs for the repository audit (docs/AUDIT_PLAN.md, Block 0).

A speed or memory fix must not change a number. This script pins the inputs
the ranking is built from, recomputes the outputs with the production code,
and later recomputes them again so a change can be compared exactly.

    # once: download the published inputs and record the outputs
    python scripts/audit_baseline.py capture --dir audit_baseline

    # after a change: recompute from the SAME inputs and compare
    python scripts/audit_baseline.py check --dir audit_baseline

Inputs pinned in <dir>/inputs (sha256 in manifest.json):
  screener_prices.parquet   the release store the 750 is ranked from
  rankings.parquet          the nightly's published ranking (for comparison)
  market_caps.parquet       what fetch_market_caps returned at capture
Repository data (data/*, the git commit) is pinned by the commit in the
manifest: check on a branch whose data/ differs and the comparison says so.

Outputs (<dir>/outputs, or <dir>/check for a check):
  ranking_750.parquet       sync_data._precompute_rankings, the nightly's own function
  backtest_equity.csv       run_backtest at fixed settings on the same frame
  summary.json              timings, peak memory, hashes

Diagnostic only: writes nothing under data/ and nothing to the release.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import resource
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.core.config import RANKINGS_SNAPSHOT_URL, SCREENER_STORE_URL  # noqa: E402

TOL = 1e-9  # numeric tolerance for "identical"; float noise only


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _peak_mb() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


def _git_head() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


def _data_dirty() -> bool:
    out = subprocess.run(["git", "status", "--porcelain", "data"], cwd=ROOT,
                         capture_output=True, text=True).stdout
    return bool(out.strip())


def _download(url: str, path: Path) -> None:
    with requests.get(url, timeout=300, stream=True) as r:
        r.raise_for_status()
        with open(path, "wb") as fh:
            for chunk in r.iter_content(1 << 18):
                fh.write(chunk)


def capture_inputs(inputs: Path) -> dict:
    inputs.mkdir(parents=True, exist_ok=True)
    files = {}
    for name, url in (("screener_prices.parquet", SCREENER_STORE_URL),
                      ("rankings.parquet", RANKINGS_SNAPSHOT_URL)):
        t = time.perf_counter()
        _download(url, inputs / name)
        files[name] = {"url": url, "bytes": (inputs / name).stat().st_size,
                       "sha256": _sha256(inputs / name),
                       "download_s": round(time.perf_counter() - t, 1)}

    from src.loaders.indices_loader import fetch_indices_data
    from src.loaders.mcap_loader import fetch_market_caps

    universe = fetch_indices_data(["NIFTY TOTAL MARKET"])
    symbols = universe["Symbol"].unique().tolist()
    mcaps = fetch_market_caps(symbols)
    pd.DataFrame({"Symbol": mcaps.index, "MarketCap": mcaps.values}).to_parquet(
        inputs / "market_caps.parquet", index=False)
    files["market_caps.parquet"] = {"sha256": _sha256(inputs / "market_caps.parquet"),
                                    "symbols": int(len(mcaps))}
    return files


def compute(inputs: Path, out: Path) -> dict:
    """Recompute every frozen output from the pinned inputs."""
    out.mkdir(parents=True, exist_ok=True)
    stages: dict[str, dict] = {}

    def stage(name: str, t0: float) -> None:
        stages[name] = {"seconds": round(time.perf_counter() - t0, 2),
                        "peak_rss_mb_so_far": round(_peak_mb(), 1)}
        print(f"  {name}: {stages[name]['seconds']} s, peak RSS {stages[name]['peak_rss_mb_so_far']} MB")

    t = time.perf_counter()
    from scripts import sync_data
    from src.core.config import DEFAULT_SECTOR_CAP, DEFAULT_STOCK_CAP, DEFAULT_TRANSACTION_COST_BPS
    from src.engine.backtester import run_backtest
    from src.engine.track_record import TRACK_RECORD_CONFIG
    from src.loaders import nse_prices, price_source, screener_loader
    from src.loaders.indices_loader import fetch_indices_data
    from src.loaders.price_loader import fetch_benchmark_history
    stage("imports", t)

    t = time.perf_counter()
    universe = fetch_indices_data(["NIFTY TOTAL MARKET"])
    symbols = universe["Symbol"].unique().tolist()
    mc = pd.read_parquet(inputs / "market_caps.parquet")
    mcaps = pd.Series(mc["MarketCap"].values, index=mc["Symbol"].values)
    stage("universe_and_caps", t)

    # 1. The 750 ranking, by the nightly's own function, from the pinned store.
    t = time.perf_counter()
    screener_loader.SCREENER_PRICES_FILE = str(inputs / "screener_prices.parquet")
    ranking_path = out / "ranking_750.parquet"
    sync_data._precompute_rankings(symbols, universe, mcaps, out_name=str(ranking_path))
    stage("ranking_750", t)

    # 2. A fixed backtest on the same frame: the research defaults, 12 months.
    t = time.perf_counter()
    store = screener_loader.load_store(str(inputs / "screener_prices.parquet"))
    src = price_source.ranking_frames(store, symbols, nse_prices.middle_close(symbols))
    bench = fetch_benchmark_history(period="5y")
    rank = pd.read_parquet(ranking_path)
    sec = rank.set_index("Symbol")["Industry"].to_dict() if "Industry" in rank else {}
    top_n = 20
    r = run_backtest(
        "audit_baseline", src.adj_close, _benchmark_close=bench, top_n=top_n,
        rebal_freq=21, weight_method="Equal Weight",
        config_weights=TRACK_RECORD_CONFIG["config_weights"],
        stock_cap=DEFAULT_STOCK_CAP, sector_cap=DEFAULT_SECTOR_CAP, sector_map=sec,
        cost_bps=float(DEFAULT_TRANSACTION_COST_BPS), buffer_n=int(top_n * 2.0),
        backtest_months=12,
    )
    eq = pd.DataFrame({"equity": r["equity_curve"], "benchmark": r["benchmark"]})
    eq.to_csv(out / "backtest_equity.csv")
    stage("backtest_12m", t)

    summary = {
        "computed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "git_head": _git_head(),
        "data_dir_dirty": _data_dirty(),
        "python": sys.version.split()[0],
        "pandas": pd.__version__,
        "ranking_rows": int(len(rank)),
        "ranking_first20_as_written": rank.head(20)["Symbol"].tolist() if "Symbol" in rank else [],
        "backtest_last_equity": float(eq["equity"].iloc[-1]),
        "backtest_rows": int(len(eq)),
        "stages": stages,
        "peak_rss_mb": round(_peak_mb(), 1),
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    return summary


def _compare_frames(a: pd.DataFrame, b: pd.DataFrame) -> dict:
    """Exact comparison: same shape, columns, labels; numbers within TOL."""
    res: dict = {"same_shape": a.shape == b.shape,
                 "same_columns": list(a.columns) == list(b.columns)}
    if not (res["same_shape"] and res["same_columns"]):
        res["identical"] = False
        res["only_left_cols"] = sorted(set(a.columns) - set(b.columns))
        res["only_right_cols"] = sorted(set(b.columns) - set(a.columns))
        return res
    worst, diff_cols = 0.0, []
    for c in a.columns:
        x, y = a[c], b[c]
        if pd.api.types.is_numeric_dtype(x) and pd.api.types.is_numeric_dtype(y):
            d = (x.astype(float) - y.astype(float)).abs()
            both_nan = x.isna() & y.isna()
            m = float(d[~both_nan].max()) if (~both_nan).any() else 0.0
            if pd.isna(m) or m > TOL:
                diff_cols.append((c, None if pd.isna(m) else m))
            worst = max(worst, 0.0 if pd.isna(m) else m)
        else:
            if not (x.astype(str).values == y.astype(str).values).all():
                diff_cols.append((c, "text differs"))
    res.update(identical=not diff_cols, max_abs_diff=worst, differing_columns=diff_cols[:20])
    return res


def compare(left: Path, right: Path) -> dict:
    ra = pd.read_parquet(left / "ranking_750.parquet").sort_values("Symbol").reset_index(drop=True)
    rb = pd.read_parquet(right / "ranking_750.parquet").sort_values("Symbol").reset_index(drop=True)
    ea = pd.read_csv(left / "backtest_equity.csv", index_col=0)
    eb = pd.read_csv(right / "backtest_equity.csv", index_col=0)
    return {"ranking_750": _compare_frames(ra, rb), "backtest_equity": _compare_frames(ea, eb)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=["capture", "check"])
    ap.add_argument("--dir", type=Path, default=ROOT / "audit_baseline")
    args = ap.parse_args()
    base: Path = args.dir.resolve()
    inputs = base / "inputs"

    if args.mode == "capture":
        print(f"Capturing inputs into {inputs}")
        files = capture_inputs(inputs)
        manifest = {"captured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "git_head": _git_head(), "data_dir_dirty": _data_dirty(), "inputs": files}
        (base / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
        print("Computing frozen outputs")
        summary = compute(inputs, base / "outputs")
        # The recomputed 750 against what the nightly published from the same store.
        pub = pd.read_parquet(inputs / "rankings.parquet").sort_values("Symbol").reset_index(drop=True)
        mine = pd.read_parquet(base / "outputs" / "ranking_750.parquet").sort_values("Symbol").reset_index(drop=True)
        vs_pub = _compare_frames(mine, pub)
        (base / "outputs" / "vs_published.json").write_text(json.dumps(vs_pub, indent=1, default=str))
        print(f"Recomputed ranking vs published: {json.dumps(vs_pub, default=str)[:600]}")
        print(json.dumps(summary, indent=1)[:1500])
        return 0

    manifest = json.loads((base / "manifest.json").read_text())
    for name, meta in manifest["inputs"].items():
        if _sha256(inputs / name) != meta["sha256"]:
            print(f"FAIL: pinned input {name} changed since capture")
            return 2
    if manifest["git_head"] != _git_head():
        print(f"note: capture was at {manifest['git_head'][:10]}, now {_git_head()[:10]};"
              " data/ may differ between the two (check `git diff --stat <capture> -- data`)")
    summary = compute(inputs, base / "check")
    result = compare(base / "outputs", base / "check")
    (base / "check" / "compare.json").write_text(json.dumps(result, indent=1, default=str))
    ok = all(v.get("identical") for v in result.values())
    print(json.dumps(result, indent=1, default=str)[:2000])
    print(f"stages: {json.dumps(summary['stages'])}")
    print("IDENTICAL" if ok else "DIFFERENT")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
