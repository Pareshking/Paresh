"""The Backtest page's stored tests of its default run (S174; owner, 21 Nov 2026, decision C).

The page opens on one run: the record's rules on the Nifty 500 as it stood, from
Jan 2010 to the last completed month, the six-monthly reset applied throughout,
30 bps a round trip (src/engine/backtest_page.py). Re-running it four more times
on every visit would cost a minute of the shared server, so the tests are run
here, once a week after the long file is rebuilt, and stored with the long file's
last session so the page can say which file they belong to:

  - the monthly reset, 60 and 100 bps a round trip (the same window);
  - the rule on the Nifty Total Market universe from Nov 2021, against that index;
  - after tax, sold at the end: the share-lot replay of
    scripts/research/rebalance_rules_after_tax.py (STCG 20.8%, LTCG 13% above
    Rs 1.25 lakh, today's rates for every year, an investor with no other gains),
    beside a Nifty 500 position bought at the start and sold at the end, taxed once
    (scripts/research/cost_and_index_tax.py, S124).

Every "a year" is compounded over calendar time, as the page and the engine.

    PYTHONPATH=. python scripts/build_backtest_reference.py [--long nse_long_close.parquet] [--out data/backtest_reference.json]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts" / "research"))

from src.core.config import BENCHMARK_SYMBOL  # noqa: E402
from src.engine import backtest_page as bp  # noqa: E402
from src.engine import index_universe as iu  # noqa: E402
from src.engine.backtester import run_backtest  # noqa: E402
from src.engine.track_record import TRACK_RECORD_CONFIG as CFG  # noqa: E402
from src.loaders import benchmark_store  # noqa: E402

OUT = ROOT / "data" / "backtest_reference.json"
LIVE_RULE = {"hold_cap": CFG["hold_cap"], "hold_cap_from": None, "buy_size": CFG["buy_size"],
             "weight_reset_months": tuple(CFG["weight_reset_months"])}


def _run(close: pd.DataFrame, key: str, bench: pd.Series, start: pd.Period, rule: dict, cost: float) -> dict:
    membership = iu.index_history(key)
    start = max(start, iu.first_month(membership))
    end = pd.Period(close.index[-1], "M") - 1
    frame = bp.frame_for(close, iu.ever_members(membership), end, to_latest=True)
    return run_backtest(
        f"reference_{key}_{cost}_{bool(rule)}", frame, top_n=CFG["top_n"], rebal_freq=21,
        ema_period=CFG["ema_period"], high_pct=CFG["high_pct"], weight_method=CFG["weight_method"],
        config_weights=tuple(CFG["config_weights"]), stock_cap=CFG["stock_cap"], sector_cap=CFG["sector_cap"],
        sector_map=_industries(frame.columns), cost_bps=cost, buffer_n=CFG["buffer_n"],
        _benchmark_close=bench, backtest_months=(end - start).n + 1, _membership=membership,
        stateful_history=True, history_start=start.start_time, _actions=[], **rule)


def _industries(columns) -> dict[str, str]:
    """The page's industry map (backtest_page.industry_map), so "as tested" is the page's own run."""
    return bp.industry_map(columns, bp.index_file_industries())[0]


def _curve(res: dict) -> pd.Series:
    eq = pd.Series(res["equity_curve"]).dropna()
    eq.index = pd.DatetimeIndex(eq.index)
    return eq


def _r(v, d=4):
    return None if v is None else round(float(v), d)


def build(close: pd.DataFrame) -> dict:
    close.index = pd.DatetimeIndex(close.index)
    n500 = benchmark_store.history(period="max", symbol=BENCHMARK_SYMBOL)
    n500.index = pd.DatetimeIndex(n500.index)
    out: dict = {"long_last_session": f"{close.index[-1]:%Y-%m-%d}",
                 "built": f"{datetime.now(timezone.utc):%Y-%m-%d}", "rows": {}}

    runs = {"as_tested": (LIVE_RULE, 30.0), "monthly_reset": ({}, 30.0),
            "cost_60": (LIVE_RULE, 60.0), "cost_100": (LIVE_RULE, 100.0)}
    base = None
    for name, (rule, cost) in runs.items():
        eq = _curve(_run(close, bp.DEFAULT_INDEX, n500, bp.DEFAULT_START, rule, cost))
        out["rows"][name] = _r(bp.a_year(eq))
        if name == "as_tested":
            base = eq
            out["window"] = [f"{eq.index[0]:%Y-%m-%d}", f"{eq.index[-1]:%Y-%m-%d}"]
            out["rows"]["nifty_500"] = _r(bp.a_year(bp.on_calendar(n500, eq.index)))
        print(name, out["rows"][name], flush=True)

    # The rule on the Total Market universe, against Nifty Total Market (NSE's file).
    from src.loaders import nse_indices as ni
    store = ni.read_compact()
    tm = store[store["key"] == bp.TOTAL_MARKET].set_index("date")["close"].sort_index()
    tm.index = pd.DatetimeIndex(tm.index)
    if len(tm):
        teq = _curve(_run(close, bp.TOTAL_MARKET, tm, pd.Period("2021-11", "M"), LIVE_RULE, 30.0))
        w = bp.window(teq, {"total_market": tm, "nifty_500": n500}, teq.index[0])
        out["total_market_universe"] = {
            "from": f"{w['from']:%Y-%m-%d}", "to": f"{w['to']:%Y-%m-%d}",
            "rule": [_r(w["rule"][0]), _r(w["rule"][1])],
            "total_market": [_r(w["total_market"][0]), _r(w["total_market"][1])],
            "nifty_500": [_r(w["nifty_500"][0]), _r(w["nifty_500"][1])]}

    # After tax, sold at the end: the share-lot replay on the same run (S111, S124).
    import cost_and_index_tax as cit
    import rebalance_rules_after_tax as rr
    rr.record_sector_map = _industries          # the replay caps industries as the page does
    # The replay values the book at its frame's last session, so the frame stops at the
    # first session after the last completed month, one day past the curve's end.
    month = pd.Period(close.index[-1], "M")
    upto = close.loc[:close.index[close.index >= month.start_time][0]]
    res, (pre, post) = rr.run(upto, n500, bp.DEFAULT_INDEX, bp.DEFAULT_START.start_time, "4 semi_reset")
    eq = _curve(res)
    yrs = bp.calendar_years(eq)
    v, v_tax, iyrs = cit.index_after_tax(n500, eq.index[0], eq.index[-1])
    out["after_tax"] = {
        "rule": _r(rr.cagr(rr.CAPITAL, post["after_liquidation"], yrs) / 100),
        "nifty_500": _r(rr.cagr(rr.CAPITAL, v_tax, iyrs) / 100),
        # The replay before tax, against the backtest's own figure: the check that the
        # replay prices the same book (a gap above 0.1 pt a year is a fault to look at).
        "replay_before_tax": _r(rr.cagr(rr.CAPITAL, pre["value"], yrs) / 100),
        "rates": "STCG 20.8%, LTCG 13% above Rs 1.25 lakh, today's rates for every year",
    }
    gap = abs(out["after_tax"]["replay_before_tax"] - out["rows"]["as_tested"]) * 100
    out["after_tax"]["replay_gap_pts"] = round(gap, 2)
    print("after tax", out["after_tax"], flush=True)
    if base is not None:
        out["check"] = {"as_tested_total": _r(float(base.iloc[-1] / base.iloc[0] - 1))}
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--long", help="nse_long_close.parquet (default: the app's loader, R2 then the release)")
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()
    if a.long:
        close = pd.read_parquet(a.long)
        if "date" in close.columns:
            close = close.set_index("date")
    else:
        from src.loaders import nse_long
        loaded = nse_long.load(with_value=False)
        if loaded is None:
            raise SystemExit("The long NSE file could not be read; the stored reference is kept.")
        close = loaded[0]
    out = build(close)
    if out["after_tax"]["replay_gap_pts"] > 0.5:
        raise SystemExit(f"The tax replay is {out['after_tax']['replay_gap_pts']} pts a year off the backtest; not written.")
    Path(a.out).write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    print("wrote", a.out)


if __name__ == "__main__":
    main()
