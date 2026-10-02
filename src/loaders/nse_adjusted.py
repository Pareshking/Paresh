"""Adjusted prices from NSE's own daily files.

Owner, 2026-09-27: build NSE adjusted prices and compare the rankings they
give with Screener's; only then make NSE the middle source (Screener, NSE,
Yahoo). This module is the first half and changes nothing the app shows.

The adjustment comes from NSE's corporate-actions file (Bc), checked against
the price. NSE's daily price file does NOT adjust its previous close for an
action: on ADANIPOWER's 1:5 split (ex 22 Sep 2025) it printed a previous close
of 709.40 against a close of 170.25 (checked in the first comparison run,
where every split and bonus was missed). So:

  1. each split, bonus or consolidation parsed from Bc (classify_purpose)
     is placed on the first session on or after its ex-date;
  2. it is applied only if the price agrees: the close that session over the
     last close before it is nearer the action's factor than to 1, and
     within 1.5x of it. Bc lists some actions twice under different dates;
     only the date the price actually moved passes. Bc also prints some
     ex-dates month-first; when the listed date fails, the date with day
     and month exchanged is tried;
  2b. a demerger has no factor in its text: it is priced at the ex-date's
     own fall (the value that left with the new company);
  3. every price before the ex-date is multiplied by the factor, volumes
     divided by it.

Ordinary dividends are not adjusted (neither does Screener), which keeps the
series comparable with Screener's. Price jumps beyond 1.8x either way with
no confirmed action are listed (demergers, special cases) but not adjusted.

Pure functions; scripts/nse_compare.py does the I/O.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.loaders.price_source import PriceFrames

SERIES = ("EQ", "BE", "RR")    # main board, EQ preferred; RR: REITs, members of the indices
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


GAP_SHARE = 0.25              # more stocks than this stepping on one day: a missing session
CONFIRM_BAND = np.log(1.5)    # the session's move must be within 1.5x of the action's factor
JUMP = np.log(1.8)            # an unexplained move beyond this either way is listed
ACTION_KINDS = ("split", "bonus", "consolidation")
DEMERGER_FLOOR, DEMERGER_CAP = 0.05, 0.98   # a demerger's fall is applied only inside this


def gap_days(close: pd.DataFrame, prev_close: pd.DataFrame,
             tol: float = STEP_TOL, share: float = GAP_SHARE) -> pd.Series:
    """Days whose previous close is not our previous session's close for most stocks.

    That is a session missing from the record -- NSE traded (a Budget Sunday,
    a muhurat session) and we hold no file for it. Returns the share of
    stocks differing, for those days.
    """
    last = close.ffill().shift(1)
    pc = prev_close.reindex_like(close)
    both = last.notna() & pc.notna()
    differs = ((pc / last - 1).abs() > tol) & both
    frac = differs.sum(axis=1) / both.sum(axis=1).replace(0, np.nan)
    return frac[frac > share]


COPY_SHARE = 0.9              # more stocks than this unchanged in close AND volume: a copy


def copied_sessions(close: pd.DataFrame, volume: pd.DataFrame,
                    share: float = COPY_SHARE) -> pd.Series:
    """Sessions that repeat the one before: an NSE holiday stored as a trading day.

    R2 holds a file for nearly every NSE holiday from 2021 (26 Jan, 15 Aug,
    Diwali...; 2024 shows 265 "sessions" in a year of 262 weekdays), each a copy
    of the session before it, so the next day's previous close still matches.
    A real session never leaves nearly every stock's close and volume exactly
    unchanged. Returns the share of stocks repeated, for those days.
    """
    c, v = close.sort_index(), volume.reindex_like(close.sort_index())
    both = c.notna() & c.shift(1).notna() & v.notna() & v.shift(1).notna()
    same = (c == c.shift(1)) & (v == v.shift(1)) & both
    frac = same.sum(axis=1) / both.sum(axis=1).replace(0, np.nan)
    return frac[frac > share]


def _parsed(actions: pd.DataFrame) -> pd.DataFrame:
    """One row per (symbol, ex-date): the product of its parsed price factors.

    Demergers carry no factor in their text (it depends on the prices); they
    are kept with a NaN factor and priced from the move on the ex-date.
    """
    known = actions["kind"].isin(ACTION_KINDS) & actions["price_factor"].notna()
    a = actions[(known | actions["kind"].eq("demerger")) & actions["ex_date"].notna()].copy()
    # One date type whatever the store held (dates, strings, other resolutions).
    a["date"] = pd.to_datetime(a["ex_date"]).dt.normalize().astype("datetime64[ns]")
    # One action, once. NSE lists the same split in its daily Bc file and in its
    # yearly corporate-action list, worded differently, so both rows survive a
    # dedupe on the text; multiplied, a 1:2 split became x0.25, which no price
    # move confirms, and the split went unapplied (HDFCBANK 2019, ADANIPOWER 2025:
    # 500 of 584 unconfirmed actions in the 2008-2026 audit, 3 Oct 2026). Two
    # different actions on one day (BAJFINANCE 2025: bonus and split) still multiply.
    a = a.assign(_f=a["price_factor"].round(6)).drop_duplicates(["symbol", "date", "kind", "_f"])
    return (a.groupby(["symbol", "date"], as_index=False)
             .agg(kind=("kind", lambda k: "+".join(sorted(set(k)))),
                  bc_factor=("price_factor", lambda f: f.prod() if f.notna().any() else np.nan)))


def _swapped(day: pd.Timestamp) -> pd.Timestamp | None:
    """The date with day and month exchanged, when that is a different date."""
    if day.day > 12 or day.day == day.month:
        return None
    return pd.Timestamp(year=day.year, month=day.day, day=day.month)


def _move_at(s: pd.Series, when: pd.Timestamp):
    """(first session on or after `when`, its close over the last close before it)."""
    after, before = s[s.index >= when].dropna(), s[s.index < when].dropna()
    if after.empty or before.empty:
        return None, np.nan
    return after.index[0], float(after.iloc[0] / before.iloc[-1])


def _confirms(move: float, factor: float) -> bool:
    off = abs(np.log(move / factor))
    return off < CONFIRM_BAND and off < abs(np.log(move))


def action_factors(close: pd.DataFrame, actions: pd.DataFrame
                   ) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(factors: dates x symbols, 1 except on a confirmed ex-date; one row per action).

    Each action's verdict:
      applied        the price moved by its factor on the ex-date
      date swapped   it did so on the date with day and month exchanged (Bc
                     files print some ex-dates month-first: E2E, MCX, VGL)
      demerger       a demerger, priced at the ex-date's own fall (the value
                     that left with the new company), as Screener does
      no move        the price did not move by it -- a duplicate date, or a
                     factor the market did not see
      no price       no session for the stock around the ex-date
    """
    close = close.copy()
    close.index = pd.DatetimeIndex(close.index).astype("datetime64[ns]")
    factors = pd.DataFrame(1.0, index=close.index, columns=close.columns)
    rows = []
    for r in _parsed(actions).itertuples(index=False):
        out = {"symbol": r.symbol, "date": r.date, "kind": r.kind,
               "bc_factor": r.bc_factor, "session": pd.NaT, "move": np.nan}
        if r.symbol not in close.columns:
            rows.append({**out, "verdict": "no price"})
            continue
        s = close[r.symbol]
        day, move = _move_at(s, r.date)
        if day is None:
            rows.append({**out, "verdict": "no price"})
            continue
        verdict, factor = "no move", np.nan
        if np.isnan(r.bc_factor):                      # demerger
            if DEMERGER_FLOOR < move < DEMERGER_CAP:
                verdict, factor = "demerger", move
        elif _confirms(move, r.bc_factor):
            verdict, factor = "applied", r.bc_factor
        else:
            alt = _swapped(r.date)
            if alt is not None:
                alt_day, alt_move = _move_at(s, alt)
                if alt_day is not None and _confirms(alt_move, r.bc_factor):
                    verdict, factor, day, move = "date swapped", r.bc_factor, alt_day, alt_move
        if verdict != "no move":
            factors.at[day, r.symbol] *= factor
        rows.append({**out, "session": day, "move": move, "verdict": verdict})
    cols = ["symbol", "date", "kind", "bc_factor", "session", "move", "verdict"]
    return factors, pd.DataFrame(rows, columns=cols)


