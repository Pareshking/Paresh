"""
Central configuration for NSE Momentum Dashboard.
Pure Paper White Design Tokens, Data Paths, and Quantitative Model Parameters.
"""

from __future__ import annotations

import os
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

# Dates NSE itself confirmed were trading days, by publishing a bhavcopy for
# them. The nightly sync already downloads those files for market caps; this is
# where what it learns gets written down instead of thrown away.
#
# It exists because counting how much of the universe has a price CANNOT tell a
# holiday from a vendor that has not finished publishing. Measured two days
# running on the same two dates:
#
#                        2026-09-16 (traded)   2026-09-14 (holiday)
#   during the sync              20%                   61%
#   a day later                  63%                   86%
#
# A single coverage threshold gets one of them wrong whichever value it takes,
# and on 2026-09-17 it would have taken the holiday and dropped the real
# session. Only the exchange's own record settles it.
REPO_TRADING_DAYS_FILE: Final[str] = os.path.join(REPO_DATA_DIR, "nse_trading_days.json")

# ── Screener.in, kept deliberately apart from Yahoo ──────────────────────────
#
# A SECOND source, never a merged one. The two do not share an adjustment
# basis, and the difference is invisible in the numbers themselves. HEG around
# its 2026-09-07 demerger, same sessions, both sources:
#
#     2026-09-04    screener  266.60    yahoo  728.25
#     2026-09-07    screener  272.20    yahoo  272.20
#
# Screener carries the adjustment back through the history; yfinance does not
# adjust demergers at all. Splice one into the other and a name acquires a
# 2.7x step in the middle of its own price series, silently, on exactly the
# names a corporate-action guard is supposed to protect. So they live in
# separate files and are chosen between, never combined.
#
# The screener frame is CLOSE AND VOLUME ONLY. The API serves Price, DMA50,
# DMA200 and Volume; every OHLC variant 404s. Anything needing a real intraday
# high -- ATR, a true 52-week high -- cannot be computed from this source, and
# the caller has to decide what that means rather than silently getting a
# close-based answer.
SCREENER_PRICES_FILE: Final[str] = os.path.join(DATA_DIR, "screener_prices.parquet")
SCREENER_IDS_FILE: Final[str] = os.path.join(REPO_DATA_DIR, "screener_company_ids.json")

# Daily resolution reaches back about a year and is downsampled to weekly
# beyond it (measured: 248 points at days=365, 522 at days=3650, 1121 at
# days=10000). Requesting more than the daily window therefore BUYS NOTHING
# and costs a bigger response, so the sync asks for the daily window only and
# grows its own history by accumulating each night.
SCREENER_DAYS: Final[int] = 365
# A symbol newly entering the authoritative NSE universe is a data-integrity
# event: acquire its available deep Screener history before allowing it into
# the normal current-universe store. Screener down-samples older observations
# to weekly, so 3650 days is the same deep-history horizon used by the one-time
# bootstrap and does not pretend to create daily observations that do not exist.
SCREENER_DEEP_HISTORY_DAYS: Final[int] = 3650

# One request per symbol per night, with a pause between them. 30 symbols
# measured at 1.74s each including this delay, which puts the full universe at
# roughly 22 minutes -- comfortably inside an overnight window, and gentle
# enough that the site sees less traffic from the whole job than one person
# browsing it.
SCREENER_DELAY_S: Final[float] = 1.2

# Which source the RANKING is computed from. The other is still collected and
# still published; this only decides which one the engine scores.
#
# "screener" is preferred because it finishes a session. Yahoo publishes an
# Indian session over a day and a half and sometimes stalls outright --
# 2026-09-17 reached 378 of 750 symbols and had not moved 44 hours later, while
# screener had all 750 the next morning.
#
# The cost is stated plainly in SCREENER_PRICES_FILE: no intraday high or low.
# The engine already falls back to closes when high_df is absent, so the
# 52-week high becomes a high of CLOSES. That is a different quantity, not a
# worse estimate of the same one -- on the live universe it moves the
# "within 5% of the 52-week high" gate from 22 names to 50.
#
# Falls back to Yahoo on its own if the screener store is missing or does not
# reach far enough back, so a failed collection night degrades instead of
# emptying the screener.
RANKING_PRICE_SOURCE: Final[str] = os.getenv("UMIYA_PRICE_SOURCE", "screener").strip().lower()


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

# Risk-free rate used as the excess-return hurdle in Sharpe and Sortino.
# It was a bare 0.065 inline in the backtester, which meant the number every
# ratio on the Backtest tab is measured against could not be found, changed or
# even seen from anywhere the user looks. Roughly the 10-year GOI yield; it is
# an assumption, so it lives where assumptions live.
RISK_FREE_RATE: Final[float] = 0.065

# Minimum real observations before a "52-week high" may be quoted at all.
# The backtester has always required this (rolling(252, min_periods=126)); the
# screener required nothing, so a stock listed 70 sessions ago got a 52-week
# high drawn from those 70 sessions, scored 0.0% below it, and passed the
# Near-52W-High gate that the backtest would have excluded it from. The gate
# was therefore easier to pass the LESS history a stock had — a bias pointing
# straight at recent listings, which a momentum screen already over-selects.
HIGH_52W_MIN_OBSERVATIONS: Final[int] = 126


