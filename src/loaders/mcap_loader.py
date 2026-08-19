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


def fetch_mcaps_from_yfinance(symbols: Sequence[str]) -> pd.Series:
    """Ask Yahoo for every symbol's market cap, ignoring every cache.

    The layered fetch in fetch_market_caps deliberately reaches yfinance LAST
    and only for symbols nothing else covered, because the live app cannot
    afford 750 individual lookups on a cold start -- there is no bulk endpoint
    for market cap the way there is for prices, so it is one request per
    company.

    The nightly job has the opposite trade-off: nobody is waiting on it, and it
    is the only place that can pay this cost once on everyone's behalf. When
    NSE refuses the runner, this is how the caps still come back with a date
    attached instead of being served undated forever.
    """
    resolved = _fetch_mcaps_yfinance(list(symbols))
    clean = {
        s: float(v) for s, v in resolved.items()
        if v is not None and not (isinstance(v, float) and np.isnan(v)) and float(v) > 0
    }
    metrics.note("mcap_yfinance_sweep_requested", len(symbols))
    metrics.note("mcap_yfinance_sweep_resolved", len(clean))
    return pd.Series(clean, dtype=float)


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

