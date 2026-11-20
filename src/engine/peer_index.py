"""One construction for an industry and for the market it is compared with (S147).

An industry's strength is its equal-weighted index of member stocks; the
benchmark it is measured against is the same construction over every ranked
stock. Comparing an equal-weighted industry with the cap-weighted Nifty 500
mixes two questions: on 18 Nov 2026 a 12-week large-company rally put 17 of 20
industries behind the Nifty 500 and 4 behind the equal-weighted market. That
gap, the typical stock against the index, is size leadership, reported on its
own (`size_gap`).

The index is daily-rebalanced: each session's return is the mean of its
members' returns that session, so a stock with no print that day neither
counts nor reads as flat. RRG has always built its industry series this way;
Sectors and the Dashboard's industry tables now read the same series, so the
pages cannot disagree about what an industry did.

Practice: an index and its benchmark are built alike (sector indices against
their parent index; equal-weight sectors against the equal-weight index, as
S&P DJI and FTSE Russell publish them). A median is a typical-stock statistic,
not an index series, and is not used here.
"""

from __future__ import annotations

import pandas as pd


def equal_weight_level(prices: pd.DataFrame) -> pd.Series:
    """Level of a daily-rebalanced equal-weighted index of `prices`' columns.

    1.0 on the first session; NaN before any member has two prints. A session
    where no member printed carries the level forward.
    """
    if prices is None or prices.empty:
        return pd.Series(dtype=float)
    px = prices.sort_index()
    daily = px.pct_change(fill_method=None).mean(axis=1, skipna=True)
    observed = daily.notna()
    if not observed.any():
        return pd.Series(index=px.index, dtype=float)
    level = (1 + daily.fillna(0)).cumprod()
    first = observed.idxmax()
    # The session before the first return is the base, 1.0.
    pos = px.index.get_loc(first)
    base = px.index[pos - 1] if pos > 0 else first
    level = level / level.loc[base]
    level[level.index < base] = float("nan")
    return level


def _on_or_before(level: pd.Series, when: pd.Timestamp) -> float | None:
    s = level.dropna()
    pos = s.index.searchsorted(when, side="right") - 1
    return float(s.iloc[pos]) if pos >= 0 else None


def window_return(level: pd.Series, start: pd.Timestamp, end: pd.Timestamp) -> float | None:
    """Return of an index level from the session on or before `start` to the one
    on or before `end`, as a fraction."""
    a, b = _on_or_before(level, start), _on_or_before(level, end)
    if a is None or b is None or a == 0:
        return None
    return b / a - 1


def industry_levels(prices: pd.DataFrame, groups: pd.Series, min_stocks: int = 2
                    ) -> tuple[dict[str, pd.Series], pd.Series, dict[str, int]]:
    """Each industry's equal-weighted level, the market's (every grouped stock),
    and each industry's member count. `groups` maps symbol -> industry."""
    g = groups.dropna().astype(str).str.strip()
    g = g[(g != "") & (g.str.lower() != "nan") & g.index.isin(prices.columns)]
    levels, counts = {}, {}
    for name, members in g.groupby(g).groups.items():
        members = list(members)
        if len(members) < min_stocks:
            continue
        levels[str(name)] = equal_weight_level(prices[members])
        counts[str(name)] = len(members)
    market = equal_weight_level(prices[list(g.index)]) if len(g) else pd.Series(dtype=float)
    return levels, market, counts


def relative_points(level: pd.Series, market: pd.Series, start: pd.Timestamp,
                    end: pd.Timestamp) -> float | None:
    """The industry's return less the market's over the same sessions, in points."""
    r, m = window_return(level, start, end), window_return(market, start, end)
    if r is None or m is None:
        return None
    return (r - m) * 100


def size_gap(market: pd.Series, index_close: pd.Series, start: pd.Timestamp,
             end: pd.Timestamp) -> float | None:
    """Size leadership: the equal-weighted market's return less a cap-weighted
    index's over the same window, in points. Below zero, large companies led."""
    r = window_return(market, start, end)
    b = window_return(pd.to_numeric(index_close, errors="coerce").dropna().sort_index(), start, end)
    if r is None or b is None:
        return None
    return (r - b) * 100
