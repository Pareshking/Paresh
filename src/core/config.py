"""
Central configuration for NSE Momentum Dashboard.
Pure Paper White Design Tokens, Data Paths, and Quantitative Model Parameters.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Final

IS_STREAMLIT_CLOUD: Final[bool] = bool(
    os.getenv("STREAMLIT_SHARING_MODE") == "enabled"
    or os.getenv("HOME", "").startswith("/home/appuser")
    or os.getenv("HOME", "").startswith("/home/adminuser")
    or os.path.exists("/mount/src")
)
BASE_DIR: Final[str] = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA_DIR: Final[str] = "/tmp/data_cache" if IS_STREAMLIT_CLOUD else os.path.join(BASE_DIR, "data_cache")
STORAGE_MODE: Final[str] = "streamlit-cloud" if IS_STREAMLIT_CLOUD else "local"
os.makedirs(DATA_DIR, exist_ok=True)

PRICES_FILE: Final[str] = os.path.join(DATA_DIR, "prices.parquet")
MCAPS_FILE: Final[str] = os.path.join(DATA_DIR, "market_caps.parquet")
MCAP_PR_FILE: Final[str] = os.path.join(DATA_DIR, "mcap_nse.parquet")

REPO_DATA_DIR: Final[str] = os.path.join(BASE_DIR, "data")
INDICES_DIR: Final[str] = os.path.join(REPO_DATA_DIR, "indices")
TV_CLASSIFICATION_FILE: Final[str] = os.path.join(REPO_DATA_DIR, "nse_tv_classification.csv")
# Market caps committed to the repository by the daily sync. NSE blocks the
# production host's IP, so production cannot fetch the NSE PR archive itself;
# the sync runs on GitHub Actions, where NSE is reachable, and leaves the
# result here for production to read.
REPO_MCAP_FILE: Final[str] = os.path.join(REPO_DATA_DIR, "nse_market_caps.csv")
# All-time highs, computed from a long history by the daily sync job and read
# back instantly by production. See ATH_HISTORY_PERIOD below.
REPO_ATH_FILE: Final[str] = os.path.join(REPO_DATA_DIR, "nse_all_time_highs.csv")

INDICES_URLS: Final[dict[str, str]] = {
    "NIFTY 50": "https://niftyindices.com/IndexConstituent/ind_nifty50list.csv",
    "NIFTY NEXT 50": "https://niftyindices.com/IndexConstituent/ind_niftynext50list.csv",
    "NIFTY MIDCAP 150": "https://niftyindices.com/IndexConstituent/ind_niftymidcap150list.csv",
    "NIFTY SMALLCAP 250": "https://niftyindices.com/IndexConstituent/ind_niftysmallcap250list.csv",
    "NIFTY MICROCAP 250": "https://niftyindices.com/IndexConstituent/ind_niftymicrocap250_list.csv",
    "NIFTY TOTAL MARKET": "https://niftyindices.com/IndexConstituent/ind_niftytotalmarket_list.csv",
}

INDICES_LOCAL: Final[dict[str, str]] = {
    "NIFTY 50": os.path.join(INDICES_DIR, "ind_nifty50list.csv"),
    "NIFTY NEXT 50": os.path.join(INDICES_DIR, "ind_niftynext50list.csv"),
    "NIFTY MIDCAP 150": os.path.join(INDICES_DIR, "ind_niftymidcap150list.csv"),
    "NIFTY SMALLCAP 250": os.path.join(INDICES_DIR, "ind_niftysmallcap250list.csv"),
    "NIFTY MICROCAP 250": os.path.join(INDICES_DIR, "ind_niftymicrocap250_list.csv"),
    "NIFTY TOTAL MARKET": os.path.join(INDICES_DIR, "ind_niftytotalmarket_list.csv"),
}

SHORT_FORMS: Final[dict[str, str]] = {
    "NIFTY 50": "N50", "NIFTY NEXT 50": "NN50", "NIFTY MIDCAP 150": "MID150",
    "NIFTY SMALLCAP 250": "SMALL250", "NIFTY MICROCAP 250": "MICRO250", "NIFTY TOTAL MARKET": "",
}

HTTP_HEADERS: Final[dict[str, str]] = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}

# Single research benchmark used wherever V1 requires a market benchmark.
BENCHMARK_SYMBOL: Final[str] = "^CRSLDX"

# Canonical System-1 economic horizons. These are calendar months, not
# fixed trading-row windows. Session-based windows are defined only by the
# portfolio/risk component that intentionally needs them.
MOMENTUM_MONTHS: Final[list[int]] = [1, 3, 6, 9, 12]
# Backward-compatible engine name. The momentum engine consumes these same
# canonical calendar-month horizons; keeping the alias prevents an import
# contract break while the rest of the codebase migrates to MOMENTUM_MONTHS.
MOMENTUM_WINDOWS: Final[list[int]] = MOMENTUM_MONTHS
DEFAULT_LOOKBACK_WEIGHTS: Final[list[float]] = [0.10, 0.30, 0.30, 0.20, 0.10]
DEFAULT_SECTOR_CAP: Final[float] = 0.30
DEFAULT_STOCK_CAP: Final[float] = 0.05
DEFAULT_TARGET_VOL: Final[float] = 0.25
DEFAULT_TRANSACTION_COST_BPS: Final[float] = 30.0

@dataclass(frozen=True)
class ThemeTokens:
    bg_main: str = "#ffffff"; bg_surface: str = "#f8fafc"; bg_card: str = "#ffffff"; border: str = "#e2e8f0"
    border_subtle: str = "#f1f5f9"; text_primary: str = "#0f172a"; text_secondary: str = "#475569"; text_muted: str = "#64748b"
    primary: str = "#4f46e5"; primary_light: str = "#eef2ff"; emerald: str = "#059669"; emerald_light: str = "#ecfdf5"
    rose: str = "#e11d48"; rose_light: str = "#fff1f2"; amber: str = "#d97706"; amber_light: str = "#fef3c7"
    sky: str = "#0284c7"; sky_light: str = "#f0f9ff"

THEME_TOKENS: Final[ThemeTokens] = ThemeTokens()
THEME: Final[dict[str, str]] = {k: getattr(THEME_TOKENS, k) for k in ThemeTokens.__dataclass_fields__}


# ── Price history windows ────────────────────────────────────────────────────
# The screener pipeline's window. Every calendar-momentum pass walks this frame
# row by row, so its length drives the cold-start cost directly -- measured at
# roughly 20s for 500 sessions x 750 symbols and far more at 2500. Lengthening
# this is a cold-start decision, not just a storage one.
PRICE_HISTORY_PERIOD: Final[str] = "2y"

# The window used for all-time highs. Fetched by the daily sync job on GitHub
# Actions, where nobody is waiting, and committed as a small per-symbol
# snapshot -- so production gets a genuine long-run high without paying to
# download or traverse that history at startup.
#
# Only the sync job pays for lengthening this; production reads the same 31 KB
# either way. build_ath_snapshot reports its elapsed time and how far back the
# data actually reached, so the cost of this constant is visible in the job log
# rather than assumed.
#
# The real risk of a longer window is not time, it is data quality: Yahoo's old
# NSE history carries bad ticks and missing corporate actions, and one spurious
# print sets a permanent phantom high that pins a stock at "-90% from ATH"
# forever. ATHDate travels with every row so such a peak can be seen rather
# than trusted -- the screener shows it on hover over % ATH.
ATH_HISTORY_PERIOD: Final[str] = "20y"


# ── Price history snapshot ───────────────────────────────────────────────────
# Production runs on Streamlit Cloud, where DATA_DIR is /tmp and is wiped on
# every container restart. So a cold start re-downloaded two years of OHLCV for
# 750 symbols from Yahoo -- roughly 38 seconds, and the point at which Yahoo
# rate-limited a ticker and took the screener down twice on 2026-08-18.
#
# The daily sync already fetches that history on GitHub Actions, where nobody
# is waiting. It now publishes it as a RELEASE ASSET rather than committing it:
# at float32/zstd the frame is ~10.5 MB, and committing that daily would add
# ~2.5 GB a year to a repository against GitHub's ~1 GB soft limit. A release
# asset is replaced in place and carries no history.
#
# Production seeds its empty cache from that asset in one HTTPS GET, and the
# loader's existing incremental path then fetches only the sessions published
# since. If the asset cannot be reached the loader behaves exactly as it did
# before -- this is an accelerator, never a dependency.
PRICE_SNAPSHOT_TAG: Final[str] = os.getenv("UMIYA_PRICE_SNAPSHOT_TAG", "data-latest")
PRICE_SNAPSHOT_REPO: Final[str] = os.getenv("UMIYA_REPO", "Pareshking/Umiya")
PRICE_SNAPSHOT_ASSET: Final[str] = "prices.parquet"
PRICE_SNAPSHOT_URL: Final[str] = (
    f"https://github.com/{PRICE_SNAPSHOT_REPO}/releases/download/"
    f"{PRICE_SNAPSHOT_TAG}/{PRICE_SNAPSHOT_ASSET}"
)
