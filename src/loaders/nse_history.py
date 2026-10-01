"""NSE's own daily record, as published, for a stretch of sessions.

The deep history the backtest and the Track Record use was Yahoo's, which
restates itself: dividends are folded back into every earlier price, and a vendor
correction rewrites a month that has long closed. NSE's closes are never
restated. They are what traded that day, so a ranking rebuilt from them is the
ranking as it stood, and a stock that has since merged away still has its prices.

This module only gathers the record. fetch_days() downloads each day's bundle
(src/loaders/nse_bundle.py), keeps what a price series needs and caches it one
file a day, so a run that stops resumes where it left off. read_cache() returns
the two tables src/loaders/nse_adjusted.py adjusts. It never adjusts a price.
"""
from __future__ import annotations

import time
from datetime import date, timedelta
from pathlib import Path
from typing import Callable, Iterable

import pandas as pd
import requests

from src.loaders import nse_adjusted as na
from src.loaders import nse_bundle as nb

KEEP = ["date", "mkt", "series", "symbol", "close", "prev_close", "high", "low",
        "volume", "value"]


def weekdays(since: date, until: date) -> list[date]:
    """Every Monday to Friday in [since, until]; NSE's holidays answer 404."""
    out, d = [], since
    while d <= until:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def _paths(cache: Path, day: date) -> tuple[Path, Path, Path]:
    s = day.isoformat()
    return cache / f"prices_{s}.parquet", cache / f"actions_{s}.parquet", cache / f"none_{s}.flag"


def fetch_days(days: Iterable[date], cache: Path, *, pause: float = 1.0,
               log: Callable[[str], None] = print) -> dict[str, int]:
    """Download and cache every day not already held. Stops cleanly if NSE
    refuses (every later day would be refused too) and returns a tally."""
    cache.mkdir(parents=True, exist_ok=True)
    tally = {"cached": 0, "fetched": 0, "no_bundle": 0, "blocked": 0}
    session = requests.Session()
    for day in days:
        prices_p, actions_p, none_p = _paths(cache, day)
        if prices_p.exists() or none_p.exists():
            tally["cached"] += 1
            continue
        try:
            files = nb.fetch_bundle(day, session=session)
        except nb.NSEBlocked as exc:
            tally["blocked"] += 1
            log(f"blocked: {exc}")
            break
        except requests.RequestException as exc:
            log(f"{day}: {type(exc).__name__}; will retry on the next run")
            time.sleep(pause * 3)
            continue
        if files is None:
            none_p.write_text("holiday or not published\n")
            tally["no_bundle"] += 1
        else:
            tables = nb.parse_bundle(files, day)
            p = tables["prices"]
            p[p["series"].isin(na.SERIES)][KEEP].to_parquet(prices_p)
            tables["corporate_actions"].to_parquet(actions_p)
            tally["fetched"] += 1
        if (tally["fetched"] + tally["no_bundle"]) % 25 == 0:
            log(f"  ... {day} ({tally})")
        time.sleep(pause)
    return tally


def read_cache(cache: Path, since: date, until: date, extra: Iterable[date] = ()
               ) -> tuple[pd.DataFrame, pd.DataFrame, list[date]]:
    """(prices, actions, days with no cache at all) for [since, until].

    `extra` are weekend sessions (a Budget Saturday, a special Sunday), which
    weekdays() cannot know about.
    """
    prices, actions, missing = [], [], []
    days = sorted(set(weekdays(since, until)) | {d for d in extra if since <= d <= until})
    for day in days:
        prices_p, actions_p, none_p = _paths(cache, day)
        if prices_p.exists():
            prices.append(pd.read_parquet(prices_p))
            if actions_p.exists():
                actions.append(pd.read_parquet(actions_p))
        elif not none_p.exists():
            missing.append(day)
    p = pd.concat(prices, ignore_index=True) if prices else pd.DataFrame(columns=KEEP)
    a = pd.concat(actions, ignore_index=True) if actions else pd.DataFrame()
    return p, dedupe_actions(a), missing


# The series is not part of an action's identity: NSE lists one bonus under both the BE and
# EQ lines of the same stock, and each would otherwise be applied.
ACTION_KEY = ["symbol", "purpose", "kind", "ex_date", "record_date", "bc_start", "bc_end"]


def dedupe_actions(actions: pd.DataFrame) -> pd.DataFrame:
    """One row per corporate action.

    NSE's Bc file lists an action on every day its book is open, so the same
    bonus turns up in each daily file until it goes ex. Stacking the days and
    multiplying the factors per (symbol, ex-date) then applied it once per day:
    HDFCBANK's 1:1 bonus, listed in 143 files and under two series, became a
    factor of 3.6e-12 that no price move could confirm, and the stock kept its full
    split drop.
    """
    if actions.empty:
        return actions
    key = [c for c in ACTION_KEY if c in actions.columns]
    return actions.drop_duplicates(subset=key).reset_index(drop=True)
