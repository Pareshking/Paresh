"""Numbers for the Backtest makeover mock-up (docs/mockups/backtest_v1.html).

Proposal stage (owner approves before anything is built). Runs the Backtest
page's "History from 2010" defaults through `run_backtest` on the NSE long file
and writes every figure the mock-up shows to one JSON, so each can be traced.

    python scripts/research/backtest_mockup_numbers.py --long <nse_long_close.parquet> --out <out.json>

Runs (each the page's default unless named):
  page      Nifty 500, 20 holdings, keep in top 40, 50D EMA, within 20% of the
            52W high, Sharpe score, 30 bps, six-monthly reset rule applied from
            the first month (the page passes hold_cap_from=None)
  monthly   the same with the monthly reset (the record's rule before Nov 2026)
  cost60 / cost100   the page run at 60 and 100 bps a round trip
  tm        Nifty Total Market universe from its list's first month, against
            Nifty Total Market (NSE's index file) and the Nifty 500

Industry labels: model_record.record_sector_map, as the record and
portfolio_history use (the page builds its own map from the screener's rows;
the two can differ for a few former members).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.core import config
from src.engine import index_universe as iu
from src.engine.backtester import run_backtest
from src.engine.metrics import drawdown, max_drawdown
from src.engine.model_record import record_sector_map
from src.engine.track_record import TRACK_RECORD_CONFIG as CFG
from src.loaders import benchmark_store

ROOT = Path(__file__).resolve().parents[2]


def live_rule() -> dict:
    return {"hold_cap": CFG["hold_cap"], "hold_cap_from": None, "buy_size": CFG["buy_size"],
            "weight_reset_months": tuple(CFG["weight_reset_months"])}


def run(close: pd.DataFrame, key: str, bench: pd.Series, *, start: pd.Period, rule: dict,
        cost: float = 30.0) -> dict:
    membership = iu.index_history(key)
    first = iu.first_month(membership)
    start = max(start, first)
    cols = sorted(iu.ever_members(membership) & set(close.columns))
    frame = close.loc[:, cols].astype("float64")
    end = pd.Period(frame.index[-1], "M") - 1
    res = run_backtest(
        f"mockup_{key}_{cost}_{bool(rule)}", frame, top_n=20, rebal_freq=21, ema_period=50,
        high_pct=0.80, weight_method="Equal Weight", config_weights=tuple(CFG["config_weights"]),
        stock_cap=0.05, sector_cap=0.40, sector_map=record_sector_map(cols), cost_bps=cost,
        buffer_n=40, _benchmark_close=bench, backtest_months=(end - start).n + 1,
        _membership=membership, stateful_history=True, history_start=start.start_time,
        _actions=[], **rule)
    return res


def curve_stats(eq: pd.Series, bm: pd.Series) -> dict:
    eq = eq.dropna()
    bm = bm.reindex(eq.index).ffill()
    dd = drawdown(eq)
    low = dd.idxmin()
    peak = eq.loc[:low].idxmax()
    after = eq.loc[low:]
    rec = after[after >= eq.loc[peak]]
    bdd = drawdown(bm)
    blow = bdd.idxmin()
    bpeak = bm.loc[:blow].idxmax()
    brec = bm.loc[blow:][bm.loc[blow:] >= bm.loc[bpeak]]
    yrs = (eq.index[-1] - eq.index[0]).days / 365.25
    return {
        "first": str(eq.index[0].date()), "last": str(eq.index[-1].date()), "years": yrs,
        "total": float(eq.iloc[-1] / eq.iloc[0] - 1), "bench_total": float(bm.iloc[-1] / bm.iloc[0] - 1),
        "cagr_calendar": float((eq.iloc[-1] / eq.iloc[0]) ** (1 / yrs) - 1),
        "bench_cagr_calendar": float((bm.iloc[-1] / bm.iloc[0]) ** (1 / yrs) - 1),
        "max_dd": max_drawdown(eq), "dd_peak": str(peak.date()), "dd_low": str(low.date()),
        "dd_recovered": str(rec.index[0].date()) if len(rec) else None,
        "dd_now": float(dd.iloc[-1]),
        "bench_max_dd": max_drawdown(bm), "bench_dd_peak": str(bpeak.date()),
        "bench_dd_low": str(blow.date()),
        "bench_dd_recovered": str(brec.index[0].date()) if len(brec) else None,
    }


def calendar(eq: pd.Series, bm: pd.Series) -> list[dict]:
    eq = eq.dropna()
    bm = bm.reindex(eq.index).ffill()
    out = []
    ye, yb = eq.resample("YE").last(), bm.resample("YE").last()
    # The first year starts at the curve's base (the first fill), not at a year-end.
    prev_e, prev_b = eq.iloc[0], bm.iloc[0]
    for d in ye.index:
        out.append({"year": d.year, "strategy": float(ye[d] / prev_e - 1), "bench": float(yb[d] / prev_b - 1),
                    "months": int(((eq.index.year == d.year)).any() and
                                  len(set(eq.index[eq.index.year == d.year].month)))})
        prev_e, prev_b = ye[d], yb[d]
    return out


def monthly(eq: pd.Series, bm: pd.Series) -> pd.DataFrame:
    eq = eq.dropna()
    bm = bm.reindex(eq.index).ffill()
    me = eq.resample("ME").last()
    mb = bm.resample("ME").last()
    first = pd.Series([eq.iloc[0]], index=[eq.index[0]])
    firstb = pd.Series([bm.iloc[0]], index=[eq.index[0]])
    s = pd.concat([first, me]).pct_change().dropna()
    b = pd.concat([firstb, mb]).pct_change().dropna()
    return pd.DataFrame({"s": s, "b": b})


def stale_exits(res: dict, close: pd.DataFrame) -> list[dict]:
    """Closed trades whose exit fill is a price carried from 5+ sessions earlier."""
    ct = res.get("closed_trades")
    out = []
    if ct is None or ct.empty:
        return out
    for _, r in ct[ct["Status"] == "Closed"].iterrows():
        s = r["Symbol"]
        try:
            d = pd.Timestamp(r["Exit Date"])
        except (TypeError, ValueError):
            continue
        if s not in close.columns:
            continue
        col = close[s].loc[:d].dropna()
        if col.empty:
            continue
        gap = int(((close.index > col.index[-1]) & (close.index <= d)).sum())
        if gap >= 5:
            out.append({"symbol": s, "exit": str(d.date()), "last_print": str(col.index[-1].date()),
                        "sessions_stale": gap, "return": float(r["Return %"])})
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--long", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    close = pd.read_parquet(a.long)
    close.index = pd.DatetimeIndex(close.index)
    n500 = benchmark_store.history(period="max", symbol=config.BENCHMARK_SYMBOL)
    n500.index = pd.DatetimeIndex(n500.index)
    start = pd.Period("2010-01", "M")
    out: dict = {"long_last_session": str(close.index[-1].date()), "runs": {}}

    runs = {
        "page": dict(key="nifty_500", rule=live_rule(), cost=30.0),
        "monthly": dict(key="nifty_500", rule={}, cost=30.0),
        "cost60": dict(key="nifty_500", rule=live_rule(), cost=60.0),
        "cost100": dict(key="nifty_500", rule=live_rule(), cost=100.0),
    }
    keep = {}
    for name, spec in runs.items():
        res = run(close, spec["key"], n500, start=start, rule=spec["rule"], cost=spec["cost"])
        eq = res["equity_curve"]
        eq.index = pd.DatetimeIndex(eq.index)
        st = res["stats"]
        out["runs"][name] = {
            "engine": {k: (float(v) if isinstance(v, (int, float, np.floating)) else v)
                       for k, v in st.items() if not isinstance(v, (list, dict))},
            "curve": curve_stats(eq, n500),
        }
        keep[name] = res
        print(name, json.dumps(out["runs"][name]["curve"]), flush=True)

    res = keep["page"]
    eq = res["equity_curve"]
    out["calendar"] = calendar(eq, n500)
    m = monthly(eq, n500)
    out["months"] = {"n": len(m), "ahead": int((m.s > m.b).sum()), "up": int((m.s > 0).sum()),
                     "best": [str(m.s.idxmax().date()), float(m.s.max())],
                     "worst": [str(m.s.idxmin().date()), float(m.s.min())],
                     "median_lead_pts": float((m.s - m.b).median()),
                     "first_half_lead": float((m.s - m.b)[m.index < "2018-07-01"].mean()),
                     "second_half_lead": float((m.s - m.b)[m.index >= "2018-07-01"].mean())}
    # Weekly series for the chart (Friday closes), strategy and Nifty 500, rebased to 100.
    both = pd.DataFrame({"s": eq, "b": n500.reindex(eq.index).ffill()})
    wk = both.resample("W-FRI").last().dropna() / both.iloc[0] * 100   # 100 at the first fill
    dd = drawdown(eq).resample("W-FRI").last().reindex(wk.index)
    bdd = drawdown(both["b"]).resample("W-FRI").last().reindex(wk.index)
    out["weekly"] = [[str(d.date()), round(float(r.s), 2), round(float(r.b), 2),
                      round(float(dd[d]) * 100, 2), round(float(bdd[d]) * 100, 2)] for d, r in wk.iterrows()]
    out["stale_exits"] = stale_exits(res, close)
    ct = res["closed_trades"]
    closed = ct[(ct["Status"] == "Closed") & ct["Return %"].notna()]
    out["trades"] = {"closed": len(closed), "won": float((closed["Return %"] > 0).mean()),
                     "open": int((ct["Status"] == "Open").sum())}
    mon = res["monthly"]
    out["turnover"] = {"avg_pct": float(mon["Turnover %"].mean()),
                       "cost_drag_total": float(res["stats"]["cost_drag_total"])}

    # Rebalances that held fewer than 20 names (the rest in cash at 0%).
    short = mon[mon["Holdings"] < 20]
    out["short_books"] = {"n": len(short), "min": int(mon["Holdings"].min()),
                          "dates": [str(pd.Timestamp(d).date()) for d in short["Period Start"]][:40]}

    # NSE's own index store (S168): Total Market, the momentum indices, dividend yields.
    store = pd.read_parquet(ROOT / "data" / "nse_indices_history.parquet")
    store["date"] = pd.to_datetime(store["date"])

    def idx(key: str) -> pd.Series:
        s = store[store["key"] == key].set_index("date")["close"].sort_index()
        return s[~s.index.duplicated()]

    n500_dy = store[store["key"] == "nifty_500"].set_index("date")["div_yield"]
    out["nifty500_div_yield"] = {"mean_2012_2026": float(n500_dy.mean()),
                                 "first": str(n500_dy.index.min().date()), "last": float(n500_dy.iloc[-1])}

    def window(eqs: pd.Series, others: dict[str, pd.Series], start: str) -> dict:
        e = eqs.loc[start:]
        res_ = {"from": str(e.index[0].date()), "to": str(e.index[-1].date())}
        yrs = (e.index[-1] - e.index[0]).days / 365.25
        res_["years"] = yrs
        res_["strategy"] = float((e.iloc[-1] / e.iloc[0]) ** (1 / yrs) - 1)
        res_["strategy_max_dd"] = max_drawdown(e)
        for name, s in others.items():
            s = s.reindex(e.index).ffill()
            res_[name] = float((s.iloc[-1] / s.iloc[0]) ** (1 / yrs) - 1)
            res_[name + "_max_dd"] = max_drawdown(s)
        return res_

    tm, mom30 = idx("nifty_total_market"), idx("nifty200_momentum_30")
    # From the first month-end after Total Market went live (14 Oct 2021).
    out["since_tm"] = window(eq, {"nifty500": n500, "total_market": tm}, "2021-10-29")
    out["since_mom30"] = window(eq, {"nifty500": n500, "nifty200_momentum_30": mom30}, "2020-08-31")

    # The Total Market universe from its list's first month, against Total Market.
    tm_res = run(close, "nifty_total_market", tm, start=pd.Period("2021-11", "M"), rule=live_rule())
    tq = tm_res["equity_curve"]
    tq.index = pd.DatetimeIndex(tq.index)
    out["tm_universe"] = {"engine": {k: float(tm_res["stats"][k]) for k in
                                     ("total_return", "bench_return", "ann_return", "ann_bench",
                                      "max_drawdown", "sharpe")},
                          "curve": curve_stats(tq, tm),
                          "vs_nifty500": window(tq, {"nifty500": n500, "total_market": tm},
                                                str(tq.index[0].date()))}
    # The three deepest separate falls from a peak (each ends when the peak is regained).
    out["episodes"] = episodes(eq)
    out["bench_episodes"] = episodes(n500.reindex(eq.index).ffill())
    out["bench_dd_now"] = float(drawdown(n500.reindex(eq.index).ffill()).iloc[-1])
    tm_y = tm.resample("YE").last()
    out["tm_years"] = {str(d.year): float(v) for d, v in tm_y.pct_change().dropna().items()}
    out["tm_years"]["2026_to_oct"] = float(tm.loc[:"2026-10-30"].iloc[-1] / tm.loc[:"2025-12-31"].iloc[-1] - 1)
    out["trades"]["median_days"] = float(closed["Holding (Days)"].median())
    out["trades"]["median_return"] = float(closed["Return %"].median())
    Path(a.out).write_text(json.dumps(out, indent=1, default=str))


def episodes(eq: pd.Series, n: int = 3) -> list[dict]:
    dd = drawdown(eq)
    under = dd < 0
    runs = (under != under.shift(fill_value=False)).cumsum()
    rows = []
    for _, seg in dd[under].groupby(runs[under]):
        low = seg.idxmin()
        peak = eq.loc[:seg.index[0]].index[-2] if len(eq.loc[:seg.index[0]]) > 1 else seg.index[0]
        after = eq.loc[seg.index[-1]:]
        recovered = after.index[1] if len(after) > 1 else None
        rows.append({"depth": float(seg.min()), "peak": str(peak.date()), "low": str(low.date()),
                     "recovered": str(recovered.date()) if recovered is not None else None,
                     "days": int((seg.index[-1] - seg.index[0]).days) + 1})
    return sorted(rows, key=lambda r: r["depth"])[:n]


if __name__ == "__main__":
    main()
