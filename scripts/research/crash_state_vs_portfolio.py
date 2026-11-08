"""Do the crash conditions describe our portfolio, or only the momentum factor?
(owner, 8 Nov 2026; TODO S110). Read-only research.

The Dashboard's "Is momentum risky?" quotes the momentum factor's next month
(top fifth minus bottom fifth). The portfolio is long-only, 20 names, with
trend filters and a buffer, so it can behave differently. This runs the
record's configuration on NSE's long file over the Nifty 500 as it stood
(the Backtest page's History from 2010), then tabulates the portfolio's next
month, absolute and against the Nifty 500, by the state at each month-end.

    python scripts/research/crash_state_vs_portfolio.py <nse_long_close.parquet>
"""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.engine import momentum_crash as mc  # noqa: E402


def portfolio_months(close: pd.DataFrame, bench: pd.Series) -> pd.DataFrame:
    """The shared run (src/engine/portfolio_history), with the month as a Period and the excess."""
    from src.engine.portfolio_history import portfolio_months as shared

    out = shared(close, bench)
    out["month"] = pd.PeriodIndex(out["month"], freq="M")
    out = out.rename(columns={"portfolio": "port", "nifty500": "n500"})
    out["excess"] = out["port"] - out["n500"]
    return out


def main(path: str) -> None:
    close = pd.read_parquet(path)
    if "date" in close.columns:
        close = close.set_index("date")
    close.index = pd.DatetimeIndex(close.index)
    bench = pd.read_csv(ROOT / "data" / "benchmarks.csv", parse_dates=["date"]).set_index("date")["nifty500"]
    pm = portfolio_months(close, bench)
    states = mc.month_end_states(bench)
    # The state at a month-end describes the NEXT month's return.
    states["month"] = states["date"].dt.to_period("M") + 1
    m = states.merge(pm, on="month")
    spread = pd.read_csv(ROOT / "data" / "momentum_health.csv")
    m = m.merge(spread[["month", "spread"]].assign(month=lambda d: pd.PeriodIndex(d["month"], freq="M")),
                on="month", how="left")
    print(f"months {len(m)}: {m['month'].iloc[0]} to {m['month'].iloc[-1]}")
    cagr = (1 + pm["port"] / 100).prod() ** (12 / len(pm)) - 1
    print(f"portfolio {cagr:.1%} a year; Nifty 500 {(1 + pm['n500'] / 100).prod() ** (12 / len(pm)) - 1:.1%}")
    rows = []
    for state in (mc.CRASH, mc.ELEVATED, mc.CALM):
        g = m[m["state"] == state]
        if g.empty:
            continue
        rows.append({"state": state, "months": len(g),
                     "portfolio": g["port"].mean(), "nifty500": g["n500"].mean(), "excess": g["excess"].mean(),
                     "excess<0": (g["excess"] < 0).mean(), "worst excess": g["excess"].min(),
                     "factor spread": g["spread"].mean()})
    print(pd.DataFrame(rows).round(2).to_string(index=False))
    print("\nworst 8 portfolio months against the Nifty 500:")
    print(m.nsmallest(8, "excess")[["month", "port", "n500", "excess", "state"]].round(1).to_string(index=False))
    print("\ncorrelation of portfolio excess with the factor spread:", round(m["excess"].corr(m["spread"]), 2))
    blocks(m)
    m.to_csv(Path(path).with_name("crash_state_vs_portfolio.csv"), index=False)


def _rank_corr(a: pd.Series, b: pd.Series) -> float:
    return float(a.rank().corr(b.rank()))   # Spearman (no scipy)


def blocks(m: pd.DataFrame) -> None:
    """The same tests in 5-year blocks (owner, 8 Nov 2026): a signal should hold in most."""
    m = m.copy()
    year = m["month"].dt.year
    m["block"] = pd.cut(year, [2009, 2014, 2019, 2024, 2030], labels=["2010-14", "2015-19", "2020-24", "2025-26"])
    rows = []
    for blk, g in m.groupby("block", observed=True):
        risky = g[g["state"] != mc.CALM]
        calm = g[g["state"] == mc.CALM]
        rows.append({
            "block": blk, "months": len(g),
            "crash/elev months": f"{(g['state'] == mc.CRASH).sum()}/{(g['state'] == mc.ELEVATED).sum()}",
            "excess calm": calm["excess"].mean(), "excess risky": risky["excess"].mean() if len(risky) else float("nan"),
            "rho excess~ret24": _rank_corr(g["ret24"], g["excess"]),
            "rho excess~volpct": _rank_corr(g["vol_pct"], g["excess"]),
            "rho port~ret24": _rank_corr(g["ret24"], g["port"]),
            "rho spread~volpct": _rank_corr(g["vol_pct"], g["spread"]),
        })
    print("\n5-year blocks (excess = portfolio minus Nifty 500, next month, pts; rho = rank correlation):")
    print(pd.DataFrame(rows).round(2).to_string(index=False))


if __name__ == "__main__":
    main(sys.argv[1])
