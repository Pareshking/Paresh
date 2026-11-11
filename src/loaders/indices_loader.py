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
from src.core.tickers import is_tradeable_symbol

SYNC_META_FILE = os.path.join(REPO_DATA_DIR, "indices_sync_meta.json")

# When each constituent CSV in data/indices/ was last written from a live
# download, under this key in the sync metadata. It is additive and feeds no
# displayed figure: "last_synced", "total_stocks" and "indices" still move only
# on a complete five-index sync (see sync_official_nse_indices below).
LOCAL_FETCH_KEY = "local_csv_fetched"


def _local_max_age_s() -> float:
    """How old the committed CSV may be before it is downloaded again.

    The daily sync writes and COMMITS data/indices/*.csv, so a checkout that is
    up to a day old already holds the bytes a download would return. 24 hours
    is one cadence of the job that writes them: miss a night and the readers go
    back to downloading, exactly as they did before this cache existed.
    """
    return float(os.getenv("INDICES_LOCAL_MAX_AGE_S", 24 * 3600))


def _download_memo_s() -> float:
    """How long one process may reuse a CSV it has already downloaded.

    run_daily_sync() downloads the five lists in step 1 and then loads the
    universe in step 2, seconds later, in the same process: 11 requests for 6
    files. Minutes, not hours -- fetch_indices_data's own TTL is an hour, and a
    warm app asking again after that must really ask.
    """
    return float(os.getenv("INDICES_DOWNLOAD_MEMO_S", 600))


# url -> (time.monotonic() when fetched, decoded CSV text). Written by every
# live download, read only by _fetch_indices_impl: a reader may reuse bytes
# this process just fetched, but the Configuration tab's "sync now" button
# (sync_official_nse_indices(force=True)) must always really ask.
_DOWNLOAD_MEMO: dict[str, tuple[float, str]] = {}


def _memoised(url: str) -> str | None:
    hit = _DOWNLOAD_MEMO.get(url)
    if hit is None:
        return None
    age = time.monotonic() - hit[0]
    if age > _download_memo_s():
        return None
    return hit[1]


def reset_download_memo() -> None:
    """Forget what this process has downloaded (tests; a long-lived process)."""
    _DOWNLOAD_MEMO.clear()


def _download_index_csv(
    idx_name: str,
    url: str,
    delays: Sequence[float],
    accept=None,
    use_memo: bool = False,
) -> str | None:
    """Download one constituent CSV, at most once per URL per process.

    `delays` is how long to wait after each failed attempt (0 for none), so
    each caller keeps its own retry rhythm. `accept` lets a caller reject a
    200 whose body it cannot use and try again, as it did before.
    """
    if use_memo:
        memo = _memoised(url)
        if memo is not None:
            logger.debug("%s: reusing the copy this process already downloaded.", idx_name)
            return memo
    for attempt, delay in enumerate(delays):
        try:
            resp = requests.get(url, headers=HTTP_HEADERS, timeout=15)
            if resp.status_code == 200 and len(resp.content) > 200:
                text = resp.content.decode("utf-8-sig", errors="replace")
                if accept is None or accept(text):
                    _DOWNLOAD_MEMO[url] = (time.monotonic(), text)
                    return text
            else:
                logger.warning(
                    f"{idx_name}: HTTP {resp.status_code} (attempt {attempt+1}/{len(delays)})"
                )
        except Exception as e:
            logger.warning(f"Attempt {attempt+1}/{len(delays)} failed for {idx_name}: {e}")
        if delay:
            time.sleep(delay)
    return None


def _has_symbol_column(text: str) -> bool:
    try:
        df = pd.read_csv(io.StringIO(text))
    except Exception:
        return False
    df.columns = [c.strip() for c in df.columns]
    sym_col = next((c for c in df.columns if c.lower() in ("symbol", "ticker")), None)
    return bool(sym_col) and len(df) > 0


def committed_copy_age_s(idx_name: str, meta: dict[str, Any] | None = None) -> float | None:
    """Seconds since data/indices/<idx>.csv was last written from a download.

    None when there is no local file, or no record of one being fetched: an
    unstamped copy is treated as stale, so a reader downloads as before.
    """
    local_path = INDICES_LOCAL.get(idx_name)
    if not local_path or not os.path.exists(local_path):
        return None
    meta = get_sync_metadata() if meta is None else meta
    stamp = (meta.get(LOCAL_FETCH_KEY) or {}).get(idx_name)
    if not stamp:
        return None
    try:
        when = datetime.fromisoformat(str(stamp))
    except ValueError:
        return None
    return (datetime.now() - when).total_seconds()


