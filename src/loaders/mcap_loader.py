"""
Market Capitalization loader with 3-tier fallback architecture:
1. NSE PR Bhavcopy zip (single request covering ~2800 stocks)
2. The market caps the daily sync committed to the repository
No Yahoo layer since 2026-10-02 (owner: Screener first, NSE second).
"""

from __future__ import annotations

import io
import os
import zipfile
from datetime import date, datetime
from typing import Sequence

import pandas as pd
import requests

from src.core import startup_metrics as metrics
from src.core.config import HTTP_HEADERS, MCAP_PR_FILE, REPO_MCAP_FILE
from src.core.market_time import recent_trading_days
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
        # Say what actually came back, per date. "NSE is unreachable from CI"
        # was believed here for a long time on the strength of a code comment
        # and a fetch that failed quietly -- and a 404 for an archive that is
        # simply not published yet looks identical, from the outside, to a
        # refusal. They call for opposite responses: wait, or stop trying.
        metrics.note(f"mcap_pr_status_{target_date.isoformat()}", resp.status_code)
        if resp.status_code in (401, 403, 429):
            logger.warning(
                "NSE PR archive refused this client for %s: HTTP %s",
                target_date, resp.status_code,
            )
            raise _NSEBlocked(f"HTTP {resp.status_code}")
        if resp.status_code != 200:
            logger.info(
                "NSE PR archive for %s: HTTP %s (not published yet, or a holiday)",
                target_date, resp.status_code,
            )
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

        # NSE equity series that can appear in the bhavcopy for a main-board
        # constituent.  EQ is normal rolling settlement.  BE is trade-for-trade
        # (enhanced surveillance, circuit stocks).  BL/BT are block-deal windows.
        # Non-equity instruments (SM=SME, ST/GB=bonds, RL/W1-W3=rights/warrants)
        # share the same bhavcopy file and must be excluded.
        #
        # When a symbol appears under more than one equity series on the same day
        # (uncommon but possible), prefer EQ because its closing price is the
        # regular market close; block-deal prices can differ.
        _EQUITY_SERIES = {"EQ", "BE", "BL", "BT"}
        col_series = next((c for c in df.columns if c.lower().strip() == "series"), None)
        if col_series is not None:
            df = df.copy()
            s = df[col_series].astype(str).str.strip().str.upper()
            df = df[s.isin(_EQUITY_SERIES)]
            # Sort so EQ rows come first; drop_duplicates(keep="first") then
            # picks EQ over BE/BL/BT when multiple rows exist for one symbol.
            df = df.assign(_eq=(s == "EQ").astype(int)).sort_values(
                "_eq", ascending=False
            ).drop(columns="_eq")
        df = df.drop_duplicates(subset=[col_sym], keep="first")

        result: dict[str, float] = df.set_index(col_sym)[col_mcap].to_dict()
    except _NSEBlocked:
        raise
    except Exception as e:
        # A timeout or DNS failure is not a refusal either, and swallowing it
        # at debug level is how this stayed a mystery.
        logger.warning(
            "NSE PR fetch failed for %s (%s: %s)", target_date, type(e).__name__, e
        )
        metrics.note(f"mcap_pr_error_{target_date.isoformat()}", type(e).__name__)
        return {}

    # OUTSIDE the try, deliberately. This log line used to sit inside it and
    # called target_date.date() -- but recent_trading_days() hands out
    # datetime.date, which has no .date(). So every fetch downloaded the zip,
    # opened it, parsed the CSV and built this dict, and then the LOGGING threw
    # AttributeError, the handler caught it, and the caller got {}. NSE was
    # answering perfectly every single day; the result was discarded on the way
    # out the door, and the silence was read as "NSE blocks this host".
    #
    # Nothing that merely reports on a result belongs where it can destroy one.
    logger.info(
        "Loaded NSE PR market cap: %d stocks for %s", len(result), target_date
    )
    metrics.note("mcap_pr_fetched_date", target_date.isoformat())
    return result


