"""Relative strength against the index and the Supertrend of that line, as a gate on the
momentum book (owner question, 28 Nov 2026; read-only research).

RS = a stock's adjusted close / the Nifty 500 close. Supertrend on RS uses a CLOSE-ONLY true range
(|change in RS|), because the long file holds closes, not highs and lows: it is not the OHLC
Supertrend a charting site draws. Bullish = trend +1 at the month-end signal close.

Fixed BEFORE any result was read (so a good-looking variant cannot be picked afterwards):
  baseline  the record's rules (TRACK_RECORD_CONFIG), Nifty 500 as it stood, Jan 2010 to date, monthly
            reset, 30 bps: the same run as let_winners_run.py "history / reset to 5%".
  gates     read at the signal close only (the engine rebalances monthly):
            entry = a name can be BOUGHT only if bullish; exit = a held name is SOLD if it turns bearish;
            both  = entry and exit.
  grid      Supertrend (period, multiplier): (10,3) first, then (7,2) (14,3) (10,2) (20,3) as neighbours;
            plus two plain relative-strength tests: RS above its 50D EMA; stock beat the index over 6 months.
  pass rule a variant "works" only if it beats the baseline's a year by 0.5 pts or more in the whole run AND
            in both halves (2010-17, 2018-26), with a worst fall no deeper, AND its neighbours do the same.
            (After docs/RISK_OVERLAYS_2026-11-19.md, which tried 2,781 combinations: 13 passed, all one idea.)

    python scripts/research/rs_supertrend.py <nse_long_close.parquet> [out.json]
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.engine import index_universe as iu  # noqa: E402
from src.engine.backtester import run_backtest  # noqa: E402
from src.engine.metrics import drawdown  # noqa: E402
from src.engine.model_record import record_sector_map  # noqa: E402
from src.engine.track_record import TRACK_RECORD_CONFIG as cfg  # noqa: E402

START = "2010-01-01"
HALF = pd.Timestamp("2018-01-01")


def supertrend_bull(rs: pd.DataFrame, period: int, mult: float) -> pd.DataFrame:
    """Close-only Supertrend on each column of ``rs``; True where the trend is up. NaN RS is False."""
    chg = rs.diff().abs()
    atr = chg.ewm(alpha=1 / period, adjust=False, min_periods=period, ignore_na=True).mean()
    x = rs.to_numpy(float)
    a = atr.to_numpy(float)
    n, k = x.shape
    up = np.full(k, np.nan)
    lo = np.full(k, np.nan)
    trend = np.ones(k, dtype=np.int8)
    out = np.zeros((n, k), dtype=bool)
    prev = np.full(k, np.nan)
    for t in range(n):
        xt, at = x[t], a[t]
        bu, bl = xt + mult * at, xt - mult * at
        ok = np.isfinite(xt) & np.isfinite(at)
        pu = np.where(np.isfinite(up), up, bu)
        pl = np.where(np.isfinite(lo), lo, bl)
        nu = np.where((bu < pu) | (prev > pu), bu, pu)
        nl = np.where((bl > pl) | (prev < pl), bl, pl)
        # flip on a close beyond the band of the previous bar
        flip_up = ok & (xt > up) & np.isfinite(up)
        flip_dn = ok & (xt < lo) & np.isfinite(lo)
        trend = np.where(flip_up, 1, np.where(flip_dn, -1, trend)).astype(np.int8)
        up = np.where(ok, nu, up)
        lo = np.where(ok, nl, lo)
        prev = np.where(np.isfinite(xt), xt, prev)
        out[t] = ok & (trend == 1)
    return pd.DataFrame(out, index=rs.index, columns=rs.columns)


def months_back(idx: pd.DatetimeIndex, months: int) -> np.ndarray:
    """Position of the last session on or before each date's calendar-month-back date (-1 if none)."""
    tgt = idx - pd.DateOffset(months=months)
    return idx.searchsorted(tgt, side="right") - 1


