"""Costs and tax against the alternative (audit 11 Nov 2026, TODO S123 and S124;
read-only research, owner: "I will go with your recommendation").

S123  The History backtest at 30, 50 and 75 bps a round trip, for the record's
      rules (six-monthly reset, the 15% hold cap, 5% buys). The pre-tax figure
      comes from the backtest itself; nothing else changes between the runs.
S124  The strategy after tax (rebalance_rules_after_tax.py's share-lot replay,
      sold at the end) beside a Nifty 500 index position bought at the start and
      sold at the end, taxed once: long-term 12.5% + 4% cess = 13% above Rs 1.25
      lakh. Both price-only (no dividends either side; see S125). Today's rates
      for every year, as in the S111 script. The index position pays no costs
      and no expense ratio, which flatters it slightly.

    python scripts/research/cost_and_index_tax.py <nse_long_close.parquet>
"""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts" / "research"))
import rebalance_rules_after_tax as rr  # noqa: E402

RULE = "4 semi_reset"     # the record's rule from the 30 Nov 2026 signal
WINDOWS = (("Nifty 500 2010-26", "nifty_500", "2010-01-01"),
           ("750 2026", "nifty_total_market", "2026-01-01"))
COSTS = (30.0, 50.0, 75.0)


def index_after_tax(bench: pd.Series, start, end) -> tuple[float, float, float]:
    b = bench.loc[start:end].dropna()
    v = rr.CAPITAL * float(b.iloc[-1] / b.iloc[0])
    held_long = (b.index[-1] - b.index[0]).days > 365
    gain = v - rr.CAPITAL
    tax = (rr.LT_RATE * max(gain - rr.LT_EXEMPT, 0.0) if held_long else rr.ST_RATE * max(gain, 0.0))
    return v, v - tax, (b.index[-1] - b.index[0]).days / 365.25


def main(path: str) -> None:
    close = pd.read_parquet(path)
    if "date" in close.columns:
        close = close.set_index("date")
    close.index = pd.DatetimeIndex(close.index)
    bench = pd.read_csv(ROOT / "data" / "benchmarks.csv", parse_dates=["date"]).set_index("date")["nifty500"]
    orig = dict(rr.cfg)
    for label, key, start in WINDOWS:
        for bps in COSTS:
            rr.cfg["cost_bps"] = bps
            rr.COST = bps / 1e4 / 2
            try:
                res, (pre, post) = rr.run(close, bench, key, start, RULE)
            finally:
                rr.cfg.clear()
                rr.cfg.update(orig)
            eq = pd.Series(res["equity_curve"]).dropna()
            eq.index = pd.DatetimeIndex(eq.index)
            yrs = (eq.index[-1] - eq.index[0]).days / 365.25
            row = {
                "window": label, "cost bps": bps,
                "from": f"{eq.index[0]:%Y-%m-%d}", "to": f"{eq.index[-1]:%Y-%m-%d}",
                "strategy pre-tax %/yr": round(rr.cagr(eq.iloc[0], eq.iloc[-1], yrs), 2),
                "strategy after tax, sold at end %/yr": round(rr.cagr(rr.CAPITAL, post["after_liquidation"], yrs), 2),
            }
            v, v_tax, iyrs = index_after_tax(bench, eq.index[0], eq.index[-1])
            row["index pre-tax %/yr"] = round(rr.cagr(rr.CAPITAL, v, iyrs), 2)
            row["index after tax, sold at end %/yr"] = round(rr.cagr(rr.CAPITAL, v_tax, iyrs), 2)
            row["lead pre-tax pts/yr"] = round(row["strategy pre-tax %/yr"] - row["index pre-tax %/yr"], 2)
            row["lead after tax pts/yr"] = round(row["strategy after tax, sold at end %/yr"]
                                                 - row["index after tax, sold at end %/yr"], 2)
            print(row, flush=True)
    rr.COST = 0.003 / 2


if __name__ == "__main__":
    main(sys.argv[1])
