"""Level A screen: does an indicator separate next month's winners from losers AMONG the stocks the
momentum book chooses from? (owner, 28 Nov 2026: "check other indicators ... individual indicators,
combinations"; read-only research.)

Pool at each month-end signal (Nifty 500 as it stood; first signal Apr 2011, after the longest look-back): names that pass the book's own gates
(above the 50D EMA, within 20% of the 52-week closing high) and rank in the top POOL (60 = the 20 holdings plus the
rest of the keep-in-top-40 zone, rounded up) on the live composite score. Forward return: close of the session after
the signal (the engine's fill) to the same session after the next signal, on adjusted closes.

Fixed BEFORE any result was read:
  * each indicator's direction ("+" = a higher reading should do better) is written below, from the literature or
    plain logic, not from the data. A result the other way round is a FAIL, not a flipped signal.
  * statistic: the month's rank correlation (Spearman) between the indicator and the forward return within the
    pool, signed by the direction; the mean over months, its t-statistic, the mean in 2010-17 and 2018-26.
  * the bar: |t| >= 3.0 over the whole run (27 indicators are tried, so the usual 2.0 is too low: Harvey, Liu & Zhu
    2016 argue for about 3) AND the same sign with t >= 1.5 in both halves. Three random columns run beside as a
    placebo: they show how large a t chance gives here.
  * a pass here is only a candidate for the engine test (Level B, with a null); the engine decides, not this.

Close-only: the long file has no highs, lows or opens, so ADX, Stochastic and ATR are written from closes
(efficiency ratio, close-to-close ranges). Volume indicators use traded value in rupees (`nse_long_value`).

    python scripts/research/indicator_screen.py <nse_long_close.parquet> <nse_long_value.parquet> [out.csv]
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.core.config import MOMENTUM_WINDOWS  # noqa: E402
from src.engine import index_universe as iu  # noqa: E402
from src.engine.backtester import _index_mask, _rolling_high_at, _signal_scores  # noqa: E402
from src.engine.calendar_momentum import anchor_frame  # noqa: E402
from src.engine.model_record import record_sector_map  # noqa: E402
from src.engine.track_record import TRACK_RECORD_CONFIG as cfg  # noqa: E402

POOL = 60
START = "2010-01-01"
HALF = pd.Timestamp("2018-01-01")

# name: (direction, group, one-line meaning)
SPEC = {
    "rs_vs_ema50": (+1, "trend", "stock/index ratio above its own 50D EMA"),
    "rel_6m": (+1, "trend", "6-month return minus the Nifty 500's"),
    "macd_hist": (+1, "trend", "(EMA12 - EMA26) / price"),
    "ema50_slope": (+1, "trend", "50D EMA change over a month"),
    "dist_52w_high": (+1, "trend", "close / 52-week closing high (George & Hwang 2004)"),
    "new_high_days": (+1, "trend", "days in the last 20 at a 52-week closing high"),
    "ret_1m": (-1, "reversal", "last month's return (short-term reversal)"),
    "ext_50": (-1, "reversal", "close / 50D EMA - 1 (stretched above its average)"),
    "ext_200": (-1, "reversal", "close / 200D EMA - 1"),
    "rsi14": (-1, "reversal", "Wilder RSI(14) on closes (overbought)"),
    "boll_b": (-1, "reversal", "Bollinger %B(20, 2)"),
    "eff_ratio_50": (+1, "smoothness", "Kaufman efficiency ratio: net move / path length over 50 sessions"),
    "trend_r2": (+1, "smoothness", "R-squared of log price on time, 126 sessions"),
    "clenow": (+1, "smoothness", "annualised slope x R-squared (Clenow), 126 sessions"),
    "fip": (+1, "smoothness", "share of up days minus down days, months 12 to 2 (Da, Gurun & Warachka 2014)"),
    "vol_126": (-1, "risk", "daily-return volatility, 126 sessions"),
    "down_vol_126": (-1, "risk", "downside deviation, 126 sessions"),
    "beta_252": (-1, "risk", "beta to the Nifty 500, 252 sessions"),
    "idio_vol": (-1, "risk", "volatility left after the market's share"),
    "mdd_126": (+1, "risk", "worst fall from a peak inside 126 sessions (less negative is better)"),
    "vol_ratio": (-1, "risk", "21-session volatility / 126-session volatility"),
    "value_surge": (+1, "volume", "traded value, 20 sessions / 120 sessions (Gervais, Kaniel & Mingelgrin 2001)"),
    "up_value_share": (+1, "volume", "share of 40 sessions' traded value on up days (accumulation proxy)"),
    "amihud": (+1, "volume", "mean |return| / traded value, 126 sessions (illiquidity premium)"),
    "log_value": (-1, "volume", "median daily traded value (a size / liquidity proxy; smaller does better)"),
    "industry_3m": (+1, "industry", "equal-weighted 3-month return of the stock's industry (Moskowitz & Grinblatt 1999)"),
    "vs_industry_6m": (+1, "industry", "6-month return minus its industry's"),
}


def back(idx: pd.DatetimeIndex, months: int) -> np.ndarray:
    """Row of the last session on or before the same date `months` earlier (0 where none)."""
    pos = idx.searchsorted(idx - pd.DateOffset(months=months), side="right") - 1
    return np.where(pos < 0, 0, pos)


def months_ret(pf: pd.DataFrame, months: int) -> pd.DataFrame:
    return pd.DataFrame(pf.to_numpy() / pf.to_numpy()[back(pf.index, months)] - 1, index=pf.index, columns=pf.columns)


def build(pf: pd.DataFrame, bench: pd.Series, val: pd.DataFrame, sector: dict[str, str]) -> dict[str, pd.DataFrame]:
    r = pf.pct_change(fill_method=None)
    rb = bench.pct_change(fill_method=None)
    ema = lambda s, n: s.ewm(span=n, adjust=False, min_periods=min(n, 30)).mean()  # noqa: E731
    P: dict[str, pd.DataFrame] = {}
    rs = pf.div(bench, axis=0)
    P["rs_vs_ema50"] = rs / ema(rs, 50) - 1
    P["rel_6m"] = months_ret(pf, 6).sub(months_ret(bench.to_frame("b"), 6)["b"], axis=0)
    P["macd_hist"] = (ema(pf, 12) - ema(pf, 26)) / pf
    e50 = ema(pf, 50)
    P["ema50_slope"] = e50 / e50.shift(21) - 1
    hi = pf.rolling("365D", min_periods=126).max()
    P["dist_52w_high"] = pf / hi
    P["new_high_days"] = (pf >= hi).astype(float).where(hi.notna()).rolling(20, min_periods=15).sum()
    P["ret_1m"] = months_ret(pf, 1)
    P["ext_50"] = pf / e50 - 1
    P["ext_200"] = pf / ema(pf, 200) - 1
    g = r.clip(lower=0).ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    l_ = (-r.clip(upper=0)).ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    P["rsi14"] = 100 - 100 / (1 + g / l_.replace(0, np.nan))
    ma20, sd20 = pf.rolling(20).mean(), pf.rolling(20).std()
    P["boll_b"] = (pf - (ma20 - 2 * sd20)) / (4 * sd20)
    path = pf.diff().abs().rolling(50).sum()
    P["eff_ratio_50"] = (pf - pf.shift(50)).abs() / path
    lp = np.log(pf)
    t = pd.Series(np.arange(len(pf), dtype=float), index=pf.index)
    c = lp.rolling(126, min_periods=100).corr(t)
    P["trend_r2"] = c ** 2
    slope = (c * lp.rolling(126, min_periods=100).std()).div(t.rolling(126, min_periods=100).std(), axis=0)
    P["clenow"] = (np.exp(slope * 252) - 1) * c ** 2
    up, dn = (r > 0).astype(float), (r < 0).astype(float)
    nz = r.notna().astype(float)
    P["fip"] = ((up - dn).where(r.notna()).rolling(231, min_periods=180).mean()).shift(21)
    del nz
    P["vol_126"] = r.rolling(126, min_periods=100).std() * np.sqrt(252)
    P["down_vol_126"] = np.sqrt((r.clip(upper=0) ** 2).rolling(126, min_periods=100).mean() * 252)
    beta = r.rolling(252, min_periods=200).cov(rb).div(rb.rolling(252, min_periods=200).var(), axis=0)
    P["beta_252"] = beta
    P["idio_vol"] = np.sqrt(((P["vol_126"] ** 2) - (beta ** 2).mul((rb.rolling(126).std() * np.sqrt(252)) ** 2, axis=0)).clip(lower=0))
    P["mdd_126"] = (pf / pf.rolling(126, min_periods=100).max()).rolling(126, min_periods=100).min() - 1
    P["vol_ratio"] = r.rolling(21).std() / r.rolling(126, min_periods=100).std()
    v = val.reindex(index=pf.index, columns=pf.columns)
    P["value_surge"] = v.rolling(20, min_periods=15).mean() / v.rolling(120, min_periods=90).mean()
    P["up_value_share"] = (v * (r > 0)).rolling(40, min_periods=30).sum() / v.rolling(40, min_periods=30).sum()
    P["amihud"] = (r.abs() / v.replace(0, np.nan)).rolling(126, min_periods=100).mean()
    P["log_value"] = np.log(v.rolling(126, min_periods=100).median().replace(0, np.nan))
    lab = pd.Series({s: sector.get(s, "Other") for s in pf.columns})
    r3, r6 = months_ret(pf, 3), months_ret(pf, 6)
    P["industry_3m"] = r3.T.groupby(lab).transform("mean").T
    P["vs_industry_6m"] = r6 - r6.T.groupby(lab).transform("mean").T
    return P


def monthly_ics(close_path: str, value_path: str, n_placebo: int = 3) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Each month's signed rank correlation (IC) and good-third-minus-bad-third spread, per indicator."""
    close = pd.read_parquet(close_path)
    close.index = pd.DatetimeIndex(close.index)
    value = pd.read_parquet(value_path)
    value.index = pd.DatetimeIndex(value.index)
    bench = pd.read_csv(ROOT / "data" / "benchmarks.csv", parse_dates=["date"]).set_index("date")["nifty500"]
    membership = iu.index_history("nifty_500")
    cols = sorted(iu.ever_members(membership) & set(close.columns))
    prices = close.loc[:, cols].astype("float64")
    bench = bench.reindex(prices.index).ffill()
    pf = prices.ffill()
    sector = record_sector_map(cols)
    ind = build(pf, bench, value.reindex(columns=cols), sector)
    rng = np.random.default_rng(11)
    placebos = [f"placebo_{k + 1}" for k in range(n_placebo)]   # drawn afresh for each month's pool

    weights = np.array(cfg["config_weights"], float)
    weights = list(weights / weights.sum())
    log_ret = np.log(prices / prices.shift(1).replace(0, np.nan))
    anchor = anchor_frame(prices)
    ema50 = prices.ewm(span=cfg["ema_period"]).mean()
    dates = prices.index
    month_last = pd.Series(dates, index=dates).groupby([dates.year, dates.month]).max().to_numpy()
    sig = [d for d in month_last if d >= pd.Timestamp(START) + pd.DateOffset(months=15)]
    pos = {d: dates.get_loc(d) for d in sig}

    ic: dict[str, list] = {n: [] for n in ["composite", *ind, *placebos]}
    sp: dict[str, list] = {n: [] for n in ["composite", *ind, *placebos]}
    when = []
    for a, b in zip(sig[:-1], sig[1:], strict=True):
        i, j = pos[a], pos[b]
        if i + 1 >= len(dates) or j + 1 >= len(dates):
            continue
        p = prices.iloc[i]
        valid = (p > ema50.iloc[i]) & (p >= _rolling_high_at(prices, i) * cfg["high_pct"]) & (p > 0)
        mask = _index_mask(membership, prices.columns, a)
        if mask is not None:
            valid &= mask
        score = _signal_scores(prices, log_ret, i, MOMENTUM_WINDOWS, weights, anchor=anchor, metric="sharpe",
                               members=mask, on=a, members_from=None)
        pool = score[valid & score.notna()].sort_values(ascending=False).head(POOL).index
        fwd = (pf.iloc[j + 1] / pf.iloc[i + 1] - 1)[pool]
        ok = fwd.notna()
        if ok.sum() < 30:
            continue
        when.append(a)
        for n in ic:
            x = (score[pool] if n == "composite" else
                 pd.Series(rng.standard_normal(len(pool)), index=pool) if n in placebos else ind[n].iloc[i][pool])
            d = 1 if n == "composite" else (SPEC[n][0] if n in SPEC else 1)
            m = ok & x.notna() & np.isfinite(x)
            if m.sum() < 30 or x[m].nunique() < 5:
                ic[n].append(np.nan)
                sp[n].append(np.nan)
                continue
            xs, ys = x[m] * d, fwd[m]
            ic[n].append(xs.rank().corr(ys.rank()))
            third = max(int(m.sum() // 3), 1)
            order = xs.sort_values(ascending=False).index
            sp[n].append(ys[order[:third]].mean() - ys[order[-third:]].mean())
    idx = pd.DatetimeIndex(when)
    return pd.DataFrame(ic, index=idx), pd.DataFrame(sp, index=idx)


def main(close_path: str, value_path: str, out: str | None) -> None:
    ic_df, sp_df = monthly_ics(close_path, value_path)
    idx = ic_df.index
    res = []
    for n in ic_df.columns:
        s = ic_df[n].dropna()
        w = sp_df[n].dropna() * 100
        h1, h2 = s[s.index < HALF], s[s.index >= HALF]
        tt = lambda x: x.mean() / (x.std(ddof=1) / np.sqrt(len(x))) if len(x) > 3 else np.nan  # noqa: E731
        res.append({"indicator": n, "group": SPEC.get(n, ("", "placebo" if n.startswith("placebo") else "ref"))[1],
                    "months": len(s), "mean IC": s.mean(), "t": tt(s), "t 2010-17": tt(h1), "t 2018-26": tt(h2),
                    "good third minus bad third, %/mo": w.mean(), "months IC>0 %": (s > 0).mean() * 100})
    df = pd.DataFrame(res).set_index("indicator")
    real = df[~df.index.str.startswith("placebo") & (df.index != "composite")]
    df["PASS"] = ((df["t"] >= 3.0) & (df["t 2010-17"] >= 1.5) & (df["t 2018-26"] >= 1.5)).astype(object)
    df.loc[df.index.str.startswith("placebo") | (df.index == "composite"), "PASS"] = "-"
    pd.set_option("display.width", 220)
    print(f"{len(idx)} month-end signals {idx[0]:%b %Y} - {idx[-1]:%b %Y}, pool = top {POOL} of the book's gate-passers")
    print(df.round(3).sort_values("t", ascending=False).to_string())
    print(f"\npassing the bar: {int((df['PASS'] == True).sum())} of {len(real)}; "
          f"largest |t| among the 3 placebos: {df.filter(like='placebo', axis=0)['t'].abs().max():.2f}")
    if out:
        df.round(4).to_csv(out)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
