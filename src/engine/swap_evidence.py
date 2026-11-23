"""What the record's swaps have added: the stocks bought against the stocks sold (owner, 21 Nov 2026).

For every rebalance buy, its return over the next 21 and 63 sessions less Nifty Total
Market's over the same sessions; for every closed trade, the same for the stock after it
was sold. If selling and replacing pays, the buys beat the market by more than the names
sold. First checked 21 Nov 2026 on the 750 record: 90 buys +3.1 pts in their first month,
70 sold names +0.2 pts (docs/ACTIONS_REQUIREMENTS.md row 29). Ten months, in-sample,
before costs, windows overlapping: evidence, not proof, and the page says so. Each window
is counted on the stock's own sessions and the market read on the same two dates; a name
with no price is named, not dropped (S193 B).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

MONTH, QUARTER = 21, 63


@dataclass(frozen=True)
class SwapEvidence:
    buys: int
    sold: int
    buy_1m: float            # mean, points against the market
    sold_1m: float
    buy_3m: float | None
    sold_3m: float | None
    rebought: int            # sold, then bought back within two months
    first: pd.Timestamp
    last: pd.Timestamp
    unpriced: tuple[str, ...] = ()   # traded, but no price to measure (named on the page, S193 B)


def _ahead(prices: pd.Series, market: pd.Series, start: pd.Timestamp, n: int) -> float | None:
    """The stock's return over its next `n` sessions from `start`, less the market's between the same
    two dates (the market's last close on or before each). Counted on the stock's sessions: counted on
    each side's own, a day the index file lacks (1 Feb and 8 Nov 2026) ended the two windows on
    different dates (S193 B)."""
    p = prices.dropna()
    p = p[p.index >= start]
    if len(p) <= n:
        return None
    m0, m1 = _market_on(market, p.index[0]), _market_on(market, p.index[n])
    if m0 is None or m1 is None:
        return None
    return float(p.iloc[n] / p.iloc[0] - 1) - (m1 / m0 - 1)


def _market_on(market: pd.Series, day: pd.Timestamp) -> float | None:
    """The market's close on `day`, or its last before it within a week (None past its last close)."""
    if market.empty or day > market.index[-1]:
        return None
    m = market.loc[:day]
    if m.empty or (day - m.index[-1]).days > 7:
        return None
    return float(m.iloc[-1])


def evidence(buys: list[tuple[str, pd.Timestamp]], sells: list[tuple[str, pd.Timestamp]],
             prices: pd.DataFrame, market: pd.Series,
             fallback: pd.DataFrame | None = None) -> SwapEvidence | None:
    """`buys`: (symbol, fill date) for every rebalance buy; `sells`: (symbol, exit date) for every closed trade.

    `fallback`: closes for names `prices` lacks (a stock that has since left the list; the record values it
    from data/former_member_prices.parquet). A traded name with a price in neither is listed in `unpriced`,
    never dropped silently (JBCHEPHARM, S193 B)."""
    market = pd.to_numeric(market, errors="coerce").dropna().sort_index()
    px = prices.sort_index()
    extra = fallback.sort_index() if fallback is not None and not fallback.empty else None

    def close_of(sym: str) -> pd.Series | None:
        for frame in (px, extra):
            if frame is not None and sym in frame.columns and frame[sym].notna().any():
                return pd.to_numeric(frame[sym], errors="coerce")
        return None

    unpriced: list[str] = []

    def run(rows, n):
        out = []
        for s, d in rows:
            c = close_of(s)
            if c is None:
                if s not in unpriced:
                    unpriced.append(s)
                continue
            out.append(_ahead(c, market, d, n))
        return [x for x in out if x is not None]
    b1, s1 = run(buys, MONTH), run(sells, MONTH)
    if not b1 or not s1:
        return None
    b3, s3 = run(buys, QUARTER), run(sells, QUARTER)
    rebought = sum(1 for s, d in sells
                   if any(bs == s and d < bd <= d + pd.Timedelta(days=65) for bs, bd in buys))
    dates = [d for _, d in buys] + [d for _, d in sells]
    return SwapEvidence(len(b1), len(s1), float(np.mean(b1)) * 100, float(np.mean(s1)) * 100,
                        float(np.mean(b3)) * 100 if b3 else None, float(np.mean(s3)) * 100 if s3 else None,
                        rebought, min(dates), max(dates), tuple(sorted(unpriced)))


def from_record(history: dict, prices: pd.DataFrame, market: pd.Series,
                fallback: pd.DataFrame | None = None) -> SwapEvidence | None:
    """The buys from the record's rebalance lines, the sells from its closed trades."""
    tb, trades = history.get("tradebook"), history.get("trades")
    if not isinstance(tb, pd.DataFrame) or not isinstance(trades, pd.DataFrame) or tb.empty or trades.empty:
        return None
    b = tb[tb["Action"].astype(str).str.contains("BUY")]
    fill = pd.to_datetime(b["Period"].astype(str).str.split("→").str[0].str.strip(), format="%d %b %Y", errors="coerce")
    buys = [(str(s), d) for s, d in zip(b["Symbol"], fill) if pd.notna(d)]
    closed = trades[trades["Status"].astype(str) != "Open"]
    out = pd.to_datetime(closed["Exit Date"], errors="coerce", format="mixed")
    sells = [(str(s), d) for s, d in zip(closed["Symbol"], out) if pd.notna(d)]
    return evidence(buys, sells, prices, market, fallback)
