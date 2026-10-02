"""The extra universe for the app: its member list and its Yahoo prices.

Kept apart from the 750's loaders on purpose. The 750's price cache judges
each session by how much of the universe has printed, and ~420 thinner stocks
in that cache would move those judgements; the index loader fetches NSE's
live lists, and this list is our own. So the extra universe has its own list
reader and its own price file (prices_extra.parquet, written nightly by
scripts/sync_extra_yahoo.py), and nothing here touches the 750's.

The ranking itself still comes from the Screener store, which holds both
universes; this Yahoo file supplies what Screener lacks (High, Low, Open) and
the depth the backtest needs, exactly as the 750's Yahoo file does.
"""

from __future__ import annotations

import io
import os

import pandas as pd
import requests
import streamlit as st

from src.core.config import PRICE_SNAPSHOT_REPO, PRICE_SNAPSHOT_TAG, REPO_DATA_DIR
from src.core.logger import logger
from src.core.tickers import is_tradeable_symbol
from src.engine import extra_universe as xu
from src.loaders import app_source

LIST_PATH = os.path.join(REPO_DATA_DIR, "indices", "ind_nanocap_list.csv")
PRICES_EXTRA_URL = (f"https://github.com/{PRICE_SNAPSHOT_REPO}/releases/download/"
                    f"{PRICE_SNAPSHOT_TAG}/prices_extra.parquet")
BATCH = 100


def members(path: str = LIST_PATH) -> pd.DataFrame:
    """The current list in the index loader's shape: Symbol, Company Name, Industry, Indices."""
    if not os.path.exists(path):
        return pd.DataFrame(columns=["Symbol", "Company Name", "Industry", "Indices"])
    frame = pd.read_csv(path)
    frame["Symbol"] = frame["Symbol"].astype(str).str.strip().str.upper()
    frame = frame[frame["Symbol"].map(is_tradeable_symbol)].drop_duplicates("Symbol")
    return pd.DataFrame({
        "Symbol": frame["Symbol"].values,
        "Company Name": frame["Company Name"].fillna(frame["Symbol"]).values,
        "Industry": frame["Industry"].fillna(xu.UNCLASSIFIED).values,
        "Indices": xu.SHORT_FORM,
    }).reset_index(drop=True)


@st.cache_data(show_spinner=False, ttl=3600)
def fetch_members() -> pd.DataFrame:
    return members()


def effective_nano(base: pd.DataFrame, extra: pd.DataFrame) -> pd.DataFrame:
    """Return Nano Cap candidates after giving the current 750 priority.

    The persisted Nano list is a month-end candidate set. Index rebalancing
    can move a candidate into the 750 before the next Nano rebuild, so the
    effective live Nano universe must always subtract the current 750.
    """
    base_symbols = set(base["Symbol"].astype(str).str.upper()) if not base.empty else set()
    out = extra[~extra["Symbol"].astype(str).str.upper().isin(base_symbols)].copy()
    assert_disjoint(base, out)
    return out.reset_index(drop=True)


def assert_disjoint(base: pd.DataFrame, nano: pd.DataFrame) -> None:
    """Hard invariant: effective Nano and the current 750 may never overlap."""
    base_symbols = set(base["Symbol"].astype(str).str.upper()) if not base.empty else set()
    nano_symbols = set(nano["Symbol"].astype(str).str.upper()) if not nano.empty else set()
    overlap = sorted(base_symbols & nano_symbols)
    if overlap:
        raise ValueError(
            "NANO universe disjointness invariant violated: " + ", ".join(overlap)
        )


def system_universe(system: str, base: pd.DataFrame, extra: pd.DataFrame) -> pd.DataFrame:
    """The stocks a system ranks: 750, effective Nano Cap, or their union.

    One definition for the app and the nightly precompute. The persisted Nano
    list is only a candidate list; the current 750 always has priority.
    """
    nano = effective_nano(base, extra)
    if system == xu.SYSTEM_NANO:
        return nano
    if system != xu.SYSTEM_COMBINED:
        return base
    return pd.concat([base, nano], ignore_index=True)


def split_symbols(system: str, idx_info: pd.DataFrame) -> tuple[list[str], list[str]]:
    """(core, extra): the part the 750's price files serve, and the rest."""
    symbols = idx_info["Symbol"].unique().tolist()
    tags = (idx_info.set_index("Symbol")["Indices"].astype(str)
            if "Indices" in idx_info else pd.Series(dtype=str))
    nano = system == xu.SYSTEM_NANO
    extra = [s for s in symbols if nano or tags.get(s, "") == xu.SHORT_FORM]
    extra_set = set(extra)
    return [s for s in symbols if s not in extra_set], extra


