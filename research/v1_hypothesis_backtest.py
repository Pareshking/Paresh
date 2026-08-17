from __future__ import annotations

import os
from pathlib import Path
from math import sqrt

import numpy as np
import pandas as pd
import requests
import yfinance as yf

NSE_URL = "https://niftyindices.com/IndexConstituent/ind_niftytotalmarket_list.csv"
OUT = Path("research/outputs")
LOOKBACKS = {"1M": 21, "3M": 63, "6M": 126, "9M": 189, "12M": 252}
WEIGHTS = {"1M": .10, "3M": .30, "6M": .30, "9M": .20, "12M": .10}
EQUAL = {k: .20 for k in LOOKBACKS}


def universe() -> list[str]:
    h = {"User-Agent": "Mozilla/5.0"}
    r = requests.get(NSE_URL, headers=h, timeout=30)
    r.raise_for_status()
    df = pd.read_csv(pd.io.common.BytesIO(r.content))
    col = next(c for c in df.columns if str(c).strip().lower() in {"symbol", "ticker"})
    s = df[col].astype(str).str.strip().str.upper()
    return sorted(x for x in s if x and x != "NAN")


def download(symbols: list[str]) -> pd.DataFrame:
    tickers = [s + ".NS" for s in symbols]
    parts = []
    for i in range(0, len(tickers), 100):
        batch = tickers[i:i+100]
        print(f"Downloading {i+1}-{i+len(batch)} / {len(tickers)}")
        x = yf.download(batch, period="10y", auto_adjust=False, progress=False,
                        group_by="ticker", threads=True)
        if x is None or x.empty:
            continue
        if isinstance(x.columns, pd.MultiIndex):
            if "Adj Close" in x.columns.get_level_values(-1):
                p = x.xs("Adj Close", level=-1, axis=1)
            else:
                p = x.xs("Close", level=-1, axis=1)
            p.columns = [str(c).replace(".NS", "").upper() for c in p.columns]
        else:
            p = x[["Adj Close" if "Adj Close" in x.columns else "Close"]].copy()
            p.columns = [batch[0].replace(".NS", "").upper()]
        parts.append(p)
    if not parts:
        raise RuntimeError("No price data downloaded")
    prices = pd.concat(parts, axis=1)
    prices = prices.loc[:, ~prices.columns.duplicated()].sort_index()
    prices.index = pd.to_datetime(prices.index).tz_localize(None)
    return prices.dropna(axis=1, how="all")


def z(s: pd.Series) -> pd.Series:
    s = s.replace([np.inf, -np.inf], np.nan)
    m = s.dropna()
    if len(m) < 20 or m.std(ddof=1) == 0:
        return pd.Series(np.nan, index=s.index)
    lo, hi = m.mean() - 3*m.std(ddof=1), m.mean() + 3*m.std(ddof=1)
    w = m.clip(lo, hi)
    return ((s - w.mean()) / (w.std(ddof=1) + 1e-12)).clip(-3, 3)


def factor(prices: pd.DataFrame, end: int, n: int):
    p = prices.iloc[end-n:end+1]
    r = p.pct_change(fill_method=None).iloc[1:]
    lr = np.log(p / p.shift(1)).iloc[1:]
    p0, p1 = p.iloc[0], p.iloc[-1]
    simple = p1 / p0 - 1
    logr = np.log(p1 / p0)
    sd = lr.std(ddof=1)
    ram_log = logr / (sd * sqrt(len(lr)))
    ram_simple = simple / (sd * sqrt(len(lr)))
    sharpe_ann = r.mean() / r.std(ddof=1) * sqrt(252)
    t = np.arange(len(p), dtype=float)
    lp = np.log(p.clip(lower=.01))
    r2 = lp.corrwith(pd.Series(t, index=lp.index)) ** 2
    pos = (r > 0).sum() / r.notna().sum().replace(0, np.nan)
    neg = (r < 0).sum() / r.notna().sum().replace(0, np.nan)
    fip = np.sign(logr) * (pos - neg)
    return {
        "simple": simple,
        "log": logr,
        "ram_simple": ram_simple,
        "ram_log": ram_log,
        "sharpe_ann": sharpe_ann,
        "ram_r2": ram_log * r2,
        "ram_fip": ram_log * fip,
        "r2": r2,
    }


def composite(factors: dict[str, pd.Series], key: str, weights: dict[str, float]) -> pd.Series:
    parts = []
    for horizon, w in weights.items():
        parts.append(z(factors[horizon][key]).fillna(0) * w)
    return sum(parts)


