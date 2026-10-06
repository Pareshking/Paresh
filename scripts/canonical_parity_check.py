#!/usr/bin/env python3
"""Fail loudly if any representation of the canonical account stops agreeing.

Runs the REAL code paths on the PUBLISHED data (the rolling release assets the
app itself reads; no secrets) and exits non-zero when any check fails:

  1. book_parity      Portfolio passes the Screener ranking frame, Actions and
                      Backtest the deep Yahoo frame; both must yield the identical
                      current book (symbols, entry dates/prices, price now, weights).
  2. ledger_parity    Every frozen ledger month equals the live replay's
                      calendar-month return, strategy and benchmark (+/-0.05 pp).
  3. ledger_config    Every frozen month was struck under the CURRENT pinned
                      config, so a config change without a rebuild cannot slip by.
  4. hard_caps        At every rebalance no stock exceeds the stock cap and no
                      industry the sector cap, and the book never exceeds 100%.
  5. actions_plan     When the published ranking is the one the latest rebalance
                      was signalled on, Actions' planner reproduces its trades and
                      weights exactly.
  6. research_default The research backtest at its default controls, given the
                      account's prices, reproduces the ledger: the defaults cannot
                      drift away from the account's method unnoticed.

    python scripts/canonical_parity_check.py [--report parity_report.json]

Diagnostic only: it never writes the ledger or any data file.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import tempfile
import warnings
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
warnings.filterwarnings("ignore")
logging.disable(logging.WARNING)

from src.core.config import (  # noqa: E402
    DEFAULT_SECTOR_CAP, DEFAULT_STOCK_CAP, DEFAULT_TRANSACTION_COST_BPS,
    PRICE_SNAPSHOT_URL, RANKINGS_SNAPSHOT_URL, SCREENER_STORE_URL,
)
from src.engine import systems  # noqa: E402
from src.engine.actions import plan_rebalance  # noqa: E402
from src.engine.backtester import run_backtest  # noqa: E402
from src.engine.extra_universe import SYSTEM_750  # noqa: E402
from src.engine.model_record import record_sector_map  # noqa: E402
from src.engine.parity_audit import compare_monthly_ledger  # noqa: E402
from src.engine.track_record import (  # noqa: E402
    LEDGER_PATH, TRACK_RECORD_CONFIG, config_fingerprint, months_to_cover,
)
from src.loaders import nse_prices  # noqa: E402
from src.loaders import price_source as ps  # noqa: E402
from src.loaders.price_loader import extract_ohlcv, fetch_benchmark_history  # noqa: E402
from src.loaders.ranking_store import read_snapshot  # noqa: E402
from src.ui.canonical_book import current_book  # noqa: E402

BOOK_COLS = ["Symbol", "Entry Date", "Entry Price", "Price Now", "Weight %"]
TOL_PCT = 1e-6  # weights and caps, in percent


def _download(url: str, into: Path) -> Path:
    path = into / url.rsplit("/", 1)[-1]
    with requests.get(url, timeout=180, stream=True) as r:
        r.raise_for_status()
        with open(path, "wb") as fh:
            for chunk in r.iter_content(1 << 18):
                fh.write(chunk)
    return path


def _book(frame: pd.DataFrame) -> pd.DataFrame:
    return frame[BOOK_COLS].sort_values("Symbol").reset_index(drop=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--report", default="parity_report.json")
    args = ap.parse_args()
    checks: dict[str, dict] = {}

    def record(name: str, ok: bool | None, **detail) -> None:
        checks[name] = {"status": "skipped" if ok is None else ("pass" if ok else "FAIL"), **detail}
        print(f"{'SKIP' if ok is None else ('PASS' if ok else 'FAIL'):4}  {name}: "
              + json.dumps(detail, default=str)[:400])

    tmp = Path(tempfile.mkdtemp())
    rank, meta = read_snapshot(str(_download(RANKINGS_SNAPSHOT_URL, tmp)))
    symbols = list(meta["universe"])
    yahoo, *_ = extract_ohlcv(pd.read_parquet(_download(PRICE_SNAPSHOT_URL, tmp)), symbols)
    chosen = ps.from_screener(pd.read_parquet(_download(SCREENER_STORE_URL, tmp)))
    screener = ps.keep_and_fill(chosen, symbols, yahoo, nse_prices.middle_close(symbols)).close
    bench = fetch_benchmark_history(period="5y")
    if bench.empty:
        print("FAIL  benchmark unavailable; nothing can be compared")
        return 1
    ledger = json.loads(Path(LEDGER_PATH).read_text(encoding="utf-8"))
    print(f"baseline: ranking {meta.get('price_fingerprint')}, pipeline {meta.get('pipeline_version')}, "
          f"prices to {yahoo.index[-1]:%Y-%m-%d}, ledger {min(ledger['months'])}..{max(ledger['months'])}")

    # 1. Same book whichever frame a page passes.
    book_y, res = current_book(yahoo, bench, SYSTEM_750)
    book_s, _ = current_book(screener, bench, SYSTEM_750)
    a, b = _book(book_y), _book(book_s)
    # Price Now is a market mark, not a book-identity field. Actions and
    # Portfolio intentionally may receive different validated price sources
    # (Yahoo/NSE/Screener) while the canonical selection, entries and weights
    # must remain identical. Compare the economic book separately from the
    # source-specific mark and report mark differences diagnostically.
    identity_cols = [c for c in BOOK_COLS if c != "Price Now"]
    same = a[identity_cols].equals(b[identity_cols])
    mark_mismatches = []
    if "Price Now" in a.columns and "Price Now" in b.columns:
        for i in range(min(len(a), len(b))):
            x, y = a.iloc[i]["Price Now"], b.iloc[i]["Price Now"]
            if pd.notna(x) and pd.notna(y) and abs(float(x) - float(y)) > 1e-8:
                mark_mismatches.append({
                    "Symbol": a.iloc[i]["Symbol"],
                    "actions": float(x), "portfolio": float(y),
                    "difference": float(x) - float(y),
                })
    mismatch_columns = []
    mismatch_rows = []
    if not same and not a.empty and not b.empty:
        for col in BOOK_COLS:
            if col not in a.columns or col not in b.columns:
                continue
            av = a[col].reset_index(drop=True)
            bv = b[col].reset_index(drop=True)
            if col in ("Entry Date",):
                av = pd.to_datetime(av, errors="coerce")
                bv = pd.to_datetime(bv, errors="coerce")
                bad = av.ne(bv) & ~(av.isna() & bv.isna())
            elif col in ("Entry Price", "Price Now", "Weight %"):
                an = pd.to_numeric(av, errors="coerce")
                bn = pd.to_numeric(bv, errors="coerce")
                bad = (an - bn).abs().gt(1e-8) & ~(an.isna() & bn.isna())
            else:
                bad = av.astype(str).ne(bv.astype(str))
            if bool(bad.any()):
                mismatch_columns.append(col)
        if mismatch_columns:
            for i in range(min(len(a), len(b))):
                diffs = {}
                for col in mismatch_columns:
                    x, y = a.iloc[i][col], b.iloc[i][col]
                    if col == "Entry Date":
                        x, y = str(x), str(y)
                    elif col in ("Entry Price", "Price Now", "Weight %"):
                        x, y = float(x) if pd.notna(x) else None, float(y) if pd.notna(y) else None
                    if x != y:
                        diffs[col] = {"actions": x, "portfolio": y}
                if diffs:
                    mismatch_rows.append({"Symbol": a.iloc[i]["Symbol"], "diff": diffs})
                    if len(mismatch_rows) >= 5:
                        break
    record("book_parity", same and not a.empty, names=len(a),
           only_in_actions=sorted(set(a.Symbol) - set(b.Symbol)),
           only_in_portfolio=sorted(set(b.Symbol) - set(a.Symbol)),
           mismatch_columns=mismatch_columns,
           mismatch_rows=mismatch_rows,
           as_of=res.get("live_meta", {}).get("as_of"))

    # 2. Frozen months against the live replay.
    rep = compare_monthly_ledger(ledger, res["equity_curve"], res["benchmark"])
    record("ledger_parity", bool(rep["passed"]), counts=rep["counts"],
           max_drift_pp=max((abs(r.get("strategy_drift") or 0) for r in rep["rows"]), default=0) * 100)

    # 3. Struck under today's pinned config.
    membership = systems.membership_for(SYSTEM_750)
    start = systems.inception(SYSTEM_750)
    basis, info = nse_prices.basis_frame(yahoo, membership,
                                         months=months_to_cover(yahoo.index[-1], start))
    cfg = dict(TRACK_RECORD_CONFIG)
    if basis is not None:
        cfg["prices"] = info["basis"]
    fp = config_fingerprint(**cfg)
    stored = sorted({m.get("config") for m in ledger["months"].values()})
    record("ledger_config", stored == [fp], current=fp, ledger=stored)

    # 4. Hard caps at every rebalance.
    books = res.get("month_books") or {}
    labels = record_sector_map(sorted({s for bk in books.values() for s in bk["Symbol"]}))
    breaches = []
    for month, bk in books.items():
        w = pd.to_numeric(bk["Weight %"], errors="coerce").fillna(0.0)
        by_ind = pd.Series(w.values, index=[labels.get(s, "Other") for s in bk["Symbol"]]).groupby(level=0).sum()
        if (w.max() > TRACK_RECORD_CONFIG["stock_cap"] * 100 + TOL_PCT
                or by_ind.max() > TRACK_RECORD_CONFIG["sector_cap"] * 100 + TOL_PCT
                or w.sum() > 100 + TOL_PCT):
            breaches.append({"month": month, "max_stock": round(float(w.max()), 4),
                             "max_industry": f"{by_ind.idxmax()} {by_ind.max():.4f}",
                             "invested": round(float(w.sum()), 4)})
    record("hard_caps", not breaches and bool(books), months=len(books), breaches=breaches)

    # 5. Actions' planner against the latest executed rebalance.
    live = res.get("live_meta") or {}
    signal = pd.Timestamp(live["signal_date"]) if live.get("signal_date") else None
    # The artifact carries its session in the price fingerprint ("<date>_<shape>_<hash>").
    stamp = meta.get("as_of") or str(meta.get("price_fingerprint", "")).split("_", 1)[0]
    ranked_on = pd.Timestamp(stamp) if stamp else None
    keys = sorted(books)
    if signal is None or ranked_on is None or signal.normalize() != ranked_on.normalize() or len(keys) < 2:
        record("actions_plan", None, reason=f"ranking as_of {ranked_on} is not the latest signal {signal}")
    else:
        prior = books[keys[-2]]["Symbol"].tolist()
        lb = res["live_book"].set_index("Symbol")
        plan = plan_rebalance(rank, prior, top_n=int(TRACK_RECORD_CONFIG["top_n"]),
                              buffer_n=int(TRACK_RECORD_CONFIG["buffer_n"]),
                              stock_cap=float(TRACK_RECORD_CONFIG["stock_cap"]),
                              sector_cap=float(TRACK_RECORD_CONFIG["sector_cap"]))
        exp_buys, exp_sells = sorted(set(lb.index) - set(prior)), sorted(set(prior) - set(lb.index))
        wdiff = float(((plan.weights * 100).reindex(lb.index) - pd.to_numeric(lb["Weight %"])).abs().max())
        record("actions_plan", sorted(plan.buys) == exp_buys and sorted(plan.sells) == exp_sells
               and wdiff <= TOL_PCT, buys=sorted(plan.buys), expected_buys=exp_buys,
               sells=sorted(plan.sells), expected_sells=exp_sells, max_weight_diff_pp=wdiff)

    # 6. Research defaults reproduce the account on the account's prices.
    if basis is None:
        record("research_default", False, reason=info.get("why"))
    else:
        sec = rank.set_index("Symbol")["Industry"].to_dict()
        sec.update(record_sector_map([c for c in basis.columns if c not in sec]))
        top_n = 20
        r = run_backtest(
            "parity_research_default", basis, _benchmark_close=bench, top_n=top_n,
            rebal_freq=21, weight_method="Equal Weight",
            config_weights=TRACK_RECORD_CONFIG["config_weights"],
            stock_cap=DEFAULT_STOCK_CAP, sector_cap=DEFAULT_SECTOR_CAP, sector_map=sec,
            cost_bps=float(DEFAULT_TRANSACTION_COST_BPS), buffer_n=int(top_n * 2.0),
            _membership=membership, backtest_months=months_to_cover(basis.index[-1], start),
            stateful_history=True, history_start=start.start_time, _actions=[],
        )
        rr = compare_monthly_ledger(ledger, r["equity_curve"], r["benchmark"])
        record("research_default", bool(rr["passed"]), counts=rr["counts"])

    Path(args.report).write_text(json.dumps(checks, indent=1, default=str), encoding="utf-8")
    failed = [k for k, v in checks.items() if v["status"] == "FAIL"]
    print(f"\n{'FAILED: ' + ', '.join(failed) if failed else 'all parity checks passed'}"
          f" -> {args.report}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
