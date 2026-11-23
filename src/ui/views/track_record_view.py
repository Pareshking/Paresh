"""Month-to-date prices and figures for the Portfolio page's record (portfolio_page.py).

What is left of the old Track Record tab: each system's own price frame
(`_comparison_price_frame`) and the running month under the record's pinned
configuration (`_record_mtd`). The frozen months are read from the ledgers in
data/ and never recomputed here.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.engine.extra_universe import SYSTEM_750
from src.engine.model_record import record_run
from src.engine.systems import membership_for


def _comparison_price_frame(system: str, selected_system: str, _fallback: pd.DataFrame) -> pd.DataFrame:
    """Build the MTD price frame from the system's own canonical universe.

    The Portfolio page normally loads the selected system's prices. That frame
    is valid for Nifty 750, but it cannot be reused for Nano Cap because Nano
    is deliberately disjoint from the 750; Combined may contain both. The
    comparison must therefore resolve each system independently.

    Screener is the canonical current ranking-price source. Membership comes
    from the same point-in-time system timeline used by record_run(). No
    fallback to another system is allowed: doing so would silently report a
    wrong MTD portfolio under the right system name.
    """
    # For the system currently selected in Portfolio, use the exact same
    # validated price frame already consumed by record_run(). This keeps the
    # headline MTD and the side-by-side MTD numerically identical. Other systems
    # still resolve their own independent canonical price frame below.
    #
    # Returned directly, never through a cache: this branch used to sit inside
    # an st.cache_data keyed on the two system names only, so after the prices
    # moved on the comparison kept serving the frame it had pickled, for up to
    # an hour (and held a 28 MB copy of it).
    if system == selected_system:
        return _fallback
    try:
        from src.loaders import screener_cache

        store, revision = screener_cache.configured()
        if store is None:
            return pd.DataFrame()
        frame = _system_prices(system, revision, store)
    except Exception:
        # A missing canonical source is a data condition, not permission to
        # substitute the currently selected system's prices.
        return pd.DataFrame()
    return frame.copy(deep=False)


@st.cache_resource(show_spinner=False, ttl=3600, max_entries=4)
def _system_prices(system: str, store_revision: str, _store: pd.DataFrame) -> pd.DataFrame:
    """One system's closes from the shared Screener store, once per revision.

    The store is the app's own (src/loaders/screener_cache.py), not a second
    download; callers get a shallow copy, which pandas copy-on-write keeps
    from reaching this one.
    """
    history = membership_for(system)
    if not history:
        return pd.DataFrame()
    from src.loaders import price_source

    chosen = price_source.from_screener(_store)
    if chosen is None or chosen.close.empty:
        return pd.DataFrame()

    # Keep every symbol appearing in the system's membership timeline.
    # record_run() itself applies the point-in-time membership and former-
    # member logic, so the price frame should not be narrowed to the
    # currently selected Portfolio's symbols.
    symbols = set()
    baseline = history.get("baseline") or {}
    symbols.update(str(s).upper() for s in (baseline.get("symbols") or []))
    for change in history.get("changes") or []:
        # The history writes "added"/"removed" (index_universe.ever_members); "add"/"remove"
        # matched nothing, so later joiners (ENNATURE) had no prices here (S194 F1).
        symbols.update(str(s).upper() for s in (change.get("added") or []))
        symbols.update(str(s).upper() for s in (change.get("removed") or []))
    if not symbols:
        return pd.DataFrame()

    available = [c for c in chosen.close.columns
                 if str(c).upper() in symbols]
    return chosen.close.loc[:, available] if available else pd.DataFrame()


def _record_mtd(
    adj_close: pd.DataFrame, benchmark_close: pd.Series | None, system: str = SYSTEM_750
) -> dict:
    """Month-to-date under the RECORD's configuration, not the Backtest tab's.

    The Backtest tab's sliders are for exploring. If MTD were taken from
    whatever they happen to be set to, the running month would be measured on a
    different strategy from every frozen month beside it, and the year-to-date
    column would silently mix the two. So run the pinned configuration.
    """
    return record_run(adj_close, benchmark_close, system).get("live_meta", {}) or {}
