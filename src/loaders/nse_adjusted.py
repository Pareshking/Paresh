"""Adjusted prices from NSE's own daily files.

Owner, 2026-09-27: build NSE adjusted prices and compare the rankings they
give with Screener's; only then make NSE the middle source (Screener, NSE,
Yahoo). This module is the first half and changes nothing the app shows.

The adjustment comes from NSE itself. On an ex-date NSE prints the previous
close already adjusted for the action -- a 1:5 split's previous close is a
fifth of the last traded price -- so

    factor(day) = prev_close(day) / last close before day

is 1 on an ordinary day and the price factor on an ex-date, for splits,
bonuses, consolidations and demergers alike, with no purpose text to parse.
Every price before the ex-date is multiplied by it. Ordinary dividends are
not adjusted (NSE does not adjust the previous close for them; neither does
Screener), which keeps the series comparable with Screener's.

The Bc file's parsed factors are a cross-check, not the source:
`crosscheck_actions` lists the splits and bonuses whose Bc factor and NSE's
step disagree, and the steps with no parsed action behind them.

Pure functions; scripts/nse_compare.py does the I/O.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.loaders.price_source import PriceFrames

SERIES = ("EQ", "BE")          # main board, EQ preferred when both trade
STEP_TOL = 1e-3                # |factor - 1| above this is an adjustment


def wide(prices: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Long NSE rows -> {field: dates x symbols} for close, prev_close, high, low, volume, value.

    Stocks only (index rows dropped), EQ before BE for a symbol that traded
    in both on a day.
    """
    p = prices[prices["series"].isin(SERIES) & (prices["symbol"].fillna("") != "")].copy()
    p["_r"] = (p["series"] != "EQ").astype(int)
    p = (p.sort_values(["date", "symbol", "_r"])
          .drop_duplicates(["date", "symbol"], keep="first"))
    out = {}
    for field in ("close", "prev_close", "high", "low", "volume", "value"):
        out[field] = (p.pivot(index="date", columns="symbol", values=field)
                        .sort_index().astype(float))
    return out


def step_factors(close: pd.DataFrame, prev_close: pd.DataFrame,
                 tol: float = STEP_TOL) -> pd.DataFrame:
    """NSE's adjustment on each day: prev_close / the stock's last close; 1 elsewhere."""
    last = close.ffill().shift(1)
    f = prev_close.reindex_like(close) / last
    step = (f - 1).abs() > tol
    return f.where(step & f.gt(0) & np.isfinite(f), 1.0)


def factor_after(factors: pd.DataFrame) -> pd.DataFrame:
    """For each day, the product of the factors dated after it."""
    f = factors.fillna(1.0)
    return f.iloc[::-1].cumprod().iloc[::-1].shift(-1).fillna(1.0)


def adjust(frame: pd.DataFrame, factors: pd.DataFrame) -> pd.DataFrame:
    """Every price multiplied by the product of the factors dated after it."""
    return frame * factor_after(factors.reindex_like(frame))


def adjusted_frames(prices: pd.DataFrame) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    """({close, high, low, volume, value} adjusted, the step factors)."""
    w = wide(prices)
    f = step_factors(w["close"], w["prev_close"])
    out = {k: adjust(w[k], f) for k in ("close", "high", "low")}
    # Volume moves the other way: a 1:5 split quintuples the share count.
    out["volume"] = w["volume"] / factor_after(f.reindex_like(w["volume"]))
    out["value"] = w["value"]
    return out, f


def events(factors: pd.DataFrame) -> pd.DataFrame:
    """One row per (symbol, date) where NSE adjusted the previous close."""
    s = factors.stack()
    s = s[(s - 1).abs() > STEP_TOL]
    return (s.rename("factor").reset_index()
             .rename(columns={"level_0": "date", "level_1": "symbol"})
             [["symbol", "date", "factor"]])


