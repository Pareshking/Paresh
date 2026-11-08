"""Four rebalancing rules, before and after an estimate of Indian capital-gains tax
(owner, 8 Nov 2026: "do research ... for all 4 cases using the backtest we already
have"; read-only research, TODO S111).

  1 monthly_reset   every holding back to 5% each month (the record until 30 Nov 2026)
  2 owner           winners run to 15%; each new buy is 5% of the account at the last
                    31 March, paid from cash (fewer shares when short); leftover cash
  3 annual_reset    as 2, and every holding back to 5% once a year (the March signal)
  4 semi_reset      as 2, and every holding back to 5% twice a year (March, September),
                    like NSE's momentum indices (semi-annual) and one Weekend Investing basket

The backtester runs each rule (same selection, filters, buffer, 30 bps). A share-lot
replay of every rebalance then estimates tax:
  short-term (held 12 months or less) 20% + 4% cess = 20.8%; long-term 12.5% + 4% = 13%
  above Rs 1.25 lakh a year; short-term losses offset either, long-term losses only
  long-term; unused losses carry forward; tax paid at the first rebalance after 31 March.
Simplifications, said plainly: today's rates for every year since 2010 (they were lower
before July 2024: 15% / 10% above Rs 1 lakh); no dividends; no surcharge; the account
starts at Rs 1 crore. The replay without tax is checked against the backtest's own return.

    python scripts/research/rebalance_rules_after_tax.py <nse_long_close.parquet>
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import src.engine.backtester as bt  # noqa: E402
from src.engine import index_universe as iu  # noqa: E402
from src.engine.model_record import record_sector_map  # noqa: E402
from src.engine.track_record import TRACK_RECORD_CONFIG as cfg  # noqa: E402

CAPITAL = 1e7
ST_RATE, LT_RATE, LT_EXEMPT = 0.208, 0.13, 125_000.0
COST = 0.003 / 2           # the backtest charges 30 bps on one-way turnover (sum|dw|/2)


def fy(d: pd.Timestamp) -> int:
    return d.year if d.month >= 4 else d.year - 1


class Replay:
    """Shares and lots through every rebalance the backtest strikes."""

    def __init__(self, start: pd.Timestamp, taxed: bool):
        self.start, self.taxed = start, taxed
        self.lots: dict[str, list[list]] = {}
        self.cash = 0.0
        self.live = False
        self.fy = None
        self.gain = {"st": 0.0, "lt": 0.0}
        self.carry = {"st": 0.0, "lt": 0.0}      # losses carried forward (positive numbers)
        self.tax_paid = 0.0
        self.curve: dict[pd.Timestamp, float] = {}

    def value(self, px: pd.Series) -> float:
        held = sum(sh * float(px.get(s, np.nan)) if np.isfinite(px.get(s, np.nan)) else sh * cost
                   for s, lots in self.lots.items() for sh, cost, _ in lots)
        return self.cash + held

    def _settle(self) -> float:
        st, lt = self.gain["st"] - self.carry["st"], self.gain["lt"] - self.carry["lt"]
        self.carry = {"st": 0.0, "lt": 0.0}
        if lt < 0:
            self.carry["lt"] = -lt
            lt = 0.0
        if st < 0:                                # a short-term loss offsets long-term gains
            use = min(-st, lt)
            lt -= use
            st += use
            if st < 0:
                self.carry["st"] = -st
                st = 0.0
        self.gain = {"st": 0.0, "lt": 0.0}
        return ST_RATE * st + LT_RATE * max(lt - LT_EXEMPT, 0.0)

    def rebalance(self, date: pd.Timestamp, px: pd.Series, target: pd.Series) -> None:
        if not self.live:
            if date < self.start:
                return
            self.live, self.cash, self.fy = True, CAPITAL, fy(date)
        value = self.value(px)
        if self.taxed and fy(date) != self.fy:
            tax = self._settle()
            self.tax_paid += tax
            self.cash -= tax
            value -= tax
        self.fy = fy(date)
        tgt = target[target > 0]
        tgt = tgt[[np.isfinite(px.get(s, np.nan)) and px.get(s) > 0 for s in tgt.index]]
        cur = {s: sum(sh for sh, _, _ in lots) * float(px.get(s)) for s, lots in self.lots.items()
               if np.isfinite(px.get(s, np.nan))}
        traded = sum(abs(float(tgt.get(s, 0.0)) * value - cur.get(s, 0.0)) for s in set(cur) | set(tgt.index))
        value_net = value - COST * traded
        self.cash -= COST * traded
        for s in list(self.lots):                     # sells first, oldest lot first
            p = px.get(s, np.nan)
            if not np.isfinite(p):
                continue
            want = float(tgt.get(s, 0.0)) * value_net / p
            have = sum(sh for sh, _, _ in self.lots[s])
            sell = have - want
            while sell > 1e-9 and self.lots[s]:
                sh, cost, when = self.lots[s][0]
                take = min(sh, sell)
                bucket = "lt" if (date - when).days > 365 else "st"
                self.gain[bucket] += take * (p - cost)
                self.cash += take * p
                sell -= take
                if take >= sh - 1e-12:
                    self.lots[s].pop(0)
                else:
                    self.lots[s][0][0] = sh - take
            if not self.lots[s]:
                del self.lots[s]
        for s, w in tgt.items():                      # then buys
            p = float(px[s])
            have = sum(sh for sh, _, _ in self.lots.get(s, []))
            buy = w * value_net / p - have
            if buy > 1e-9:
                self.lots.setdefault(s, []).append([buy, p, date])
                self.cash -= buy * p
        self.curve[date] = self.value(px)

    def finish(self, date: pd.Timestamp, px: pd.Series) -> dict:
        v = self.value(px)
        self.curve[date] = v
        out = {"value": v, "tax_paid": self.tax_paid}
        if self.taxed:                                # liquidate: tax on what is still unrealised
            gain = dict(self.gain)
            for s, lots in self.lots.items():
                p = px.get(s, np.nan)
                if np.isfinite(p):
                    for sh, cost, when in lots:
                        gain["lt" if (date - when).days > 365 else "st"] += sh * (p - cost)
            self.gain = gain
            out["after_liquidation"] = v - self._settle()
        return out


def run(close, bench, key, start, rule):
    membership = iu.index_history(key)
    cols = sorted(iu.ever_members(membership) & set(close.columns))
    frame = close.loc[:, cols].astype("float64")
    months = (pd.Period(frame.index[-1], "M") - pd.Period(start, "M")).n
    fn = bt.run_backtest
    while hasattr(fn, "__wrapped__"):
        fn = fn.__wrapped__
    replays = [Replay(pd.Timestamp(start), taxed=False), Replay(pd.Timestamp(start), taxed=True)]
    seen = {}
    orig_drift, orig_step = bt._drift_holdings, bt._step_portfolio_allocation

    def drift(prev_weights, prices, from_idx, to_idx):
        seen["prices"], seen["idx"] = prices, to_idx
        return orig_drift(prev_weights, prices, from_idx, to_idx)

    def step(wts, prev_weights, columns, cost_bps):
        out = orig_step(wts, prev_weights, columns, cost_bps)
        p, i = seen["prices"], seen["idx"]
        for r in replays:
            r.rebalance(pd.Timestamp(p.index[i]), p.iloc[i], out[0])
        return out

    bt._drift_holdings, bt._step_portfolio_allocation = drift, step
    try:
        res = fn(f"rr-{key}-{rule}", frame, top_n=cfg["top_n"], rebal_freq=21, ema_period=cfg["ema_period"],
                 high_pct=cfg["high_pct"], weight_method=cfg["weight_method"],
                 config_weights=cfg["config_weights"], cost_bps=cfg["cost_bps"], buffer_n=cfg["buffer_n"],
                 stock_cap=cfg["stock_cap"], sector_cap=cfg["sector_cap"], sector_map=record_sector_map(cols),
                 _benchmark_close=bench, backtest_months=months, _membership=membership,
                 stateful_history=True, history_start=pd.Timestamp(start), _actions=[], **RULES[rule])
    finally:
        bt._drift_holdings, bt._step_portfolio_allocation = orig_drift, orig_step
    last = frame.ffill().iloc[-1]
    end = pd.Timestamp(frame.index[-1])
    return res, [r.finish(end, last) for r in replays]


RULES = {
    "1 monthly_reset": {},
    "2 owner": {"hold_cap": 0.15, "buy_size": 0.05},
    "3 annual_reset": {"hold_cap": 0.15, "buy_size": 0.05, "weight_reset_months": (3,)},
    "4 semi_reset": {"hold_cap": 0.15, "buy_size": 0.05, "weight_reset_months": (3, 9)},
}


def cagr(v0, v1, years):
    return ((v1 / v0) ** (1 / years) - 1) * 100


def main(path: str) -> None:
    close = pd.read_parquet(path)
    if "date" in close.columns:
        close = close.set_index("date")
    close.index = pd.DatetimeIndex(close.index)
    bench = pd.read_csv(ROOT / "data" / "benchmarks.csv", parse_dates=["date"]).set_index("date")["nifty500"]
    rows = {}
    for label, key, start in (("history 2010-26 (Nifty 500)", "nifty_500", "2010-01-01"),
                              ("record 2026 (750)", "nifty_total_market", "2026-01-01")):
        for rule in RULES:
            res, (pre, post) = run(close, bench, key, start, rule)
            eq = pd.Series(res["equity_curve"]).dropna()
            eq.index = pd.DatetimeIndex(eq.index)
            yrs = (eq.index[-1] - eq.index[0]).days / 365.25
            row = {
                "backtest a year %": cagr(eq.iloc[0], eq.iloc[-1], yrs),
                "replay pre-tax a year %": cagr(CAPITAL, pre["value"], yrs),
                "after tax paid a year %": cagr(CAPITAL, post["value"], yrs),
                "after tax if sold at end a year %": cagr(CAPITAL, post["after_liquidation"], yrs),
                "tax paid, Rs lakh": post["tax_paid"] / 1e5,
                "worst drawdown %": (eq / eq.cummax() - 1).min() * 100,
                "volatility %": eq.pct_change().dropna().std() * np.sqrt(252) * 100,
            }
            rows[(label, rule)] = row
            print(label, rule, {k: round(v, 2) for k, v in row.items()}, flush=True)
    print("\n" + pd.DataFrame(rows).T.round(2).to_string())


if __name__ == "__main__":
    main(sys.argv[1])
