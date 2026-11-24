"""NSE's sector for the Screener's Sector column on Nano, Combined and the Nifty 1000.

NSE's index lists name a sector (the 22 groups) for their own members only, so the
> ₹2,000 Cr list was grouped by TradingView's sectors and its table showed "Health Technology"
where the 750 shows "Healthcare" (S189 item 6 (a)). data/reference/nse_classification.csv
(scripts/nse_classification.py, monthly) holds NSE's four levels for every stock the site
lists. This module gives the Screener's table NSE's sector in the 750's spelling:

  1. NSE's own lists: the Nifty Total Market's industry, then the Nifty 1000's;
  2. the classification file's Sector;
  3. the value the row already has.

`with_nse_levels` adds NSE's other levels beside it (S226: the owner, 24 Nov 2026, "remove trading
views sector or Industry and use Screener 4 level for any filtering"): NSE_Macro, NSE_Industry and
NSE_Basic_Industry, for the Screener's search and the Sectors page's grouping.

Display only. The ranking's "Industry" column also feeds the model plan's sector cap
(actions.plan_rebalance) and the record uses record_sector_map, so the caller passes a copy
to the Screener and Sectors and nothing here reaches a rank, a book or the record (the cap's
switch is measured by scripts/s226_measure.py and is the owner's to take).
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


# NSE's levels below and above the sector, as columns of a display copy (S226). The sector itself
# stays in "Industry", the name the 750's lists and every page already use for it.
LEVEL_COLUMNS = {"NSE_Macro": "Macro", "NSE_Industry": "Industry", "NSE_Basic_Industry": "Basic_Industry"}
# What a page calls each level (NSE's own names, docs/DATA_CORRECTNESS.md).
LEVEL_NAMES = {"Industry": "NSE sector", "NSE_Macro": "NSE macro sector", "NSE_Industry": "NSE industry",
               "NSE_Basic_Industry": "NSE basic industry"}
UNCLASSIFIED = xu.UNCLASSIFIED


def levels_map(classification_path: str = CLASSIFICATION_PATH) -> dict[str, dict[str, str]]:
    """{column: {symbol: label}} for NSE_Macro, NSE_Industry and NSE_Basic_Industry; {} without the file."""
    try:
        cls = pd.read_csv(classification_path, dtype=str, keep_default_na=False)
    except (OSError, ValueError):
        return {}
    if "Symbol" not in cls:
        return {}
    syms = cls["Symbol"].astype(str).str.strip().str.upper()
    out: dict[str, dict[str, str]] = {}
    for col, level in LEVEL_COLUMNS.items():
        if level not in cls:
            continue
        out[col] = {s: " ".join(str(v).split()) for s, v in zip(syms, cls[level]) if str(v).strip()}
    return out


@st.cache_data(show_spinner=False, ttl=3600)
def fetch_levels_map() -> dict[str, dict[str, str]]:
    return levels_map()


def coverage(frame: pd.DataFrame, labels: dict[str, str]) -> float:
    """Share of `frame`'s symbols `labels` names (0 for an empty frame)."""
    if frame is None or frame.empty or "Symbol" not in frame:
        return 0.0
    return float(frame["Symbol"].astype(str).str.upper().map(labels).notna().mean())


def with_nse_levels(frame: pd.DataFrame, system: str, sectors: dict[str, str] | None = None,
                    levels: dict[str, dict[str, str]] | None = None,
                    min_coverage: float = MIN_COVERAGE) -> pd.DataFrame:
    """A display copy: "Industry" as `with_nse_sectors` gives it, plus NSE's other levels.

    Each level is added only when it covers `min_coverage` of the rows, so a page never offers a
    grouping that holds half the stocks. A stock the file lacks reads UNCLASSIFIED at that level
    and is counted in `attrs["nse_unclassified"]` ({column: n}); TradingView's labels are never
    mixed into NSE's levels. `attrs["nse_sectors"]` is True when "Industry" holds NSE's sector
    (always on the 750, on the others when the sector passed the coverage guard). The input frame
    is never changed.
    """
    if frame is None or frame.empty or "Symbol" not in frame:
        return frame
    sectors = fetch_sector_map() if sectors is None else sectors
    levels = fetch_levels_map() if levels is None else levels
    out = with_nse_sectors(frame, system, sectors, min_coverage)
    out = frame.copy() if out is frame else out
    out.attrs = dict(frame.attrs)
    out.attrs["nse_sectors"] = system == xu.SYSTEM_750 or coverage(frame, sectors) >= min_coverage
    sym = out["Symbol"].astype(str).str.upper()
    missing: dict[str, int] = {}
    for col in LEVEL_COLUMNS:
        labels = levels.get(col) or {}
        mapped = sym.map(labels)
        if mapped.notna().mean() < min_coverage:
            continue
        missing[col] = int(mapped.isna().sum())
        out[col] = mapped.fillna(UNCLASSIFIED)
    out.attrs["nse_unclassified"] = missing
    return out


def nse_levels_present(frame: pd.DataFrame) -> list[str]:
    """The NSE level columns a display copy carries, macro first, basic industry last."""
    return [c for c in LEVEL_COLUMNS if frame is not None and c in frame]
