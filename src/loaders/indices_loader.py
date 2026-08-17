"""
Index constituents loader with live official NSE sync, multi-tier caching, and local fallbacks.
"""

from __future__ import annotations

import io
import json
import os
import time
from datetime import datetime
from typing import Any, Sequence

import pandas as pd
import requests
import streamlit as st

from src.core.config import (
    DATA_DIR,
    HTTP_HEADERS,
    INDICES_LOCAL,
    INDICES_URLS,
    REPO_DATA_DIR,
    SHORT_FORMS,
)
from src.core.logger import logger

SYNC_META_FILE = os.path.join(REPO_DATA_DIR, "indices_sync_meta.json")


def get_sync_metadata() -> dict[str, Any]:
    """Reads index sync metadata from disk."""
    if os.path.exists(SYNC_META_FILE):
        try:
            with open(SYNC_META_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"last_synced": None, "total_stocks": 0, "indices": {}}


def _save_sync_metadata(meta: dict[str, Any]) -> None:
    """Saves index sync metadata to disk."""
    try:
        os.makedirs(os.path.dirname(SYNC_META_FILE), exist_ok=True)
        with open(SYNC_META_FILE, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)
    except Exception as e:
        logger.warning(f"Could not save sync metadata: {e}")


def sync_official_nse_indices(force: bool = True) -> dict[str, Any]:
    """
    Downloads live constituent CSVs directly from official niftyindices.com servers
    and writes them to data/indices/ on disk, keeping the repo 100% up to date with
    recent rebalances, mergers, and delistings.
    """
    results: dict[str, Any] = {"success": True, "downloaded": {}, "errors": {}}
    os.makedirs(os.path.join(DATA_DIR, "indices"), exist_ok=True)

    total_unique_stocks: set[str] = set()

    for idx_name, url in INDICES_URLS.items():
        if idx_name == "NIFTY TOTAL MARKET":
            continue  # Total Market is maintained as the canonical master CSV.

        downloaded_ok = False
        for attempt in range(3):
            try:
                resp = requests.get(url, headers=HTTP_HEADERS, timeout=15)
                if resp.status_code == 200 and len(resp.content) > 200:
                    text_content = resp.content.decode("utf-8-sig", errors="replace")
                    df = pd.read_csv(io.StringIO(text_content))
                    df.columns = [c.strip() for c in df.columns]
                    sym_col = next(
                        (c for c in df.columns if c.lower() in ("symbol", "ticker")),
                        None,
                    )

                    if sym_col and len(df) > 0:
                        local_path = INDICES_LOCAL.get(idx_name)
                        if local_path:
                            os.makedirs(os.path.dirname(local_path), exist_ok=True)
                            with open(local_path, "w", encoding="utf-8") as f:
                                f.write(text_content)
                            logger.info(
                                f"[SYNC] Synced {idx_name} ({len(df)} constituents) -> {local_path}"
                            )
                            results["downloaded"][idx_name] = {
                                "count": len(df),
                                "status": "Updated",
                                "time": datetime.now().isoformat(),
                            }
                            total_unique_stocks.update(
                                df[sym_col].astype(str).str.strip().str.upper()
                            )
                            downloaded_ok = True
                            break
            except Exception as e:
                logger.warning(f"Attempt {attempt+1}/3 failed for {idx_name}: {e}")
            time.sleep(1)

        if not downloaded_ok:
            results["errors"][idx_name] = "Live fetch failed; using existing fallback"
            results["success"] = False

    meta = {
        "last_synced": datetime.now().strftime("%d %b %Y, %H:%M"),
        "timestamp": datetime.now().isoformat(),
        "total_stocks": len(total_unique_stocks),
        "indices": results["downloaded"],
    }
    _save_sync_metadata(meta)
    return meta


