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
# Prices read every series that is the company's ordinary share, ranked so a
# day traded in more than one takes the main board's price (owner,
# 2026-10-03: the right stock and the right price, whatever the series). A
# stock moved to BZ (trade-for-trade, companies in default or out of
# compliance) dropped out of the price file -- 4,921 stock-days over 33
# stocks since 2008 (UNITECH, JYOTISTRUC, SUPREMEINF) -- and its return to EQ
# read as one fake jump over the gap. Not read: bonds (N1-N9, NA-NZ), gold
# bonds and G-secs (GB, GS), MF, depository receipts (DR), warrants (W*),
# partly paid shares (P1, another price), block deals (BL, negotiated) and
# E1/X1. SERIES itself is unchanged: it also picks the Nano Cap universe.
SERIES_RANK = {"EQ": 0, "BE": 1, "RR": 1, "IV": 1, "BZ": 2, "T0": 3, "SM": 4, "ST": 4, "SZ": 5}
PRICE_SERIES = tuple(SERIES_RANK)
STEP_TOL = 1e-3                # |factor - 1| above this is an adjustment


def wide(prices: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Long NSE rows -> {field: dates x symbols} for close, prev_close, high, low, volume, value.

    Stocks only (index rows dropped); a symbol traded in more than one series
    on a day takes the best ranked (SERIES_RANK: EQ, then BE, then BZ ...).
    """
    p = prices[prices["series"].isin(PRICE_SERIES) & (prices["symbol"].fillna("") != "")].copy()
    p["_r"] = p["series"].map(SERIES_RANK).fillna(9)
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
# A scheme of arrangement is priced as a demerger only on a fall beyond 15%:
# a merger or capital change under the same words leaves the price where it
# trades, and an ordinary down day on its ex-date must stay a real move.
SCHEME_CAP = 0.85
SMALL_FACTOR, SMALL_DAYS = 0.7, 45


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
    a = actions[(known | actions["kind"].isin(("demerger", "scheme"))) & actions["ex_date"].notna()].copy()
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
      duplicate      the same action already applied on that session: the Bc
                     file's 2 Jan and the yearly list's 1 Feb (month-first) for
                     MCX's 2026 split both landed on 2 Jan and both confirmed,
                     so the split was applied twice (audit, 2026-10-03)
      no price       no session for the stock around the ex-date
      small, applied a bonus or split too small for the price to confirm
                     (factor >= SMALL_FACTOR), applied once on NSE's word
      rights         a rights issue priced under the market (rights_factor)
      no terms       a rights issue whose issue price the list does not give
      not in the money  a rights issue at or above the last close
      large dividend a payout of LARGE_DIVIDEND of the last close or more
    """
    close = close.copy()
    close.index = pd.DatetimeIndex(close.index).astype("datetime64[ns]")
    factors = pd.DataFrame(1.0, index=close.index, columns=close.columns)
    rows = []
    done: set[tuple] = set()
    small: list[tuple] = []
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
        if np.isnan(r.bc_factor):                      # demerger, or a scheme
            cap = SCHEME_CAP if r.kind == "scheme" else DEMERGER_CAP
            if DEMERGER_FLOOR < move < cap:
                verdict, factor = "demerger", move
        elif _confirms(move, r.bc_factor):
            verdict, factor = "applied", r.bc_factor
        else:
            alt = _swapped(r.date)
            if alt is not None:
                alt_day, alt_move = _move_at(s, alt)
                if alt_day is not None and _confirms(alt_move, r.bc_factor):
                    verdict, factor, day, move = "date swapped", r.bc_factor, alt_day, alt_move
        key = (r.symbol, day, r.kind, round(float(factor), 6) if verdict != "demerger" else "d")
        if verdict != "no move" and key in done:
            verdict = "duplicate"
        elif verdict != "no move":
            done.add(key)
            factors.at[day, r.symbol] *= factor
        elif SMALL_FACTOR <= r.bc_factor < 1:
            small.append((len(rows), r, day, move))
        rows.append({**out, "session": day, "move": move, "verdict": verdict})
    # A small bonus moves the price less than an ordinary day can (KTKBANK 1:10
    # on 17 Mar 2020, KARURVYSYA 1:10 in 2018, GOLDIAM 1:3 in 2026: the Screener
    # audit, 3 Oct 2026), so the price cannot confirm it. NSE listed it; apply
    # it unless the same action is already applied within SMALL_DAYS (the Bc
    # file and the yearly list can date one action differently).
    for i, r, day, move in small:
        f = round(float(r.bc_factor), 6)
        if any(k[0] == r.symbol and k[2] == r.kind and k[3] == f
               and abs((k[1] - day).days) <= SMALL_DAYS for k in done):
            rows[i]["verdict"] = "duplicate"
            continue
        done.add((r.symbol, day, r.kind, f))
        factors.at[day, r.symbol] *= r.bc_factor
        rows[i]["verdict"] = "small, applied"
    for r in _rights(actions).itertuples(index=False):
        out = {"symbol": r.symbol, "date": r.date, "kind": "rights", "bc_factor": np.nan,
               "session": pd.NaT, "move": np.nan}
        if r.symbol not in close.columns:
            rows.append({**out, "verdict": "no price"})
            continue
        s = close[r.symbol]
        day, move = _move_at(s, r.date)
        if day is None:
            rows.append({**out, "verdict": "no price"})
            continue
        before = float(s[s.index < r.date].dropna().iloc[-1])
        factor = rights_factor(before, r.issue_price, r.ratio_new, r.ratio_held)
        verdict = "no terms" if np.isnan(r.issue_price) else "not in the money"
        if np.isfinite(factor) and RIGHTS_FLOOR < factor < 1 - STEP_TOL:
            verdict = "rights"
            factors.at[day, r.symbol] *= factor
        rows.append({**out, "bc_factor": factor, "session": day, "move": move, "verdict": verdict})
    for r in _dividends(actions).itertuples(index=False):
        if r.symbol not in close.columns:
            continue
        s = close[r.symbol]
        day, move = _move_at(s, r.date)
        if day is None:
            continue
        before = float(s[s.index < r.date].dropna().iloc[-1])
        y = r.amount / before
        if y < LARGE_DIVIDEND:
            continue
        out = {"symbol": r.symbol, "date": r.date, "kind": "dividend", "session": day, "move": move}
        # The price must have fallen by at least half the payout: a text that
        # reads as a large amount the market never paid out is not applied.
        if y < 1 and move < 1 - y / 2:
            factor = 1 - y
            factors.at[day, r.symbol] *= factor
            rows.append({**out, "bc_factor": factor, "verdict": "large dividend"})
        else:
            rows.append({**out, "bc_factor": 1 - y, "verdict": "no move"})
    cols = ["symbol", "date", "kind", "bc_factor", "session", "move", "verdict"]
    return factors, pd.DataFrame(rows, columns=cols)


# Large dividends (owner, 2026-10-03: option 1). Ordinary dividends stay
# unadjusted, like Screener and the live system, so History and Live stay on
# one basis; a payout of LARGE_DIVIDEND of the last close or more is a return
# of capital the holder kept, not a fall: PFIZER's Rs 360 on 5 Dec 2013 (21%),
# WYETH's Rs 145 the same day, PATNI 2010, IDFC 2023 (23 events, 2008-2026).
# Factor (P - D) / P on the ex-date.
LARGE_DIVIDEND = 0.10


def _dividends(actions: pd.DataFrame) -> pd.DataFrame:
    """One row per (symbol, ex-date) dividend: every amount its text names, added.

    "Final Rs 6.50 And Special Rs 60" is 66.50. A rights text quoting a
    premium ("Rht1:5@Prem-Rs100/Div-Rs2") is not a payout. The Bc file and the
    yearly list both carry most dividends: the larger reading is kept once.
    """
    from src.loaders.nse_bundle import _AMOUNT

    cols = ["symbol", "date", "amount"]
    if "kind" not in actions or "purpose" not in actions or actions.empty:
        return pd.DataFrame(columns=cols)
    text = actions["purpose"].fillna("").str.upper()
    a = actions[(actions["kind"] == "dividend") & actions["ex_date"].notna()
                & ~text.str.contains(r"RI?GH?TS?\b|\bRHT")].copy()
    if a.empty:
        return pd.DataFrame(columns=cols)
    a["date"] = pd.to_datetime(a["ex_date"]).dt.normalize().astype("datetime64[ns]")
    a["amount"] = [sum(float(x) for x in _AMOUNT.findall(t.upper())) for t in a["purpose"].fillna("")]
    a = a[a["amount"] > 0]
    return (a.groupby(["symbol", "date"], as_index=False)["amount"].max())[cols]


# Rights issues (owner, 2026-10-03: rights of index stocks may be corrected).
# Yahoo, Tijori, Screener and NSE's MarketLens adjust them; without it the
# ex-date's fall reads as a loss the holder did not have (M&MFIN 1:1 at Rs 50
# on 22 Jul 2020: -33% in one session; CENTRALBK 2011, NDTV 2025, NCC 2014 --
# the Screener audit found 74 such steps). The standard factor: the
# theoretical ex-rights price over the last close before the ex-date,
#     (held x P + new x S) / ((held + new) x P),   S = face value + premium.
# Only an issue priced under the market moves the price; a factor below
# RIGHTS_FLOOR is a misread, not a rights issue.
RIGHTS_FLOOR = 0.3


def rights_factor(close_before: float, issue_price: float, new: float, held: float) -> float:
    """Price factor of a rights issue of `new` shares per `held` at `issue_price`."""
    if not (close_before > 0 and new > 0 and held > 0 and issue_price >= 0) or issue_price >= close_before:
        return np.nan
    return (held * close_before + new * issue_price) / ((held + new) * close_before)


def _rights(actions: pd.DataFrame) -> pd.DataFrame:
    """One row per (symbol, ex-date) rights issue: ratio and issue price.

    The purpose text gives the ratio and the premium; the face value comes
    from NSE's yearly list (face_value), from the same row or, when a daily
    Bc row lacks it, from the symbol's nearest row that has one.
    """
    from src.loaders.nse_bundle import classify_purpose

    cols = ["symbol", "date", "ratio_new", "ratio_held", "issue_price"]
    if "kind" not in actions or "purpose" not in actions or actions.empty:
        return pd.DataFrame(columns=cols)
    a = actions[(actions["kind"] == "rights") & actions["ex_date"].notna()].copy()
    if a.empty:
        return pd.DataFrame(columns=cols)
    a["date"] = pd.to_datetime(a["ex_date"]).dt.normalize().astype("datetime64[ns]")
    parsed = pd.DataFrame([classify_purpose(p) for p in a["purpose"].fillna("")], index=a.index)
    a["ratio_new"], a["ratio_held"], a["premium"] = parsed["ratio_new"], parsed["ratio_held"], parsed["amount"]
    fv = pd.to_numeric(actions.get("face_value"), errors="coerce") if "face_value" in actions else None
    if fv is not None and fv.notna().any():
        known = actions.assign(_fv=fv, _d=pd.to_datetime(actions["ex_date"], errors="coerce"))
        known = known[known["_fv"] > 0]
        a["face_value"] = fv.reindex(a.index)
        for i in a.index[a["face_value"].isna()]:
            k = known[known["symbol"] == a.at[i, "symbol"]]
            if len(k):
                a.at[i, "face_value"] = k.loc[(k["_d"] - a.at[i, "date"]).abs().idxmin(), "_fv"]
    else:
        a["face_value"] = np.nan
    a["issue_price"] = a["face_value"] + a["premium"]
    a = a[a["ratio_new"].notna() & a["ratio_held"].notna()]
    # One issue once: the Bc file and the yearly list both carry it; keep the row with terms.
    a = a.sort_values("issue_price", na_position="last").drop_duplicates(["symbol", "date"])
    return a[cols].reset_index(drop=True)


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