def build_gates(close: pd.DataFrame, bench: pd.Series) -> dict[str, pd.DataFrame]:
    b = bench.reindex(close.index).ffill()
    rs = close.div(b, axis=0)
    gates: dict[str, pd.DataFrame] = {}
    for p, m in ((10, 3.0), (7, 2.0), (14, 3.0), (10, 2.0), (20, 3.0)):
        gates[f"st{p}_{m:g}"] = supertrend_bull(rs, p, m)
    gates["rs_above_ema50"] = rs > rs.ewm(span=50, adjust=False, min_periods=30).mean()
    pos = months_back(close.index, 6)
    ok = pos >= 0
    prior = rs.to_numpy()[np.where(ok, pos, 0)]
    g6 = pd.DataFrame(rs.to_numpy() > prior, index=rs.index, columns=rs.columns)
    g6.loc[~ok] = False
    gates["rs_beats_6m"] = g6
    return gates


def run(close, bench, gate=None, mode="both", index_key="nifty_500", start=START, **extra):
    membership = iu.index_history(index_key)
    cols = sorted(iu.ever_members(membership) & set(close.columns))
    frame = close.loc[:, cols].astype("float64")
    months = (pd.Period(frame.index[-1], "M") - pd.Period(start, "M")).n
    fn = run_backtest
    while hasattr(fn, "__wrapped__"):
        fn = fn.__wrapped__
    g = gate.loc[:, [c for c in cols if c in gate.columns]] if gate is not None else None
    kw = dict(top_n=cfg["top_n"], rebal_freq=21, ema_period=cfg["ema_period"],
              high_pct=cfg["high_pct"], weight_method=cfg["weight_method"], config_weights=cfg["config_weights"],
              cost_bps=cfg["cost_bps"], buffer_n=cfg["buffer_n"], stock_cap=cfg["stock_cap"],
              sector_cap=cfg["sector_cap"], sector_map=record_sector_map(cols), _benchmark_close=bench,
              backtest_months=months, _membership=membership, stateful_history=True,
              history_start=pd.Timestamp(start), _actions=[], extra_gate=g, extra_gate_mode=mode)
    kw.update(extra)
    return fn("rs-test", frame, **kw)


def stats(eq: pd.Series) -> dict:
    def cagr(s):
        if len(s) < 2:
            return float("nan")
        y = (s.index[-1] - s.index[0]).days / 365.25
        return ((s.iloc[-1] / s.iloc[0]) ** (1 / y) - 1) * 100
    return {"a year %": cagr(eq), "2010-17 %": cagr(eq[eq.index < HALF]), "2018-26 %": cagr(eq[eq.index >= HALF]),
            "worst fall %": drawdown(eq).min() * 100}


def main(path: str, out: str | None) -> None:
    close = pd.read_parquet(path)
    if "date" in close.columns:
        close = close.set_index("date")
    close.index = pd.DatetimeIndex(close.index)
    bench = pd.read_csv(ROOT / "data" / "benchmarks.csv", parse_dates=["date"]).set_index("date")["nifty500"]
    gates = build_gates(close, bench)
    rows = {}
    res = run(close, bench)
    eq = pd.Series(res["equity_curve"]).dropna()
    eq.index = pd.DatetimeIndex(eq.index)
    rows["baseline"] = stats(eq)
    rows["baseline"]["turnover"] = None
    print("baseline", {k: round(v, 2) for k, v in rows["baseline"].items() if v is not None}, flush=True)
    for name, g in gates.items():
        for mode in ("entry", "exit", "both"):
            r = run(close, bench, g, mode)
            if r is None:
                continue
            e = pd.Series(r["equity_curve"]).dropna()
            e.index = pd.DatetimeIndex(e.index)
            rows[f"{name}/{mode}"] = stats(e)
            print(name, mode, {k: round(v, 2) for k, v in rows[f"{name}/{mode}"].items() if v is not None}, flush=True)
    df = pd.DataFrame(rows).T
    base = df.loc["baseline"]
    for c in ("a year %", "2010-17 %", "2018-26 %"):
        df[f"{c} vs base"] = df[c] - base[c]
    print("\n" + df.round(2).to_string())
    if out:
        Path(out).write_text(df.round(3).to_json(orient="index", indent=1))


