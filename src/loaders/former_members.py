"""Prices and industries for stocks that were in the index and later were not.

The app's deep price history is the CURRENT constituents' (price_loader). A
backtest scored on the index as it stood must also be able to hold a name that
has since been dropped, or the pool it picks from is only the survivors, which
flatters the result. In 2026, 54 to 98 of the 750 members at each month end had
no prices at all.

data/former_member_prices.parquet holds the adjusted closes of every stock that
was a member at any recorded date and is not in the current universe, filed under
its current ticker. scripts/sync_former_member_prices.py maintains it; this module
only reads it and joins it onto a price frame.

Names with no usable history (merged out of existence, so Yahoo has nothing) are
listed in the sidecar JSON rather than hidden.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from src.core.config import TV_CLASSIFICATION_FILE
from src.engine.membership import members_on

REPO_DATA = Path(__file__).resolve().parents[2] / "data"
PRICES_FILE = REPO_DATA / "former_member_prices.parquet"
META_FILE = REPO_DATA / "former_member_prices.json"
INDEX_FILE = REPO_DATA / "indices" / "ind_niftytotalmarket_list.csv"
# Fewer valid sessions than this is not a price history; it is a stray print.
MIN_SESSIONS = 60


def symbols_needed(history: dict[str, Any] | None, columns: Iterable[str]) -> list[str]:
    """Every name the record ever lists as a member (under its current ticker)
    that the price frame does not already carry."""
    if not history or not history.get("baseline"):
        return []
    dates = [history["baseline"]["date"]] + [c["date"] for c in history.get("changes") or []]
    union: set[str] = set()
    for d in dates:
        union |= members_on(history, d, canonical=True) or set()
    return sorted(union - set(columns))


def load() -> pd.DataFrame:
    """The stored adjusted closes, or an empty frame when there is no file."""
    if not PRICES_FILE.exists():
        return pd.DataFrame()
    return pd.read_parquet(PRICES_FILE)


def unavailable() -> list[str]:
    """Names the sync could not find usable prices for."""
    try:
        return list(json.loads(META_FILE.read_text(encoding="utf-8")).get("unavailable", []))
    except (OSError, ValueError):
        return []


def with_former_members(adj_close: pd.DataFrame, history: dict[str, Any] | None = None,
                        *, stored: pd.DataFrame | None = None) -> pd.DataFrame:
    """`adj_close` plus a column for each stored former member it lacks.

    Only names the membership record lists are added, so a stale file can never
    widen the pool beyond the index's own members, and with no record nothing is
    added at all. The backtester's membership mask then decides on every date who
    may be held; the extra columns on their own select nothing.
    """
    extra = load() if stored is None else stored
    if extra.empty or adj_close.empty or not history:
        return adj_close
    wanted = set(symbols_needed(history, adj_close.columns))
    keep = [c for c in extra.columns if c in wanted]
    if not keep:
        return adj_close
    add = extra[keep].reindex(adj_close.index).astype("float32")
    return pd.concat([adj_close, add], axis=1)


def industry_for(symbols: Iterable[str], *, tv_file: Path | str = TV_CLASSIFICATION_FILE,
                 index_file: Path | str = INDEX_FILE) -> dict[str, str]:
    """An NSE industry for each of `symbols`, for the sector cap.

    The index files label only the CURRENT members, so a former member has no NSE
    industry on file. Its TradingView industry is mapped to the NSE industry most
    of the current members with that TradingView industry carry (leave-one-out
    accuracy 82% on the 750). A name nothing can place falls to "Other", which the
    cap treats as one group.
    """
    idx = pd.read_csv(index_file)
    idx.columns = [str(c).strip() for c in idx.columns]
    tv = pd.read_csv(tv_file)
    tv.columns = [str(c).strip() for c in tv.columns]
    nse = dict(zip(idx["Symbol"], idx["Industry"]))
    votes: dict[str, Counter] = defaultdict(Counter)
    sector_votes: dict[str, Counter] = defaultdict(Counter)
    for sym, sector, industry in zip(tv["Symbol"], tv["TV_Sector"], tv["TV_Industry"]):
        if sym in nse:
            votes[industry][nse[sym]] += 1
            sector_votes[sector][nse[sym]] += 1
    cls = {r.Symbol: (r.TV_Sector, r.TV_Industry) for r in tv.itertuples()}

    def top(counter: Counter) -> str | None:
        return sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))[0][0] if counter else None

    out: dict[str, str] = {}
    for s in symbols:
        sector, industry = cls.get(s, (None, None))
        out[s] = top(votes.get(industry, Counter())) or top(sector_votes.get(sector, Counter())) or "Other"
    return out
