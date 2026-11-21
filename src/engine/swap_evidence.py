"""What the record's swaps have added: the stocks bought against the stocks sold (owner, 21 Nov 2026).

For every rebalance buy, its return over the next 21 and 63 sessions less Nifty Total
Market's over the same sessions; for every closed trade, the same for the stock after it
was sold. If selling and replacing pays, the buys beat the market by more than the names
sold. First checked 21 Nov 2026 on the 750 record: 90 buys +3.1 pts in their first month,
70 sold names +0.2 pts (docs/ACTIONS_REQUIREMENTS.md row 29). Ten months, in-sample,
before costs, windows overlapping: evidence, not proof, and the page says so.
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


def _ahead(prices: pd.Series, market: pd.Series, start: pd.Timestamp, n: int) -> float | None:
    p = prices.dropna()
    p = p[p.index >= start]
    m = market[market.index >= start]
    if len(p) <= n or len(m) <= n:
        return None
    return float(p.iloc[n] / p.iloc[0] - 1) - float(m.iloc[n] / m.iloc[0] - 1)


def evidence(buys: list[tuple[str, pd.Timestamp]], sells: list[tuple[str, pd.Timestamp]],
             prices: pd.DataFrame, market: pd.Series) -> SwapEvidence | None:
    """`buys`: (symbol, fill date) for every rebalance buy; `sells`: (symbol, exit date) for every closed trade."""
    market = pd.to_numeric(market, errors="coerce").dropna().sort_index()
    px = prices.sort_index()

    def run(rows, n):
        out = [_ahead(px[s], market, d, n) for s, d in rows if s in px.columns]
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
                        rebought, min(dates), max(dates))


def from_record(history: dict, prices: pd.DataFrame, market: pd.Series) -> SwapEvidence | None:
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
    return evidence(buys, sells, prices, market)