def _committed_copy_is_fresh(idx_name: str, meta: dict[str, Any] | None = None) -> bool:
    age = committed_copy_age_s(idx_name, meta)
    return age is not None and 0 <= age <= _local_max_age_s()


def _record_local_fetches(fetched: dict[str, str], meta: dict[str, Any] | None = None) -> None:
    """Stamp the CSVs just written from a download, keeping every other key."""
    if not fetched:
        return
    meta = get_sync_metadata() if meta is None else meta
    stamps = dict(meta.get(LOCAL_FETCH_KEY) or {})
    stamps.update(fetched)
    meta[LOCAL_FETCH_KEY] = stamps
    _save_sync_metadata(meta)


def get_sync_metadata() -> dict[str, Any]:
    """Reads index sync metadata from disk."""
    if os.path.exists(SYNC_META_FILE):
        try:
            with open(SYNC_META_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:
            logger.warning("Unreadable %s (%s); treating as absent.", SYNC_META_FILE, type(exc).__name__)
    # Every key the successful path writes appears here too, holding None or a
    # zero. Callers may then read the shape unconditionally: a run that has
    # never succeeded reports "no sync yet" rather than a missing key, and a
    # failed run preserving these values keeps the same shape as a good one.
    return {
        "last_synced": None,
        "timestamp": None,
        "total_stocks": 0,
        "indices": {},
    }


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
    # idx -> when its committed CSV was written from this run's download.
    local_fetched: dict[str, str] = {}

    for idx_name, url in INDICES_URLS.items():
        if idx_name == "NIFTY TOTAL MARKET":
            continue  # Total Market is maintained as the canonical master CSV.

        downloaded_ok = False
        # Three attempts, a second apart, each rejecting a 200 whose body has
        # no symbol column -- as before. The memo is deliberately NOT read
        # here: this is also the Configuration tab's "sync now", and a forced
        # sync must really ask niftyindices.
        text_content = _download_index_csv(
            idx_name, url, delays=(1, 1, 1), accept=_has_symbol_column
        )
        if text_content is not None:
            try:
                df = pd.read_csv(io.StringIO(text_content))
                df.columns = [c.strip() for c in df.columns]
                sym_col = next(
                    (c for c in df.columns if c.lower() in ("symbol", "ticker")),
                    None,
                )
                local_path = INDICES_LOCAL.get(idx_name)
                if sym_col and len(df) > 0 and local_path:
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
                    local_fetched[idx_name] = datetime.now().isoformat()
                    downloaded_ok = True
            except Exception as e:
                logger.warning(f"Could not store {idx_name}: {e}")

        if not downloaded_ok:
            results["errors"][idx_name] = "Live fetch failed; using existing fallback"
            results["success"] = False

    # A run that fetched NOTHING must not stamp itself as a sync.
    #
    # This block used to overwrite last_synced unconditionally, so the run on
    # 2026-08-29 -- in which all five downloads failed, fifteen requests, not
    # one byte of constituent data -- recorded "last_synced: 29 Aug 2026,
    # 01:04" alongside "total_stocks: 0". The Configuration tab read that and
    # announced a green "Engine Active (0 Stocks)" under a reassuring
    # timestamp. The date recorded when the JOB RAN and was displayed as when
    # the DATA was refreshed, which are not the same fact and diverge exactly
    # when it matters.
    #
    # The headline figures now move only on a COMPLETE sync. A partial one
    # still writes each CSV it managed to fetch -- that is per-index and
    # already done above -- but its constituent count would be a real
    # undercount, and publishing an undercount as the universe size is how a
    # partial failure comes to look like a shrinking market.
    now = datetime.now()
    meta = get_sync_metadata()
    complete = bool(results["downloaded"]) and not results["errors"]

    if complete:
        meta.update({
            "last_synced": now.strftime("%d %b %Y, %H:%M"),
            "timestamp": now.isoformat(),
            "total_stocks": len(total_unique_stocks),
            "indices": results["downloaded"],
        })

    # Always recorded, success or not: "when did this last run" is a real
    # question, it is just a different one from "how current is the data".
    meta["last_attempt"] = now.strftime("%d %b %Y, %H:%M")
    meta["last_attempt_timestamp"] = now.isoformat()
    meta["last_attempt_fetched"] = len(results["downloaded"])
    meta["last_attempt_errors"] = results["errors"]
    meta["last_attempt_ok"] = complete

    # Which committed CSVs this run rewrote from a download, so the readers
    # below (and precompute_systems, and the app) can use them instead of
    # downloading the same bytes again.
    if local_fetched:
        stamps = dict(meta.get(LOCAL_FETCH_KEY) or {})
        stamps.update(local_fetched)
        meta[LOCAL_FETCH_KEY] = stamps

    _save_sync_metadata(meta)
    return meta


def _fetch_indices_impl(
    selected_indices: Sequence[str] | None = None,
    prefer_local: bool = True,
) -> pd.DataFrame:
    """Core logic to fetch, parse, and auto-persist index constituent CSVs.

    `prefer_local` (the default) reads the committed data/indices/*.csv when the
    sync metadata says they were downloaded within INDICES_LOCAL_MAX_AGE_S. The
    daily sync writes and commits those files, so a reader was downloading the
    same bytes the checkout already held -- 6 requests on every cold start and
    again every hour, and 6 more from precompute_systems minutes after the sync
    wrote them. The job that REFRESHES the files passes prefer_local=False, so
    nothing here can let a committed copy go unrefreshed: a day without a
    successful sync makes the stamps stale and every reader downloads again,
    exactly as before.
    """
    stock_map: dict[str, dict[str, Any]] = {}
    discarded: list[str] = []
    nse_failed: list[str] = []
    meta_now = get_sync_metadata()
    local_fetched: dict[str, str] = {}

    for idx_name, url in INDICES_URLS.items():
        csv_text: str | None = None
        is_live = False

        # Layer 0: the committed copy, while the sync that writes it is current.
        if prefer_local and _committed_copy_is_fresh(idx_name, meta_now):
            local_path = INDICES_LOCAL.get(idx_name)
            try:
                with open(local_path, "r", encoding="utf-8-sig", errors="replace") as f:
                    csv_text = f.read()
                logger.debug(f"{idx_name}: using the committed copy ({local_path})")
            except Exception as e:
                logger.warning(f"{idx_name}: committed copy unreadable: {e}")
                csv_text = None

        # Layer 1: Live NSE download (3 attempts with exponential backoff)
        if csv_text is None:
            csv_text = _download_index_csv(
                idx_name, url, delays=(1, 2, 0), use_memo=True
            )
            if csv_text is not None:
                is_live = True
                # Auto-persist fresh content to disk so local offline copy is never stale
                local_path = INDICES_LOCAL.get(idx_name)
                if local_path:
                    try:
                        os.makedirs(os.path.dirname(local_path), exist_ok=True)
                        with open(local_path, "w", encoding="utf-8") as f:
                            f.write(csv_text)
                        logger.debug(f"Persisted live {idx_name} to disk")
                        local_fetched[idx_name] = datetime.now().isoformat()
                    except Exception as e:
                        logger.debug(f"Could not persist {idx_name} to disk: {e}")

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
                if not is_tradeable_symbol(symbol):
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
        stamps = dict(meta.get(LOCAL_FETCH_KEY) or {})
        stamps.update(local_fetched)
        _save_sync_metadata(
            {
                "last_synced": datetime.now().strftime("%d %b %Y, %H:%M"),
                "timestamp": datetime.now().isoformat(),
                "total_stocks": len(full),
                "indices": {
                    k: {"count": len(full), "status": "Loaded"} for k in INDICES_URLS
                },
                LOCAL_FETCH_KEY: stamps,
            }
        )
    else:
        # Stamp whichever committed CSVs this call rewrote from a download, so
        # the next reader (precompute_systems; the app's next cold start) takes
        # them from disk. Every other key is preserved.
        _record_local_fetches(local_fetched, meta)

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


@st.cache_data(show_spinner=False, ttl=3600)  # 1 hour: universe membership is a live production input
def fetch_indices_data(
    selected_indices: Sequence[str] | None = None,
    prefer_local: bool = True,
) -> pd.DataFrame:
    """Public cached loader for index constituents.

    prefer_local=False is for the job that REFRESHES data/indices/*.csv
    (scripts/sync_data.py); every other caller reads the committed copy while
    that job's stamp is current.
    """
    key = tuple(sorted(selected_indices or []))
    return _fetch_indices_impl(list(key), prefer_local=prefer_local)
