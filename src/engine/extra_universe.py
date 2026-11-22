"""The extra universe: every listed stock of ₹2,000 Cr or more outside the 750.

Owner, 2026-09-27: a second, optional universe beside Nifty Total Market --
"have the ₹2,000 Cr floor" rather than a fixed count. It is selectable in
Configuration; the default stays the 750, and the model portfolio, Actions and
the track record never use it. Name TBC ("Nano Cap" for now): change NAME and
SHORT_FORM, nothing else keys on the words.

Membership is point in time. It is fixed from NSE's market-cap file on the
last trading day of each month and used from the 1st of the next, so a month's
ranking never sees a stock that only crossed the floor later.

Pure functions only; scripts/build_extra_universe.py does the I/O.
"""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from src.core.tickers import is_tradeable_symbol

NAME = "NANO CAP"
# The three systems (owner, 2026-09-27), chosen in Configuration (session key
# cfg_system). Every page follows the choice; each system is ranked, booked and
# recorded on its own.
SYSTEM_750 = "750"
SYSTEM_1000 = "1000"
SYSTEM_NANO = "nano"
SYSTEM_COMBINED = "combined"
# Owner, 21 Nov 2026 (S175): four systems. Nifty 1000 is NSE's index (the 750
# plus 250 more); "nano" keeps its key, so its ledger, nightly files and
# ?sys=nano links are unchanged, and is shown as "> ₹2,000 Cr" (it is every
# stock of ₹2,000 Cr or more outside the 750, not NSE's nano caps).
SYSTEMS = (SYSTEM_750, SYSTEM_1000, SYSTEM_NANO, SYSTEM_COMBINED)
SYSTEM_NAMES = {SYSTEM_750: "Nifty 750", SYSTEM_1000: "Nifty 1000",
                SYSTEM_NANO: "> ₹2,000 Cr", SYSTEM_COMBINED: "Combined"}
# The month each system's live record starts. The 750's is the record's own
# INCEPTION (src/engine/track_record.py); Nano Cap and Combined start with the
# first book signalled after they were built, at the 30 Sep 2026 close; the
# Nifty 1000 with November 2026 (owner, 21 Nov: "start date is 01-Nov"), whose
# membership is reconstructed until NSE's first list (src/engine/nifty1000_backfill.py).
# How a page names the system's ranked universe in a sentence ("the 750", "Equal-weighted 750").
UNIVERSE_SHORT = {SYSTEM_750: "750", SYSTEM_1000: "1000",
                  SYSTEM_NANO: "> ₹2,000 Cr list", SYSTEM_COMBINED: "combined universe"}
SYSTEM_INCEPTION = {SYSTEM_1000: "2026-11", SYSTEM_NANO: "2026-10", SYSTEM_COMBINED: "2026-10"}
# The 250 the Nifty 1000 adds to the 750, as one group beside NSE's size tiers
# (owner's name). Our own cut, not an index NSE publishes.
NANOCAP_250_NAME = "NIFTY NANOCAP 250"
NANOCAP_250_SHORT = "NANO250"
SHORT_FORM = "NANO"
FLOOR_RUPEES = 2_000 * 10_000_000        # ₹2,000 Cr
SERIES = ("EQ", "BE")                     # main board; SME (SM/ST) is excluded
LIST_COLUMNS = ["Company Name", "Industry", "Symbol", "Series", "ISIN Code"]
UNCLASSIFIED = "Unclassified"

# Exchange-traded products share the equity series in NSE's files.
_FUND_WORDS = ("ETF", "BEES", "EXCHANGE TRADED", "MUTUAL FUND", "INDEX FUND")


def _is_fund(symbol: str, security: str) -> bool:
    s, name = symbol.upper(), str(security).upper()
    return (s.endswith(("BEES", "ETF", "IETF")) or any(w in name for w in _FUND_WORDS))


def members(market_caps: pd.DataFrame, exclude: set[str],
            classification: dict[str, dict[str, str]] | None = None,
            floor: float = FLOOR_RUPEES) -> pd.DataFrame:
    """The list, largest first, in the same columns as NSE's index files.

    market_caps is one day of nse/market_caps (src/loaders/nse_bundle.py).
    exclude is the 750. Industry is TradingView's sector where the
    classification file has the stock, else UNCLASSIFIED for a later lookup.
    """
    classification = classification or {}
    m = market_caps[market_caps["series"].isin(SERIES)
                    & (market_caps["mcap"] >= floor)].copy()
    if "category" in m.columns:
        cat = m["category"].fillna("").str.strip().str.lower()
        m = m[(cat == "") | (cat == "listed")]
    m = m[~m["symbol"].isin(exclude)]
    m = m[m["symbol"].map(is_tradeable_symbol)]
    m = m[~m.apply(lambda r: _is_fund(r["symbol"], r["security"]), axis=1)]
    # EQ before BE when a symbol has both.
    m = (m.assign(_r=(m["series"] != "EQ").astype(int))
          .sort_values(["_r", "mcap"], ascending=[True, False])
          .drop_duplicates("symbol").sort_values("mcap", ascending=False))
    return pd.DataFrame({
        "Company Name": m["security"].fillna(m["symbol"]).astype(str).str.strip().values,
        "Industry": [classification.get(s, {}).get("TV_Sector") or UNCLASSIFIED
                     for s in m["symbol"]],
        "Symbol": m["symbol"].values,
        "Series": m["series"].values,
        "ISIN Code": "",
        "MarketCapCr": (m["mcap"] / 10_000_000).round(0).values,
    })


def with_isins(listed: pd.DataFrame, equity_list: pd.DataFrame | None) -> pd.DataFrame:
    """The list with each stock's ISIN from NSE's equity list (EQUITY_L.csv), by symbol.

    NSE's market-cap file carries no ISIN, so the list was written with the
    column blank and could only be matched by ticker, which a rename breaks
    (S175). A symbol the equity list lacks keeps a blank, never a guess.
    """
    if equity_list is None or equity_list.empty:
        return listed
    e = equity_list.copy()
    e.columns = [str(c).strip() for c in e.columns]
    if "SYMBOL" not in e or "ISIN NUMBER" not in e:
        return listed
    isin = (e.assign(SYMBOL=e["SYMBOL"].astype(str).str.strip().str.upper())
              .drop_duplicates("SYMBOL").set_index("SYMBOL")["ISIN NUMBER"].astype(str).str.strip())
    out = listed.copy()
    out["ISIN Code"] = out["Symbol"].map(isin).fillna("").values
    return out


def _last_weekday(year: int, month: int) -> date:
    d = (date(year + (month == 12), month % 12 + 1, 1) - timedelta(days=1))
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def membership_day(held: set[date], today: date) -> date | None:
    """The month-end session whose market caps set the current list.

    The newest held session when it is its month's last weekday (the list is
    built that evening, ready for the 1st), or when its month is over. Else
    the last held session of the month before. A holiday on the last weekday
    therefore builds on the 1st instead of the evening before.
    """
    if not held:
        return None
    newest = max(held)
    month_over = (today.year, today.month) > (newest.year, newest.month)
    if newest == _last_weekday(newest.year, newest.month) or month_over:
        return newest
    first = newest.replace(day=1)
    earlier = [d for d in held if d < first]
    return max(earlier) if earlier else None


def effective_from(day: date) -> date:
    """The 1st of the month after the membership day."""
    return date(day.year + (day.month == 12), day.month % 12 + 1, 1)
