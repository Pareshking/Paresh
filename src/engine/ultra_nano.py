"""Ultra Nano Cap: the rule S198 measures before the January 2027 switch.

Owner, 22 Nov 2026 (TODO S198): from the January 2027 book the "nano" system
(key kept) holds every main-board stock of ₹1,000 Cr or more OUTSIDE the
Nifty 1000, the Nifty 1000 taken on each month-end date (point in time).
The band ("Tracked only"):

    ≥ ₹1,000 Cr   eligible: ranked and buyable
    ₹500-1,000 Cr tracked: a member that fell below ₹1,000 Cr keeps its prices
                  and membership recorded but cannot be bought; it leaves the
                  tracked set below ₹500 Cr
    ≥ ₹800 Cr     prices collected, so a joiner has history ready
    holding < ₹1,000 Cr on the month-end list: sold at that rebalance ("sell
                  at rebalance"), as a stock that leaves its index is sold

Measurement only: nothing in the live systems reads this module until S198 (e)
(`src/engine/extra_universe.py` keeps today's ₹2,000 Cr outside the 750).
Pure functions; scripts/s198_measure.py does the I/O.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

import pandas as pd

from src.engine import extra_universe as xu

CRORE = 10_000_000
BUY_FLOOR_CR = 1_000.0      # eligible: ranked and buyable
TRACK_FLOOR_CR = 500.0      # a former eligible member stays tracked down to here
PRICE_FLOOR_CR = 800.0      # prices collected from here
TODAY_FLOOR_CR = xu.FLOOR_RUPEES / CRORE   # today's "> ₹2,000 Cr" list, outside the 750

ELIGIBLE, TRACKED, PRICED = "eligible", "tracked", "priced"
MEMBER_STATES = (ELIGIBLE, TRACKED)
NIFTY_1000_SIZE = 1000

# Why a holding is sold at the rebalance (sell_at_rebalance).
SOLD_BELOW_FLOOR = "below ₹1,000 Cr"
SOLD_INTO_1000 = "joined the Nifty 1000"
SOLD_NO_CAP = "not in NSE's market-cap file"


def screened_caps(market_caps: pd.DataFrame, floor_cr: float = TRACK_FLOOR_CR) -> pd.Series:
    """{symbol: market cap in ₹ Cr} for the main-board stocks today's list admits, at or above `floor_cr`.

    The same screen as today's list (`extra_universe.members`: EQ/BE, category
    Listed, a real ticker, no ETF or fund, EQ before BE), with nothing excluded
    and the exact figure kept (the list's own column is rounded to ₹1 Cr, which
    would move a ₹999.6 Cr stock over the line).
    """
    if market_caps is None or market_caps.empty:
        return pd.Series(dtype=float)
    listed = xu.members(market_caps, set(), floor=floor_cr * CRORE)
    if listed.empty:
        return pd.Series(dtype=float)
    exact = market_caps.assign(symbol=market_caps["symbol"].astype(str), series=market_caps["series"].astype(str))
    exact = exact.drop_duplicates(["symbol", "series"]).set_index(["symbol", "series"])["mcap"]
    keys = list(zip(listed["Symbol"].astype(str), listed["Series"].astype(str)))
    caps = pd.Series([float(exact.loc[k]) / CRORE for k in keys], index=listed["Symbol"].astype(str).values)
    return caps.sort_values(ascending=False)


def nifty_1000_proxy(caps_cr: pd.Series, total_market: set[str], size: int = NIFTY_1000_SIZE) -> set[str]:
    """The Nifty 1000 on a date before NSE published it: the 750 plus the largest others to `size`.

    NSE's own construction is the Nifty Total Market plus the next 250 by
    average full market cap, reviewed in March and September; this proxy takes
    the month-end cap instead, so it is a proxy and every figure built on it
    says so.
    """
    others = caps_cr[~caps_cr.index.isin(total_market)].sort_values(ascending=False)
    return set(total_market) | set(others.index[: max(0, size - len(total_market))])


def classify(caps_cr: pd.Series, nifty_1000: set[str],
             previous: Mapping[str, str] | None = None) -> dict[str, str]:
    """Each stock's state on one month-end list: eligible, tracked or priced.

    `caps_cr` is `screened_caps` of that session (floor ≤ ₹500 Cr), `nifty_1000`
    the index on that date, `previous` the last list's states. Inside the
    Nifty 1000 a stock is in that system, not this one, whatever its size.
    """
    previous = previous or {}
    out: dict[str, str] = {}
    for sym, cap in caps_cr.items():
        if sym in nifty_1000 or pd.isna(cap):
            continue
        if cap >= BUY_FLOOR_CR:
            out[sym] = ELIGIBLE
        elif cap >= TRACK_FLOOR_CR and previous.get(sym) in MEMBER_STATES:
            out[sym] = TRACKED
        elif cap >= PRICE_FLOOR_CR:
            out[sym] = PRICED
    return out


def eligible(states: Mapping[str, str]) -> set[str]:
    return {s for s, v in states.items() if v == ELIGIBLE}


def members(states: Mapping[str, str]) -> set[str]:
    """Eligible and tracked: the names whose prices and membership are recorded."""
    return {s for s, v in states.items() if v in MEMBER_STATES}


def price_set(states: Mapping[str, str]) -> set[str]:
    """Every name whose prices are collected: the members plus the ₹800-1,000 Cr joiners-in-waiting."""
    return set(states)


def sell_at_rebalance(holdings: Iterable[str], states: Mapping[str, str], nifty_1000: set[str],
                      caps_cr: pd.Series | None = None) -> dict[str, str]:
    """{holding: why} for every holding sold at this rebalance by the universe rule alone.

    A holding not eligible on the month-end list is sold, whatever its rank:
    below ₹1,000 Cr (tracked, or gone below ₹500 Cr), moved into the Nifty 1000,
    or absent from NSE's file (`caps_cr` is that session's screened caps at any
    floor; without it an absent name counts as below the floor). Rank, trend
    and high filters are the engine's.
    """
    out: dict[str, str] = {}
    for sym in holdings:
        if states.get(sym) == ELIGIBLE:
            continue
        if sym in nifty_1000:
            out[sym] = SOLD_INTO_1000
        elif sym in states or caps_cr is None or sym in caps_cr.index:
            out[sym] = SOLD_BELOW_FLOOR
        else:
            out[sym] = SOLD_NO_CAP
    return out


@dataclass
class Turnover:
    """How the buyable list changed from one month-end to the next."""
    before: int
    after: int
    joined: list[str] = field(default_factory=list)
    left: list[str] = field(default_factory=list)
    left_why: dict[str, int] = field(default_factory=dict)

    @property
    def rate(self) -> float | None:
        """Names that left, over the list before (one way)."""
        return len(self.left) / self.before if self.before else None

    def as_dict(self) -> dict:
        return {"before": self.before, "after": self.after, "joined": len(self.joined),
                "left": len(self.left), "left_why": dict(self.left_why),
                "rate": None if self.rate is None else round(self.rate, 4)}


def turnover(prev: Mapping[str, str], now: Mapping[str, str], caps_cr: pd.Series,
             nifty_1000: set[str]) -> Turnover:
    """Joined and left between two lists' eligible sets, each leaver with its reason.

    Reasons: below ₹1,000 Cr (still in NSE's file), into the Nifty 1000, or
    no market cap (delisted, suspended or out of the main board).
    """
    a, b = eligible(prev), eligible(now)
    left = sorted(a - b)
    why: dict[str, int] = {}
    for s in left:
        if s in nifty_1000:
            r = SOLD_INTO_1000
        elif s in caps_cr.index:
            r = SOLD_BELOW_FLOOR
        else:
            r = SOLD_NO_CAP
        why[r] = why.get(r, 0) + 1
    return Turnover(before=len(a), after=len(b), joined=sorted(b - a), left=left, left_why=why)


def today_list(caps_cr: pd.Series, total_market: set[str]) -> set[str]:
    """Today's system on the same date: ₹2,000 Cr or more outside the 750."""
    return {s for s, c in caps_cr.items() if c >= TODAY_FLOOR_CR and s not in total_market}


def cap_buckets(caps_cr: pd.Series, names: Iterable[str]) -> dict[str, int]:
    """How many of `names` sit in each size band, ₹ Cr."""
    c = caps_cr.reindex(sorted(set(names))).dropna()
    edges = [(0, 500), (500, 800), (800, 1_000), (1_000, 2_000), (2_000, 5_000), (5_000, 10_000),
             (10_000, float("inf"))]
    out = {}
    for lo, hi in edges:
        label = f"{lo:,.0f}+" if hi == float("inf") else f"{lo:,.0f}-{hi:,.0f}"
        n = int(((c >= lo) & (c < hi)).sum())
        if n or lo >= 500:
            out[label] = n
    return out
