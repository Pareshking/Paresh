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
from src.loaders.app_pack import resolve as _pack

LIST_PATH = os.path.join(REPO_DATA_DIR, "indices", "ind_nanocap_list.csv")
# NSE's Nifty 1000 list, written by the daily sync (S175).
NIFTY_1000_PATH = os.path.join(REPO_DATA_DIR, "indices", "ind_nifty1000_list.csv")


def members(path: str = LIST_PATH) -> pd.DataFrame:
    """The current list in the index loader's shape: Symbol, Company Name, Industry, Indices."""
    if not os.path.exists(path):
        return pd.DataFrame(columns=["Symbol", "Company Name", "Industry", "Indices"])
    frame = pd.read_csv(_pack(path))
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


def nifty_1000_members(path: str = NIFTY_1000_PATH) -> pd.DataFrame:
    """NSE's Nifty 1000 list in the index loader's shape, NSE's own industry kept.

    Indices is NANOCAP_250_SHORT for every row: system_universe() keeps the
    750's own rows (and their tags) and uses this only for the other 250.
    """
    if not os.path.exists(path):
        return pd.DataFrame(columns=["Symbol", "Company Name", "Industry", "Indices"])
    frame = pd.read_csv(_pack(path))
    frame.columns = [str(c).strip() for c in frame.columns]
    frame["Symbol"] = frame["Symbol"].astype(str).str.strip().str.upper()
    frame = frame[frame["Symbol"].map(is_tradeable_symbol)].drop_duplicates("Symbol")
    return pd.DataFrame({
        "Symbol": frame["Symbol"].values,
        "Company Name": frame["Company Name"].fillna(frame["Symbol"]).values,
        "Industry": frame["Industry"].fillna(xu.UNCLASSIFIED).map(nse_industry).values,
        "Indices": xu.NANOCAP_250_SHORT,
    }).reset_index(drop=True)


_LABELS_750: dict[str, str] | None = None
_UNMATCHED: set[str] = set()


def _industry_key(label) -> str:
    """A spelling-proof key: case, punctuation, spacing and "&" / "and" ignored."""
    import re
    return re.sub(r"[^a-z0-9]", "", str(label).lower().replace("&", "and"))


def _labels_750() -> dict[str, str]:
    """{key: label} for every industry the 750's own file (Nifty Total Market) uses."""
    global _LABELS_750
    if _LABELS_750 is None:
        path = os.path.join(REPO_DATA_DIR, "indices", "ind_niftytotalmarket_list.csv")
        try:
            frame = pd.read_csv(_pack(path))
            frame.columns = [str(c).strip() for c in frame.columns]
            _LABELS_750 = {_industry_key(v): str(v).strip() for v in frame["Industry"].dropna().unique()}
        except (OSError, KeyError, ValueError):
            _LABELS_750 = {}
    return _LABELS_750


def nse_industry(label) -> str:
    """NSE's industry in the 750's own spelling, matched automatically.

    The Nifty 1000 file wrote "Oil, Gas & Consumable Fuels" and "Media, Entertainment & Publication" where the 750's
    write them without commas, so one sector was two on Sectors and under the live sector cap (S194 F2). Owner,
    22 Nov 2026: "we should match both so in future same issue should be handled automatically". Every label is
    matched to the 750's label with the same key (case, punctuation, spacing, "&"/"and" ignored); a label the 750
    does not use at all is kept as NSE writes it and logged once by name.
    """
    text = " ".join(str(label).replace(",", " ").split())
    hit = _labels_750().get(_industry_key(label))
    if hit is not None:
        return hit
    if _labels_750() and text not in _UNMATCHED and text != xu.UNCLASSIFIED:
        _UNMATCHED.add(text)
        import logging
        logging.getLogger("nse_momentum").warning(
            "Nifty 1000 industry %r matches none of the 750's; kept as NSE writes it.", text)
    return text


@st.cache_data(show_spinner=False, ttl=3600)
def fetch_nifty_1000_members() -> pd.DataFrame:
    return nifty_1000_members()


def extra_members(system: str) -> pd.DataFrame:
    """The list a system adds to the 750: none, the ₹2,000 Cr list, or the Nifty 1000."""
    if system == xu.SYSTEM_750:
        return pd.DataFrame(columns=["Symbol"])
    return fetch_nifty_1000_members() if system == xu.SYSTEM_1000 else fetch_members()


def nanocap_250(base: pd.DataFrame, n1000: pd.DataFrame) -> pd.DataFrame:
    """NIFTY NANOCAP 250: the Nifty 1000's members outside the current 750."""
    base_symbols = set(base["Symbol"].astype(str).str.upper()) if not base.empty else set()
    if n1000.empty:
        return n1000
    return n1000[~n1000["Symbol"].astype(str).str.upper().isin(base_symbols)].reset_index(drop=True)


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
    """The stocks a system ranks: 750, effective Nano Cap, their union, or the Nifty 1000.

    `extra` is the list the system adds (extra_members): the ₹2,000 Cr list,
    or for the Nifty 1000 NSE's list. One definition for the app and the
    nightly precompute. The persisted Nano
    list is only a candidate list; the current 750 always has priority.
    """
    if system == xu.SYSTEM_1000:
        # The 750 with its own rows and tags, then NSE's other 250 (NIFTY NANOCAP 250).
        return pd.concat([base, nanocap_250(base, extra)], ignore_index=True)
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
    listed = pd.read_csv(_pack(path)) if os.path.exists(path) else None
    if listed is None or "MarketCapCr" not in listed.columns:
        return pd.Series(dtype=float)
    caps = listed.set_index("Symbol")["MarketCapCr"] * 1e7
    return caps.reindex(symbols).dropna()


def system_market_caps(symbols, nse_path: str | None = None, list_path: str = LIST_PATH) -> pd.Series:
    """Market caps in rupees for a system's ranked stocks (S193 C, K4).

    NSE's file (data/nse_market_caps.csv) holds the Nifty 1000 only: on 30 Oct it priced
    192 of the 411 stocks on the > ₹2,000 Cr list (₹7.2 lakh Cr of ₹36.9 lakh Cr), so a share
    "of the list's market value" left out every stock outside the Nifty 1000. NSE's daily file has
    them all; the nightly snapshot now keeps the list's stocks too (scripts/sync_data.py). A stock
    the snapshot still lacks takes its month-end value from the list itself.
    """
    from src.core.config import REPO_MCAP_FILE

    symbols = [str(s) for s in symbols]
    path = nse_path or REPO_MCAP_FILE
    try:
        nse = pd.read_csv(_pack(path)).set_index("Symbol")["MarketCap"]
        nse = pd.to_numeric(nse[~nse.index.duplicated()], errors="coerce").reindex(symbols)
    except (OSError, KeyError, ValueError):
        nse = pd.Series(index=symbols, dtype=float)
    missing = [s for s in symbols if pd.isna(nse.get(s))]
    if missing:
        nse = nse.fillna(list_market_caps(missing, list_path))
    return nse.dropna()


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
        with open(_pack(path), encoding="utf-8") as fh:
            months = json.load(fh).get("months", {})
    except (OSError, ValueError):
        return {}
    if not months:
        return {}
    as_of = max(months)
    entry = months[as_of]
    return {"as_of": as_of, "effective_from": entry.get("effective_from"),
            "count": entry.get("count", len(entry.get("symbols", [])))}
