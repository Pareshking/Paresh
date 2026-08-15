"""
Central configuration for NSE Momentum Dashboard.
"""

import os
from typing import Dict, List

# ── Environment & Storage Paths ──────────────────────────────────────────────
IS_STREAMLIT_CLOUD = (
    os.getenv("STREAMLIT_SHARING_MODE") == "enabled"
    or os.getenv("HOME", "").startswith("/home/appuser")
    or os.getenv("HOME", "").startswith("/home/adminuser")
    or os.path.exists("/mount/src")
)

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA_DIR = "/tmp/data_cache" if IS_STREAMLIT_CLOUD else os.path.join(BASE_DIR, "data_cache")
STORAGE_MODE = "streamlit-cloud" if IS_STREAMLIT_CLOUD else "local"
os.makedirs(DATA_DIR, exist_ok=True)

# Cache Files
PRICES_FILE = os.path.join(DATA_DIR, "prices.parquet")
MCAPS_FILE = os.path.join(DATA_DIR, "market_caps.parquet")
MCAP_PR_FILE = os.path.join(DATA_DIR, "mcap_nse.parquet")
DELIVERY_FILE = os.path.join(DATA_DIR, "delivery.parquet")
DELIVERY_META_FILE = os.path.join(DATA_DIR, "delivery_meta.json")

# Static Taxonomy & Index Fallbacks
REPO_DATA_DIR = os.path.join(BASE_DIR, "data")
INDICES_DIR = os.path.join(REPO_DATA_DIR, "indices")
TV_CLASSIFICATION_FILE = os.path.join(REPO_DATA_DIR, "nse_tv_classification.csv")

# ── NSE & Index Endpoints ───────────────────────────────────────────────────
INDICES_URLS: Dict[str, str] = {
    "NIFTY 50": "https://niftyindices.com/IndexConstituent/ind_nifty50list.csv",
    "NIFTY NEXT 50": "https://niftyindices.com/IndexConstituent/ind_niftynext50list.csv",
    "NIFTY MIDCAP 150": "https://niftyindices.com/IndexConstituent/ind_niftymidcap150list.csv",
    "NIFTY SMALLCAP 250": "https://niftyindices.com/IndexConstituent/ind_niftysmallcap250list.csv",
    "NIFTY MICROCAP 250": "https://niftyindices.com/IndexConstituent/ind_niftymicrocap250_list.csv",
    "NIFTY TOTAL MARKET": "https://niftyindices.com/IndexConstituent/ind_niftytotalmarket_list.csv",
}

INDICES_LOCAL: Dict[str, str] = {
    "NIFTY 50": os.path.join(INDICES_DIR, "ind_nifty50list.csv"),
    "NIFTY NEXT 50": os.path.join(INDICES_DIR, "ind_niftynext50list.csv"),
    "NIFTY MIDCAP 150": os.path.join(INDICES_DIR, "ind_niftymidcap150list.csv"),
    "NIFTY SMALLCAP 250": os.path.join(INDICES_DIR, "ind_niftysmallcap250list.csv"),
    "NIFTY MICROCAP 250": os.path.join(INDICES_DIR, "ind_niftymicrocap250_list.csv"),
    "NIFTY TOTAL MARKET": os.path.join(INDICES_DIR, "ind_niftytotalmarket_list.csv"),
}

SHORT_FORMS: Dict[str, str] = {
    "NIFTY 50": "N50",
    "NIFTY NEXT 50": "NN50",
    "NIFTY MIDCAP 150": "MID150",
    "NIFTY SMALLCAP 250": "SMALL250",
    "NIFTY MICROCAP 250": "MICRO250",
    "NIFTY TOTAL MARKET": "",
}

HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
}

# ── Model Parameters & Default Weights ──────────────────────────────────────
MOMENTUM_WINDOWS: List[int] = [21, 63, 126, 189, 252]  # 1M, 3M, 6M, 9M, 12M
DEFAULT_LOOKBACK_WEIGHTS: List[float] = [0.10, 0.30, 0.30, 0.20, 0.10]

DEFAULT_SECTOR_CAP: float = 0.30  # 30% max in single sector
DEFAULT_STOCK_CAP: float = 0.05   # 5% max in single stock
DEFAULT_TARGET_VOL: float = 0.25  # 25% annualized target volatility

# ── Color Tokens (Pure Paper White Theme) ──────────────────────────────────
THEME = {
    "bg_main": "#ffffff",
    "bg_surface": "#f8fafc",
    "bg_card": "#ffffff",
    "border": "#e2e8f0",
    "border_subtle": "#f1f5f9",
    "text_primary": "#0f172a",
    "text_secondary": "#475569",
    "text_muted": "#64748b",
    "primary": "#4f46e5",
    "primary_light": "#eef2ff",
    "emerald": "#059669",
    "emerald_light": "#ecfdf5",
    "rose": "#e11d48",
    "rose_light": "#fff1f2",
    "amber": "#d97706",
    "amber_light": "#fef3c7",
    "sky": "#0284c7",
    "sky_light": "#f0f9ff",
}
