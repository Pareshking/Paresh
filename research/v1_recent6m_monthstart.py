from pathlib import Path
import numpy as np
import pandas as pd
import requests
import yfinance as yf

NSE_URL = "https://niftyindices.com/IndexConstituent/ind_niftytotalmarket_list.csv"
OUT = Path("research/outputs")
LOOK = {"1M": 21, "3M": 63, "6M": 126, "9M": 189, "12M": 252}
WEIGHTS = {"1M": .10, "3M": .30, "6M": .30, "9M": .20, "12M": .10}
EQUAL = {k: .20 for k in LOOK}


def universe():
    r = requests.get(NSE_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    r.raise_for_status()
    d = pd.read_csv(pd.io.common.BytesIO(r.content))
    c = next(c for c in d.columns if str(c).strip().lower() in {"symbol", "ticker"})
    return sorted(x for x in d[c].astype(str).str.strip().str.upper() if x and x != "NAN")


def download(symbols):
    parts = []
    tickers = [s + ".NS" for s in symbols]
    for i in range(0, len(tickers), 100):
        x = yf.download(tickers[i:i+100], period="10y", auto_adjust=False,
                        progress=False, group_by="ticker", threads=True)
        if x is None or x.empty:
            continue
        if isinstance(x.columns, pd.MultiIndex):
            levels = x.columns.get_level_values(-1)
            col = "Adj Close" if "Adj Close" in levels else "Close"
            p = x.xs(col, level=-1, axis=1)
            p.columns = [str(c).replace(".NS", "").upper() for c in p.columns]
        else:
            col = "Adj Close" if "Adj Close" in x.columns else "Close"
            p = x[[col]].copy()
            p.columns = [tickers[i].replace(".NS", "").upper()]
        parts.append(p)
    if not parts:
        raise RuntimeError("No price data downloaded")
    p = pd.concat(parts, axis=1)
    p = p.loc[:, ~p.columns.duplicated()].sort_index()
    p.index = pd.to_datetime(p.index).tz_localize(None)
    return p.dropna(axis=1, how="all")


def zscore(s):
    s = s.replace([np.inf, -np.inf], np.nan)
    valid = s.dropna()
    if len(valid) < 20 or valid.std(ddof=1) == 0:
        return pd.Series(np.nan, index=s.index)
    lo = valid.mean() - 3 * valid.std(ddof=1)
    hi = valid.mean() + 3 * valid.std(ddof=1)
    w = valid.clip(lo, hi)
    return ((s - w.mean()) / (w.std(ddof=1) + 1e-12)).clip(-3, 3)


def factor(prices, end, n):
    p = prices.iloc[end-n:end+1]
    r = p.pct_change(fill_method=None).iloc[1:]
    lr = np.log(p / p.shift(1)).iloc[1:]
    sd = lr.std(ddof=1)
    log_return = np.log(p.iloc[-1] / p.iloc[0])
    simple_return = p.iloc[-1] / p.iloc[0] - 1
    sharpe = r.mean() / r.std(ddof=1) * np.sqrt(252)
    t = pd.Series(np.arange(len(p), dtype=float), index=p.index)
    r2 = np.log(p.clip(lower=0.01)).corrwith(t) ** 2
    ram = log_return / (sd * np.sqrt(len(lr)))
    return {
        "simple": simple_return,
        "log": log_return,
        "ram": ram,
        "sharpe": sharpe,
        "r2": ram * r2,
    }


def composite(factors, key, weights):
    return sum(zscore(factors[h][key]).fillna(0) * w for h, w in weights.items())


def future_return(prices, end, months):
    n = {1: 21, 3: 63, 6: 126}[months]
    if end + n >= len(prices):
        return pd.Series(np.nan, index=prices.columns)
    return prices.iloc[end+n] / prices.iloc[end] - 1


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    prices = download(universe())
    last = prices.index.max()

    # Exactly the latest six calendar months, using only the first available
    # trading day of each month as the signal/snapshot date.
    last_month = last.to_period("M")
    first_month = last_month - 5
    recent = prices[prices.index.to_period("M").between(first_month, last_month)]
    snapshot_dates = [g.index[0] for _, g in recent.groupby(recent.index.to_period("M"))]
    ends = [prices.index.get_loc(d) for d in snapshot_dates]

    rows = []
    for end in ends:
        factors = {h: factor(prices, end, n) for h, n in LOOK.items()}
        models = {
            "Simple_Return": composite(factors, "simple", EQUAL),
            "Log_Return": composite(factors, "log", EQUAL),
            "RAM": composite(factors, "ram", EQUAL),
            "Annual_Sharpe": composite(factors, "sharpe", EQUAL),
            "RAM_x_R2": composite(factors, "r2", EQUAL),
            "RAM_Default_10_30_30_20_10": composite(factors, "ram", WEIGHTS),
        }
        for name, score in models.items():
            row = {"model": name, "date": prices.index[end].date().isoformat()}
            for horizon in (1, 3, 6):
                fwd = future_return(prices, end, horizon).reindex(score.index)
                valid = score.notna() & fwd.notna()
                if valid.sum() < 30:
                    row[f"ic_{horizon}m"] = np.nan
                    row[f"top_{horizon}m"] = np.nan
                    row[f"bottom_{horizon}m"] = np.nan
                    row[f"spread_{horizon}m"] = np.nan
                    row[f"n_{horizon}m"] = int(valid.sum())
                else:
                    s = score[valid]
                    f = fwd[valid]
                    q = s.rank(pct=True)
                    row[f"ic_{horizon}m"] = s.corr(f, method="spearman")
                    row[f"top_{horizon}m"] = f[q >= .9].mean()
                    row[f"bottom_{horizon}m"] = f[q <= .1].mean()
                    row[f"spread_{horizon}m"] = row[f"top_{horizon}m"] - row[f"bottom_{horizon}m"]
                    row[f"n_{horizon}m"] = int(valid.sum())
            rows.append(row)

    detail = pd.DataFrame(rows)
    summary_rows = []
    for model, g in detail.groupby("model"):
        row = {"model": model, "snapshots": len(g)}
        for h in (1, 3, 6):
            vals = g[f"ic_{h}m"].dropna()
            row[f"rank_ic_{h}m"] = vals.mean() if len(vals) else np.nan
            row[f"positive_ic_{h}m"] = (vals > 0).mean() if len(vals) else np.nan
            row[f"top_{h}m_avg"] = g[f"top_{h}m"].dropna().mean()
            row[f"spread_{h}m_avg"] = g[f"spread_{h}m"].dropna().mean()
            row[f"matured_snapshots_{h}m"] = int(g[f"ic_{h}m"].notna().sum())
        summary_rows.append(row)

    summary = pd.DataFrame(summary_rows).sort_values("rank_ic_6m", ascending=False, na_position="last")
    detail.to_csv(OUT / "v1_recent6m_monthstart_detail.csv", index=False)
    summary.to_csv(OUT / "v1_recent6m_monthstart_summary.csv", index=False)
    print("SNAPSHOT_DATES", [d.strftime("%Y-%m-%d") for d in snapshot_dates])
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
