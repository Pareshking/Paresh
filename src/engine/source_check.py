"""Day-by-day agreement between NSE, Screener and Yahoo.

NSE's own bundle is the reference: it is the exchange's record of the day.
Two checks per stock on each date NSE published:

  level   Screener's close against NSE's close on the same day. Screener
          quotes the day as it traded, so these should match to the paisa;
          anything past LEVEL_TOL is a wrong or stale price.
  return  each source's one-day move against NSE's (close / previous close).
          Comparing MOVES, not price levels, is what makes Yahoo usable here:
          its dividend adjustment shifts every older price a little, so its
          level drifts from NSE's over the years while its daily move still
          matches except on an ex-date -- where the gap is about the dividend
          yield, rarely near the 7% line.

Nothing here decides a price. It lists where the sources disagree, for the
page to show and for a person to judge.
"""

from __future__ import annotations

import pandas as pd

RETURN_TOL = 0.07   # owner, 2026-09-27: a gap above 7% is flagged
LEVEL_TOL = 0.01

CHECK_COLUMNS = ["date", "symbol", "check", "nse_close", "nse_return",
                 "screener_close", "screener_return", "yahoo_return", "gap"]


def nse_closes(prices: pd.DataFrame) -> pd.DataFrame:
    """One row per equity symbol: close and one-day return, EQ before BE.

    Index rows are MKT = Y with no symbol. IND_SEC = Y marks index MEMBER
    stocks (the Nifty 50 names), which are exactly the ones to keep.
    """
    eq = prices[(prices["series"].isin(["EQ", "BE"])) & (prices["mkt"] != "Y")
                & (prices["symbol"] != "")]
    eq = eq.assign(_rank=(eq["series"] != "EQ").astype(int)).sort_values("_rank")
    eq = eq.drop_duplicates("symbol").set_index("symbol")
    ret = eq["close"] / eq["prev_close"] - 1
    return pd.DataFrame({"close": eq["close"], "ret": ret})


def _day_and_prev(closes: pd.DataFrame, day: pd.Timestamp) -> tuple[pd.Series, pd.Series]:
    """A source's close on `day` and on its session before, per symbol."""
    closes = closes.sort_index()
    if day not in closes.index:
        empty = pd.Series(dtype=float)
        return empty, empty
    pos = closes.index.get_loc(day)
    today = closes.iloc[pos]
    prev = closes.iloc[pos - 1] if pos > 0 else pd.Series(index=closes.columns, dtype=float)
    return today, prev


def compare(nse_prices: pd.DataFrame, screener_close: pd.DataFrame | None,
            yahoo_close: pd.DataFrame | None, symbols: list[str]) -> pd.DataFrame:
    """Rows for every disagreement on NSE's date, among `symbols`."""
    day = pd.Timestamp(nse_prices["date"].iloc[0]).normalize()
    nse = nse_closes(nse_prices).reindex(symbols)
    s_today, s_prev = (_day_and_prev(screener_close, day) if screener_close is not None
                       else (pd.Series(dtype=float), pd.Series(dtype=float)))
    y_today, y_prev = (_day_and_prev(yahoo_close, day) if yahoo_close is not None
                       else (pd.Series(dtype=float), pd.Series(dtype=float)))
    s_close = s_today.reindex(symbols)
    s_ret = (s_today / s_prev - 1).reindex(symbols)
    y_ret = (y_today / y_prev - 1).reindex(symbols)

    rows = []

    def add(sym, check, gap):
        rows.append({"date": day, "symbol": sym, "check": check,
                     "nse_close": nse.at[sym, "close"], "nse_return": nse.at[sym, "ret"],
                     "screener_close": s_close.get(sym), "screener_return": s_ret.get(sym),
                     "yahoo_return": y_ret.get(sym), "gap": gap})

    for sym in symbols:
        n_close, n_ret = nse.at[sym, "close"], nse.at[sym, "ret"]
        if pd.isna(n_close):
            add(sym, "missing_at_nse", float("nan"))
            continue
        sc = s_close.get(sym)
        if screener_close is not None and len(s_today):
            if pd.isna(sc):
                add(sym, "missing_at_screener", float("nan"))
            elif abs(sc / n_close - 1) > LEVEL_TOL:
                add(sym, "screener_level", sc / n_close - 1)
        for name, r in (("screener_return", s_ret.get(sym)), ("yahoo_return", y_ret.get(sym))):
            if pd.notna(r) and pd.notna(n_ret) and abs(r - n_ret) > RETURN_TOL:
                add(sym, name, r - n_ret)
    return pd.DataFrame(rows, columns=CHECK_COLUMNS)
