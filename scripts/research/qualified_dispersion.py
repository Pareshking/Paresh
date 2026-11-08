"""Share qualified and return dispersion, each month-end from 2010, against the
next month's momentum spread (TODO S110, item 2; research, read-only).

Qualified: the strategy's own price gates (backtester.py: close above its
50-day EMA, pandas ewm span 50, and at least 80% of its 52-week high) among
the Nifty 500's point-in-time members. Dispersion: the cross-sectional
standard deviation of the members' returns over the month, the measure of
Stivers and Sun (JFQA 45(4), 2010), who found it negatively related to the
next momentum premium.

    python scripts/research/qualified_dispersion.py <nse_long_close.parquet>
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.engine import index_universe as iu  # noqa: E402
from src.engine.membership import members_on  # noqa: E402


def monthly_readings(close: pd.DataFrame) -> pd.DataFrame:
    hist = iu.index_history("nifty_500")
    ema = close.ewm(span=50).mean()
    high = close.rolling(252, min_periods=200).max()
    ends = close.groupby(close.index.to_period("M")).apply(lambda s: s.index[-1])
    rows = []
    prev = None
    for t in ends:
        if t < pd.Timestamp("2010-01-01"):
            prev = t
            continue
        mem = [s for s in members_on(hist, t) if s in close.columns]
        p = close.loc[t, mem]
        ok = p.notna() & ema.loc[t, mem].notna() & high.loc[t, mem].notna()
        q = ((p > ema.loc[t, mem]) & (p >= 0.8 * high.loc[t, mem]))[ok]
        disp = np.nan
        if prev is not None:
            r = (close.loc[t, mem] / close.loc[prev, mem] - 1).dropna()
            r = r[(r > -0.9) & (r < 3)]
            disp = float(r.std())
        rows.append({"date": t, "members": int(ok.sum()), "qualified_share": float(q.mean()), "dispersion": disp})
        prev = t
    return pd.DataFrame(rows)


def main(path: str) -> None:
    close = pd.read_parquet(path)
    if "date" in close.columns:
        close = close.set_index("date")
    close.index = pd.DatetimeIndex(close.index)
    d = monthly_readings(close)
    sp = pd.read_csv(Path(__file__).resolve().parents[2] / "data" / "momentum_health.csv", parse_dates=["date"])
    d["month"] = d["date"].dt.to_period("M")
    sp["month"] = sp["date"].dt.to_period("M")
    m = d.merge(sp[["month", "spread"]], on="month")
    print(f"months {len(m)}, {m['date'].iloc[0]:%b %Y} to {m['date'].iloc[-1]:%b %Y}")
    print(m[["qualified_share", "dispersion"]].describe().round(3).to_string())
    for col in ("qualified_share", "dispersion"):
        rho = m[col].rank().corr(m["spread"].rank())  # Spearman = Pearson on ranks (no scipy)
        m["q"] = pd.qcut(m[col], 4, labels=["lowest", "2", "3", "highest"])
        g = m.groupby("q", observed=True)["spread"]
        print(f"\n{col}: Spearman with next month's spread {rho:+.2f}")
        print(pd.DataFrame({"months": g.size(), "mean": g.mean().round(2), "share<0": g.apply(lambda s: (s < 0).mean()).round(2),
                            "worst": g.min().round(1)}).to_string())
    print("\nlatest:", m.iloc[-1][["date", "members", "qualified_share", "dispersion"]].to_dict())
    m.drop(columns=["q"]).to_csv(Path(path).with_name("qualified_dispersion.csv"), index=False)


if __name__ == "__main__":
    main(sys.argv[1])
