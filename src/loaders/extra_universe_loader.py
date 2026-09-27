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
PRICES_EXTRA = "app/prices_extra"
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
    """The nightly file: R2 first, the release second. None when neither serves."""
    body = app_source.fetch_latest(PRICES_EXTRA, "prices_extra")
    if body is not None:
        try:
            app_source.record("prices_extra", "r2")
            return pd.read_parquet(io.BytesIO(body))
        except Exception as exc:
            logger.info("prices_extra from R2 unreadable (%s).", type(exc).__name__)
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
