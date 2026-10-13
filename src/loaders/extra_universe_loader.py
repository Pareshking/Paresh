"""The extra universe for the app: its member list and market caps.

Kept apart from the 750's loaders on purpose: the index loader fetches NSE's
live lists, and this list is our own. So the extra universe has its own list
reader, and nothing here touches the 750's.

Its prices come from the Screener store, which holds both universes, with NSE
for what Screener lacks (src/loaders/price_source.py). The Yahoo download that
used to sit here was removed (TODO S10, 13 Oct 2026).
"""

from __future__ import annotations

import os

import pandas as pd
import streamlit as st

from src.core.config import REPO_DATA_DIR
from src.core.tickers import is_tradeable_symbol
from src.engine import extra_universe as xu

LIST_PATH = os.path.join(REPO_DATA_DIR, "indices", "ind_nanocap_list.csv")


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
