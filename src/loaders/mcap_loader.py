"""
Market Capitalization loader with 3-tier fallback architecture:
1. NSE PR Bhavcopy zip (single request covering ~2800 stocks)
2. Cached yfinance market caps (parquet)
3. Multi-threaded live yfinance scraper with multiple fallbacks
"""

from __future__ import annotations

import concurrent.futures
import io
import os
import time
import zipfile
from datetime import date, datetime, timedelta
from typing import Sequence

import numpy as np
import pandas as pd
import requests
import yfinance as yf

from src.core import startup_metrics as metrics
from src.core.config import HTTP_HEADERS, MCAP_PR_FILE, MCAPS_FILE, REPO_MCAP_FILE
from src.core.market_time import ist_now, recent_trading_days
from src.core.logger import logger


# Close prices from the most recent PR bhavcopy parse, keyed by symbol. Held
# beside the market caps rather than threaded through _fetch_mcap_from_pr_zip's
# return type, which several call sites treat as dict[str, float].
_PR_CLOSE_PRICES: dict[str, float] = {}


class _NSEBlocked(Exception):
    """NSE refused the client outright rather than lacking the file.

    A 401/403 means every other date will be refused too, so walking further
    back is guaranteed waste. On a cold start that cost up to five sequential
    15s requests before the fallback even began.
    """


def _fetch_mcap_from_pr_zip(target_date: datetime | date) -> dict[str, float]:
    """Download NSE Bhavcopy PR zip and extract mcap*.csv.

    Returns an empty dict when the archive for that date is simply not there
    (not published yet, or a holiday) -- the caller should try an earlier day.
    Raises _NSEBlocked when NSE refuses the client, where trying earlier days
    cannot help.
    """
    zip_date = target_date.strftime("%d%m%y")
    csv_date = target_date.strftime("%d%m%Y")
    zip_url = (
        f"https://archives.nseindia.com/archives/equities/bhavcopy/pr/PR{zip_date}.zip"
    )
    csv_filename = f"mcap{csv_date}.csv"

    try:
        resp = requests.get(zip_url, headers=HTTP_HEADERS, timeout=15)
        if resp.status_code in (401, 403, 429):
            raise _NSEBlocked(f"HTTP {resp.status_code}")
        if resp.status_code != 200:
            return {}

        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            names = zf.namelist()
            match = (
                csv_filename
                if csv_filename in names
                else next((n for n in names if n.lower().startswith("mcap")), None)
            )
            if not match:
                return {}

            with zf.open(match) as f:
                df = pd.read_csv(f)

        df.columns = df.columns.str.strip()
        col_sym = next((c for c in df.columns if "symbol" in c.lower()), None)
        col_mcap = next((c for c in df.columns if "market cap" in c.lower()), None)

        if not col_sym or not col_mcap:
            return {}

        # The close price NSE used for this market cap. Capturing it lets the
        # app scale a published market cap by the price move since the
        # bhavcopy, so the figure tracks today's price instead of being as old
        # as the last sync. See scale_market_caps_to_price().
        col_close = next(
            (c for c in df.columns if "close price" in c.lower()), None
        )

        df[col_sym] = df[col_sym].astype(str).str.strip().str.upper()
        df[col_mcap] = pd.to_numeric(
            df[col_mcap].astype(str).str.strip().str.replace(",", ""),
            errors="coerce",
        )
        df = df[df[col_mcap].notna() & (df[col_mcap] > 0)]

        # Equity series only. The same symbol can appear under other series
        # with a different paid-up value, and those rows would overwrite the
        # equity row in the dict below.
        col_series = next((c for c in df.columns if c.lower().strip() == "series"), None)
        if col_series is not None:
            eq = df[df[col_series].astype(str).str.strip().str.upper() == "EQ"]
            if not eq.empty:
                df = eq

        result: dict[str, float] = df.set_index(col_sym)[col_mcap].to_dict()

        if col_close is not None:
            closes = pd.to_numeric(
                df[col_close].astype(str).str.strip().str.replace(",", ""),
                errors="coerce",
            )
            _PR_CLOSE_PRICES.clear()
            _PR_CLOSE_PRICES.update(
                {
                    sym: float(px)
                    for sym, px in zip(df[col_sym], closes)
                    if pd.notna(px) and px > 0
                }
            )

        logger.info(
            f"Loaded NSE PR market cap: {len(result)} stocks for {target_date.date()}"
        )
        return result
    except _NSEBlocked:
        raise
    except Exception as e:
        logger.debug(f"PR mcap fetch failed for {target_date}: {e}")
        return {}