# One bhavcopy is published per trading day, so the cache is worth re-checking
# about once a day -- but the window has to sit BELOW the 24-hour cadence, not
# above it. At 30 hours a cache written on one nightly run was still "fresh" on
# the next, which is how the daily sync came to commit the previous day's
# market caps every single day. 22 hours keeps roughly two hours of slack for a
# late run (GitHub's scheduler has been firing this job ~28 minutes behind its
# cron) while guaranteeing the following day's run sees the cache as stale.
#
# The sync no longer depends on this -- it passes force_refresh=True, because a
# job whose purpose is a current snapshot should not consult a heuristic sized
# for interactive sessions. This governs the app's own reads.
MCAP_CACHE_MAX_AGE_S: int = 22 * 60 * 60


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
        return (datetime.now() - last).total_seconds() < MCAP_CACHE_MAX_AGE_S
    except Exception:
        return False


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
                except Exception as exc:
                    logger.warning("NSE PR market-cap cache write failed (%s).", type(exc).__name__)
                break

    # Layer 1c: market caps committed to the repository by the daily sync.
    # Used in two situations:
    # (a) Production cannot reach the NSE PR archive at all (NSE blocks the
    #     cloud host's IP) -- this file is then the only source.
    # (b) The live NSE PR zip succeeded but did not cover all constituents:
    #     a stock that hit a circuit breaker or was temporarily moved to the
    #     BE/BL series on that specific day is absent from the EQ bhavcopy,
    #     but is still a valid index member with a known market cap from the
    #     prior day's sync, which this top-up supplies.
    if os.path.exists(REPO_MCAP_FILE):
        gap = [s for s in symbols if s not in master]
        if not master or gap:
            try:
                repo_caps = pd.read_csv(REPO_MCAP_FILE)
                repo_caps["Symbol"] = repo_caps["Symbol"].astype(str).str.strip().str.upper()
                repo_caps["MarketCap"] = pd.to_numeric(repo_caps["MarketCap"], errors="coerce")
                repo_caps = repo_caps[repo_caps["MarketCap"].notna() & (repo_caps["MarketCap"] > 0)]
                repo_map = repo_caps.set_index("Symbol")["MarketCap"].to_dict()
                if repo_map:
                    if not master:
                        master = repo_map
                        metrics.note("mcap_path", "repo_snapshot")
                    else:
                        filled = {s: repo_map[s] for s in gap if s in repo_map}
                        if filled:
                            master.update(filled)
                            metrics.note("mcap_repo_gap_fill", len(filled))
                            logger.info(
                                "Repo snapshot gap-fill: %d symbol(s) not in today's bhavcopy: %s",
                                len(filled), ", ".join(sorted(filled)),
                            )
                    if "AsOf" in repo_caps.columns:
                        stamped = [v for v in repo_caps["AsOf"].dropna().astype(str) if v.strip()]
                        if stamped:
                            metrics.note("mcap_as_of", stamped[0])
                    logger.info(f"Repository market cap snapshot: {len(repo_map)} stocks")
            except Exception as e:
                logger.warning(f"Repository market cap snapshot unreadable: {e}")
                if not master:
                    master = {}

    # No Yahoo layer (owner, 2026-10-02): a stock neither NSE's bhavcopy nor
    # the committed snapshot carries stays without a cap, and says so.
    missing = [s for s in symbols if s not in master]
    if missing:
        metrics.note("mcap_unresolved_list", ",".join(sorted(missing)))
        logger.warning("No market cap from NSE or the snapshot for %d symbols: %s",
                       len(missing), ", ".join(sorted(missing)))

    vmap = {s: master[s] for s in symbols if s in master}
    metrics.note("mcap_symbols_requested", len(symbols))
    metrics.note("mcap_symbols_resolved", len(vmap))
    metrics.note("mcap_symbols_missing", len(symbols) - len(vmap))
    return pd.Series(vmap, dtype=float)