def unexplained_jumps(close: pd.DataFrame, factors: pd.DataFrame) -> pd.DataFrame:
    """Session moves beyond 1.8x either way that no applied action explains."""
    move = close / close.ffill().shift(1)
    big = (np.log(move.where(move > 0)).abs() > JUMP) & (factors.reindex_like(close) == 1.0)
    s = move.where(big).stack().dropna()
    return (s.rename("move").reset_index()
             .rename(columns={"level_0": "date", "level_1": "symbol"})
             [["symbol", "date", "move"]].sort_values("date", ascending=False))


def factor_after(factors: pd.DataFrame) -> pd.DataFrame:
    """For each day, the product of the factors dated after it."""
    f = factors.fillna(1.0)
    return f.iloc[::-1].cumprod().iloc[::-1].shift(-1).fillna(1.0)


def adjust(frame: pd.DataFrame, factors: pd.DataFrame) -> pd.DataFrame:
    """Every price multiplied by the product of the factors dated after it."""
    return frame * factor_after(factors.reindex_like(frame))


def adjusted_frames(prices: pd.DataFrame, actions: pd.DataFrame
                    ) -> tuple[dict[str, pd.DataFrame], pd.DataFrame, pd.DataFrame]:
    """({close, high, low, volume, value} adjusted, the factors, each action's verdict)."""
    w = wide(prices)
    f, verdicts = action_factors(w["close"], actions)
    f.index = w["close"].index
    out = {k: adjust(w[k], f) for k in ("close", "high", "low")}
    # Volume moves the other way: a 1:5 split quintuples the share count.
    out["volume"] = w["volume"] / factor_after(f.reindex_like(w["volume"]))
    out["value"] = w["value"]
    return out, f, verdicts


def events(factors: pd.DataFrame) -> pd.DataFrame:
    """One row per (symbol, date) where NSE adjusted the previous close."""
    s = factors.stack()
    s = s[(s - 1).abs() > STEP_TOL]
    return (s.rename("factor").reset_index()
             .rename(columns={"level_0": "date", "level_1": "symbol"})
             [["symbol", "date", "factor"]])


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
        notes=["NSE closes, adjusted with the Bc file's splits and bonuses, price-confirmed"],
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
