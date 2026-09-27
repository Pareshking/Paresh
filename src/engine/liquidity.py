"""The liquidity floor: a stock's 20-day average traded value, in ₹ crore.

Owner, 2026-09-27: an option in Configuration, off by default, set in ₹ Cr of
20-day average traded value, for every system. When on, the Portfolio book
and the Backtest pass over a stock whose average falls below it -- at each
rebalance, on the value known that day. The track record's pinned
configuration does not use it.

Traded value is close x volume, both from the ranking's own source, so a
price and its volume are never from two vendors. A stock with no volume
record for the window has no known liquidity and does not pass the floor.
"""

from __future__ import annotations

import pandas as pd

WINDOW = 20
MIN_SESSIONS = 15
DEFAULT_FLOOR_CR = 5
CRORE = 1e7


def traded_value_cr(close: pd.DataFrame | None, volume: pd.DataFrame | None,
                    window: int = WINDOW) -> pd.DataFrame | None:
    """Each stock's trailing average of close x volume, in ₹ crore."""
    if close is None or volume is None or close.empty or volume.empty:
        return None
    cols = [c for c in close.columns if c in set(volume.columns)]
    value = close[cols] * volume.reindex(index=close.index, columns=cols)
    return value.rolling(window, min_periods=MIN_SESSIONS).mean() / CRORE


def passes(traded_value: pd.DataFrame | None, columns: pd.Index, on,
           floor_cr: float) -> pd.Series | None:
    """True for each column whose average on `on` is at least the floor.

    None when the floor is off or there is no traded-value record at all --
    the caller then applies no liquidity condition.
    """
    if not floor_cr or floor_cr <= 0 or traded_value is None or traded_value.empty:
        return None
    upto = traded_value.loc[:pd.Timestamp(on)]
    if upto.empty:
        return pd.Series(False, index=columns)
    row = upto.iloc[-1].reindex(columns)
    return (row >= floor_cr).fillna(False)
