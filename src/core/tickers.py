"""Canonical ticker-label normalisation.

Yahoo returns "INDIGO.NS"; every cache, snapshot and frame in this app stores
"INDIGO". Converting between the two is a one-line expression, which is exactly
why it ended up written twelve times -- ten inline copies plus two helper
functions in different modules, spelled differently.

That is not a style problem. It is the surface the duplicate-column bug lived
on: the incremental price merge normalised one frame and not the other, the
labels disagreed, and a vertical concat silently produced 7,500 columns where
3,750 belonged -- each series split in half with NaNs on both sides.

Two frames can only be merged safely if they were labelled by the same code.
So there is one implementation, here, and everything calls it.
"""

from __future__ import annotations

import pandas as pd

NSE_SUFFIX = ".NS"


def normalise_symbol(value: object) -> str:
    """"indigo.ns " -> "INDIGO". Idempotent, and safe on any object.

    Case is folded BEFORE the suffix is removed. Every inline copy of this did
    it the other way round -- .replace(".NS", "").strip().upper() -- which
    leaves a lowercase ".ns" untouched and yields "INDIGO.NS". Yahoo happens to
    send uppercase, so the flaw never fired; it was still one casing change
    away from producing two labels for one stock.

    removesuffix, not replace: a ".NS" occurring anywhere but the end is part
    of the name, not a market suffix.
    """
    return str(value).strip().upper().removesuffix(NSE_SUFFIX).strip()


def is_tradeable_symbol(value: object) -> bool:
    """False for NSE's placeholder and junk rows, True for a real ticker.

    NSE ships DUMMY rows in its constituent files for corporate actions in
    flight -- "Dummy Triveni Ltd.,Capital Goods,DUMMYTRVN,EQ,DUM256C01024" is a
    real line in ind_niftytotalmarket_list.csv. They have no price history, so a
    universe carrying one could rank and buy a ticker that cannot be traded.

    Defined once, here, because the index loader and the point-in-time
    membership store must agree on what counts as a constituent. If they
    disagreed, membership diffs would show phantom additions and removals every
    time a placeholder came or went.
    """
    symbol = str(value).strip().upper()
    return bool(symbol) and not (
        symbol.startswith("DUMMY") or len(symbol) < 2 or symbol == "NAN"
    )


def normalise_columns(df: pd.DataFrame, level: int = 0) -> pd.DataFrame:
    """Return a copy of ``df`` with its ticker labels normalised.

    For a MultiIndex, only ``level`` is touched -- the price-field level must
    keep its own capitalisation ("Close", not "CLOSE"). Level order is not
    assumed: callers state which level holds the ticker.
    """
    if df is None or df.empty:
        return df

    out = df.copy()
    if isinstance(out.columns, pd.MultiIndex):
        arrays = [list(out.columns.get_level_values(i)) for i in range(out.columns.nlevels)]
        arrays[level] = [normalise_symbol(c) for c in arrays[level]]
        names = (
            out.columns.names
            if out.columns.names and out.columns.names[0]
            else ["Ticker", "Price"]
        )
        out.columns = pd.MultiIndex.from_arrays(arrays, names=names)
    else:
        out.columns = [normalise_symbol(c) for c in out.columns]
    return out