def _is_mcap_cache_fresh() -> bool:
    if not os.path.exists(MCAP_PR_FILE):
        return False
    try:
        df = pd.read_parquet(MCAP_PR_FILE)
        if df.empty:
            return False
        if "TradeDate" not in df.columns:
            # Written before the trade date travelled with the data. Treating it
            # as fresh keeps that gap alive forever: the disk path cannot report
            # a date, so the daily sync stamps its committed snapshot with an
            # empty AsOf and "Market caps" reads "date unknown" in the footer.
            # One refetch re-stamps it.
            return False
        last = pd.Timestamp(df["LastUpdated"].max())
        return (datetime.now() - last).total_seconds() < 108000  # 30 hours
    except Exception:
        return False


def _fetch_single_mcap(symbol: str) -> tuple[str, float]:
    """Single ticker market cap fetcher with fast_info and info fallbacks."""
    time.sleep(0.03)
    ticker_name = symbol + ".NS" if not symbol.endswith(".NS") else symbol
    tkr = yf.Ticker(ticker_name)

    # Method 1: fast_info.market_cap
    try:
        mcap = getattr(tkr.fast_info, "market_cap", None)
        if mcap and not (isinstance(mcap, float) and np.isnan(mcap)):
            return symbol, float(mcap)
    except Exception:
        pass

    # Method 2: price * shares
    try:
        p = getattr(tkr.fast_info, "last_price", None)
        s = getattr(tkr.fast_info, "shares", None)
        if p and s:
            return symbol, float(p * s)
    except Exception:
        pass

    # Method 3: info dict
    try:
        mcap = tkr.info.get("marketCap")
        if mcap:
            return symbol, float(mcap)
    except Exception:
        pass

    return symbol, np.nan


def _fetch_mcaps_yfinance(symbols: Sequence[str]) -> dict[str, float]:
    """Multi-threaded yfinance market cap scraper."""
    if not symbols:
        return {}

    result: dict[str, float] = {}
    failed: list[str] = []
    metrics.note("mcap_threaded_requested", len(symbols))

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        futs = {pool.submit(_fetch_single_mcap, s): s for s in symbols}
        for f in concurrent.futures.as_completed(futs):
            try:
                sym, mc = f.result(timeout=25)
                if mc is not None and not np.isnan(mc):
                    result[sym] = mc
                else:
                    failed.append(futs[f])
            except Exception:
                failed.append(futs[f])

    metrics.note("mcap_threaded_failed", len(failed))
    for sym in failed:
        metrics.incr("mcap_sequential_retries")
        try:
            _, mc = _fetch_single_mcap(sym)
            if mc is not None and not np.isnan(mc):
                metrics.incr("mcap_sequential_recovered")
                result[sym] = mc
        except Exception:
            pass

    return result


