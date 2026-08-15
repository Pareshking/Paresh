"""
TradingView 119-industry and 20-sector taxonomy loader with automatic auto-reconciliation.
"""

from __future__ import annotations

import os

import pandas as pd
import streamlit as st

from src.core.config import TV_CLASSIFICATION_FILE
from src.core.logger import logger


@st.cache_data(show_spinner=False, ttl=86400)
def load_tv_classification() -> dict[str, dict[str, str]]:
    """
    Loads TradingView industry and sector classification from static CSV.
    Returns: {SYMBOL: {"TV_Sector": str, "TV_Industry": str}}
    """
    if not os.path.exists(TV_CLASSIFICATION_FILE):
        logger.warning("TV classification CSV not found — falling back to NSE industry")
        return {}

    try:
        df = pd.read_csv(TV_CLASSIFICATION_FILE)
        df["Symbol"] = df["Symbol"].astype(str).str.strip().str.upper()
        df = df.dropna(subset=["TV_Sector", "TV_Industry"]).drop_duplicates("Symbol")
        result: dict[str, dict[str, str]] = df.set_index("Symbol")[
            ["TV_Sector", "TV_Industry"]
        ].to_dict("index")
        logger.debug(
            f"Loaded TV classification: {len(result)} stocks, "
            f"{df['TV_Sector'].nunique()} sectors, {df['TV_Industry'].nunique()} industries"
        )
        return result
    except Exception as e:
        logger.error(f"Failed to load TV classification: {e}")
        return {}


def reconcile_and_update_tv_classification(universe_df: pd.DataFrame) -> None:
    """
    Automatically checks if any new universe constituents are missing from
    nse_tv_classification.csv, and appends them with their NSE sector/industry
    so new additions, IPOs, and rebalanced stocks are never missing.
    """
    if universe_df is None or universe_df.empty or "Symbol" not in universe_df.columns:
        return

    try:
        existing: set[str] = set()
        if os.path.exists(TV_CLASSIFICATION_FILE):
            df_exist = pd.read_csv(TV_CLASSIFICATION_FILE)
            df_exist["Symbol"] = df_exist["Symbol"].astype(str).str.strip().str.upper()
            existing = set(df_exist["Symbol"].tolist())
        else:
            df_exist = pd.DataFrame(columns=["Symbol", "TV_Sector", "TV_Industry"])

        new_rows: list[dict[str, str]] = []
        for _, row in universe_df.iterrows():
            sym = str(row["Symbol"]).strip().upper()
            if sym not in existing and len(sym) >= 2 and sym != "NAN":
                ind = str(row.get("Industry", "Other")).strip()
                new_rows.append(
                    {
                        "Symbol": sym,
                        "TV_Sector": ind,
                        "TV_Industry": ind,
                    }
                )
                existing.add(sym)

        if new_rows:
            os.makedirs(os.path.dirname(TV_CLASSIFICATION_FILE), exist_ok=True)
            updated_df = pd.concat(
                [df_exist, pd.DataFrame(new_rows)], ignore_index=True
            )
            updated_df.drop_duplicates("Symbol", inplace=True)
            updated_df.to_csv(TV_CLASSIFICATION_FILE, index=False)
            logger.info(
                f"[RECONCILE] Added {len(new_rows)} new stocks to TV classification on disk"
            )
    except Exception as e:
        logger.warning(f"Could not reconcile TV classification: {e}")