# ── Price history windows ────────────────────────────────────────────────────
# The screener pipeline's window. Every calendar-momentum pass walks this frame
# row by row, so its length drives the cold-start cost directly -- measured at
# roughly 20s for 500 sessions x 750 symbols and far more at 2500. Lengthening
# this is a cold-start decision, not just a storage one.
PRICE_HISTORY_PERIOD: Final[str] = "2y"

# The ARCHIVE window. Deliberately much longer than the screener's, and
# deliberately NOT loaded by the app.
#
# Two different jobs want two different things. The screener wants the shortest
# frame that supports its signals, because its cost is per-row at cold start.
# The track record wants depth: it reports from Jan 2026 forever and each month
# needs a 12-month formation window before it, so a 2y archive stops being
# enough somewhere in 2027 -- at which point the monthly freeze fails, prints
# into a log nobody reads, and the record silently stops growing.
#
# So the daily sync fetches this window, publishes it whole for jobs where
# nobody is waiting, and publishes the trailing PRICE_HISTORY_PERIOD of it as
# the app's cold-start snapshot. One download, two files, no change to how fast
# the app starts.
PRICE_ARCHIVE_PERIOD: Final[str] = "10y"

# How far back the nightly sync re-asks for history it already holds.
#
# The incremental price path is append-only: it requests from the last cached
# session FORWARD, so anything the vendor changes behind that point is
# invisible to it forever. Two things routinely change behind it. Yahoo
# backfills a missing Indian close days after the session, and it restates a
# whole split-adjusted series one to four weeks after the corporate action.
#
# Neither is hypothetical here. The published snapshot carries 572 missing
# closes across 337 symbols, clustered on five dates where 11-18% of the
# universe vanished at once -- the signature of a partial fetch frozen in by an
# append-only merge.
#
# 90 days, raised from 45 once the cost was actually measured rather than
# assumed. Widening the window is close to free: the request count does not
# change, and wall time is dominated by per-ticker round trips, not by how many
# sessions each response carries. Timed over 15 tickers, one batched request
# each:
#
#     heal_days=45    34 sessions    503 cells    2.6s
#     heal_days=90    65 sessions    968 cells    0.8s
#
# The 90-day call was the faster of the two -- twice the history for no cost,
# the difference being warm connections rather than anything about the range.
#
# 45 already covered the vendor's 1-4 week backfill latency. 90 covers a late
# restatement, which is the case that actually bit: a split Yahoo restates six
# weeks after the fact falls outside 45 and is then only repaired by the weekly
# FORCE_FULL -- so a failed weekly run used to mean waiting another week.
#
# It is still not a full restatement window. The weekly FORCE_FULL re-reads the
# ENTIRE archive (force_refresh, where heal_days is 0 precisely because
# everything is being re-fetched anyway), and corporate_actions.py neutralises
# a restatement that has not landed yet. This is the daily safety net under
# that, and it runs where nobody is waiting.
PRICE_HEAL_DAYS: Final[int] = 90

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
# The repository whose release carries the published snapshots. This defaults
# to THIS repository, because this repository is the one whose daily sync
# publishes them ($GITHUB_REPOSITORY in the workflow).
#
# It used to default to a different repo of the same owner's. Both happened to
# be in sync, so nothing was visibly wrong -- but the app was reading from a
# repository nothing here publishes to. Rename, archive or delete that one and
# this app would not fail loudly: it would fall back to downloading 750 symbols
# from Yahoo on every cold start, which is the exact fragility the snapshot
# exists to remove, and Yahoo refuses that volume often enough to matter.
#
# PRICE_SNAPSHOT_REPO is the env var to set; UMIYA_REPO is still honoured so an
# existing deployment override keeps working.
PRICE_SNAPSHOT_REPO: Final[str] = (
    os.getenv("PRICE_SNAPSHOT_REPO")
    or os.getenv("UMIYA_REPO")
    or "Pareshking/Paresh"
)
PRICE_SNAPSHOT_ASSET: Final[str] = "prices.parquet"
PRICE_SNAPSHOT_URL: Final[str] = (
    f"https://github.com/{PRICE_SNAPSHOT_REPO}/releases/download/"
    f"{PRICE_SNAPSHOT_TAG}/{PRICE_SNAPSHOT_ASSET}"
)

# The ranking the nightly job computed from the very snapshot above, so a cold
# start can read the answer instead of spending ~30 seconds deriving it while
# somebody watches a spinner. Published alongside the prices, on the same
# rolling tag, and used only when its embedded contract matches exactly --
# see src/loaders/ranking_store.py.
RANKINGS_SNAPSHOT_ASSET: Final[str] = "rankings.parquet"
# Overridable, like PRICE_SNAPSHOT_REPO above, so a fork, a staging deployment
# or an end-to-end test can point this at its own artifact without editing
# source. Unset, it resolves to this repository's rolling release asset.
RANKINGS_SNAPSHOT_URL: Final[str] = os.getenv("UMIYA_RANKINGS_URL") or (
    f"https://github.com/{PRICE_SNAPSHOT_REPO}/releases/download/"
    f"{PRICE_SNAPSHOT_TAG}/{RANKINGS_SNAPSHOT_ASSET}"
)

# The screener store, published by the same release as the price snapshot.
SCREENER_STORE_ASSET: Final[str] = "screener_prices.parquet"
SCREENER_STORE_URL: Final[str] = os.getenv("UMIYA_SCREENER_URL") or (
    f"https://github.com/{PRICE_SNAPSHOT_REPO}/releases/download/"
    f"{PRICE_SNAPSHOT_TAG}/{SCREENER_STORE_ASSET}"
)