def controls(path: str, seeds: int = 40) -> None:
    """After the grid: (1) how often each gate binds on the baseline's own picks; (2) neighbours of the one
    plain-RS cell that passed (EMA span 20 - 200); (3) a NULL: a random gate that removes as many names as the
    RS gate does, to show how far a filter with no information moves a year's figure."""
    close = pd.read_parquet(path)
    if "date" in close.columns:
        close = close.set_index("date")
    close.index = pd.DatetimeIndex(close.index)
    bench = pd.read_csv(ROOT / "data" / "benchmarks.csv", parse_dates=["date"]).set_index("date")["nifty500"]
    gates = build_gates(close, bench)
    rs = close.div(bench.reindex(close.index).ffill(), axis=0)
    base = run(close, bench)
    tb = base["tradebook"]
    tb = tb[tb["Action"].str.contains("BUY|HOLD")].copy()
    tb["date"] = pd.to_datetime(tb["Period Start"])
    print("\nBind rate on the baseline's own holdings (share failing the gate at the signal close):")
    for name in ("st10_3", "rs_above_ema50", "rs_beats_6m"):
        g = gates[name]
        ok = np.array([bool(g.at[d, sym]) if (d in g.index and sym in g.columns) else False
                       for d, sym in zip(tb["date"], tb["Symbol"])])
        new = tb["Action"].str.contains("BUY").to_numpy()
        print(f"  {name:16s} fail on new buys {100 * (1 - ok[new].mean()):5.1f}%   on kept names {100 * (1 - ok[~new].mean()):5.1f}%")
    print("\nPlain RS above its EMA, other spans (mode both):")
    for span in (20, 30, 40, 50, 70, 100, 150, 200):
        g = rs > rs.ewm(span=span, adjust=False, min_periods=min(30, span)).mean()
        e = pd.Series(run(close, bench, g, "both")["equity_curve"]).dropna()
        e.index = pd.DatetimeIndex(e.index)
        st = stats(e)
        print(f"  span {span:3d}  {st['a year %']:.2f}  2010-17 {st['2010-17 %']:.2f}  2018-26 {st['2018-26 %']:.2f}  worst {st['worst fall %']:.1f}")
    bstat = stats(pd.Series(base["equity_curve"]).dropna().set_axis(pd.DatetimeIndex(pd.Series(base["equity_curve"]).dropna().index)))
    g = gates["rs_above_ema50"]
    ok = g.loc[:, [c for c in g.columns]]
    # The RS gate fails 0.6% of the book's new buys and 5% of kept names (above), NOT 71% of all stock-days, so the
    # null removes a matching small share at random from every month-end candidate list.
    rng = np.random.default_rng(7)
    for p_pass in (0.99, 0.95):
        diffs = []
        for _ in range(seeds):
            rg = pd.DataFrame(rng.random(g.shape) < p_pass, index=g.index, columns=g.columns)
            e = pd.Series(run(close, bench, rg, "both")["equity_curve"]).dropna()
            e.index = pd.DatetimeIndex(e.index)
            st = stats(e)
            diffs.append([st["a year %"] - bstat["a year %"], st["2010-17 %"] - bstat["2010-17 %"],
                          st["2018-26 %"] - bstat["2018-26 %"], st["worst fall %"]])
        d = pd.DataFrame(diffs, columns=["a year", "2010-17", "2018-26", "worst fall"])
        print(f"\nNULL: random gate failing {100 * (1 - p_pass):.0f}% of candidates, {seeds} seeds, change against the baseline (pts):")
        print(d.describe(percentiles=[.05, .5, .95]).round(2).to_string())
        print(f"seeds with +0.5 pts in the run and both halves: {int(((d['a year'] >= .5) & (d['2010-17'] >= .5) & (d['2018-26'] >= .5)).sum())} of {seeds}")
        print(f"seeds at or above +1.3 pts in the run: {int((d['a year'] >= 1.3).sum())} of {seeds}")


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[2] == "controls":
        controls(sys.argv[1])
    else:
        main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