def skip_month(factors: dict[str, pd.Series], prices: pd.DataFrame, end: int) -> pd.Series:
    n = 252
    p = prices.iloc[end-n:end-20]
    return p.iloc[-1] / p.iloc[0] - 1


def future_return(prices: pd.DataFrame, end: int, months: int) -> pd.Series:
    step = {1:21, 3:63, 6:126, 12:252}[months]
    if end + step >= len(prices):
        return pd.Series(np.nan, index=prices.columns)
    return prices.iloc[end+step] / prices.iloc[end] - 1


def metrics(records: list[dict]) -> pd.DataFrame:
    rows = []
    for model in sorted({r["model"] for r in records}):
        rr = [r for r in records if r["model"] == model]
        out = {"model": model, "snapshots": len(rr)}
        for h in (1, 3, 6, 12):
            ic = [r[f"ic_{h}"] for r in rr if np.isfinite(r[f"ic_{h}"])]
            top = [r[f"top_{h}"] for r in rr if np.isfinite(r[f"top_{h}"])]
            bot = [r[f"bot_{h}"] for r in rr if np.isfinite(r[f"bot_{h}"])]
            spread = [a-b for a,b in zip(top, bot)]
            out[f"rank_ic_{h}m"] = np.nanmean(ic) if ic else np.nan
            out[f"top_{h}m_avg"] = np.nanmean(top) if top else np.nan
            out[f"spread_{h}m_avg"] = np.nanmean(spread) if spread else np.nan
            if top:
                equity = np.cumprod(1 + np.nan_to_num(top, nan=0.0))
                years = len(top) / 12
                out[f"top_{h}m_cagr"] = equity[-1] ** (1/max(years, 1e-9)) - 1
            else:
                out[f"top_{h}m_cagr"] = np.nan
        rows.append(out)
    return pd.DataFrame(rows)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    syms = universe()
    print(f"Universe: {len(syms)}")
    prices = download(syms)
    print(f"Prices: {prices.shape}, {prices.index.min().date()} -> {prices.index.max().date()}")

    # Monthly causal snapshots. Signal at month-end T; forward returns begin after T.
    month_ends = prices.groupby(prices.index.to_period("M")).apply(lambda x: x.index[-1])
    ends = [prices.index.get_loc(d) for d in month_ends]
    ends = [e for e in ends if e >= 260 and e + 252 < len(prices)]
    records = []
    detail = []

    for j, end in enumerate(ends):
        fs = {h: factor(prices, end, n) for h,n in LOOKBACKS.items()}
        models = {
            "simple_return": composite(fs, "simple", EQUAL),
            "log_return": composite(fs, "log", EQUAL),
            "RAM_simple": composite(fs, "ram_simple", EQUAL),
            "RAM_log": composite(fs, "ram_log", EQUAL),
            "Sharpe_annual": composite(fs, "sharpe_ann", EQUAL),
            "RAM_x_R2": composite(fs, "ram_r2", EQUAL),
            "RAM_x_FIP": composite(fs, "ram_fip", EQUAL),
            "RAM_log_default_10_30_30_20_10": composite(fs, "ram_log", WEIGHTS),
            "RAM_x_R2_default_10_30_30_20_10": composite(fs, "ram_r2", WEIGHTS),
            "RAM_log_12M_skip1M": z(skip_month(fs["12M"], prices, end)),
        }
        for model, score in models.items():
            rec = {"model": model}
            for h in (1,3,6,12):
                fwd = future_return(prices, end, h).reindex(score.index)
                valid = score.notna() & fwd.notna()
                if valid.sum() < 30:
                    rec[f"ic_{h}"] = np.nan; rec[f"top_{h}"] = np.nan; rec[f"bot_{h}"] = np.nan
                    continue
                rec[f"ic_{h}"] = score[valid].corr(fwd[valid], method="spearman")
                ranks = score[valid].rank(pct=True)
                rec[f"top_{h}"] = fwd[valid][ranks >= .90].mean()
                rec[f"bot_{h}"] = fwd[valid][ranks <= .10].mean()
            records.append(rec)
            detail.append({"date": prices.index[end], **rec})

    summary = metrics(records).sort_values("rank_ic_6m", ascending=False)
    summary.to_csv(OUT / "v1_hypothesis_summary.csv", index=False)
    pd.DataFrame(detail).to_csv(OUT / "v1_hypothesis_detail.csv", index=False)
    print("\n=== V1 HYPOTHESIS RESULTS ===")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
