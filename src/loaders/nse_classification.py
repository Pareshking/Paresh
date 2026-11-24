"""NSE's sector for the Screener's Sector column on Nano, Combined and the Nifty 1000.

NSE's index lists name a sector (the 22 groups) for their own members only, so the
> ₹2,000 Cr list was grouped by TradingView's sectors and its table showed "Health Technology"
where the 750 shows "Healthcare" (S189 item 6 (a)). data/reference/nse_classification.csv
(scripts/nse_classification.py, monthly) holds NSE's four levels for every stock the site
lists. This module gives the Screener's table NSE's sector in the 750's spelling:

  1. NSE's own lists: the Nifty Total Market's industry, then the Nifty 1000's;
  2. the classification file's Sector;
  3. the value the row already has.

Display only. The ranking's "Industry" column also feeds the model plan's sector cap
(actions.plan_rebalance) and the record uses record_sector_map, so the caller passes a copy
to the Screener and nothing here reaches a rank, a book or the record.
"""

from __future__ import annotations

import os

import pandas as pd
import streamlit as st

from src.core.config import REPO_DATA_DIR
from src.engine import extra_universe as xu

CLASSIFICATION_PATH = os.path.join(REPO_DATA_DIR, "reference", "nse_classification.csv")
TOTAL_MARKET_PATH = os.path.join(REPO_DATA_DIR, "indices", "ind_niftytotalmarket_list.csv")


def _list_sectors(path: str) -> dict[str, str]:
    try:
        frame = pd.read_csv(path)
    except (OSError, ValueError):
        return {}
    frame.columns = [str(c).strip() for c in frame.columns]
    if "Symbol" not in frame or "Industry" not in frame:
        return {}
    frame = frame.dropna(subset=["Industry"])
    return dict(zip(frame["Symbol"].astype(str).str.strip().str.upper(), frame["Industry"].astype(str)))


def sector_map(classification_path: str = CLASSIFICATION_PATH,
               total_market_path: str = TOTAL_MARKET_PATH,
               nifty_1000_path: str | None = None) -> dict[str, str]:
    """{symbol: NSE sector, in the 750's spelling}: NSE's lists first, then the classification file."""
    from src.loaders.extra_universe_loader import NIFTY_1000_PATH, nse_industry

    out: dict[str, str] = {}
    try:
        cls = pd.read_csv(classification_path, dtype=str, keep_default_na=False)
        out.update({str(s).strip().upper(): v for s, v in zip(cls["Symbol"], cls["Sector"]) if str(v).strip()})
    except (OSError, KeyError, ValueError):
        pass
    out.update(_list_sectors(nifty_1000_path or NIFTY_1000_PATH))
    out.update(_list_sectors(total_market_path))
    return {s: nse_industry(v) for s, v in out.items() if str(v).strip() and v != xu.UNCLASSIFIED}


@st.cache_data(show_spinner=False, ttl=3600)
def fetch_sector_map() -> dict[str, str]:
    return sector_map()


# Below this share of a system's stocks with an NSE sector, the column stays as it was: half the
# rows in NSE's names and half in TradingView's is the mix S189 item 6 (a) removes (the file is
# filled by one sweep; until it runs, or if Screener stops it early, it covers only some).
MIN_COVERAGE = 0.9


def with_nse_sectors(frame: pd.DataFrame, system: str, sectors: dict[str, str] | None = None,
                     min_coverage: float = MIN_COVERAGE) -> pd.DataFrame:
    """A copy of `frame` whose Industry is NSE's sector where one is known; the 750 unchanged.

    A symbol with no NSE sector keeps the value it has (TradingView's sector on Nano). When
    fewer than `min_coverage` of the rows have one, the frame is returned as it is.
    """
    if system == xu.SYSTEM_750 or frame is None or frame.empty or "Symbol" not in frame:
        return frame
    sectors = fetch_sector_map() if sectors is None else sectors
    nse = frame["Symbol"].astype(str).str.upper().map(sectors)
    if nse.notna().mean() < min_coverage:
        import logging
        logging.getLogger("nse_momentum").warning(
            "NSE sector known for %d of %d stocks; the Screener keeps today's sectors.",
            int(nse.notna().sum()), len(frame))
        return frame
    out = frame.copy()
    current = out["Industry"] if "Industry" in out else pd.Series("", index=out.index)
    out["Industry"] = nse.fillna(current)
    return out
