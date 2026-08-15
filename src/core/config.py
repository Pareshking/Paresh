"""
Central configuration for NSE Momentum Dashboard.
Pure Paper White Design Tokens, Data Paths, and Quantitative Model Parameters.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Final

# ── Environment & Storage Paths ──────────────────────────────────────────────
IS_STREAMLIT_CLOUD: Final[bool] = bool(
    os.getenv("STREAMLIT_SHARING_MODE") == "enabled"
    or os.getenv("HOME", "").startswith("/home/appuser")
    or os.getenv("HOME", "").startswith("/home/adminuser")
    or os.path.exists("/mount/src")
)

BASE_DIR: Final[str] = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA_DIR: Final[str] = (
    "/tmp/data_cache" if IS_STREAMLIT_CLOUD else os.path.join(BASE_DIR, "data_cache")
)
STORAGE_MODE: Final[str] = "streamlit-cloud" if IS_STREAMLIT_CLOUD else "local"
os.makedirs(DATA_DIR, exist_ok=True)

# ── Cache Files (Parquet & JSON) ─────────────────────────────────────────────
PRICES_FILE: Final[str] = os.path.join(DATA_DIR, "prices.parquet")
MCAPS_FILE: Final[str] = os.path.join(DATA_DIR, "market_caps.parquet")
MCAP_PR_FILE: Final[str] = os.path.join(DATA_DIR, "mcap_nse.parquet")
DELIVERY_FILE: Final[str] = os.path.join(DATA_DIR, "delivery.parquet")
DELIVERY_META_FILE: Final[str] = os.path.join(DATA_DIR, "delivery_meta.json")

# ── Static Taxonomy & Index Fallbacks ────────────────────────────────────────
REPO_DATA_DIR: Final[str] = os.path.join(BASE_DIR, "data")
INDICES_DIR: Final[str] = os.path.join(REPO_DATA_DIR, "indices")
TV_CLASSIFICATION_FILE: Final[str] = os.path.join(REPO_DATA_DIR, "nse_tv_classification.csv")

# ── Official NSE & Index Constituent Endpoints ──────────────────────────────
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
    "NIFTY 50": "N50",
    "NIFTY NEXT 50": "NN50",
    "NIFTY MIDCAP 150": "MID150",
    "NIFTY SMALLCAP 250": "SMALL250",
    "NIFTY MICROCAP 250": "MICRO250",
    "NIFTY TOTAL MARKET": "",
}

HTTP_HEADERS: Final[dict[str, str]] = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}

# ── Quantitative Model Parameters & Default Lookbacks ───────────────────────
MOMENTUM_WINDOWS: Final[list[int]] = [21, 63, 126, 189, 252]  # 1M, 3M, 6M, 9M, 12M
DEFAULT_LOOKBACK_WEIGHTS: Final[list[float]] = [0.10, 0.30, 0.30, 0.20, 0.10]

DEFAULT_SECTOR_CAP: Final[float] = 0.30  # 30% max in single sector
DEFAULT_STOCK_CAP: Final[float] = 0.05  # 5% max in single stock
DEFAULT_TARGET_VOL: Final[float] = 0.25  # 25% annualized target volatility
DEFAULT_TRANSACTION_COST_BPS: Final[float] = 30.0  # 30 bps round-trip friction

# ── Pure Paper White Design System Color Palette ────────────────────────────
@dataclass(frozen=True)
class ThemeTokens:
    bg_main: str = "#ffffff"
    bg_surface: str = "#f8fafc"
    bg_card: str = "#ffffff"
    border: str = "#e2e8f0"
    border_subtle: str = "#f1f5f9"
    text_primary: str = "#0f172a"
    text_secondary: str = "#475569"
    text_muted: str = "#64748b"
    primary: str = "#4f46e5"
    primary_light: str = "#eef2ff"
    emerald: str = "#059669"
    emerald_light: str = "#ecfdf5"
    rose: str = "#e11d48"
    rose_light: str = "#fff1f2"
    amber: str = "#d97706"
    amber_light: str = "#fef3c7"
    sky: str = "#0284c7"
    sky_light: str = "#f0f9ff"


THEME_TOKENS: Final[ThemeTokens] = ThemeTokens()
THEME: Final[dict[str, str]] = {
    "bg_main": THEME_TOKENS.bg_main,
    "bg_surface": THEME_TOKENS.bg_surface,
    "bg_card": THEME_TOKENS.bg_card,
    "border": THEME_TOKENS.border,
    "border_subtle": THEME_TOKENS.border_subtle,
    "text_primary": THEME_TOKENS.text_primary,
    "text_secondary": THEME_TOKENS.text_secondary,
    "text_muted": THEME_TOKENS.text_muted,
    "primary": THEME_TOKENS.primary,
    "primary_light": THEME_TOKENS.primary_light,
    "emerald": THEME_TOKENS.emerald,
    "emerald_light": THEME_TOKENS.emerald_light,
    "rose": THEME_TOKENS.rose,
    "rose_light": THEME_TOKENS.rose_light,
    "amber": THEME_TOKENS.amber,
    "amber_light": THEME_TOKENS.amber_light,
    "sky": THEME_TOKENS.sky,
    "sky_light": THEME_TOKENS.sky_light,
}