def list_market_caps(symbols: list[str], path: str = LIST_PATH) -> pd.Series:
    """The extra universe's market caps from its month-end list, in rupees.

    Not fetch_market_caps: production cannot reach NSE, its repo snapshot
    holds only the 750, and the fallback is one Yahoo request per stock.
    """
    listed = pd.read_csv(path) if os.path.exists(path) else None
    if listed is None or "MarketCapCr" not in listed.columns:
        return pd.Series(dtype=float)
    caps = listed.set_index("Symbol")["MarketCapCr"] * 1e7
    return caps.reindex(symbols).dropna()


def join_prices(core: pd.DataFrame | None, extra: pd.DataFrame | None,
                extra_symbols: list[str]) -> pd.DataFrame:
    """The 750's price frame beside the extra universe's, one copy per stock.

    The 750's Yahoo files keep every stock they ever held, so a stock that
    left the 750 for Nano Cap (HEG, 2026-09) is in both: two copies of the
    same columns, and the stale one was taken. The extra universe's file is
    the current one for its members, so the 750's copy is dropped.
    """
    parts = []
    if core is not None and not core.empty:
        drop = set(extra_symbols)
        parts.append(core.loc[:, [c for c in core.columns if c[0] not in drop]] if drop else core)
    if extra is not None and not extra.empty:
        parts.append(extra)
    parts = [f for f in parts if not f.empty]
    if not parts:
        return pd.DataFrame()
    return parts[0] if len(parts) == 1 else pd.concat(parts, axis=1).sort_index()


# ── Yahoo prices ─────────────────────────────────────────────────────────────

def strip_suffix(frame: pd.DataFrame) -> pd.DataFrame:
    """(SYM.NS, field) columns -> (SYM, field), rows with no price at all dropped."""
    if frame is None or frame.empty or not isinstance(frame.columns, pd.MultiIndex):
        return pd.DataFrame()
    frame = frame.copy()
    frame.columns = pd.MultiIndex.from_tuples(
        [(str(t).upper().removesuffix(".NS"), f) for t, f in frame.columns])
    idx = pd.DatetimeIndex(frame.index)
    if idx.tz is not None:
        idx = idx.tz_localize(None)
    frame.index = idx.normalize()
    return frame.dropna(how="all").sort_index()


def download(symbols: list[str], period: str = "2y", fetch=None) -> pd.DataFrame:
    """Yahoo's history for `symbols`, 100 tickers a call."""
    if fetch is None:
        import yfinance as yf

        def fetch(batch):
            return yf.download(batch, period=period, progress=False,
                               group_by="ticker", threads=True, auto_adjust=True)
    parts = []
    for start in range(0, len(symbols), BATCH):
        got = strip_suffix(fetch([s + ".NS" for s in symbols[start:start + BATCH]]))
        if not got.empty:
            parts.append(got)
    return pd.concat(parts, axis=1).sort_index() if parts else pd.DataFrame()


def _published() -> pd.DataFrame | None:
    """The nightly file from the GitHub release. None when it does not serve."""
    try:
        resp = requests.get(PRICES_EXTRA_URL, timeout=60)
        if resp.status_code == 200:
            app_source.record("prices_extra", "release")
            return pd.read_parquet(io.BytesIO(resp.content))
        logger.info("prices_extra release asset: HTTP %s", resp.status_code)
    except Exception as exc:
        logger.info("prices_extra release asset failed (%s).", type(exc).__name__)
    return None


@st.cache_data(show_spinner=False, ttl=3600)
def load_prices(sym_key: str, _symbols: list[str]) -> pd.DataFrame:
    """The extra universe's Yahoo OHLCV, one (symbol, field) column pair each.

    The published nightly file when there is one; otherwise a direct Yahoo
    download of the whole list (about a minute), so the page still works on
    the day the list first appears.
    """
    symbols = list(_symbols)
    frame = _published()
    if frame is None or frame.empty:
        logger.info("No published prices_extra; downloading %d symbols from Yahoo.", len(symbols))
        frame = download(symbols)
    if frame.empty:
        return frame
    keep = [c for c in frame.columns if c[0] in set(symbols)]
    return frame.loc[:, keep]


HISTORY_PATH = os.path.join(REPO_DATA_DIR, "nanocap_membership.json")


def membership_summary(path: str = HISTORY_PATH) -> dict:
    """The newest month's list: count, the session it came from, and its first day in use."""
    import json

    try:
        with open(path, encoding="utf-8") as fh:
            months = json.load(fh).get("months", {})
    except (OSError, ValueError):
        return {}
    if not months:
        return {}
    as_of = max(months)
    entry = months[as_of]
    return {"as_of": as_of, "effective_from": entry.get("effective_from"),
            "count": entry.get("count", len(entry.get("symbols", [])))}