def fetch_market_caps(symbols: Sequence[str], force_refresh: bool = False) -> pd.Series:
    """
    Fetches market caps in Rs for requested symbols.
    """
    master: dict[str, float] = {}

    # Layer 1: NSE PR cache
    if not force_refresh and _is_mcap_cache_fresh():
        try:
            cache = pd.read_parquet(MCAP_PR_FILE)
            master = cache.set_index("Symbol")["MarketCap"].to_dict()
            metrics.note("mcap_path", "pr_disk_cache")
            if "ClosePrice" in cache.columns:
                _PR_CLOSE_PRICES.clear()
                _PR_CLOSE_PRICES.update({
                    str(sym): float(px)
                    for sym, px in zip(cache["Symbol"], cache["ClosePrice"])
                    if pd.notna(px) and float(px) > 0
                })
            if "TradeDate" in cache.columns:
                dated = [
                    str(v).strip() for v in cache["TradeDate"].dropna().astype(str)
                    if str(v).strip()
                ]
                if dated:
                    metrics.note("mcap_pr_date", dated[0])
                    metrics.note("mcap_as_of", dated[0])
            logger.info(f"NSE PR market cap cache hit: {len(master)} stocks")
        except Exception as e:
            logger.warning(f"NSE PR cache read error: {e}")
            master = {}

    # Layer 1b: Live NSE PR Bhavcopy zip
    if not master:
        logger.info("Attempting live NSE PR zip for market caps…")
        # Walk back through recent trading days: today's archive is not
        # published until after the close, and a holiday has no archive at
        # all, so the newest date that actually returns data wins. Weekends
        # are skipped outright; holidays cost one failed lookup each.
        for td in recent_trading_days(6):
            metrics.incr("mcap_pr_zip_attempts")
            try:
                nse_map = _fetch_mcap_from_pr_zip(td)
            except _NSEBlocked as exc:
                # Every earlier date would be refused too. Stop immediately
                # instead of burning the remaining attempts.
                metrics.note("mcap_pr_blocked", str(exc))
                logger.warning(f"NSE PR archive refused the client ({exc}); "
                               "skipping remaining dates and using fallback.")
                break
            if nse_map:
                metrics.note("mcap_path", "pr_live_zip")
                metrics.note("mcap_pr_date", td.isoformat())
                metrics.note("mcap_as_of", td.isoformat())
                master.update(nse_map)
                try:
                    # TradeDate travels with the data. It is a property of the
                    # bhavcopy, not of how the bhavcopy was obtained, so the
                    # disk-cache path below can report it too. Without it that
                    # path knew the caps but not their date, and the daily sync
                    # stamped the committed snapshot with an empty AsOf --
                    # which dropped "Market caps" out of the freshness ribbon.
                    cache_df = pd.DataFrame(
                        [
                            {"Symbol": k, "MarketCap": v,
                             "ClosePrice": _PR_CLOSE_PRICES.get(k),
                             "TradeDate": td.isoformat(),
                             "LastUpdated": datetime.now()}
                            for k, v in nse_map.items()
                        ]
                    )
                    cache_df.to_parquet(MCAP_PR_FILE, compression="snappy")
                except Exception:
                    pass
                break

    # Layer 1c: market caps committed to the repository by the daily sync.
    # Production cannot reach the NSE PR archive -- NSE blocks the host's IP --
    # so without this the only remaining source is yfinance, which on a cold
    # start meant 750 individual lookups and the slowest stage of startup.
    # The sync runs where NSE is reachable and leaves its result in the repo.
    if not master and os.path.exists(REPO_MCAP_FILE):
        try:
            repo_caps = pd.read_csv(REPO_MCAP_FILE)
            repo_caps["Symbol"] = repo_caps["Symbol"].astype(str).str.strip().str.upper()
            repo_caps["MarketCap"] = pd.to_numeric(repo_caps["MarketCap"], errors="coerce")
            repo_caps = repo_caps[repo_caps["MarketCap"].notna() & (repo_caps["MarketCap"] > 0)]
            master = repo_caps.set_index("Symbol")["MarketCap"].to_dict()
            if master:
                metrics.note("mcap_path", "repo_snapshot")
                if "ClosePrice" in repo_caps.columns:
                    _PR_CLOSE_PRICES.clear()
                    _PR_CLOSE_PRICES.update({
                        str(sym): float(px)
                        for sym, px in zip(repo_caps["Symbol"], repo_caps["ClosePrice"])
                        if pd.notna(px) and float(px) > 0
                    })
                if "AsOf" in repo_caps.columns:
                    stamped = [v for v in repo_caps["AsOf"].dropna().astype(str) if v.strip()]
                    if stamped:
                        metrics.note("mcap_as_of", stamped[0])
                logger.info(f"Repository market cap snapshot: {len(master)} stocks")
        except Exception as e:
            logger.warning(f"Repository market cap snapshot unreadable: {e}")
            master = {}

    # Layer 2: yfinance disk cache
    missing = [s for s in symbols if s not in master]
    if missing and not force_refresh and os.path.exists(MCAPS_FILE):
        try:
            yf_cache = pd.read_parquet(MCAPS_FILE)
            yf_cache["LastUpdated"] = pd.to_datetime(yf_cache["LastUpdated"])
            cutoff = datetime.now() - timedelta(hours=30)
            fresh = yf_cache[
                yf_cache["Symbol"].isin(missing) & (yf_cache["LastUpdated"] > cutoff)
            ]
            if not fresh.empty:
                yf_cached_map = fresh.set_index("Symbol")["MarketCap"].to_dict()
                master.update(yf_cached_map)
                missing = [s for s in symbols if s not in master]
        except Exception as e:
            logger.warning(f"yfinance mcap cache read error: {e}")

    # Layer 3: Live yfinance fetch
    if missing:
        metrics.note("mcap_yfinance_fallback_symbols", len(missing))
        logger.info(f"Fetching market caps from yfinance for {len(missing)} stocks…")
        yf_map = _fetch_mcaps_yfinance(missing)
        master.update(yf_map)

        if yf_map:
            try:
                new_rows = pd.DataFrame(
                    [
                        {"Symbol": k, "MarketCap": v, "LastUpdated": datetime.now()}
                        for k, v in yf_map.items()
                    ]
                )
                if os.path.exists(MCAPS_FILE):
                    existing = pd.read_parquet(MCAPS_FILE)
                    existing = existing[~existing["Symbol"].isin(yf_map.keys())]
                    updated = pd.concat([existing, new_rows], ignore_index=True)
                else:
                    updated = new_rows
                updated.to_parquet(MCAPS_FILE, compression="snappy")
            except Exception:
                pass

    vmap = {s: master[s] for s in symbols if s in master}
    metrics.note("mcap_symbols_requested", len(symbols))
    metrics.note("mcap_symbols_resolved", len(vmap))
    metrics.note("mcap_symbols_missing", len(symbols) - len(vmap))
    return pd.Series(vmap, dtype=float)