def _fetch_indices_impl(selected_indices: Sequence[str] | None = None) -> pd.DataFrame:
    """Core logic to fetch, parse, and auto-persist index constituent CSVs."""
    stock_map: dict[str, dict[str, Any]] = {}
    discarded: list[str] = []
    nse_failed: list[str] = []

    for idx_name, url in INDICES_URLS.items():
        csv_text: str | None = None
        is_live = False

        # Layer 1: Live NSE download (3 attempts with exponential backoff)
        for attempt in range(3):
            try:
                resp = requests.get(url, headers=HTTP_HEADERS, timeout=15)
                if resp.status_code == 200 and len(resp.content) > 200:
                    csv_text = resp.content.decode("utf-8-sig", errors="replace")
                    is_live = True
                    # Auto-persist fresh content to disk so local offline copy is never stale
                    local_path = INDICES_LOCAL.get(idx_name)
                    if local_path:
                        try:
                            os.makedirs(os.path.dirname(local_path), exist_ok=True)
                            with open(local_path, "w", encoding="utf-8") as f:
                                f.write(csv_text)
                            logger.debug(f"Persisted live {idx_name} to disk")
                        except Exception as e:
                            logger.debug(f"Could not persist {idx_name} to disk: {e}")
                    break
                logger.warning(
                    f"{idx_name}: HTTP {resp.status_code} (attempt {attempt+1}/3)"
                )
            except requests.RequestException as e:
                logger.warning(
                    f"{idx_name}: request error (attempt {attempt+1}/3): {e}"
                )
            if attempt < 2:
                time.sleep(2**attempt)

        # Layer 2: Fall back to local CSV from repo
        if csv_text is None:
            local_path = INDICES_LOCAL.get(idx_name)
            if local_path and os.path.exists(local_path):
                try:
                    with open(local_path, "r", encoding="utf-8-sig", errors="replace") as f:
                        csv_text = f.read()
                    logger.info(f"{idx_name}: using local fallback ({local_path})")
                except Exception as e:
                    logger.error(f"{idx_name}: local fallback read failed: {e}")

        if csv_text is None:
            logger.error(
                f"{idx_name}: failed after 3 attempts + no local fallback — skipping"
            )
            nse_failed.append(idx_name)
            continue

        # Parse CSV
        try:
            df = pd.read_csv(io.StringIO(csv_text))
            df.columns = [c.strip() for c in df.columns]
            sym_col = next(
                (c for c in df.columns if c.lower() in ("symbol", "ticker")), None
            )
            ind_col = next(
                (
                    c
                    for c in df.columns
                    if c.lower() in ("industry", "sector", "macro economic sector")
                ),
                None,
            )
            if not (sym_col and ind_col):
                logger.warning(
                    f"{idx_name}: columns not recognized: {list(df.columns[:5])}"
                )
                continue

            count = 0
            name_col = next(
                (
                    c
                    for c in df.columns
                    if "company" in c.lower() or "name" in c.lower()
                ),
                None,
            )
            for _, row in df.iterrows():
                symbol = str(row[sym_col]).strip().upper()
                if symbol.startswith("DUMMY") or len(symbol) < 2 or symbol == "NAN":
                    discarded.append(symbol)
                    continue
                comp_name = (
                    str(row[name_col]).strip()
                    if name_col and pd.notna(row[name_col])
                    else symbol
                )
                if symbol not in stock_map:
                    stock_map[symbol] = {
                        "company_name": comp_name,
                        "industry": str(row[ind_col]).strip(),
                        "indices": set(),
                    }
                stock_map[symbol]["indices"].add(idx_name)
                count += 1
            logger.debug(f"{idx_name}: loaded {count} stocks (live={is_live})")
        except Exception as e:
            logger.error(f"{idx_name}: parse error: {e}")

    if nse_failed:
        logger.warning(
            f"NSE blocked {len(nse_failed)} indices: {', '.join(nse_failed)}"
        )

    if discarded:
        logger.debug(f"Discarded {len(discarded)} dummy/invalid symbols")

    rows = []
    for sym, info in stock_map.items():
        tags = sorted(
            SHORT_FORMS.get(i, i) for i in info["indices"] if SHORT_FORMS.get(i, i)
        )
        rows.append(
            {
                "Symbol": sym,
                "Company Name": info.get("company_name", sym),
                "Industry": info["industry"],
                "Indices": ", ".join(tags),
            }
        )

    full = pd.DataFrame(rows)
    logger.info(
        f"Loaded total universe: {len(full)} unique stocks from {len(INDICES_URLS)} indices"
    )

    # Update metadata if not recorded
    meta = get_sync_metadata()
    if not meta.get("last_synced") and not full.empty:
        _save_sync_metadata(
            {
                "last_synced": datetime.now().strftime("%d %b %Y, %H:%M"),
                "timestamp": datetime.now().isoformat(),
                "total_stocks": len(full),
                "indices": {
                    k: {"count": len(full), "status": "Loaded"} for k in INDICES_URLS
                },
            }
        )

    if full.empty or not selected_indices:
        return full

    keep = full["Symbol"].map(
        lambda s: bool(
            stock_map.get(s, {"indices": set()})["indices"] & set(selected_indices)
        )
    )
    filtered = full[keep].reset_index(drop=True)
    logger.info(
        f"Selected indices filter: {len(filtered)} stocks matching {selected_indices}"
    )
    return filtered


@st.cache_data(show_spinner=False, ttl=604800)  # 7 days cache
def fetch_indices_data(selected_indices: Sequence[str] | None = None) -> pd.DataFrame:
    """Public cached loader for index constituents."""
    key = tuple(sorted(selected_indices or []))
    return _fetch_indices_impl(list(key))