def crosscheck_actions(factors: pd.DataFrame, actions: pd.DataFrame,
                       tol: float = 0.02) -> dict[str, pd.DataFrame]:
    """Bc splits/bonuses against NSE's steps.

    mismatched  a parsed factor NSE's step disagrees with by more than tol
    missing     a parsed split/bonus with no step on its ex-date
    unparsed    a step with no parsed split/bonus (demergers, special cases)
    """
    ev = events(factors)
    a = actions[actions["kind"].isin(["split", "bonus", "consolidation"])
                & actions["price_factor"].notna() & actions["ex_date"].notna()].copy()
    a["date"] = pd.to_datetime(a["ex_date"]).dt.normalize()
    a = (a.groupby(["symbol", "date"], as_index=False)
          .agg(kind=("kind", lambda k: "+".join(sorted(set(k)))),
               bc_factor=("price_factor", "prod")))
    both = a.merge(ev, on=["symbol", "date"], how="outer", indicator=True)
    matched = both[both["_merge"] == "both"]
    bad = matched[(matched["factor"] / matched["bc_factor"] - 1).abs() > tol]
    in_window = both["date"].between(factors.index.min(), factors.index.max())
    return {
        "mismatched": bad.drop(columns="_merge"),
        "missing": both[(both["_merge"] == "left_only") & in_window].drop(columns="_merge"),
        "unparsed": both[both["_merge"] == "right_only"].drop(columns="_merge"),
    }


def as_price_frames(adjusted: dict[str, pd.DataFrame], symbols: list[str] | None = None,
                    intraday: bool = False) -> PriceFrames:
    """The engine's input, like price_source.from_screener's.

    intraday=False ranks on closes exactly as the Screener ranking does, so
    a comparison measures the prices, not the high/low basis.
    """
    cols = [s for s in (symbols or adjusted["close"].columns) if s in adjusted["close"].columns]
    close = adjusted["close"][cols]
    return PriceFrames(
        adj_close=close, close=close,
        high=adjusted["high"][cols] if intraday else None,
        low=adjusted["low"][cols] if intraday else None,
        volume=adjusted["volume"][cols], source="nse", intraday=intraday,
        notes=["NSE closes, adjusted with NSE's own previous-close steps"],
    )


def level_drift(nse_close: pd.DataFrame, other_close: pd.DataFrame,
                sessions: int = 400) -> pd.DataFrame:
    """Per stock, how far the NSE/other price ratio wanders over the window.

    Two correctly adjusted series differ by a constant at most (none, for
    Screener); a drift means one side adjusted an action the other did not.
    """
    common = [c for c in nse_close.columns if c in other_close.columns]
    a = nse_close[common].tail(sessions)
    b = other_close.reindex(index=a.index, columns=common)
    ratio = a / b
    med = ratio.median()
    dev = (ratio / med - 1).abs()
    out = pd.DataFrame({
        "median_ratio": med,
        "max_drift": dev.max(),
        "worst_date": dev.idxmax(),
        "days": ratio.notna().sum(),
    })
    return out.dropna(subset=["max_drift"]).sort_values("max_drift", ascending=False)


def compare_rankings(a: pd.DataFrame, b: pd.DataFrame, top: tuple[int, ...] = (20, 50)) -> dict:
    """Two ranking tables (Symbol, Rank) side by side."""
    m = a[["Symbol", "Rank"]].merge(b[["Symbol", "Rank"]], on="Symbol", how="outer",
                                    suffixes=("_a", "_b"))
    both = m.dropna()
    out = {
        "a_rows": int(a["Rank"].notna().sum()), "b_rows": int(b["Rank"].notna().sum()),
        "common": len(both),
        # Spearman as the Pearson correlation of ranks: pandas' own
        # method="spearman" needs scipy, which the app does not install.
        "spearman": (float(both["Rank_a"].rank().corr(both["Rank_b"].rank()))
                     if len(both) > 2 else float("nan")),
        "only_a": sorted(m.loc[m["Rank_b"].isna(), "Symbol"]),
        "only_b": sorted(m.loc[m["Rank_a"].isna(), "Symbol"]),
    }
    for n in top:
        ta = set(a.nsmallest(n, "Rank")["Symbol"])
        tb = set(b.nsmallest(n, "Rank")["Symbol"])
        out[f"top{n}_overlap"] = len(ta & tb)
        out[f"top{n}_only_a"] = sorted(ta - tb)
        out[f"top{n}_only_b"] = sorted(tb - ta)
    both = both.assign(shift=(both["Rank_a"] - both["Rank_b"]).abs())
    out["largest_moves"] = both.sort_values("shift", ascending=False).head(15)
    return out