def pr_close_prices() -> pd.Series:
    """Close prices NSE used for the market caps currently loaded."""
    if not _PR_CLOSE_PRICES:
        return pd.Series(dtype=float)
    return pd.Series(_PR_CLOSE_PRICES, dtype=float)


def scale_market_caps_to_price(
    market_caps: pd.Series,
    latest_close: pd.Series,
    reference_close: pd.Series | None = None,
) -> tuple[pd.Series, int]:
    """Move each market cap from its bhavcopy date to today's price.

    NSE publishes a market cap and the close price it was computed from. Shares
    outstanding is the ratio of the two, and it changes only on a corporate
    action -- issuance, buyback, bonus -- while the price changes every session.
    So the stale half of a day-old market cap is the price, and that is the half
    we can replace:

        live = published * (today's close / bhavcopy close)

    which is identical to (published / bhavcopy close) * today's close, i.e.
    shares outstanding times the current price. Anchoring to NSE's own figure
    rather than to Issue Size sidesteps the partly-paid securities whose
    "Close Price/Paid up value" column is a paid-up value and not a price --
    160 of 2295 rows on 18 Aug 2026.

    Returns the scaled caps and how many were scaled. A symbol with no
    reference close keeps its published figure rather than being dropped.
    """
    if market_caps is None or market_caps.empty:
        return pd.Series(dtype=float), 0

    ref = pr_close_prices() if reference_close is None else reference_close
    if ref is None or ref.empty or latest_close is None or latest_close.empty:
        return market_caps, 0

    idx = market_caps.index
    ref_aligned = pd.to_numeric(ref.reindex(idx), errors="coerce")
    now_aligned = pd.to_numeric(latest_close.reindex(idx), errors="coerce")

    factor = now_aligned / ref_aligned.replace(0, np.nan)
    usable = factor.notna() & np.isfinite(factor) & (factor > 0)

    scaled = market_caps.copy()
    scaled[usable] = market_caps[usable] * factor[usable]
    return scaled, int(usable.sum())
